"""Tests for api.history JSONL persistence (tmp_path isolated)."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from api import history


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "LOG_DIR", tmp_path)
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / ".bot-api-history.jsonl")
    monkeypatch.setattr(history, "REPO_ROOT", tmp_path)
    return tmp_path


def test_append_and_load():
    history.append({"run_id": "a", "task": "weight", "status": "merged"})
    history.append({"run_id": "b", "task": "enu", "status": "submitted"})
    records, total = history.load()
    assert total == 2
    assert records[0]["run_id"] == "b"  # newest first
    assert records[1]["run_id"] == "a"


def test_load_pagination_and_search():
    for i in range(5):
        history.append({"run_id": str(i), "task": "weight", "status": "merged"})
    history.append({"run_id": "x", "task": "enu", "status": "submitted"})
    records, total = history.load(limit=2, offset=0, query="enu")
    assert total == 1
    assert records[0]["run_id"] == "x"
    records, total = history.load(limit=2, offset=1)
    assert len(records) == 2
    assert records[0]["run_id"] == "4"  # newest first, offset skips "x"
    assert total == 6


def test_resolve_dir_relative_and_absolute():
    assert history._resolve_dir("logs") == history.REPO_ROOT / "logs"
    assert history._resolve_dir("/tmp/x") == __import__("pathlib").Path("/tmp/x")
    assert history._resolve_dir("~/bot-logs").is_absolute()


def test_empty_file():
    records, total = history.load()
    assert records == [] and total == 0


def test_corrupt_line_skipped(tmp_path):
    (tmp_path / ".bot-api-history.jsonl").write_text("not json\n", encoding="utf-8")
    history.append({"run_id": "a", "task": "t", "status": "ok"})
    records, _ = history.load()
    assert len(records) == 1


def test_rotation_on_date_change(tmp_path):
    import os
    import time

    yesterday = date.today() - timedelta(days=1)
    f = history.HISTORY_FILE
    f.write_text(json.dumps({"run_id": "old"}) + "\n", encoding="utf-8")
    os.utime(f, (time.mktime(yesterday.timetuple()),) * 2)  # mtime = yesterday
    history.append({"run_id": "new", "task": "t", "status": "ok"})
    rotated = history.REPO_ROOT / f"{f.name}.{yesterday.isoformat()}"
    assert rotated.is_file()
    assert history.HISTORY_FILE.is_file()
    records, _ = history.load()
    # load merges the rotated file back in — old record included, newest first
    assert [r["run_id"] for r in records] == ["new", "old"]


def test_load_merges_rotated_files(tmp_path):
    old = date.today() - timedelta(days=1)
    rotated = tmp_path / f".bot-api-history.jsonl.{old.isoformat()}"
    rotated.write_text(
        json.dumps({"run_id": "old1", "started_at": "2026-08-13T10:00:00+08:00"}) + "\n",
        encoding="utf-8",
    )
    history.append(
        {"run_id": "new1", "started_at": "2026-08-14T10:00:00+08:00", "task": "t", "status": "ok"}
    )
    records, total = history.load()
    assert total == 2
    assert [r["run_id"] for r in records] == ["new1", "old1"]  # newest first


def test_prune_old(tmp_path):

    old = date.today() - timedelta(days=40)
    stale = tmp_path / f".bot-api-history.jsonl.{old.isoformat()}"
    stale.write_text("x\n", encoding="utf-8")
    recent = tmp_path / ".bot-api-history.jsonl.2026-08-01"
    recent.write_text("x\n", encoding="utf-8")
    history._prune_old()
    assert not stale.exists()
    assert recent.exists()
