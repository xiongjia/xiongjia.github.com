"""FastAPI lifespan: startup cleanup and graceful shutdown.

Startup: prune old history files, and run stale-worktree cleanup in the
background (``poe bot cleanup``). Shutdown: terminate in-flight bot
subprocesses (whole process groups) so no orphan worktree runs keep
mutating the repo.

The stale-worktree cleanup can be disabled with
``BOT_API_STARTUP_CLEANUP=false`` (tests set it; dev can too).
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import history as history_store
from api.executor import terminate_proc
from api.state import RUNNING, active_runs


def _cleanup_enabled() -> bool:
    return os.environ.get("BOT_API_STARTUP_CLEANUP", "true").strip().lower() in ("true", "1", "yes")


async def _stale_worktree_cleanup() -> None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "poe",
            "bot",
            "cleanup",
            start_new_session=True,  # own group so terminate_proc can't kill us
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            terminate_proc(proc)  # don't orphan the cleanup process (git locks)
            await proc.wait()
    except Exception:
        pass  # best effort — cleanup can be retried later


@asynccontextmanager
async def run_lifespan(app: FastAPI):
    history_store._prune_old()
    if _cleanup_enabled():
        asyncio.get_running_loop().create_task(_stale_worktree_cleanup())
    yield
    # graceful shutdown: terminate in-flight bot subprocesses
    for run in active_runs.values():
        if run.status == RUNNING and run.proc is not None:
            terminate_proc(run.proc)
