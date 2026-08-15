"""System endpoints: health, version, task schema, task list."""

from __future__ import annotations

import asyncio
import os
import subprocess

from fastapi import APIRouter, HTTPException

from api.models import UploadRequest, task_names, task_schema
from api.uploads import save_uploads

router = APIRouter(prefix="/api", tags=["system"])


@router.post("/upload")
async def upload(payload: UploadRequest) -> dict:
    """Stage browser-uploaded images (base64 JSON) into ``.bot-api/uploads/``.

    Returns absolute host paths for the console to use as ``--image`` values;
    create_moment reads them via absolute paths, worktree-agnostic.
    """
    try:
        paths = await asyncio.to_thread(save_uploads, [f.model_dump() for f in payload.files])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"files": paths}


def _git_short_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
    except Exception:
        return "unknown"


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict:
    # to_thread: don't block the event loop on the git subprocess
    git_hash = os.environ.get("GIT_HASH") or await asyncio.to_thread(_git_short_hash)
    return {"version": "0.1.0", "git_hash": git_hash}


@router.get("/tasks")
async def tasks() -> dict:
    return {"tasks": task_names()}


@router.get("/schema/{task}")
async def schema(task: str) -> dict:
    s = task_schema(task)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown task {task!r}")
    return s.model_dump()
