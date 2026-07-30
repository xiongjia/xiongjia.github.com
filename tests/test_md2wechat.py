"""Smoke tests for md2wechat conversion against the sample fixture."""

from pathlib import Path

import scripts.md2wechat as md2wechat

SAMPLE = Path("scripts/md2wechat/sample.md")
SAMPLE_TEXT = SAMPLE.read_text(encoding="utf-8")


def test_convert_sample():
    """Conversion of sample.md returns expected elements."""
    html, body, warnings = md2wechat.convert_md_to_wechat(str(SAMPLE))

    assert isinstance(html, str)
    assert len(html) > 100
    assert "<!DOCTYPE html>" in html
    assert "<title>" in html
    assert "md2wechat" in html or "test" in html

    assert isinstance(body, str)
    assert len(body) > 50
    # Body should not contain full document wrappers
    assert "<!DOCTYPE" not in body
    assert "<html" not in body
    assert "<title>" not in body

    assert isinstance(warnings, list)
    assert len(warnings) > 0


def test_sample_contains_expected_sections():
    """Check that key markdown features are detected and produce output."""
    _, body, w = md2wechat.convert_md_to_wechat(str(SAMPLE))

    assert "Code block" in body or "screenshot" in body

    assert "📌" in body  # note
    assert "ℹ️" in body  # info
    assert "💡" in body  # tip
    assert "⚠️" in body  # warning
    assert "🚫" in body  # danger

    assert "✅" in body
    assert "⬜" in body

    assert any("Mermaid" in item for item in w)


def test_rejects_draft():
    """Draft articles should be rejected."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("---\ntitle: Draft\ndraft: true\n---\nContent")
        tmp = f.name

    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "scripts.md2wechat", tmp, "--preview-only"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    os.unlink(tmp)
    assert "draft" in (result.stdout + result.stderr).lower()
    assert result.returncode != 0
