"""In-memory run state (single process, no Redis).

``active_runs`` is capped at ``ACTIVE_CAP``; overflow is flushed to the
JSONL history file by the executor and dropped from memory. A restart loses
in-flight runs (history file survives).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

RUNNING = "running"
SUBMITTED = "submitted"
MERGED = "merged"
FAILED = "failed"
ABORTED = "aborted"

ACTIVE_CAP = 50
# cap on the in-memory log list so a long noisy run can't grow unbounded
LOG_LIST_CAP = 500

# log level heuristic: emoji → level (best effort, raw lines otherwise)
_LEVELS = {
    "✅": "ok",
    "📦": "ok",
    "🚀": "ok",
    "🧹": "ok",
    "🔍": "info",
    "▶": "info",
    "🌿": "info",
    "⏳": "info",
    "⏭": "warn",
    "⚠": "warn",
    "❌": "err",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log_level(line: str) -> str:
    for emoji, level in _LEVELS.items():
        if emoji in line:
            return level
    return "info"


@dataclass
class BotRun:
    run_id: str
    task: str
    args: str
    status: str = RUNNING
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    pr_url: str | None = None
    logs: list[dict] = field(default_factory=list)
    log_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    proc: asyncio.subprocess.Process | None = None
    branch: str | None = None

    def log(self, msg: str, level: str | None = None) -> None:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level or log_level(msg),
            "msg": msg,
        }
        self.logs.append(entry)
        if len(self.logs) > LOG_LIST_CAP:
            del self.logs[: len(self.logs) - LOG_LIST_CAP]
        self.log_queue.put_nowait(entry)

    def finish(self, status: str, pr_url: str | None = None) -> None:
        self.status = status
        self.finished_at = now_iso()
        if pr_url:
            self.pr_url = pr_url
        self.log_queue.put_nowait(None)  # sentinel: end of stream

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "args": self.args,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "pr_url": self.pr_url,
            "logs": self.logs,
        }


active_runs: dict[str, BotRun] = {}


def trim_active() -> None:
    """Drop finished runs beyond the cap (oldest first); running ones stay.

    Note: if more than ``ACTIVE_CAP`` runs are *running* concurrently, the
    cap is soft — running runs are never dropped, only finished overflow.
    """
    if len(active_runs) <= ACTIVE_CAP:
        return
    finished = sorted(
        (r for r in active_runs.values() if r.status != RUNNING),
        key=lambda r: r.started_at,
    )
    for run in finished[: len(active_runs) - ACTIVE_CAP]:
        active_runs.pop(run.run_id, None)
