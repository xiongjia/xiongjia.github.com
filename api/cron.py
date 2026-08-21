"""Scheduled bot runs (cron) — config-driven from ``mkdocs.yml``.

Thin scheduling shell over ``api.executor.execute_bot_spec()``: APScheduler's
``AsyncIOScheduler`` fires jobs on the FastAPI event loop; each job runs a
raw ``poe bot run`` spec (``extra.bot.cron`` in mkdocs.yml) through the
existing handoff flow (worktree → task → CI gate → draft PR). Jobs
re-register from mkdocs.yml at every startup — config is the source of
truth, no jobstore persistence (restart loses nothing: the schedule comes
from config, run results from the JSONL history).

Kill switch: ``BOT_API_CRON_ENABLED=false`` disables scheduling entirely —
dynamic env check, same pattern as ``BOT_API_STARTUP_CLEANUP`` in
``api/lifespan.py`` (tests and ops can disable it without touching config).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from api import executor
from api import history as history_store
from api.state import RUNNING
from shared.mkdocs_yaml import MkdocsYamlError, load_extra

logger = logging.getLogger("api.cron")

# APScheduler job options: a missed fire (server down / busy) coalesces into
# one run instead of backlog, and fires within an hour of the slot are still
# executed (later ones are dropped).
MISFIRE_GRACE_S = 3600


class CronConfigError(RuntimeError):
    """Bad ``extra.bot.cron`` config — loud at startup, like
    ``api.models.validate_schemas``."""


@dataclass
class CronJob:
    """One scheduled job. ``spec`` is a raw ``poe bot run`` spec — may
    compose multiple tasks with ``' + '`` (one worktree/branch/PR)."""

    name: str
    schedule: str  # 5-field cron string (server-local TZ unless timezone set)
    spec: str
    handoff: bool = True  # draft PR; never auto-merge (dev decision)
    enabled: bool = True
    timezone: str | None = None


# runtime state (single process, like active_runs)
_scheduler: AsyncIOScheduler | None = None
_last_run: dict[str, executor.BotRun] = {}

# ---------------------------------------------------------------------------
#  Runtime enable/disable overrides (persisted in the .bot-api/ data dir)
#
# mkdocs.yml extra.bot.cron is the static source of truth; these overrides
# let the API/console disable a job at runtime without touching config, and
# survive restarts (the API process owns the schedule, like active_runs —
# the file is the durable record). Stored as ``{name: {disabled_at: iso}}``
# in ``.bot-api/cron-state.json`` next to the run history.
# ---------------------------------------------------------------------------


def _state_path() -> Path:
    # resolved at call time so tests (conftest monkeypatches history.LOG_DIR
    # to a tmp dir) get isolated state files automatically
    return history_store.LOG_DIR / "cron-state.json"


def _load_state() -> dict[str, dict]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}  # corrupt/partial state — treat as no overrides


def _save_state(state: dict[str, dict]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)  # atomic — no torn file on crash


def disabled_jobs() -> set[str]:
    """Names with a runtime disable override (re-read every call — the file
    is tiny and the console re-queries on each refresh)."""
    return set(_load_state())


def is_active(job: CronJob) -> bool:
    """Effective on-state: the static config AND no runtime disable override."""
    return job.enabled and job.name not in disabled_jobs()


def set_disabled(name: str, disabled: bool) -> bool:
    """Runtime on/off override, persisted in ``.bot-api/cron-state.json`` and
    reflected on a running scheduler. Disabling pauses an active job (stops
    firing, ``next_run_at`` → null); enabling resumes it — or re-registers it
    on the fly when it was disabled at startup (scheduler skipped it). Returns
    the effective disabled state. A disabled name that is not in the config is
    harmless (nothing pauses); the router 404s unknown jobs before this."""
    state = _load_state()
    if disabled:
        state[name] = {"disabled_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    else:
        state.pop(name, None)
    _save_state(state)
    if _scheduler is not None:
        if disabled:
            if _scheduler.get_job(name) is not None:
                _scheduler.pause_job(name)
                logger.info("cron %s paused (runtime disable)", name)
        else:
            if _scheduler.get_job(name) is not None:
                _scheduler.resume_job(name)
                logger.info("cron %s resumed (runtime enable)", name)
            else:
                job = load_cron_config().get(name)
                if job is not None and is_active(job):
                    _register(_scheduler, job)  # was disabled at startup — register now
                    logger.info("cron %s registered (runtime enable)", name)
    return name in state


def _register(scheduler: AsyncIOScheduler, job: CronJob) -> None:
    """Add one job to a scheduler (shared by ``start()`` and the
    runtime-enable path)."""
    scheduler.add_job(
        _fire,
        trigger=CronTrigger.from_crontab(job.schedule, timezone=job.timezone),
        args=[job],
        id=job.name,
        name=job.name,
        coalesce=True,
        misfire_grace_time=MISFIRE_GRACE_S,
    )


def _enabled() -> bool:
    return os.environ.get("BOT_API_CRON_ENABLED", "true").strip().lower() in ("true", "1", "yes")


def _as_bool(name: str, key: str, value: Any, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise CronConfigError(f"cron job {name!r}: {key} must be a boolean, got {value!r}")
    return value


def _validate(job: CronJob) -> None:
    """Fail fast on a bad schedule / spec — a typo must not silently disable
    a job (or worse, let an unknown task fire into the engine)."""
    if not job.schedule:
        raise CronConfigError(f"cron job {job.name!r}: missing schedule")
    if not job.spec:
        raise CronConfigError(f"cron job {job.name!r}: missing spec")
    try:
        CronTrigger.from_crontab(job.schedule, timezone=job.timezone)
    except (ValueError, TypeError) as exc:
        raise CronConfigError(
            f"cron job {job.name!r}: bad schedule {job.schedule!r}: {exc}"
        ) from exc
    try:
        executor.parse_task_specs([job.spec])
    except executor.BotError as exc:
        # only the engine's own parser error is a config problem — anything
        # else (TypeError etc.) is a real bug and must surface as-is
        raise CronConfigError(f"cron job {job.name!r}: bad spec {job.spec!r}: {exc}") from exc


def load_cron_config() -> dict[str, CronJob]:
    """Read + validate ``extra.bot.cron`` from mkdocs.yml (empty dict when
    absent or ``cron: {}``). Re-read on every call — cheap, and the API
    reflects config edits without restarting the scheduler state."""
    try:
        raw = load_extra("bot", label="cron", strict=True).get("cron") or {}
    except MkdocsYamlError as exc:
        raise CronConfigError(str(exc)) from exc
    jobs: dict[str, CronJob] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise CronConfigError(
                f"cron job {name!r}: expected a mapping, got {type(entry).__name__}"
            )
        job = CronJob(
            name=str(name),
            schedule=str(entry.get("schedule", "")),
            spec=str(entry.get("spec", "")),
            handoff=_as_bool(name, "handoff", entry.get("handoff"), True),
            enabled=_as_bool(name, "enabled", entry.get("enabled"), True),
            timezone=entry.get("timezone") or None,
        )
        _validate(job)
        jobs[name] = job
    return jobs


async def _fire(job: CronJob) -> None:
    """APScheduler job callback (async — runs on the event loop).

    Overlap guard: skip the fire while the previous run of the same job is
    still RUNNING, so a long sync+CI job can't stack a second worktree/PR.
    Manual triggers (``trigger()``) bypass this — explicit user action.
    Exceptions from the spawn propagate to APScheduler (which logs them and
    keeps the scheduler alive) after being logged here with the job name.
    """
    prev = _last_run.get(job.name)
    if prev is not None and prev.status == RUNNING:
        logger.warning(
            "cron %s: previous run %s still running — skipping fire", job.name, prev.run_id
        )
        return
    _run_job(job)


def _run_job(job: CronJob) -> executor.BotRun:
    """Spawn the job's spec through ``execute_bot_spec`` and record it as the
    job's last run. A spawn failure is logged (the fire is lost, but the
    scheduler survives — same contract as the executor's FAILED path)."""
    try:
        run = executor.execute_bot_spec(job.spec, handoff=job.handoff)
    except Exception as exc:
        logger.error("cron %s fire failed: %s", job.name, exc, exc_info=True)
        raise
    _last_run[job.name] = run
    logger.info("cron %s fired → run %s (%s)", job.name, run.run_id, job.spec)
    return run


