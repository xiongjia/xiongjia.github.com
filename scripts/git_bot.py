"""Local bot: run task scripts in an isolated git worktree and publish as a PR.

Usage (``poe bot`` — the first argument auto-selects the subcommand):

    poe bot "weight 82" "text-moment hello"    # one-step draft PR (--now)
    poe bot "weight 82" --preview                # stop after local preview (port 8123)
    poe bot "weight 82" --auto-merge             # + squash-merge when CI is green
    poe bot --plan morning 81.5                  # plan file with vars (positional / --var)
    poe bot list                                 # list instances
    poe bot submit <name>                        # commit + push + draft PR (after preview)
    poe bot abort <name>                         # discard an instance
    poe bot cleanup [<name>]                     # clean merged instances

Full design: internal/bot-auto-pr-design.md.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# bootstrap repo root so `shared/` is importable regardless of how this runs
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.ci_checks import CHECKS  # noqa: E402
from shared.env import load_env_files  # noqa: E402
from shared.github_api import GitHubAPI, GitHubError  # noqa: E402
from shared.mkdocs_yaml import MkdocsYamlError, load_extra  # noqa: E402

DEFAULT_WORKTREE_BASE = Path.home() / ".cache" / f"{REPO_ROOT.name}-bot" / "worktrees"
MARKER = ".bot-active"
PREVIEW_PORT = 8123
# shown when task specs are passed unquoted (argparse-level and task-level errors)
QUOTE_HINT = (
    "task specs with values/options must be quoted as one arg, "
    'e.g. `poe bot "weight 82 --date 2026-08-05"`'
)


def base_branch() -> str:
    """Bot fork base — read lazily so a BOT_BASE_BRANCH set in .env (loaded in
    main()) is honored (a module-level constant would read the env too early)."""
    return os.environ.get("BOT_BASE_BRANCH", "master")


def run_time_tag() -> str:
    """Bot run timestamp, e.g. ``2026-08-12 10:31`` — appended to the commit
    subject / PR title so every bot entry states action + time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def resolve_date_label(raw: str) -> str:
    """Message label for a task date arg: resolve ``today``/``yesterday``
    aliases to the real date so messages never say ``(today)``."""
    now = datetime.now()
    if raw in ("today", "今天"):
        return now.strftime("%Y-%m-%d")
    if raw == "yesterday":
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return raw


class BotError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------


def git(
    *args: str,
    cwd: Path,
    check: bool = True,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> str:
    """Run git; ``env`` (when given) replaces the inherited environment —
    used to inject auth via GIT_CONFIG_* without putting secrets in argv."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise BotError(f"git {' '.join(args)} timed out after {timeout}s in {cwd}") from exc
    if check and proc.returncode != 0:
        raise BotError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Run a command in cwd, streaming output; raise BotError on failure.

    ``env``, when given, **replaces** the inherited environment (so callers
    can drop leaked variables, e.g. run_ci_gate removing BUCKET_SYNC_*); when
    None the current process env is inherited.
    """
    merged = dict(env) if env is not None else dict(os.environ)
    proc = subprocess.run(cmd, cwd=cwd, env=merged, check=False)
    if proc.returncode != 0:
        raise BotError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def _apply_proxy() -> None:
    """Export BOT_HTTP_PROXY to subprocess env (urllib / uv / mkdocs read these).

    The bot has its own proxy var (GitHub may be unreachable directly, e.g.
    mainland China). When set it **wins over** any shell HTTP(S)_PROXY — the
    bot's network must go through it; when unset, shell values are kept.
    """
    proxy = os.environ.get("BOT_HTTP_PROXY")
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy
        os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")


def _git_proxy_args() -> list[str]:
    """``-c http.proxy=…`` args for git network ops when BOT_HTTP_PROXY is set.

    git does not reliably read HTTPS_PROXY as http.proxy, so network git
    commands (fetch / push / remote delete) pass it explicitly. HTTP/2 is
    forced off as well (``http.version=HTTP/1.1``): git's HTTP/2 over a
    CONNECT proxy frequently dies with "Error in the HTTP2 framing layer"
    (e.g. through the local 127.0.0.1:1095 proxy).
    """
    proxy = os.environ.get("BOT_HTTP_PROXY")
    if not proxy:
        return []  # direct connections keep HTTP/2 (only proxy CONNECT trips it)
    return ["-c", f"http.proxy={proxy}", "-c", "http.version=HTTP/1.1"]


def worktree_base(args) -> Path:
    base = getattr(args, "workdir", None) or os.environ.get("BOT_WORKTREE_DIR")
    return Path(base).expanduser() if base else DEFAULT_WORKTREE_BASE


# -- worktree / env ----------------------------------------------------------


def create_worktree(branch: str, workdir: Path) -> None:
    workdir.parent.mkdir(parents=True, exist_ok=True)
    git(*_git_proxy_args(), "fetch", "origin", cwd=REPO_ROOT)
    git("worktree", "add", "-b", branch, str(workdir), f"origin/{base_branch()}", cwd=REPO_ROOT)


def remove_worktree(workdir: Path) -> None:
    if not workdir.exists():
        return
    for name in (".venv", ".env", ".env.local", "docs/assets/bucket"):
        link = workdir / name
        if link.is_symlink():
            link.unlink()
    # mermaid asset symlinks (git-ignored, downloaded at build time)
    for src in REPO_ROOT.glob("docs/assets/javascripts/mermaid.*"):
        link = workdir / "docs/assets/javascripts" / src.name
        if link.is_symlink():
            link.unlink()
    link = workdir / "docs/.mermaid-version"
    if link.is_symlink():
        link.unlink()
    git("worktree", "remove", "--force", str(workdir), cwd=REPO_ROOT)


def symlink_env(workdir: Path) -> None:
    """Symlink main-repo .venv / .env / .env.local / bucket / mermaid assets
    into the worktree.

    The worktree only checks out tracked files, so without this the bot loses
    the venv, the git-ignored local config (PAT, R2, MKDOCS_BUCKET_*), the
    local bucket image copies (no not_found build warnings) and the
    downloaded mermaid bundle (would re-download ~3.2 MB on every build).
    """
    links = {
        ".venv": True,
        ".env": False,
        ".env.local": False,
        "docs/assets/bucket": True,  # bucket local copies (build/preview)
    }
    for name, is_dir in links.items():
        src = REPO_ROOT / name
        dst = workdir / name
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst, target_is_directory=is_dir)
    _symlink_mermaid(workdir)


