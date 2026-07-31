"""Integration tests for CLI scripts: create_post frontmatter and
optimize_images dry-run (no files mutated)."""

import base64
import subprocess
import sys
from pathlib import Path

from scripts import optimize_images

REPO_ROOT = Path(__file__).resolve().parent.parent

# 1x1 red PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# --- create_post ---


def _run_create_post(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/create_post.py"), *args, "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )


def test_create_post_frontmatter_defaults(tmp_path):
    proc = _run_create_post(tmp_path, "Hello World")
    assert proc.returncode == 0, proc.stderr

    post_dir = tmp_path / "notes/posts/posts" / "bits"
    files = list(post_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")

    assert "title: Hello World" in content
    assert "draft: true" in content  # default is draft
    assert "slug: hello-world" in content
    assert "categories:" in content and "- bits" in content


def test_create_post_frontmatter_custom(tmp_path):
    proc = _run_create_post(
        tmp_path, "Custom Post", "--category", "dev", "--tags", "go,cli", "--no-draft"
    )
    assert proc.returncode == 0, proc.stderr

    post_dir = tmp_path / "notes/posts/posts" / "dev"
    files = list(post_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")

    assert "draft: true" not in content
    assert "- go" in content and "- cli" in content
    assert "categories:" in content and "- dev" in content


def test_create_post_backdate_filename_and_date(tmp_path):
    proc = _run_create_post(tmp_path, "Backdated", "--time", "yesterday 9am")
    assert proc.returncode == 0, proc.stderr

    import datetime

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    pattern = f"{yesterday.strftime('%Y%m%d')}-*.md"
    files = list((tmp_path / "notes/posts/posts" / "bits").glob(pattern))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert f"created: {yesterday.strftime('%Y-%m-%d')}" in content


def test_create_post_duplicate_rejected(tmp_path):
    assert _run_create_post(tmp_path, "Dup").returncode == 0
    proc = _run_create_post(tmp_path, "Dup")
    assert proc.returncode == 1
    assert "already exists" in proc.stderr


# --- optimize_images ---


def test_optimize_images_dry_run_no_mutation(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(_PNG)

    dst = optimize_images.convert_to_webp(src, dry_run=True)
    assert dst == src.with_suffix(".webp")
    assert not dst.exists()  # nothing written in dry-run


def test_optimize_images_converts_and_skips_existing(tmp_path):
    from PIL import Image

    src = tmp_path / "photo.png"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(src)

    dst = optimize_images.convert_to_webp(src)  # real conversion
    assert dst is not None and dst.exists()

    # second pass: webp exists and is not smaller → skip (None)
    assert optimize_images.convert_to_webp(src) is None


def test_optimize_images_update_md_refs_dry_run(tmp_path, monkeypatch):
    md = tmp_path / "post.md"
    md.write_text("![img](photo.png)", encoding="utf-8")
    src = tmp_path / "photo.png"
    src.write_bytes(_PNG)

    monkeypatch.setattr(optimize_images, "DOCS", tmp_path)  # scan tmp dir, not docs/

    optimize_images.update_md_references(src, src.with_suffix(".webp"), dry_run=True)
    assert "photo.webp" not in md.read_text(encoding="utf-8")  # unchanged

    optimize_images.update_md_references(src, src.with_suffix(".webp"))
    assert "photo.webp" in md.read_text(encoding="utf-8")