def start() -> None:
    """Start the scheduler (no-op when disabled, misconfigured, or already
    running). Called from the FastAPI lifespan startup.

    Deliberately fail-fast: a bad ``extra.bot.cron`` config raises
    ``CronConfigError`` (like ``api.models.validate_schemas`` at import) —
    the API server refuses to start rather than silently running with a
    missing/typo'd job. ``BOT_API_CRON_ENABLED=false`` avoids this entirely."""
    global _scheduler
    if _scheduler is not None or not _enabled():
        return
    jobs = load_cron_config()
    if not jobs:
        logger.info("cron: no jobs in extra.bot.cron — scheduler not started")
        return
    scheduler = AsyncIOScheduler()
    for job in jobs.values():
        if not is_active(job):
            continue
        _register(scheduler, job)
    scheduler.start()
    _scheduler = scheduler
    logger.info("cron: started with %d job(s)", len(scheduler.get_jobs()))


def shutdown() -> None:
    """Stop the scheduler (no-op when never started). Called from the
    lifespan shutdown — in-flight cron runs are terminated with the other
    runs by the existing graceful shutdown (they are normal BotRuns)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("cron: stopped")


def next_run_time(name: str) -> str | None:
    """ISO next-fire time for a job (None when the scheduler is not running
    or the job is disabled/unknown)."""
    if _scheduler is None:
        return None
    job = _scheduler.get_job(name)
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.astimezone().isoformat(timespec="seconds")


def _run_summary(run: executor.BotRun) -> dict:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "pr_url": run.pr_url,
    }


def last_run_info(name: str, job: CronJob | None = None) -> dict | None:
    """Per-job last run summary: the most recent run of this process first,
    else the newest finished history record whose task equals the job's spec
    (cron runs record the raw spec as the task) — so the console still shows
    the last run + its time after a restart. None when the job never ran.

    ``job`` may be passed in to avoid re-reading mkdocs.yml (the router
    already parsed it); it is re-resolved when None.

    NOTE: the history fallback matches on the spec string, so a manual
    console/TG run of the same spec (e.g. the ``hello`` task vs the
    ``smoke-hello`` cron job) is indistinguishable and counts as the job's
    last run — an acceptable approximation, not a perfect attribution."""
    run = _last_run.get(name)
    if run is not None:
        return _run_summary(run)
    if job is None:
        job = load_cron_config().get(name)
        if job is None:
            return None
    records, _ = history_store.load(limit=50)
    for rec in records:  # newest-first
        if rec.get("task") == job.spec and rec.get("status") != RUNNING:
            return {
                "run_id": rec.get("run_id"),
                "status": rec.get("status"),
                "started_at": rec.get("started_at"),
                "finished_at": rec.get("finished_at"),
                "pr_url": rec.get("pr_url"),
            }
    return None


def get_job(name: str) -> CronJob | None:
    return load_cron_config().get(name)


def trigger(name: str) -> executor.BotRun:
    """Manual run-now: fire regardless of enabled/schedule/overlap (explicit
    user action — the smoke-test path). Unknown job → KeyError (router maps
    it to 404)."""
    job = get_job(name)
    if job is None:
        raise KeyError(name)
    return _run_job(job)
