# Bot Auto PR — Design Document

> Local bot automation: turn existing task scripts (e.g. `uv run poe update-weight 82`) into a full publish pipeline — branch → edit → format →
> local CI checks → commit → push → draft PR → wait CI → auto-merge. All work
> happens in an isolated `git worktree`; the developer's working copy is never
> touched.
>
> Requirements & iteration history: git-ignored `internal/local-draft.md`
> (this is the consolidated design).

## Goals

1. One command completes a full data-update publish cycle:
   `poe bot weight 82` → opens a PR, auto-merges when CI is green.
1. Zero impact on the current working copy (`git worktree` isolation).
1. Auto-format changed md/py, then run the full local CI-equivalent checks
   (fmt → fmt-check → lint → test → build) before push.
1. Optional preview on a dedicated port (8123, not the dev server's 8000).
1. Composable: multiple tasks in one branch/PR
   (e.g. `weight 82` + `text-moment "..."`).
1. Branch names encode bot + timestamp + task; commit messages are clear,
   task-related, and carry a `[bot]` prefix.
1. No repeated `uv sync` — reuse the main repo `.venv` and `.env` (time/disk).
1. Full lifecycle: `list` / `submit` / `abort` / `cleanup`, safe under
   concurrent bot instances.

## Core Flow

### Submission modes (one flag decides)

| Mode              | Command                          | Behavior                                                                                                   |
| ----------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| default (`--now`) | `poe bot weight 82`              | One step: task → format → CI checks → commit → push → **draft PR**                                         |
| handoff           | `poe bot weight 82 --handoff`    | Same as default, explicit: draft PR → **clean up the local worktree** → dev handles the PR (no wait/merge) |
| preview           | `poe bot weight 82 --preview`    | Stop after local preview (state `ready`); then `submit` / `abort` / edit worktree & `submit`               |
| auto-merge        | `poe bot weight 82 --auto-merge` | One step + merge: draft PR → CI green → ready → auto squash-merge                                          |

Safety net for every mode: a **draft PR** is opened first (not merged = not
published), and `poe bot abort <name>` can discard it at any point with zero
remote trace.

### Phase A — prepare (only mutates the isolated worktree)

```
1. Parse task args → branch name: bot/weight/20260811-2130
2. git worktree add -b <branch> <workdir> origin/master   # fork from current master
                                                          # (base: BOT_BASE_BRANCH, default master)
3. Symlink .venv / .env / .env.local from the main repo (reuse environment)
4. Run the task script inside workdir (cwd=workdir, e.g. update_weight.py)
5. [--preview] mkdocs serve -a 127.0.0.1:8123  (Ctrl-C ends; worktree kept)
6. Auto-format + CI-equivalent checks (abort on any failure):
   poe fmt → poe check-fmt → poe lint-py → poe test → mkdocs build
→ instance state ready; print worktree path + change summary + next steps
  (poe bot submit <name> / poe bot abort <name>)
(default / --now: after 4→6 continue straight into Phase B)
```

### Phase B — submit (after developer confirmation)

```
7. git add -A + commit (message from task template, [bot] prefix)
8. git push -u origin <branch>   (bot PAT auth via http.extraheader)
9. Create draft PR (title/body from task template) — cloud-level second gate
10. [--wait-ci] poll check-runs → all green → mark ready / auto-merge
11. Tear down: git worktree remove + prune
```

### Abandon

```
poe bot abort <name>
- not pushed: remove worktree + local branch (zero remote trace)
- pushed / draft PR open: close PR (no merge) + delete remote branch
  + remove worktree + local branch
```

## Credential Strategy

`gh` is bound to a work account — it is **not used**. GitHub interaction goes
through a small **Python API client** (curl-like, reusable), and the token
lives in the git-ignored `.env`.

### Token setup (one-time)

1. Create a fine-grained PAT at https://github.com/settings/tokens
   (repository `xiongjia.github.com`):
   - `Contents: Read and write` (branch / push)
   - `Pull requests: Read and write` (open PR / merge / auto-merge)
   - `Actions: Read` (check-runs)
   - Or classic PAT with `repo` (or `public_repo` if the repo is public —
     least privilege). `workflow` scope is **not** needed (bot tasks never
     touch `.github/workflows/`); add it only if a future task would.
1. Write it to `.env` (git-ignored; loaded automatically by
   `shared/env.py`; precedence shell > `.env.local` > `.env`):
   ```bash
   cp .env.example .env
   printf '\n# --- Local bot ---\nBOT_GH_TOKEN=ghp_xxxxxxxxxxxxxxxx\n' >> .env
   ```
1. Verify:
   ```bash
   uv run python -c "from shared.env import load_env_files; import os; load_env_files(); print('ok' if os.environ.get('BOT_GH_TOKEN') else 'MISSING')"
   ```

### Python API client (`shared/github_api.py`)

- Standard-library `urllib.request`, **zero new dependencies**; a class in
  `shared/` (plugins & scripts layer) so later needs (bot status page,
  auto-closing stale PRs, stats) can import it directly.
- Core methods (core-flow steps 9/10):
  - `create_pr(head, base, title, body, draft=True)` → PR number + URL
  - `wait_checks(sha, timeout)` → poll `commits/{sha}/check-runs`,
    returns all-green / failed / timeout
  - `mark_ready(pr)` / `merge(pr, method="squash")`
  - `list_bot_prs()` (cleanup)
- Auth: `load_env_files()` at init, reads `BOT_GH_TOKEN`; missing → print the
  Token setup guide above and exit. Every request sends
  `Authorization: Bearer <token>` + `Accept: application/vnd.github+json`.
- Errors: non-2xx → parse the error body `message`, print it, raise — so the
  bot can surface it in the PR body / to the user.

### push stays `git` (subprocess wrapper)

```python
basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
subprocess.run(
    ["git", "-c", f"http.extraheader=AUTHORIZATION: basic {basic}", "push", "-u", "origin", branch],
    cwd=workdir,
    check=True,
)
```

- Token never enters the URL or `git remote -v`; the preemptive auth header
  avoids a 401 that would fall back to the credential helper (which may hold
  work-account credentials).

### Proxy (bot-specific)

GitHub may be unreachable directly (e.g. mainland China), so the bot has its
own proxy variable — the developer's other tools keep their own settings.

- `BOT_HTTP_PROXY` in `.env` (same mechanism as `RCLONE_HTTP_PROXY`).
- Applied in three places:
  1. **GitHub API client** — `ProxyHandler` on the urllib opener (only when
     the var is set).
  1. **git network ops** (fetch / push / remote delete) — passed explicitly
     as `-c http.proxy=…` (git does not reliably read `HTTPS_PROXY`), with
     HTTP/2 forced off (`-c http.version=HTTP/1.1`) — git's HTTP/2 over a
     CONNECT proxy frequently fails with “Error in the HTTP2 framing layer”.
  1. **Subprocess env** — exported as `HTTP_PROXY` / `HTTPS_PROXY`
     (`NO_PROXY=127.0.0.1,localhost`) so `uv` / `mkdocs` (mermaid download)
     inherit it.
- `NO_PROXY` keeps localhost out of the proxy (preview server, git local ops).

## Design Decisions

### 1. Working copy isolation → `git worktree`; user-specified path

- Bot branches always **fork from the current master** (origin/master,
  fetched fresh) — the base branch defaults to `master` and is configurable
  via `BOT_BASE_BRANCH` in `.env` (e.g. `BOT_BASE_BRANCH=dev`). The fork
  point is independent of the main repo's checked-out branch.

- Worktrees share `.git` objects with the main repo (cheap to create, little
  disk). The bot only ever `add/commit/push` inside the workdir.

- Worktree path is developer-configurable (highest first):

  1. CLI: `poe bot weight 82 --workdir /path/to/worktrees`
  1. Env / `.env`: `BOT_WORKTREE_DIR=/path/to/worktrees` (`.env.local`
     overrides per machine)
  1. Default: `~/.cache/<repo>-bot/worktrees/`

- Semantics: `--workdir` is a **base dir**; each run creates
  `<workdir>/<branch-slug>` (concurrent bots don't collide); the run removes
  the subdir, the base dir stays.

- Validation: must be creatable; must not be the main repo or a subdir of it;
  must not be the current working directory.

### 2. CI gate (auto-format + pre-push checks + remote checks)

- **Auto-format (only when there are changes)**: `poe fmt` (ruff format +
  mdformat) formats the changed md/py. Running it full-tree in the worktree
  is safe — origin/master is CI-clean, so no extra diff appears. Format
  happens *before* checks (fix first, then verify).
- **Pre-push local checks** (in order; any failure aborts, no push):
  1. `poe fmt` — auto-format (mutates)
  1. `poe check-fmt` — confirm clean
  1. `poe lint-py` — ruff static checks
  1. `poe test` — pytest
  1. `uv run mkdocs build` — build check (bucket rewrite already enabled,
     see §7.5)
- **Post-push (remote)**: `github_api.wait_checks()` polls until all green;
  `--auto-merge` → when green: `mark_ready()` + `merge(squash)` (REST has no
  reliable auto-merge toggle, so the bot polls and merges itself).
- Keep the local check list in sync with `ci.yml` (shared constant).
- Note: `fmt` mutates, `check-fmt` verifies — CI only runs `check-fmt` (a bot
  must never reformat master); locally `fmt` runs first so the committed code
  is clean. mdformat excludes `docs/notes/health/_summary.md`
  (health-summary output).

### 3. Preview & submission gate

- `--preview` serves `mkdocs serve -a 127.0.0.1:8123` inside the workdir
  (dedicated port, avoids the dev server's 8000); prints the URL, runs in the
  foreground, Ctrl-C to end.
- Preview is the pre-commit decision point: only the isolated worktree was
  mutated (no commit, no push), instance state `ready`:
  - happy → `poe bot submit <name>` starts the submit chain
  - tweaks → edit files in the worktree directly (bot prints the path), then
    `submit`
  - unhappy → `poe bot abort <name>` discards, zero remote trace
- Default (`--now`) goes straight through; the safety net is the draft PR.

### 4. Task orchestration

**Task registry**: each task is either a Python unit (builtin, declaring
`name` / `parse_args(args)` / `run(ctx, args)` / commit·PR template) or a
**template task configured in `mkdocs.yml`** → `extra.bot.tasks` (no code
needed):

```yaml
# mkdocs.yml
  bot:
    tasks:
      text-moment:
        args: [text]
        cmd: ["uv", "run", "python", "scripts/create_moment.py", "{text}"]
        commit: '[bot] feat(moment): add text "{text}"'
        body: "- text moment: {text}"
```

- `args` names the positional placeholders; `cmd` / `commit` / `body` are
  format strings using them; extra CLI args are appended to `cmd` (e.g.
  `--draft`). Missing required args raise a clear error.
- Config entries add new tasks or **override** builtin ones (same name).
- `mkdocs.yml` is read with a custom YAML loader that tolerates its `!ENV`
  and `!!python/name:` tags.

**Composition syntax** — several tasks in one command, run sequentially:

```bash
poe bot "weight 81.5" "text-moment 晨跑5km" "health-summary"
poe bot "weight 81.5 + text-moment 晨跑5km"   # + shorthand
```

- Each quoted pair = one task + args; all run in the **same worktree/branch**.
- One commit after everything succeeds (`git add -A` is safe: the worktree
  starts clean).

**Commit / PR aggregation**:

- subject = main change + abbreviated extras (length-controlled), with the
  bot run time appended — action + time; free-text task content (scrap/moment
  text) never goes in the title, short structured values (e.g. the weight
  figure) may stay:
  `[bot] feat(weight): record 81.5 kg + add text-moment (2026-08-12 10:31)`
- body lists each task's summary (details — scrap/moment text, measurement
  date — live here, not in the title):
  ```
  - weight 81.5 kg (2026-08-12)
  - text moment: 晨跑5km
  ```
- PR title = subject; PR body = task summary + run time + a
  `` Generated by `poe bot`. `` trailer, hard-capped at **100 chars**
  (`build_pr_body` truncates long detail lines with … first, trailer always
  kept).

**Failure handling (fail-fast)**: any task failure stops the run — **no
commit, no push**; the worktree stays (state `stale`), bot prints the failed
task + changed files and suggests `poe bot list` / `bot cleanup <name>` (or
manual inspection in the worktree). Failures are **abort-only**: no resume /
checkpoint mechanism — discard with `poe bot abort <name>` or
`poe bot cleanup <name> --force`.

**Plan files (recurring flows)**: CLI composition suits one-offs; fixed daily/
weekly flows use a YAML plan file. **Parameters are not hard-coded** — use
`{var}` placeholders + a `vars` block:

```yaml
# .bot/plans/morning.yml
vars:                       # order = CLI positional arg order
  weight: {desc: "今天体重(kg)", required: true}
  note:   {desc: "备注（可选，留空跳过 moment）", default: ""}
tasks:
  - "weight {weight}"
  - "text-moment {note}"    # empty note → task skipped
  - "health-summary"
auto_merge: true
```

- **Two value channels, both command-line (no interactive prompts)**:
  1. Positional args in `vars` order: `poe bot --plan morning 81.5`
  1. Key/value: `poe bot --plan morning --var weight=81.5`
- **Missing handling**: a `required` var missing → error + print each var's
  `desc` and `--var key=value` usage; vars with `default` may be omitted.
- **Empty-arg task skip**: a task whose args resolve empty is skipped (empty
  `note` → no moment), so one plan covers "plain check-in" and
  "check-in + note".
- Placeholders exist only in `--plan` files; direct CLI composition passes
  args inline (`poe bot "weight 81.5" ...`).
- Order in the plan file expresses dependencies (e.g. health-summary after
  weight/sync-running); no automatic dependency graph for now (YAGNI).

**Plan files are local-only**: `.bot/` is git-ignored — no example plans ship
with the repo, create your own in `.bot/plans/<name>.yml` when a recurring
flow warrants it (format above). The default everyday path is the shared
`mkdocs.yml` task definitions with inline CLI composition
(`poe bot "weight 81.5" ...`); plans are the escape hatch for special
orchestrations (fixed daily/weekly routines).

**Idempotency**: tasks guarantee their own repeatability (e.g.
`update_weight` warns on same-day overwrite); the orchestrator doesn't
intervene.

### 4.5 Config & state layering

Three layers, each with its own home and commit policy:

| Layer                     | Where                                                               | What it holds                                                          | Committed?           |
| ------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------- |
| **Task definitions**      | `mkdocs.yml` → `extra.bot.tasks` + builtins in `scripts/git_bot.py` | what tasks exist and how to run them (`cmd`/`commit`/`body` templates) | ✅ shared            |
| **Plans (orchestration)** | `.bot/plans/*.yml` (git-ignored)                                    | personal routine: `vars` + task order + `auto_merge`                   | ❌ local-only        |
| **Instance state**        | `.bot-active` in each worktree (git-ignored)                        | per-run status: pid / branch / started / state / tasks                 | ❌ never (ephemeral) |

- **Task definitions** are shared product config (versioned, reviewed);
  `load_task_config()` reads the main repo's `mkdocs.yml` (REPO_ROOT), so
  worktrees don't need the task config checked out.
- **Plans** are personal usage (language, habits); committing them adds
  noise for other clones — keep them local.
- **`.bot-active`** is pure runtime bookkeeping (see §8).

### 5. Branch naming

```
bot/<task-slug>/<YYYYMMDD>-<HHMMSS>
bot/weight/20260811-213000
bot/text-moment/20260811-213100
bot/weight+text-moment/20260811-213200  # composed tasks
```

- `bot` prefix marks robot origin; second-level timestamp avoids concurrent
  collisions; task slug is human-readable.

### 6. Commit / PR messages (`[bot]` prefix)

- Conventional commits, subject prefixed with `[bot]`; the bot run time
  (`YYYY-MM-DD HH:MM`) is appended so each entry states **action + time**;
  free-text task content (scrap/moment text) stays in the body / PR desc,
  never in the title (short structured values like the weight figure may
  stay in the title):
  - `[bot] feat(weight): record 82 kg (2026-08-12 10:31)`
  - `[bot] feat(enu): add scrap (2026-08-12 10:31)`
  - `[bot] feat(moment): add text (2026-08-12 10:31)`
  - composed: `[bot] feat(weight): record 82 kg + feat(enu): add scrap (2026-08-12 10:31)`
- **PR title also carries `[bot]`**: auto-merge squashes with the PR title as
  the resulting commit message — without the prefix the marker would be lost
  in master history.
- PR body = task summary + run time + a `` Generated by `poe bot`. `` trailer,
  hard-capped at **100 chars** (long detail lines truncated with `…` first,
  trailer kept); date aliases (`today`/`yesterday`) are resolved to real
  dates in messages.

### 7. Reuse the main repo environment: `.venv` + `.env` symlinks

- **`.venv`**: symlink the main repo's `.venv` (≈228 MB; `uv run` honors
  `VIRTUAL_ENV`, so it works directly). The worktree's tracked files match
  the main repo, so no reinstall.
- **`.env` / `.env.local`**: symlink these too — `shared/env.py` resolves
  `REPO_ROOT` from the script's own path (the workdir), so without symlinks
  the bot loses `BOT_GH_TOKEN`, R2 credentials, `MKDOCS_BUCKET_*`, etc.
  Belt-and-braces: the bot process calls `load_env_files()` at startup
  (cwd = main repo); inherited env vars win in children (highest precedence).
- Fallback: if `pyproject.toml` / `uv.lock` changed (bot tasks never touch
  deps), `--resync` forces `uv sync`; warn on lock drift by default.
- `site/` / `.cache/` are gitignored and regenerate inside the workdir.

### 7.5 Missing-path audit (git-ignored files in a worktree)

A worktree only checks out tracked files; git-ignored locals are all absent:

| Path                                                         | Impact when missing                                   | Handling                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------ | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.venv/`                                                     | uv environment                                        | symlink main repo `.venv` (§7)                                                                                                                                                                                                                                                                |
| `.env` / `.env.local`                                        | credentials/local config (PAT, R2, `MKDOCS_BUCKET_*`) | symlink + env injection (§7)                                                                                                                                                                                                                                                                  |
| `docs/assets/bucket/`                                        | local copies of large images                          | **Optional** — symlinked from the main repo (like `.venv`/`.env`) so the worktree has real local copies (no not_found build warnings); `bucket.enabled: true` (mkdocs.yml) rewrites `assets/bucket/` links to the R2 `base_url` regardless, and CI only warns (non-strict) on missing targets |
| `docs/assets/javascripts/mermaid.*`, `docs/.mermaid-version` | downloaded at build                                   | symlinked from the main repo (`_symlink_mermaid`) — no re-download; fallback: download at build if missing (proxy env passed through)                                                                                                                                                         |
| `site/`, `.cache/`, `__pycache__/`, `*.egg-info/`            | none (regenerated)                                    | ignore                                                                                                                                                                                                                                                                                        |
| `external/`                                                  | external research data (not counted)                  | ignore                                                                                                                                                                                                                                                                                        |
| `.pi/`, `.pi-subagents/`                                     | no build impact                                       | ignore                                                                                                                                                                                                                                                                                        |

> Conclusion: besides `.venv`/`.env` (symlinked) and the mermaid download
> (network/proxy), no other path blocks the build; `docs/assets/bucket/` is
> covered natively by the R2 rewrite.

### 8. Lifecycle: list / submit / abort / cleanup (multi-bot safe)

- Every instance leaves a **`.bot-active` marker file** in its own workdir —
  git-ignored runtime bookkeeping, never committed. Contents:
  `pid` (bot process), `branch`, `started` (ISO timestamp), `state`
  (`running` → `ready` → `submitted`, or `stale` on failure), `tasks`
  (JSON task list — lets `submit` rebuild the commit message).

  Its four roles:

  1. **Active vs stale**: `cleanup`/`list` read the pid and probe it with
     `os.kill(pid, 0)` — a live pid means an active bot (skip); a dead one
     means leftover (cleanable). This is what makes multi-bot cleanup safe.
  1. **State machine**: `submit` accepts only `ready`/`stale` (rejects
     `running`); `running` → `ready` (after `--preview`) → `submitted`;
     failures flip it to `stale` so the worktree is preserved for retry or
     abort.
  1. **Task list**: `tasks` JSON lets `poe bot submit <name>` rebuild the
     commit/PR messages without re-running anything.
  1. **Lifecycle**: written when the worktree is created; deleted together
     with the worktree on success; left as `stale` on failure/crash for
     `abort`/`cleanup` to find.

**`poe bot list`** — scan the workdir base dir + `git worktree list`
(branches matching `bot/`); one line per bot: bot name (branch), worktree
path, state (active / stale / merged / ready), start time (from
`.bot-active`).

**`poe bot submit <name>`** — commit a `ready` instance (CI gate + commit +
push + draft PR).

**`poe bot abort <name>`** — discard an unfinished instance: not pushed →
remove worktree + local branch; pushed / draft PR open → close PR (no merge)

- delete remote branch + remove worktree + local branch.

**`poe bot cleanup [<name>]`** — collect merged instances:

1. Skip active instances (`.bot-active` present and pid alive)
1. Merged branches (`git branch --merged origin/master`) →
   `git worktree remove --force` (unlink marker first to avoid symlink errors)
1. Stale instances (marker with dead pid / no marker but branch is `bot/...`):
   list only by default, delete with `--force`; non-bot worktrees are never
   touched
1. Delete merged local bot branches; `list_bot_prs()` (state=merged) →
   delete corresponding remote branches (`git push origin --delete`)
1. `git worktree prune`

Concurrent bots don't interfere: worktree dirs are isolated per branch, branch
names carry second-level timestamps, and cleanup only touches
"merged + not active" instances.

## File Layout

```
scripts/git_bot.py          # bot entrypoint (subcommands: run / list / submit / abort / cleanup)
shared/github_api.py        # Python GitHub API client (zero deps, reusable)
shared/ci_checks.py?        # local CI-equivalent check list (synced with ci.yml)
.bot/plans/*.yml            # orchestration plan files (e.g. morning.yml)
.env.example                # BOT_GH_TOKEN / BOT_WORKTREE_DIR comment placeholders
pyproject.toml              # poe task: bot = python scripts/git_bot.py
README.md / internal/*      # usage docs (this design + commands.md + architecture.md)
```

## Implementation Phases

### Phase 1 — minimal (weight single task)

- [ ] `scripts/git_bot.py` (poe task `bot`)
- [ ] worktree create/remove + `.venv`/`.env` symlinks + `.bot-active` marker
- [ ] task registry skeleton + `weight` task (reuses `update_weight.py`)
- [ ] local gate: `poe fmt` → `check-fmt` → `lint-py` → `test` → `mkdocs build`
- [ ] branch name + commit/PR templates; submission-mode parsing
  (`--now` default / `--preview` stops at ready)
- [ ] `shared/github_api.py` (create_pr / wait_checks / merge / list_bot_prs)
- [ ] push via subprocess + `http.extraheader` PAT (bypasses credential helper)
- [ ] draft PR creation
- [ ] `.env.example` `BOT_GH_TOKEN` placeholder (real value only in .env)
- [ ] `bot list` / `bot cleanup <name>` / `bot submit <name>` / `bot abort <name>`
- [ ] config: worktree path (`--workdir` / `BOT_WORKTREE_DIR` / default),
  remote, base branch, author identity, PAT (.env.local)

### Phase 2 — preview & CI gating

- [ ] `--preview`: `mkdocs serve -a 127.0.0.1:8123` in workdir
- [ ] `--wait-ci`: `wait_checks()` poll until green
- [ ] `--auto-merge`: green → `mark_ready()` + `merge()` squash after green
- [ ] draft → ready transition timing

### Phase 3 — orchestration & multi-task

- [ ] registry framework: parse_args / run(ctx) / commit·PR templates
- [ ] multi-task composition: `poe bot "weight 82" "text-moment ..."` one branch/PR
- [ ] commit/PR aggregation: merged subject + per-task body
- [ ] fail-fast: stop on failure, worktree stays stale, cleanup hint
- [ ] plan files: `poe bot --plan morning` (YAML: vars placeholders +
  command-line values + empty-arg skip)
- [ ] register more tasks: sync-running / enu / create-post / text-moment (text-only)

### Phase 4 — robustness & cleanup

- [ ] concurrent bots: worktree/branch isolation per instance, preview port
  increments
- [ ] cleanup concurrency safety: skip active instances (pid alive), clean
  stale only
- [ ] mermaid download failure / proxy-unreachable build fallback message
- [ ] friendly errors: token invalid / remote auth failure (API error message +
  guidance)
- [ ] cleanup extras: stale worktree detection, expired bot branches

## Constraints & Risks

- **The AI never executes this bot**: it is a developer-invoked script using
  the developer's own git/PAT credentials; the AI respects the repo rules
  (no commit / no push / no branch creation) and only implements the script.
- **`.venv` symlink gotcha**: unlink before `git worktree remove` (it errors
  on a symlinked dir); warn on venv/lock drift.
- **CI list drift**: local checks must match `ci.yml`, else "green locally,
  red remotely".
- **Concurrency**: multi-bot collisions avoided via second-level branch
  timestamps + per-branch worktree dirs + preview port increments; cleanup
  skips active instances.
- **Push failure**: remote branch exists / base moved ahead → instruct the
  user to resolve manually.
- **Credentials**: no `gh` dependency; everything through `BOT_GH_TOKEN`.
  Missing → abort with the token-setup guide. Token needs
  `Contents: write` + `Pull requests: write` + `Actions: read`
  (fine-grained) or `repo` / `public_repo` (classic, no `workflow` needed).
- **Token exposure surface**: PAT lives only in `.env` / `.env.local`
  (git-ignored) and process env; never in remote URLs / branch names /
  commit messages; the `http.extraheader` command-line token appears in shell
  history (acceptable, same as rclone's `.env` handling).
- **Network dependency**: worktree builds need to download mermaid assets
  (`http_proxy`/`https_proxy` must be passed to children); offline builds
  fail with a clear message.
