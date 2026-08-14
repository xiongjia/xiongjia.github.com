"""Async bot-task execution: thin shell over ``poe bot run …``.

Builds the subprocess argv (task spec string), streams stdout into the
run's log queue, detects the outcome from the exit code + output scan, and
persists finished runs to the JSONL history. ``runner`` is an injectable
boundary so unit tests never spawn a real ``poe bot``.

Runs are **handoff-only** (dev decision): the API never passes
``--auto-merge`` — every run ends in a draft PR for the developer. The
engine's CLI flag remains a manual option.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import uuid
from pathlib import Path

from api import history as history_store
from api.models import RunRequest, assemble_args, task_schema
from api.state import (
    ABORTED,
    FAILED,
    MERGED,
    RUNNING,
    SUBMITTED,
    BotRun,
    active_runs,
    trim_active,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# how many trailing log lines the history record keeps (diagnose failures
# without bloating the JSONL)
HISTORY_LOG_TAIL = 20

RE_MERGED = re.compile(r"merged PR #\d+")
RE_SUBMITTED = re.compile(r"Draft PR #(\d+): (\S+)")
RE_BRANCH = re.compile(r"🌿 branch (bot/\S+)")


class Runner:
    """Subprocess boundary (replace in tests with a fake)."""

    async def run(
        self, argv: list[str], cwd: Path, env: dict[str, str] | None = None
    ) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=env,
            # own session → the whole process group (uv → poe → python → …)
            # is killable with one signal; otherwise only the direct child
            # dies and the engine survives as an orphan that keeps running
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )


runner = Runner()


def terminate_proc(proc: asyncio.subprocess.Process) -> None:
    """Terminate the subprocess and its whole process group (SIGTERM).

    The direct child is ``uv``; without killing the group its children
    (poe → python git_bot → task scripts) survive and keep running.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass


def assemble_argv(
    task: str,
    args: list[str],
    auto_merge: bool = False,
    handoff: bool = True,
    stage_dir: str | None = None,
) -> list[str]:
    """``uv run poe bot run "<task> <args…>" --handoff|--wait-ci …``.

    The task spec is a single argv token; ``git_bot.parse_task_specs``
    splits it, and template tasks with a rest arg rejoin free-text tokens.
    ``--handoff`` (draft PR immediately) is the default; unchecked handoff
    passes ``--wait-ci`` instead (wait for CI checks, still draft, never
    merged — ``--auto-merge`` stays an internal test-only knob).
    """
    argv = ["uv", "run", "poe", "bot", "run", " ".join([task, *args])]
    argv.append("--handoff" if handoff else "--wait-ci")
    if auto_merge:
        argv.append("--auto-merge")
    if stage_dir:
        argv += ["--stage-dir", stage_dir]
    return argv


def execute_bot_task(
    task: str,
    args: list[str],
    auto_merge: bool = False,
    handoff: bool = True,
    stage_dir: str | None = None,
) -> BotRun:
    """Create a run, schedule the subprocess in the background, return now."""
    if task_schema(task) is None:
        raise ValueError(f"unknown task {task!r}")
    run = BotRun(run_id=uuid.uuid4().hex[:12], task=task, args=" ".join(args))
    active_runs[run.run_id] = run
    trim_active()
    run.log(f"▶ submitting: {task} {' '.join(args)}")
    asyncio.get_running_loop().create_task(
        _run_bot(run, task, args, auto_merge, handoff, stage_dir)
    )
    return run


async def _run_bot(
    run: BotRun,
    task: str,
    args: list[str],
    auto_merge: bool,
    handoff: bool,
    stage_dir: str | None,
) -> None:
    try:
        argv = assemble_argv(task, args, auto_merge, handoff, stage_dir)
        run.log(f"$ {' '.join(argv)}", level="cmd")
        # PYTHONUNBUFFERED keeps engine stderr/stdout arriving in real order
        # (block-buffered stdout piped into the log stream otherwise reorders
        # error lines before earlier output). Merge into the current env —
        # passing a bare dict replaces it entirely (loses PATH → ENOENT).
        subprocess_env = dict(os.environ)
        subprocess_env["PYTHONUNBUFFERED"] = "1"
        proc = await runner.run(argv, cwd=REPO_ROOT, env=subprocess_env)
        run.proc = proc
        if run.status == ABORTED:  # aborted while spawning — kill before it does work
            terminate_proc(proc)
            await proc.wait()
            return
        if proc.stdout is not None:
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    run.log(line)
                    if m := RE_BRANCH.search(line):
                        run.branch = m.group(1)
        code = await proc.wait()
        if run.status == ABORTED:
            return  # abort_run already persisted the record
        _finalize(run, code)
    except asyncio.CancelledError:
        run.finish(ABORTED)
        raise
    except Exception as exc:  # subprocess spawn failure etc.
        run.log(f"❌ {exc}", level="err")
        run.finish(FAILED)


def _finalize(run: BotRun, code: int) -> None:
    if code == 0:
        text = "\n".join(e["msg"] for e in run.logs)
        if m := RE_SUBMITTED.search(text):
            run.finish(SUBMITTED, pr_url=m.group(2))
        elif RE_MERGED.search(text):
            run.finish(MERGED)
        else:
            run.finish(SUBMITTED)
    else:
        run.log(f"❌ bot exited with code {code}", level="err")
        run.finish(FAILED)
    record = run.to_dict()
    record["logs"] = record["logs"][-HISTORY_LOG_TAIL:]
    history_store.append(record)


async def abort_run(run_id: str) -> BotRun | None:
    """Terminate a running run and persist the ABORTED record.

    Finished runs are returned unchanged (their status is not overwritten);
    a run still spawning is marked aborted and killed by ``_run_bot`` as
    soon as the process handle exists.
    """
    run = active_runs.get(run_id)
    if run is None:
        return None
    if run.status != RUNNING:
        return run
    if run.proc is not None:
        terminate_proc(run.proc)
    run.finish(ABORTED)
    record = run.to_dict()
    record["logs"] = record["logs"][-HISTORY_LOG_TAIL:]
    history_store.append(record)
    if run.branch:
        asyncio.get_running_loop().create_task(_cleanup_branch(run.branch))
    return run


async def _cleanup_branch(branch: str) -> None:
    try:
        proc = await runner.run(["uv", "run", "poe", "bot", "abort", branch], cwd=REPO_ROOT)
        await proc.communicate()  # drain output so the process can't block
    except Exception:  # best effort — worktree cleanup is not critical
        pass


def run_from_request(req: RunRequest) -> tuple[str, list[str]]:
    """Resolve raw args or assemble from schema fields (validates the task)."""
    if task_schema(req.task) is None:
        raise ValueError(f"unknown task {req.task!r}")
    if req.fields is not None:
        args = assemble_args(req.task, req.fields)
    else:
        args = list(req.args or [])
    return req.task, args
