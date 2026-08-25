"""Integration tests for CLI scripts: create_post frontmatter and
optimize_images dry-run (no files mutated)."""

import base64
import subprocess
import sys
from pathlib import Path

import yaml

import shared.mkdocs_yaml
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


def test_optimize_images_quality_passthrough(tmp_path, monkeypatch):
    from PIL import Image

    src = tmp_path / "photo.png"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(src)
    captured: dict = {}

    class FakeImage:
        info = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getexif(self):
            # no Orientation tag → the transpose step is skipped entirely
            return Image.Exif()

        def save(self, dst, fmt, **kwargs):
            captured.update(kwargs)
            Path(dst).write_bytes(b"fake webp")

    monkeypatch.setattr(Image, "open", lambda _path: FakeImage())
    dst = optimize_images.convert_to_webp(src, quality=80)
    assert dst is not None and dst.exists()
    assert captured["quality"] == 80


def test_optimize_images_config_quality(tmp_path, monkeypatch):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text("extra:\n  optimize_images:\n    quality: 70\n", encoding="utf-8")
    monkeypatch.setattr(shared.mkdocs_yaml, "MKDOCS_YML", yml)
    assert optimize_images.config_quality() == 70

    # numeric string is accepted (e.g. a !ENV default)
    yml.write_text("extra:\n  optimize_images:\n    quality: '80'\n", encoding="utf-8")
    assert optimize_images.config_quality() == 80

    # bool (int subclass) and absent key -> None
    yml.write_text("extra:\n  optimize_images:\n    quality: true\n", encoding="utf-8")
    assert optimize_images.config_quality() is None
    yml.write_text("extra:\n  other: 1\n", encoding="utf-8")
    assert optimize_images.config_quality() is None


def test_optimize_images_resolve_quality():
    default = optimize_images.DEFAULT_WEBP_QUALITY
    assert optimize_images.resolve_quality(None, None) == default
    assert optimize_images.resolve_quality(None, 70) == 70
    assert optimize_images.resolve_quality(80, 70) == 80


def test_optimize_images_quality_clamped(tmp_path):
    from PIL import Image

    src = tmp_path / "photo.png"
    Image.new("RGB", (8, 8)).save(src)

    # out-of-range values clamp to the valid range instead of raising
    assert optimize_images._clamp_quality(150) == 100
    assert optimize_images._clamp_quality(0) == 1
    assert optimize_images._clamp_quality(-5) == 1
    assert optimize_images._clamp_quality(80) == 80

    dst = optimize_images.convert_to_webp(src, quality=150)
    assert dst is not None and dst.exists()


def test_optimize_images_bakes_exif_orientation(tmp_path):
    """EXIF Orientation is baked into the WebP pixels (and the tag dropped),
    so viewers that ignore WebP orientation won't render the photo rotated;
    GPS (and other EXIF) survives the transpose."""
    from PIL import Image
    from PIL.TiffImagePlugin import IFDRational

    src = tmp_path / "sideways.jpg"
    im = Image.new("RGB", (400, 300), "red")  # stored wide
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW to display upright
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (IFDRational(31, 1), IFDRational(10, 1), IFDRational(0, 1))
    gps[3] = "E"
    gps[4] = (IFDRational(121, 1), IFDRational(28, 1), IFDRational(0, 1))
    im.save(src, exif=exif)

    dst = optimize_images.convert_to_webp(src)
    assert dst is not None and dst.exists()

    with Image.open(dst) as webp:
        # pixels physically transposed: 400x300 → 300x400
        assert webp.size == (300, 400)
        assert webp.getexif().get(0x0112) is None  # orientation tag dropped
        kept_gps = webp.getexif().get_ifd(0x8825)
        assert kept_gps is not None and 2 in kept_gps  # GPS preserved


def test_optimize_images_no_orientation_not_transposed(tmp_path):
    """Correctly-oriented / tagless images skip the transpose entirely (size
    unchanged) — exif_transpose would copy the whole image otherwise."""
    from PIL import Image

    src = tmp_path / "wide.png"
    Image.new("RGB", (400, 300), "red").save(src)
    dst = optimize_images.convert_to_webp(src)
    assert dst is not None and dst.exists()
    with Image.open(dst) as webp:
        assert webp.size == (400, 300)
        assert webp.getexif().get(0x0112) is None


def test_optimize_images_convert_to_custom_dst(tmp_path):
    """convert_to_webp(dst=...) targets a custom path (bucket-upload uses it
    to convert straight into the keyed staging file); the default still lands
    next to the source."""
    from PIL import Image

    src = tmp_path / "photo.png"
    Image.new("RGB", (8, 8)).save(src)

    custom = tmp_path / "nested" / "sub" / "photo.webp"
    custom.parent.mkdir(parents=True)
    result = optimize_images.convert_to_webp(src, dst=custom)
    assert result == custom and custom.exists()

    # default dst unchanged: src.with_suffix(".webp") next to the source
    default = optimize_images.convert_to_webp(src)
    assert default == src.with_suffix(".webp") and default.exists()


# --- create_moment EXIF ---


def test_exif_camera_date_extracts_make_model_datetime(tmp_path):
    from PIL import Image

    from scripts import create_moment

    src = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[0x010F] = "Apple"  # Make
    exif[0x0110] = "iPhone 15 Pro"  # Model
    exif[0x9003] = "2026:08:01 15:30:00"  # DateTimeOriginal
    Image.new("RGB", (32, 32), (200, 30, 30)).save(src, "JPEG", exif=exif)

    camera, photo_date = create_moment.exif_camera_date(src)
    assert camera == "Apple iPhone 15 Pro"
    assert photo_date == "2026-08-01 15:30"