def _symlink_mermaid(workdir: Path) -> None:
    """Reuse the main repo's downloaded mermaid assets (git-ignored,
    downloaded by plugins/mermaid_assets.py at build time) so the worktree
    build doesn't re-download the bundle every run."""
    for src in REPO_ROOT.glob("docs/assets/javascripts/mermaid.*"):
        dst = workdir / src.relative_to(REPO_ROOT)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst)
    src = REPO_ROOT / "docs/.mermaid-version"
    if src.exists():
        dst = workdir / "docs/.mermaid-version"
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst)


def git_identity() -> tuple[str, str]:
    name = os.environ.get("BOT_GIT_NAME") or git("config", "user.name", cwd=REPO_ROOT, check=False)
    email = os.environ.get("BOT_GIT_EMAIL") or git(
        "config", "user.email", cwd=REPO_ROOT, check=False
    )
    return name, email


def commit_workdir(workdir: Path, message: str, body: list[str]) -> None:
    name, email = git_identity()
    args = ["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message]
    for line in body:
        args += ["-m", line]
    # Stage the task output, then unstage worktree-only artifacts (symlinks /
    # marker). `git add -A` alone can't use :(exclude) pathspecs here — when
    # the checked-out .gitignore already ignores them (post-merge master) the
    # exclude pathspec collides with the ignore rule and git aborts; when it
    # doesn't (older master) the symlinks would be staged. `git add -A` +
    # `git reset -- <paths>` is a no-op on unstaged/ignored paths, so it works
    # for both.
    git("add", "-A", cwd=workdir)
    git(
        "reset",
        "--",
        ".bot-active",
        ".venv",
        ".env",
        ".env.local",
        "docs/assets/bucket",
        cwd=workdir,
        check=False,
    )
    proc = subprocess.run(["git", *args], cwd=workdir, capture_output=True, text=True, check=False)
    if proc.returncode != 0 and "nothing to commit" not in proc.stdout + proc.stderr:
        raise BotError(
            f"git commit failed in {workdir}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    # "nothing to commit" is fine — a previous submit already committed (e.g.
    # the branch was pushed but PR creation failed and we're retrying).


def _git_auth_env() -> dict[str, str]:
    """Environment injecting the bot PAT as ``http.extraheader`` via
    GIT_CONFIG_* (git ≥2.31) — keeps the token out of argv (ps-visible)."""
    basic = _basic_auth()
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraheader"
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {basic}"
    return env


_PUSH_RETRIABLE = (
    "remote end closed",
    "http2 framing",
    "timed out",
    "connection",
    "could not read from remote",
)


def push_branch(workdir: Path, branch: str) -> None:
    """Push with retries on transient connection failures.

    Pushing through an HTTP proxy sometimes drops the connection after the
    server already accepted the ref ("Remote end closed connection without
    response") — the ref lands but git reports failure. Retry a few times
    before giving up; auth/config errors are not retried.
    """
    args = _git_proxy_args()
    last: BotError | None = None
    for attempt in range(3):
        try:
            git(*args, "push", "-u", "origin", branch, cwd=workdir, env=_git_auth_env())
            return
        except BotError as exc:
            last = exc
            if not any(s in str(exc).lower() for s in _PUSH_RETRIABLE):
                raise
            print(
                f"⚠ push failed ({attempt + 1}/3): {exc} — retrying…",
                file=sys.stderr,
            )
            time.sleep(3 * (attempt + 1))
    raise last


def delete_remote_branch(branch: str) -> None:
    _bot_branch_guard(branch)
    args = _git_proxy_args()
    git(*args, "push", "origin", "--delete", branch, cwd=REPO_ROOT, env=_git_auth_env())


def _basic_auth() -> str:
    token = os.environ.get("BOT_GH_TOKEN")
    if not token:
        raise BotError(
            "BOT_GH_TOKEN missing — see internal/bot-auto-pr-design.md → "
            "Credential Strategy (create a PAT and put it in .env)"
        )
    return base64.b64encode(f"x-access-token:{token}".encode()).decode()


# -- instance marker ---------------------------------------------------------


def write_marker(
    workdir: Path, branch: str, state: str, tasks: list[tuple[str, list[str]]]
) -> None:
    tasks_json = json.dumps([[name, targs] for name, targs in tasks], ensure_ascii=False)
    (workdir / MARKER).write_text(
        "pid={pid}\nbranch={branch}\nstarted={started}\nstate={state}\ntasks={tasks}\n".format(
            pid=os.getpid(),
            branch=branch,
            started=datetime.now().isoformat(timespec="seconds"),
            state=state,
            tasks=tasks_json,
        ),
        encoding="utf-8",
    )


def read_marker(workdir: Path) -> dict[str, str] | None:
    f = workdir / MARKER
    if not f.is_file():
        return None
    data: dict[str, str] = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            data[key] = value
    return data


def marker_state(workdir: Path) -> tuple[str | None, bool]:
    """Return ``(state, active)`` — active means the recorded pid is alive."""
    marker = read_marker(workdir)
    if not marker:
        return None, False
    pid = int(marker.get("pid", "0"))
    alive = False
    if pid > 0:
        try:
            os.kill(pid, 0)
            alive = True
        except (ProcessLookupError, PermissionError):
            alive = False
    return marker.get("state"), alive


def rebuild_tasks_run(marker: dict) -> list[tuple[str, dict]]:
    specs = json.loads(marker.get("tasks", "[]"))
    return [(name, _plan_task(name, targs)) for name, targs in specs]


def find_workdir(base: Path, name: str) -> Path | None:
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            marker = read_marker(child)
            if marker and marker.get("branch") == name:
                return child
            if child.name == name:
                return child
    for branch, path in _worktree_entries():
        if branch == name:
            return Path(path)
    return None


def _worktree_entries() -> list[tuple[str, str]]:
    """[(branch, path)] from `git worktree list --porcelain` (bot branches only)."""
    out = git("worktree", "list", "--porcelain", cwd=REPO_ROOT, check=False)
    entries: list[tuple[str, str]] = []
    path, branch = "", ""
    for line in out.splitlines():
        if line.startswith("worktree "):
            if branch.startswith("bot/") and path:
                entries.append((branch, path))
            path, branch = line[len("worktree ") :], ""
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/") :]
    if branch.startswith("bot/") and path:
        entries.append((branch, path))
    return entries


def _branch_merged(branch: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, f"origin/{base_branch()}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return proc.returncode == 0


def _bot_branch_guard(branch: str) -> None:
    """Refuse to delete/remove anything that isn't a bot branch (``bot/...``).

    Deleting is destructive — never trust a caller-provided name blindly (a
    tampered marker, a typo'd arg, a future code path).
    """
    if not branch.startswith("bot/"):
        raise BotError(f"refusing to touch non-bot branch {branch!r}")


def _teardown_local(branch: str, workdir: Path) -> None:
    """Remove the worktree then the local bot branch.

    Order matters: git refuses to delete a branch that a worktree is still
    checked out on ("cannot delete branch used by worktree").
    """
    remove_worktree(workdir)
    if branch:
        _bot_branch_guard(branch)
        git("branch", "-D", branch, cwd=REPO_ROOT, check=False)


def _delete_local(branch: str, workdir: Path) -> None:
    _teardown_local(branch, workdir)


def _delete_remote(branch: str) -> None:
    try:
        delete_remote_branch(branch)
    except BotError:
        pass  # never pushed / already deleted


# ---------------------------------------------------------------------------
# task registry
# ---------------------------------------------------------------------------


def task_weight(ctx, args: list[str]) -> dict:
    if not args:
        raise BotError('weight task needs a value, e.g. "weight 82"')
    weight = args[0]
    if len(args) > 2 and args[1] == "--date":
        date = args[2]
    else:
        date = args[1] if len(args) > 1 else "today"
    return {
        "cmd": ["uv", "run", "python", "scripts/update_weight.py", *args],
        "commit": f"[bot] feat(weight): record {weight} kg",
        "body": f"- weight {weight} kg ({resolve_date_label(date)})",
    }


class TemplateTask:
    """Config-driven task from ``extra.bot.tasks`` in mkdocs.yml.

    ``cmd`` / ``commit`` / ``body`` are format strings with ``{arg}``
    placeholders named in ``args``; extra CLI args are appended to ``cmd``
    (pass-through, e.g. ``--draft``). Missing args raise a clear error.

    A trailing ``name...`` in ``args`` marks a rest consumer: remaining
    non-flag tokens are joined into it (free text with spaces), while
    ``-`` tokens stay extra CLI args (pass flag values as one token, e.g.
    ``--time=9am``).
    """

    def __init__(self, spec: dict):
        self.args = list(spec.get("args", []))
        self.cmd = list(spec["cmd"])
        self.commit = spec.get("commit", "")
        self.body = spec.get("body", "")

    def plan(self, args: list[str]) -> dict:
        rest_name = None
        declared = self.args
        if declared and declared[-1].endswith("..."):
            rest_name = declared[-1][:-3]
            declared = declared[:-1]
        if len(args) < len(declared):
            raise BotError(
                f"task needs {len(declared)} arg(s): {', '.join(declared)} — got {args!r}"
            )
        values = {name: args[i] for i, name in enumerate(declared)}
        extra = list(args[len(declared) :])
        if rest_name:
            text, flags = [], []
            for tok in extra:
                (flags if tok.startswith("-") else text).append(tok)
            if not text:
                raise BotError(f"task needs {rest_name} content — got {args!r}")
            values[rest_name] = " ".join(text)
            extra = flags
        cmd = [part.format(**values) for part in self.cmd] + extra
        return {
            "cmd": cmd,
            "commit": self.commit.format(**values),
            "body": self.body.format(**values) if self.body else "",
        }


def load_task_config() -> dict:
    """Read ``extra.bot.tasks`` from mkdocs.yml (empty dict when absent).

    mkdocs.yml contains ``!ENV`` tags, so a plain ``yaml.safe_load`` would
    fail; shared.mkdocs_yaml resolves them (bot task config never uses them).
    A broken mkdocs.yml fails fast — the bot must not run without its task
    registry.
    """
    try:
        return load_extra("bot", label="bot", strict=True).get("tasks", {}) or {}
    except MkdocsYamlError as exc:
        raise BotError(str(exc)) from exc


def _plan_task(name: str, args: list[str]) -> dict:
    """Plan a task (builtin function or config TemplateTask) → runnable info."""
    task = TASKS[name]
    if isinstance(task, TemplateTask):
        return task.plan(args)
    return task(None, args)


def task_health_summary(ctx, args: list[str]) -> dict:
    return {
        "cmd": ["uv", "run", "python", "scripts/update_health_summary.py", *args],
        "commit": "[bot] docs(health): refresh summary",
        "body": "- health summary refreshed",
    }


def task_sync_running(ctx, args: list[str]) -> dict:
    return {
        "cmd": ["uv", "run", "python", "scripts/sync_running.py", *args],
        "commit": "[bot] docs(health): sync running data",
        "body": "- running data synced",
    }


_ENU_OPT_ARGS = {"--date", "--dir"}


def task_enu(ctx, args: list[str]) -> dict:
    """enu content is free text (may contain spaces) — the remaining tokens
    are joined into one content; --date/--dir take a value and stay options."""
    if not args:
        raise BotError('enu task needs a scrap, e.g. "enu cumbersome"')
    opts: list[str] = []
    text: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in _ENU_OPT_ARGS and i + 1 < len(args):
            opts += [args[i], args[i + 1]]
            i += 2
        elif args[i].startswith("--"):
            opts.append(args[i])
            i += 1
        else:
            text.append(args[i])
            i += 1
    content = " ".join(text)
    if not content:
        raise BotError('enu task needs a scrap, e.g. "enu cumbersome"')
    return {
        "cmd": ["uv", "run", "python", "scripts/enu.py", "add", content, *opts],
        "commit": "[bot] feat(enu): add scrap",  # content stays in the body / PR desc
        "body": f"- scrap: {content}",
    }


TASKS: dict[str, object] = {
    "weight": task_weight,
    "health-summary": task_health_summary,
    "sync-running": task_sync_running,
    "enu": task_enu,
}
for _name, _spec in load_task_config().items():
    TASKS[_name] = TemplateTask(_spec)


def parse_task_specs(specs: list[str]) -> list[tuple[str, list[str]]]:
    """['weight 82', 'text-moment x'] → [('weight', ['82']), ('text-moment', ['x'])].

    Also splits the '+' shorthand inside one spec: 'weight 82 + text-moment x'.
    """
    parsed: list[tuple[str, list[str]]] = []
    for spec in specs:
        for part in re.split(r"\s+\+\s+", spec):
            tokens = part.split()
            if not tokens:
                continue
            name, rest = tokens[0], tokens[1:]
            if name not in TASKS:
                hint = ""
                if name.startswith("-") or (rest and rest[0].startswith("-")):
                    hint = f" — {QUOTE_HINT}"
                elif re.match(r"^[-\d.]+$", name):
                    hint = (
                        " — a bare value outside its task? quote the whole spec, "
                        'e.g. `poe bot "weight 82"`'
                    )
                raise BotError(
                    f"unknown task {name!r}; available: {', '.join(sorted(TASKS))}{hint}"
                )
            parsed.append((name, rest))
    return parsed


def aggregate_commit(
    tasks_run: list[tuple[str, dict]], now_tag: str | None = None
) -> tuple[str, list[str]]:
    """Merged subject + per-task body lines from executed task infos.

    Subject = action summary + run time, e.g.
    ``[bot] feat(weight): record 82 kg + feat(enu): add scrap (2026-08-12 10:31)``;
    free-text task content (scrap/moment text) never goes in the title — it
    lives in the body / PR description. Short structured values (e.g. the
    weight figure) may stay.
    """
    if not tasks_run:
        raise BotError("no tasks ran")
    now_tag = now_tag or run_time_tag()
    subject = tasks_run[0][1]["commit"]
    extras = [info["commit"] for _, info in tasks_run[1:]]
    if extras:
        short = [re.sub(r"^\[bot\] ", "", msg) for msg in extras]
        subject += " + " + " + ".join(short)
    body = [info["body"] for _, info in tasks_run]
    return f"{subject} ({now_tag})", body


PR_DESC_LIMIT = 100


def build_pr_body(lines: list[str], limit: int = PR_DESC_LIMIT, now_tag: str | None = None) -> str:
    """PR description = task detail lines + run time + generator trailer,
    hard-capped at ``limit`` chars. Long detail lines are truncated (with …)
    first; the run-time line and ``Generated by poe bot.`` trailer always stay.
    """
    trailer = f"\n- {now_tag or run_time_tag()}\n\nGenerated by `poe bot`."
    limit = max(limit, len(trailer))  # never below the trailer itself
    budget = limit - len(trailer)
    out: list[str] = []
    for line in lines:
        room = budget - sum(len(ln) + 1 for ln in out)
        if room < 4:  # too small to be meaningful — drop the rest (room only shrinks)
            break
        out.append(line if len(line) <= room else line[: room - 1] + "…")
    return "\n".join(out) + trailer


# ---------------------------------------------------------------------------
# phases
# ---------------------------------------------------------------------------


def _env_true(key: str) -> bool:
    """Parse an env flag: true/1/yes (same convention as MKDOCS_* flags)."""
    return os.environ.get(key, "").strip().lower() in ("true", "1", "yes")


def run_ci_gate(workdir: Path) -> None:
    print("🔍 local CI gate (fmt → check-fmt → lint → test → build)…")
    for cmd in CHECKS:
        env = None
        if cmd[-1] == "test":
            # pytest may run inside a worktree checked out from master: if the
            # .env loaded by the bot carries BUCKET_SYNC_* overrides, the
            # rclone tests (which assert default values) would fail — drop
            # them, matching the CI environment (no .env). The repo tests
            # also self-isolate once merged to master.
            env = {k: v for k, v in os.environ.items() if not k.startswith("BUCKET_SYNC_")}
            # Local escape hatch while master's tests are not yet
            # self-isolating: BOT_SKIP_TESTS=true skips the unittest step
            # (default off — CI still runs them).
            if _env_true("BOT_SKIP_TESTS"):
                print("⏭  skipping python unittest (BOT_SKIP_TESTS=true)")
                continue
        run(cmd, cwd=workdir, env=env)


def free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise BotError(f"no free port near {start}")


def preview_server(workdir: Path) -> None:
    port = free_port(PREVIEW_PORT)
    print(f"▶ Preview: http://127.0.0.1:{port}  (Ctrl-C to stop)")
    run(["uv", "run", "mkdocs", "serve", "-a", f"127.0.0.1:{port}"], cwd=workdir)


def do_submit(
    workdir: Path,
    branch: str,
    tasks_run: list[tuple[str, dict]],
    wait_ci: bool,
    auto_merge: bool,
    handoff: bool = False,
) -> None:
    now_tag = run_time_tag()  # one run time shared by commit title + PR desc
    subject, body = aggregate_commit(tasks_run, now_tag=now_tag)
    commit_workdir(workdir, subject, body)
    print("🚀 pushing…")
    push_branch(workdir, branch)

    api = GitHubAPI()
    pr_body = build_pr_body(body, now_tag=now_tag)
    number, url = api.create_pr(
        head=branch, base=base_branch(), title=subject, body=pr_body, draft=True
    )
    print(f"📦 Draft PR #{number}: {url}")

    if wait_ci or auto_merge:
        sha = git("rev-parse", "HEAD", cwd=workdir)
        print("⏳ waiting for CI checks…")
        ok, summary = api.wait_checks(sha)
        print("\n".join(f"   {line}" for line in summary))
        if not ok:
            raise BotError(f"CI checks failed for {branch} — review PR #{number} manually")
        if auto_merge:
            api.mark_ready(number)
            api.merge(number, method="squash")
            print(f"✅ merged PR #{number}")
    remove_worktree(workdir)
    git("branch", "-D", branch, cwd=REPO_ROOT, check=False)
    if wait_ci or auto_merge:
        print(f"🧹 worktree removed ({branch})")
    else:
        mode = "handoff" if handoff else "default"
        print(
            f"✅ PR #{number} {mode} — worktree cleaned, draft PR awaits the dev (no wait/merge)."
        )


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def cmd_run(args) -> None:
    specs = list(args.tasks)
    if args.plan:
        specs = plan_specs(args)
    tasks = parse_task_specs(specs)
    if not tasks:
        raise BotError('no tasks given — e.g. `poe bot "weight 82"`')

    branch = branch_for([name for name, _ in tasks])
    base = worktree_base(args)
    workdir = base / branch.rsplit("/", 1)[-1]

    create_worktree(branch, workdir)
    symlink_env(workdir)
    if args.resync:
        run(["uv", "sync"], cwd=workdir)
    write_marker(workdir, branch, "running", tasks)
    print(f"🌿 branch {branch}\n📁 worktree {workdir}")

    tasks_run: list[tuple[str, dict]] = []
    try:
        for name, targs in tasks:
            info = _plan_task(name, targs)
            print(f"▶ {name} {' '.join(targs)}")
            run(info["cmd"], cwd=workdir)
            tasks_run.append((name, info))

        run_ci_gate(workdir)

        if args.preview:
            write_marker(workdir, branch, "ready", tasks)
            preview_server(workdir)
            print("\n⏸ preview done — worktree kept. Next:")
            print(f"   poe bot submit {branch}   (commit + push + draft PR)")
            print(f"   poe bot abort {branch}    (discard)")
            return

        write_marker(workdir, branch, "submitting", tasks)
        do_submit(workdir, branch, tasks_run, args.wait_ci, args.auto_merge, args.handoff)
    except Exception as exc:
        write_marker(workdir, branch, "stale", tasks)
        print(f"❌ {exc}", file=sys.stderr)
        print(f"   worktree kept at {workdir} (state stale).")
        print(f"   → poe bot list | poe bot abort {branch} | poe bot cleanup {branch}")
        sys.exit(1)


def _plan_skip_empty(name: str, targs: list[str]) -> bool:
    """Plan empty-arg skip: a template task that requires args but got none
    after rendering (e.g. "text-moment {note}" with an empty note) is
    skipped. Builtins are left to the executor (they raise a clear error if
    an arg is missing) — no per-builtin list to keep in sync."""
    task = TASKS.get(name)
    return not targs and isinstance(task, TemplateTask) and bool(task.args)


def plan_specs(args) -> list[str]:
    path = REPO_ROOT / ".bot" / "plans" / f"{args.plan}.yml"
    if not path.is_file():
        raise BotError(f"plan not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    vars_def = data.get("vars") or {}
    var_names = list(vars_def)

    values: dict[str, str] = {}
    for name, val in zip(var_names, args.tasks):  # positional args in vars order
        values[name] = val
    for kv in args.var:
        key, _, val = kv.partition("=")
        values[key] = val
    for name, spec in vars_def.items():
        if name not in values and isinstance(spec, dict) and "default" in spec:
            values[name] = str(spec["default"])

    missing = [
        name
        for name, spec in vars_def.items()
        if name not in values and isinstance(spec, dict) and spec.get("required")
    ]
    if missing:
        usage = "\n".join(f"  {name}: {vars_def[name].get('desc', '')}" for name in missing)
        raise BotError(
            f"missing required vars: {', '.join(missing)}\n"
            f"usage: poe bot --plan {args.plan} <vals in order> or --var key=value\n{usage}"
        )

    specs: list[str] = []
    for tpl in data.get("tasks", []):
        try:
            rendered = tpl.format(**values)
        except KeyError as exc:
            raise BotError(f"plan task {tpl!r}: unknown var {exc}") from exc
        if not rendered.strip():
            continue
        parsed = parse_task_specs([rendered])
        name, targs = parsed[0]
        if len(parsed) == 1 and _plan_skip_empty(name, targs):
            # rendered with an empty arg (e.g. "text-moment {note}" with empty
            # note) — skip the task entirely
            continue
        specs.append(rendered)

    if args.auto_merge is None:
        args.auto_merge = bool(data.get("auto_merge"))  # plan default; CLI flag wins
    return specs


def cmd_list(args) -> None:
    base = worktree_base(args)
    lines: list[tuple[str, str, str]] = []
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            marker = read_marker(child)
            if not marker:
                continue
            branch = marker.get("branch", "")
            state, active = marker_state(child)
            merged = _branch_merged(branch) if branch else False
            lines.append((branch, str(child), _state_label(state, active, merged)))
    seen_paths = {path for _, path, _ in lines}
    for branch, path in _worktree_entries():
        if path not in seen_paths:
            merged = _branch_merged(branch)
            lines.append((branch, path, "merged" if merged else "active/unknown"))

    if not lines:
        print("(no bot instances)")
        return
    print(f"{'BOT NAME':<44} {'STATE':<12} WORKTREE")
    for name, path, state in sorted(lines):
        print(f"{name:<44} {state:<12} {path}")


def _state_label(state: str | None, active: bool, merged: bool) -> str:
    if active:
        return "active"
    if merged:
        return "merged"
    return state or "stale"


def cmd_submit(args) -> None:
    base = worktree_base(args)
    workdir = find_workdir(base, args.name)
    if not workdir:
        raise BotError(f"no bot instance named {args.name!r} — see `poe bot list`")
    marker = read_marker(workdir) or {}
    branch = marker.get("branch") or args.name
    state, active = marker_state(workdir)
    if active and not args.force:
        raise BotError(f"{branch} is still running — wait for it or use --force")
    if state == "running":
        raise BotError(f"{branch} is mid-run (state=running) — use `bot abort` first")

    try:
        tasks_run = rebuild_tasks_run(marker)
        run_ci_gate(workdir)  # re-check after any manual tweaks
        do_submit(workdir, branch, tasks_run, args.wait_ci, args.auto_merge, args.handoff)
    except Exception as exc:
        # preserve the original task list in the stale marker
        write_marker(workdir, branch, "stale", json.loads(marker.get("tasks", "[]")))
        print(f"❌ {exc}", file=sys.stderr)
        print(f"   worktree kept at {workdir} (state stale).")
        print(f"   → fix the cause, then: poe bot submit {branch} (retry)")
        print(f"   → or give up: poe bot abort {branch}")
        sys.exit(1)


def cmd_abort(args) -> None:
    base = worktree_base(args)
    workdir = find_workdir(base, args.name)
    branch = args.name
    if workdir:
        marker = read_marker(workdir) or {}
        branch = marker.get("branch") or args.name
        state, active = marker_state(workdir)
        if active and not args.force:
            raise BotError(
                f"{branch} is still running (pid {marker.get('pid')}) — use --force to abort"
            )

    try:
        api = GitHubAPI()
        pr = api.find_pr_by_head(branch)
        if pr and pr["state"] != "closed":
            api.close_pr(pr["number"])
            print(f"🔒 closed PR #{pr['number']}")
    except GitHubError as exc:
        print(f"⚠  could not reach GitHub ({exc}) — continuing locally", file=sys.stderr)

    _delete_remote(branch)
    if workdir:
        _delete_local(branch, workdir)
    else:
        # worktree already gone (e.g. PR cleanup after a successful submit) —
        # still drop the local branch if it lingers. Guard the name: without
        # a marker we only accept a full bot branch name (a bare dir slug
        # would be pushed as a branch and fail remotely).
        if not branch.startswith("bot/"):
            raise BotError(
                f"{branch!r} is not a bot branch — use the full name from `poe bot list`"
            )
        _bot_branch_guard(branch)
        git("branch", "-D", branch, cwd=REPO_ROOT, check=False)
    print(f"🗑  aborted {branch}")


def cmd_cleanup(args) -> None:
    base = worktree_base(args)
    found = False
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            marker = read_marker(child)
            branch = (marker or {}).get("branch") or child.name
            if not branch.startswith("bot/"):
                continue
            if args.name and branch != args.name and child.name != args.name:
                continue
            found = True
            state, active = marker_state(child)
            if active:
                print(f"⏭  skip active: {branch} (pid alive)")
                continue
            if state == "ready":
                print(f"⏭  skip ready (uncommitted): {branch} — use `bot abort` or --force")
                continue
            merged = _branch_merged(branch)
            if not merged and not args.force:
                print(f"⏭  skip unmerged: {branch} — use `bot abort` or --force")
                continue
            print(f"🗑  {branch} ({child})")
            if merged:
                _delete_remote(branch)
            _delete_local(branch, child)
    if not found:
        print("(no bot worktrees under the workdir base)")
    git("worktree", "prune", cwd=REPO_ROOT)


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------


def branch_for(tasks: list[str], now: datetime | None = None) -> str:
    now = now or datetime.now()
    slug = "+".join(tasks)
    return f"bot/{slug}/{now:%Y%m%d-%H%M%S}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bot",
        description="Local bot: run tasks in an isolated worktree, publish as a PR.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run tasks and publish (default)")
    p_run.add_argument("tasks", nargs="*", help='task specs, e.g. "weight 82" "text-moment x"')
    p_run.add_argument("--plan", metavar="NAME", help="run .bot/plans/<NAME>.yml")
    p_run.add_argument("--var", action="append", default=[], metavar="KEY=VALUE")
    p_run.add_argument("--workdir", help="worktree base dir (default: ~/.cache/.../worktrees)")
    p_run.add_argument("--preview", action="store_true", help="stop after local preview")
    p_run.add_argument("--wait-ci", action="store_true", help="wait for remote CI checks")
    p_run.add_argument(
        "--auto-merge", action="store_true", default=None, help="merge when CI is green"
    )
    p_run.add_argument(
        "--handoff",
        action="store_true",
        help="stop after the draft PR — clean up the local worktree, dev handles the PR "
        "(default; ignored when --wait-ci/--auto-merge is given)",
    )
    p_run.add_argument("--resync", action="store_true", help="force uv sync instead of symlink")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="list bot instances")
    p_list.add_argument("--workdir")
    p_list.set_defaults(func=cmd_list)

    p_submit = sub.add_parser("submit", help="submit a ready instance")
    p_submit.add_argument("name", help="bot name (branch), from `poe bot list`")
    p_submit.add_argument("--workdir")
    p_submit.add_argument("--wait-ci", action="store_true")
    p_submit.add_argument("--auto-merge", action="store_true", default=None)
    p_submit.add_argument(
        "--handoff",
        action="store_true",
        help="stop after draft PR, clean up locally (default; ignored with --wait-ci/--auto-merge)",
    )
    p_submit.add_argument("--force", action="store_true")
    p_submit.set_defaults(func=cmd_submit)

    p_abort = sub.add_parser("abort", help="discard an instance")
    p_abort.add_argument("name", help="bot name (branch)")
    p_abort.add_argument("--workdir")
    p_abort.add_argument("--force", action="store_true")
    p_abort.set_defaults(func=cmd_abort)

    p_cleanup = sub.add_parser("cleanup", help="clean merged instances")
    p_cleanup.add_argument("name", nargs="?", help="optional: only this bot")
    p_cleanup.add_argument("--workdir")
    p_cleanup.add_argument("--force", action="store_true")
    p_cleanup.set_defaults(func=cmd_cleanup)

    return parser


def main() -> int:
    load_env_files()
    _apply_proxy()
    argv = sys.argv[1:]
    # implicit `run`: bare task specs (no known subcommand) default to run
    if argv and argv[0] not in ("run", "list", "submit", "abort", "cleanup"):
        argv = ["run", *argv]
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
        ns.func(ns)
    except BotError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n(interrupted)")
        return 130
    except SystemExit as exc:  # argparse rejects unknown options before task parsing
        code = exc.code if isinstance(exc.code, int) else 1
        if code:
            print(f"💡 {QUOTE_HINT}", file=sys.stderr)
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
