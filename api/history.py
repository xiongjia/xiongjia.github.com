"""JSONL persistence for finished runs.

The runtime data dir is ``BOT_API_LOG_DIR`` (default: repo-local
``.bot-api/``, absolute or repo-relative); the history file
``history.jsonl`` lives there and is appended line by line. The file
rotates by the date of its last write (``history.jsonl.<date>``) and
rotated files older than ``KEEP_DAYS`` are pruned. The same dir hosts the
upload staging (``uploads/``) once the uploads feature lands.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from api.config import settings

REPO_ROOT = Path(__file__).resolve().parent.parent
KEEP_DAYS = 30
LOAD_LIMIT = 200


def _resolve_dir(raw: str) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


LOG_DIR = _resolve_dir(settings.log_dir)
HISTORY_FILE = LOG_DIR / "history.jsonl"


def _rotate_if_needed() -> None:
    if not HISTORY_FILE.is_file():
        return
    mtime = datetime.fromtimestamp(HISTORY_FILE.stat().st_mtime)
    if mtime.date() == date.today():
        return
    rotated = HISTORY_FILE.with_name(f"{HISTORY_FILE.name}.{mtime.date().isoformat()}")
    HISTORY_FILE.rename(rotated)


def _prune_old() -> None:
    cutoff = date.today() - timedelta(days=KEEP_DAYS)
    for path in LOG_DIR.glob(f"{HISTORY_FILE.name}.*"):
        try:
            day = date.fromisoformat(path.suffix.lstrip("."))
        except ValueError:
            continue
        if day < cutoff:
            path.unlink(missing_ok=True)


def append(record: dict) -> None:
    _rotate_if_needed()
    _prune_old()
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_file(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _all_records() -> list[dict]:
    """Records from rotated files (older) + the current file (today).

    History rotates by date at midnight, so the current file alone would
    only ever show today's runs — merge the rotated files back in.
    """
    records: list[dict] = []
    for path in sorted(LOG_DIR.glob(f"{HISTORY_FILE.name}.*")):
        records.extend(_read_file(path))
    records.extend(_read_file(HISTORY_FILE))
    return records


def load(
    limit: int = LOAD_LIMIT,
    offset: int = 0,
    query: str | None = None,
) -> tuple[list[dict], int]:
    """Return ``(records, total)`` newest-first across all history files.

    Newest-first by ``started_at``; records without a timestamp fall back
    to their append order (index tiebreak), which is chronological.
    """
    records: list[dict] = []
    for rec in _all_records():
        if query and query.lower() not in json.dumps(rec, ensure_ascii=False).lower():
            continue
        records.append(rec)
    indexed = sorted(
        enumerate(records),
        key=lambda t: (t[1].get("started_at", ""), t[0]),
        reverse=True,
    )
    ordered = [rec for _, rec in indexed]
    return ordered[offset : offset + limit], len(ordered)