def test_exif_camera_date_missing_fields(tmp_path):
    from PIL import Image

    from scripts import create_moment

    # no EXIF at all → both empty
    plain = tmp_path / "plain.jpg"
    Image.new("RGB", (16, 16)).save(plain, "JPEG")
    assert create_moment.exif_camera_date(plain) == ("", "")

    # model only → camera is just the model, no date
    model_only = tmp_path / "model.jpg"
    exif = Image.Exif()
    exif[0x0110] = "X-T5"  # Model
    Image.new("RGB", (16, 16)).save(model_only, "JPEG", exif=exif)
    camera, photo_date = create_moment.exif_camera_date(model_only)
    assert camera == "X-T5"
    assert photo_date == ""


def test_exif_camera_date_rejects_impossible_datetime(tmp_path):
    from PIL import Image

    from scripts import create_moment

    # corrupt EXIF date — must be dropped
    src = tmp_path / "bad.jpg"
    exif = Image.Exif()
    exif[0x9003] = "2026:99:99 99:99"
    Image.new("RGB", (16, 16)).save(src, "JPEG", exif=exif)
    assert create_moment.exif_camera_date(src) == ("", "")

    # day exceeds the month's real length (Feb 2026 has 28 days) — dropped too
    feb = tmp_path / "feb30.jpg"
    exif = Image.Exif()
    exif[0x9003] = "2026:02:30 10:00"
    Image.new("RGB", (16, 16)).save(feb, "JPEG", exif=exif)
    assert create_moment.exif_camera_date(feb) == ("", "")


# --- add_weight_week ---


_WEIGHT_YML = (
    "# Height: set once\n"
    "cm: 176\n\n"
    'start_date: "2026-07-27"\n\n'
    "# Display labels (i18n) — values use Chinese for the UI\n"
    "labels:\n"
    "  height: 身高\n\n"
    "# 7 days per week; use null for missed days\n"
    "weeks:\n"
    "  # Week 1 — Mon 2026-07-27\n"
    "  - days: [null, 82.35, 81.50, 82.90, 82.40, 82.40, 81.90]\n"
)


def _run_add_weight_week(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/add_weight_week.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )


def test_add_weight_week_appends_into_weeks_list(tmp_path):
    """New weeks must land inside `weeks:` (not before labels:), YAML stays valid."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(_WEIGHT_YML, encoding="utf-8")

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    # YAML valid, weeks list grew by exactly one
    assert len(data["weeks"]) == 2
    assert data["weeks"][1]["days"] == [None] * 7
    # Week 2 label computed from the anchor (2026-07-27 + 7 days)
    assert "# Week 2 — Mon 2026-08-03" in content

    # Regression: nothing inserted between start_date: and labels:
    head = content.split("labels:", 1)[0]
    assert "- days:" not in head


def test_add_weight_week_multiple(tmp_path):
    """Adding several weeks keeps numbering and YAML integrity."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(_WEIGHT_YML, encoding="utf-8")

    proc = _run_add_weight_week(tmp_path, "2")
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert len(data["weeks"]) == 3
    assert "# Week 2 — Mon 2026-08-03" in content
    assert "# Week 3 — Mon 2026-08-10" in content
    assert "- days:" not in content.split("labels:", 1)[0]


def test_add_weight_week_empty_weeks_key(tmp_path):
    """`weeks:` present but empty parses to None — must not crash, list gets filled."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(
        "# Height: set once\ncm: 176\n\n"
        'start_date: "2026-07-27"\n\n'
        "labels:\n  height: 身高\n\n"
        # no trailing newline after `weeks:` — entry must still start on its own line
        "weeks:",
        encoding="utf-8",
    )

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert len(data["weeks"]) == 1
    assert data["weeks"][0]["days"] == [None] * 7
    assert "weeks:\n  # Week 1 — Mon 2026-07-27" in content


def test_add_weight_week_no_weeks_key(tmp_path):
    """File without any weeks: key gets a fresh weeks: block appended at the end."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(
        '# Height: set once\ncm: 176\n\nstart_date: "2026-07-27"\n\nlabels:\n  height: 身高\n',
        encoding="utf-8",
    )

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert len(data["weeks"]) == 1
    assert "# Week 1 — Mon 2026-07-27" in content
    assert content.rstrip().endswith("- days: [null, null, null, null, null, null, null]")


def test_add_weight_week_corrupt_file_fails_cleanly(tmp_path):
    """Corrupt YAML fails with a clean message, not a raw traceback."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(
        'cm: 176\nstart_date: "2026-07-27"\n  - days: [null]\n',
        encoding="utf-8",
    )

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode != 0
    assert "invalid YAML" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_add_weight_week_weeks_key_first_line(tmp_path):
    """`weeks:` as the very first line must be found, not treated as missing."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text("weeks:\n", encoding="utf-8")

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert len(data["weeks"]) == 1
    assert "weeks:\n  # Week 1\n  - days:" in content


def test_add_weight_week_first_line_no_trailing_newline(tmp_path):
    """`weeks:` first line AND no trailing newline — entry still on its own line."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text("weeks:", encoding="utf-8")

    proc = _run_add_weight_week(tmp_path)
    assert proc.returncode == 0, proc.stderr

    content = data_file.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert len(data["weeks"]) == 1
    assert content.startswith("weeks:\n  # Week 1\n  - days:")


def test_add_weight_week_rejects_non_positive_count(tmp_path):
    """count < 1 must fail with a clear message, not silently no-op."""
    data_file = tmp_path / "docs" / "notes" / "health" / "data" / "weight.yml"
    data_file.parent.mkdir(parents=True)
    data_file.write_text(_WEIGHT_YML, encoding="utf-8")

    proc = _run_add_weight_week(tmp_path, "0")
    assert proc.returncode != 0
    assert "positive" in proc.stderr
