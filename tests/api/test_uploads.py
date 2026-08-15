"""Unit tests for api/uploads.py — base64 staging of console uploads.

No network / FastAPI involved; the router-level endpoint test lives in
test_bot_router.py. UPLOAD_DIR is patched to a tmp dir.
"""

from __future__ import annotations

import base64
import os
import time

import pytest

from api import uploads as up


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(up, "UPLOAD_DIR", tmp_path / "uploads")
    return tmp_path / "uploads"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def test_sanitize_name():
    assert up._sanitize_name("My Photo.JPG") == "my_photo.jpg"
    assert up._sanitize_name("IMG_2024.png") == "img_2024.png"
    assert up._sanitize_name("照片 café.jpg") == "caf_.jpg"  # non-ascii runs → _
    assert up._sanitize_name("../../evil.webp") == "evil.webp"  # path traversal
    with pytest.raises(ValueError, match="unsupported image type"):
        up._sanitize_name("")  # no name and no extension
    with pytest.raises(ValueError, match="unsupported image type"):
        up._sanitize_name("notes.txt")
    with pytest.raises(ValueError, match="unsupported image type"):
        up._sanitize_name("noext")


def test_save_uploads_basic(upload_dir):
    paths = up.save_uploads(
        [{"name": "photo.png", "data": _b64(b"PNGDATA")}, {"name": "a.jpg", "data": _b64(b"JPEG")}]
    )
    assert len(paths) == 2
    # no timestamp/uuid prefix — the file keeps the author's (sanitized) name
    assert paths[0] == str(upload_dir / "photo.png")
    assert paths[1] == str(upload_dir / "a.jpg")
    assert upload_dir.joinpath("photo.png").read_bytes() == b"PNGDATA"
    assert upload_dir.joinpath("a.jpg").read_bytes() == b"JPEG"


def test_save_uploads_overwrites_duplicate(upload_dir):
    # re-uploading the same name overwrites the staging file (it is
    # transient — the moment flow converts + uploads to R2 immediately)
    p1 = up.save_uploads([{"name": "photo.png", "data": _b64(b"OLD")}])[0]
    p2 = up.save_uploads([{"name": "photo.png", "data": _b64(b"NEW")}])[0]
    assert p1 == p2
    assert upload_dir.joinpath("photo.png").read_bytes() == b"NEW"
    assert list(upload_dir.iterdir()) == [upload_dir / "photo.png"]


def test_save_uploads_same_name_in_batch_collapses(upload_dir):
    # two same-name files inside ONE batch → a single path (last wins)
    paths = up.save_uploads(
        [{"name": "a.png", "data": _b64(b"OLD")}, {"name": "a.png", "data": _b64(b"NEW")}]
    )
    assert paths == [str(upload_dir / "a.png")]
    assert upload_dir.joinpath("a.png").read_bytes() == b"NEW"
    assert len(list(upload_dir.iterdir())) == 1


def test_save_uploads_prunes_stale(upload_dir, monkeypatch):
    # staging is transient: files untouched for STALE_DAYS are pruned on save
    monkeypatch.setattr(up, "STALE_DAYS", 30)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stale = upload_dir / "old.jpg"
    stale.write_bytes(b"old")
    old = time.time() - 31 * 86400
    os.utime(stale, (old, old))
    up.save_uploads([{"name": "new.png", "data": _b64(b"new")}])
    assert not stale.exists()
    assert upload_dir.joinpath("new.png").exists()
    # recent files survive
    recent = upload_dir / "recent.jpg"
    recent.write_bytes(b"recent")
    up.save_uploads([{"name": "new2.png", "data": _b64(b"new2")}])
    assert recent.exists()


def test_save_uploads_empty():
    assert up.save_uploads([]) == []


def test_save_uploads_invalid_base64(upload_dir):
    with pytest.raises(ValueError, match="invalid base64"):
        up.save_uploads([{"name": "x.png", "data": "!!!not-base64!!!"}])


def test_save_uploads_empty_file(upload_dir):
    with pytest.raises(ValueError, match="empty file"):
        up.save_uploads([{"name": "x.png", "data": ""}])


def test_save_uploads_size_limit(upload_dir, monkeypatch):
    monkeypatch.setattr(up, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ValueError, match="exceeds"):
        up.save_uploads([{"name": "big.png", "data": _b64(b"x" * 11)}])


def test_save_uploads_atomic_on_bad_batch(upload_dir):
    # a failing file in the batch must not leave the earlier one written
    with pytest.raises(ValueError, match="invalid base64"):
        up.save_uploads([{"name": "ok.png", "data": _b64(b"ok")}, {"name": "bad.png", "data": "!"}])
    assert list(upload_dir.iterdir()) == []
