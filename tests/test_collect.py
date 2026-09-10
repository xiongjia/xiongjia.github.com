"""Tests for scripts/collect.py (Collection Scraps inbox append)."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_REL = Path("notes/collection/scraps/inbox.md")


def _run_collect(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/collect.py"), *args, "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )


def _inbox(tmp_path: Path) -> Path:
    return tmp_path / INBOX_REL


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def test_add_creates_inbox_with_blank_line_separator(tmp_path):
    """A fresh inbox keeps a blank line between the header comment and entries."""
    proc = _run_collect(tmp_path, "add", "jsonrepair")
    assert proc.returncode == 0, proc.stderr

    content = _inbox(tmp_path).read_text(encoding="utf-8")
    assert "draft: true" in content
    assert "title: Collection Scraps Inbox" in content
    assert content.endswith(f"-->\n\n{_today()} jsonrepair\n")


def test_add_after_arch_keeps_blank_line_separator(tmp_path):
    """Adding to a header-only inbox (post-arch state) inserts the separator."""
    inbox = _inbox(tmp_path)
    inbox.parent.mkdir(parents=True)
    inbox.write_text(
        "---\ndraft: true\ntitle: Collection Scraps Inbox\n---\n\n<!--\n...\n-->\n",
        encoding="utf-8",
    )

    proc = _run_collect(tmp_path, "add", "yt-dlp", "--date", "2026-09-10")
    assert proc.returncode == 0, proc.stderr
    assert _inbox(tmp_path).read_text(encoding="utf-8").endswith("-->\n\n2026-09-10 yt-dlp\n")


def test_add_appends_entries_without_extra_blank_lines(tmp_path):
    assert _run_collect(tmp_path, "add", "first", "--date", "2026-09-08").returncode == 0
    assert _run_collect(tmp_path, "add", "second", "--date", "2026-09-09").returncode == 0

    lines = _inbox(tmp_path).read_text(encoding="utf-8").splitlines()
    assert lines[-3] == ""
    assert lines[-2] == "2026-09-08 first"
    assert lines[-1] == "2026-09-09 second"
