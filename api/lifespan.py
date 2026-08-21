"""FastAPI lifespan: startup cleanup and graceful shutdown.

Startup: prune old history files, run stale-worktree cleanup in the
background (``poe bot cleanup``), and start the Telegram bot (polling or
webhook per ``TG_MODE``) when a token is configured. Shutdown: stop the
bot, then terminate in-flight bot subprocesses (whole process groups) so
no orphan worktree runs keep mutating the repo.

The stale-worktree cleanup can be disabled with
``BOT_API_STARTUP_CLEANUP=false`` (tests set it; dev can too).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from fastapi import FastAPI

from api import cron as cron_scheduler
from api import history as history_store
from api.config import tg_settings
from api.executor import terminate_proc
from api.routers import tg as tg_router
from api.state import RUNNING, active_runs

logger = logging.getLogger("api.lifespan")

# long-poll timeout for getUpdates. Telegram recommends ≤ 50s, but the
# privoxy proxy on this machine tears down longer idle connections (the
# getUpdates request sits half-open in CLOSE_WAIT and polling stalls).
# 10s (PTB's default) is verified stable here; a message still arrives
# instantly — long polling returns as soon as an update exists. Raise it
# only if you know the proxy holds connections that long.
POLL_TIMEOUT_S = 10

# set once shutdown starts so the polling error callback stays quiet: the
# in-flight getUpdates connection is torn down by the loop closing, which
# is expected and not actionable
_shutting_down = False


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


def _poll_error_cb(exc) -> None:
    """Log polling errors — except during shutdown, where the connection
    teardown raises a harmless TelegramError (PTB's default callback would
    print a full traceback on every Ctrl+C)."""
    if _shutting_down:
        return
    msg = str(exc)
    if "Conflict" in msg and "getUpdates" in msg:
        # permanent, not retryable: another instance is polling this token
        # (Telegram allows exactly ONE getUpdates consumer). Restarting this
        # process after killing the other one is the only fix.
        logger.error(
            "telegram polling stopped: %s — another bot instance is polling "
            "this token; kill the other instance and restart (409 is permanent)",
            exc,
        )
        return
    logger.error("telegram polling error: %s", exc)


async def _tg_startup():
    """initialize/start the PTB Application; polling or webhook per mode."""
    app = tg_router.get_app()
    if app is None:
        return None
    try:
        await app.initialize()
        await app.start()
        if tg_settings.mode == "webhook":
            url = tg_settings.webhook_url.strip()
            if not url:
                logger.warning(
                    "TG_MODE=webhook but TG_WEBHOOK_URL is empty — webhook not registered"
                )
            else:
                await app.bot.set_webhook(url)
                logger.info("telegram webhook registered: %s", url)
        else:
            await app.updater.start_polling(
                timeout=timedelta(seconds=POLL_TIMEOUT_S),
                error_callback=_poll_error_cb,
            )
            logger.info("telegram polling started (long-poll timeout %ss)", POLL_TIMEOUT_S)
    except Exception as exc:
        logger.error("telegram startup failed: %s", exc)
        return None
    return app


async def _tg_shutdown(app) -> None:
    global _shutting_down
    if app is None:
        return
    _shutting_down = True
    try:
        if tg_settings.mode == "webhook":
            await app.bot.delete_webhook()
        # Application.stop() does NOT stop the updater (PTB docs) — stop it
        # explicitly FIRST so the in-flight getUpdates is cancelled before
        # the event loop tears down; otherwise the polling task survives and
        # logs a connection-error traceback on Ctrl+C.
        if app.updater is not None:
            with suppress(Exception):
                await app.updater.stop()
        await app.stop()
        await app.shutdown()
    except Exception as exc:
        logger.warning("telegram shutdown failed: %s", exc)


@asynccontextmanager
async def run_lifespan(app: FastAPI):
    history_store._prune_old()
    if _cleanup_enabled():
        asyncio.get_running_loop().create_task(_stale_worktree_cleanup())
    tg_app = await _tg_startup()
    cron_scheduler.start()
    yield
    cron_scheduler.shutdown()
    await _tg_shutdown(tg_app)
    # graceful shutdown: terminate in-flight bot subprocesses
    for run in active_runs.values():
        if run.status == RUNNING and run.proc is not None:
            terminate_proc(run.proc)
