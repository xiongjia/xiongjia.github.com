"""Tests for scripts/enu.py (English Scraps inbox append)."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_REL = Path("notes/research/topics/english/scraps/inbox.md")


def _run_enu(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/enu.py"), *args, "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )


def _inbox(tmp_path: Path) -> Path:
    return tmp_path / INBOX_REL


def test_enu_add_creates_inbox_with_frontmatter(tmp_path):
    proc = _run_enu(tmp_path, "add", "cumbersome")
    assert proc.returncode == 0, proc.stderr

    content = _inbox(tmp_path).read_text(encoding="utf-8")
    assert "draft: true" in content
    assert "title: English Scraps Inbox" in content
    today = datetime.now().strftime("%Y-%m-%d")
    assert f"{today} cumbersome\n" in content


def test_enu_add_appends_multiple_lines(tmp_path):
    assert _run_enu(tmp_path, "add", "come up with").returncode == 0
    assert _run_enu(tmp_path, "add", "by and large").returncode == 0

    lines = _inbox(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    today = datetime.now().strftime("%Y-%m-%d")
    assert lines[-2] == f"{today} come up with"
    assert lines[-1] == f"{today} by and large"


def test_enu_add_custom_date(tmp_path):
    proc = _run_enu(tmp_path, "add", "cumbersome", "--date", "2026-08-08")
    assert proc.returncode == 0, proc.stderr
    assert "2026-08-08 cumbersome\n" in _inbox(tmp_path).read_text(encoding="utf-8")


def test_enu_add_invalid_date_errors(tmp_path):
    proc = _run_enu(tmp_path, "add", "cumbersome", "--date", "not-a-date")
    assert proc.returncode != 0
    assert "invalid --date" in proc.stderr


def test_enu_add_empty_content_errors(tmp_path):
    proc = _run_enu(tmp_path, "add", "   ")
    assert proc.returncode != 0
    assert "content must not be empty" in proc.stderr
    assert not _inbox(tmp_path).exists()


def test_enu_add_collapses_whitespace(tmp_path):
    proc = _run_enu(tmp_path, "add", "the   implementation   is   cumbersome")
    assert proc.returncode == 0, proc.stderr
    today = datetime.now().strftime("%Y-%m-%d")
    assert f"{today} the implementation is cumbersome\n" in _inbox(tmp_path).read_text(
        encoding="utf-8"
    )
