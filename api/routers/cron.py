"""Cron endpoints: job list (with next/last run) + manual run-now trigger."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api import cron as cron_scheduler
from api.models import RunResponse

router = APIRouter(prefix="/api", tags=["cron"])


def _require_job(name: str) -> None:
    if cron_scheduler.get_job(name) is None:
        raise HTTPException(status_code=404, detail=f"unknown cron job {name!r}")


@router.get("/cron")
async def cron_jobs() -> dict:
    """Configured cron jobs from ``extra.bot.cron`` (re-read on every call,
    so the list reflects mkdocs.yml edits) with scheduler state: next fire
    time (None when scheduling is disabled/not running or the job is paused),
    the last run of this process, and the runtime disable override."""
    disabled = cron_scheduler.disabled_jobs()
    jobs = []
    for name, job in cron_scheduler.load_cron_config().items():
        jobs.append(
            {
                "name": name,
                "schedule": job.schedule,
                "spec": job.spec,
                "handoff": job.handoff,
                "enabled": job.enabled,  # static config (mkdocs.yml)
                "disabled": name in disabled,  # runtime override (.bot-api)
                "active": job.enabled and name not in disabled,
                "timezone": job.timezone,
                "next_run_at": cron_scheduler.next_run_time(name),
                "last_run": cron_scheduler.last_run_info(name, job),
            }
        )
    return {"jobs": jobs}


@router.post("/cron/{name}/run", response_model=RunResponse)
async def cron_run(name: str) -> RunResponse:
    """Manual run-now — fires the job's spec through the normal handoff flow
    regardless of its schedule/enabled flag (explicit user action; the
    smoke-test path). Unknown job → 404."""
    try:
        run = cron_scheduler.trigger(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown cron job {name!r}")
    except ValueError as exc:  # spawn failure (invalid spec surfaced at trigger time)
        raise HTTPException(status_code=400, detail=str(exc))
    return RunResponse(
        run_id=run.run_id,
        task=run.task,
        args=run.args,
        status=run.status,
        started_at=run.started_at,
        stream_url=f"/api/bot/stream/{run.run_id}",
    )


@router.post("/cron/{name}/disable")
async def cron_disable(name: str) -> dict:
    """Pause a job at runtime (persisted in ``.bot-api/cron-state.json``,
    survives restarts). The schedule stops firing; ``next_run_at`` goes null.
    Manual run-now still works (explicit action)."""
    _require_job(name)
    return {"name": name, "disabled": cron_scheduler.set_disabled(name, True)}


@router.post("/cron/{name}/enable")
async def cron_enable(name: str) -> dict:
    """Resume a runtime-disabled job (clears the override). Re-registers it
    on the fly if it was disabled at startup and never scheduled."""
    _require_job(name)
    return {"name": name, "disabled": cron_scheduler.set_disabled(name, False)}
