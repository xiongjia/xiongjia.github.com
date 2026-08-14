"""Bot endpoints: run, status, SSE stream, history, abort."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api import history as history_store
from api.executor import abort_run, execute_bot_task, run_from_request
from api.models import RunRequest, RunResponse
from api.state import RUNNING, active_runs

router = APIRouter(prefix="/api/bot", tags=["bot"])

HEARTBEAT_S = 15
REPLAY_TAIL = 50


@router.post("/run", response_model=RunResponse)
async def run(req: RunRequest) -> dict:
    try:
        task, args = run_from_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run = execute_bot_task(task, args, handoff=req.handoff)  # never auto-merge
    return {
        "run_id": run.run_id,
        "task": run.task,
        "args": run.args,
        "status": run.status,
        "started_at": run.started_at,
        "stream_url": f"/api/bot/stream/{run.run_id}",
    }


@router.get("/status/{run_id}")
async def status(run_id: str) -> dict:
    run = active_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.to_dict()


def _sse(data: str) -> str:
    return f"data: {data}\n\n"


@router.get("/stream/{run_id}")
async def stream(run_id: str) -> StreamingResponse:
    run = active_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def gen():
        yield _sse("[RESET]")  # client clears its log pane on reconnect
        for entry in run.logs[-REPLAY_TAIL:]:
            yield _sse(json.dumps(entry, ensure_ascii=False))
        if run.status != RUNNING:
            yield _sse("[DONE]")
            return
        # drain entries queued before subscription (already in the snapshot),
        # but keep the None end-of-stream sentinel for the live loop
        while not run.log_queue.empty():
            item = run.log_queue.get_nowait()
            if item is None:
                run.log_queue.put_nowait(None)
                break
        while True:
            try:
                entry = await asyncio.wait_for(run.log_queue.get(), timeout=HEARTBEAT_S)
            except asyncio.TimeoutError:
                if run.status != RUNNING:
                    break  # finished while we waited
                yield ": ping\n\n"
                continue
            if entry is None:
                break
            yield _sse(json.dumps(entry, ensure_ascii=False))
        yield _sse("[DONE]")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
async def history(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = None,
) -> dict:
    records, total = history_store.load(limit=limit, offset=offset, query=q)
    running = [r.to_dict() for r in active_runs.values() if r.status == RUNNING]
    return {"total": total, "records": records, "running": running}


@router.post("/abort/{run_id}")
async def abort(run_id: str) -> dict:
    run = await abort_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run.run_id, "status": run.status}
