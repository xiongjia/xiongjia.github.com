"""Tests for `poe film-tv-upload-covers` — the developer's upload step.

No rclone and no bucket are involved: the subprocess boundary is faked, so these
tests pin the decisions (what counts as pending, filtering, dry-run safety) and
the remote layout (the archive-root-relative ``covers/…`` key must survive the
upload, otherwise every baked-in cover URL 404s).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import film_tv_upload_covers as up  # noqa: E402
from shared.film_tv_store import Entry, write_file  # noqa: E402

MAPPING = {
    "prefix": "assets/bucket/film-tv/",
    "name": "film-tv",
    "bucket": "web-assets",
    "remote_prefix": "data/film-tv",
    "base_url": "https://cdn.example.com/data/film-tv",
}


@dataclass
class FakeConfig:
    """Just the paths the upload script reads from `extra.film_tv`."""

    data_dir: Path
    cover_dir: Path


@pytest.fixture
def tree(tmp_path, monkeypatch) -> Path:
    """A minimal repo tree: one year file + a local cover mirror."""
    root = tmp_path
    data_dir = root / "docs" / "notes" / "film-tv" / "data"
    data_dir.mkdir(parents=True)
    cover_root = root / "docs" / "assets" / "bucket" / "film-tv"
    covers = cover_root / "covers"
    (covers / "1292052").mkdir(parents=True)
    (covers / "1292052" / "01.webp").write_bytes(b"a" * 100)
    (covers / "1292052" / "02.webp").write_bytes(b"b" * 200)
    (covers / "999").mkdir(parents=True)
    # orphan on disk (no record references it) — must never be uploaded
    (covers / "999" / "01.webp").write_bytes(b"c" * 300)

    write_file(
        data_dir / "movies-2009.yml",
        [
            Entry(
                machine={
                    "id": "1292052",
                    "title": "肖申克的救赎",
                    "type": "movie",
                    "slug": "shawshank-redemption",
                    "covers": ["covers/1292052/01.webp", "covers/1292052/02.webp"],
                    "marked_at": "2009-05-01",
                },
                user={},
                user_raw="",
                meta={"detail_synced_at": "2026-09-27"},
            ),
            # referenced but not cached yet (detail fetched, cover download failed)
            Entry(
                machine={
                    "id": "42",
                    "title": "无封面",
                    "type": "movie",
                    "slug": "no-cover",
                    "covers": ["covers/42/01.webp"],
                    "marked_at": "2009-06-01",
                },
                user={},
                user_raw="",
                meta={"detail_synced_at": "2026-09-27"},
            ),
            # hand-picked cover: referenced through `user.cover`, not `machine.covers`
            Entry(
                machine={
                    "id": "7",
                    "title": "手选封面",
                    "type": "movie",
                    "slug": "hand-picked",
                    "covers": ["covers/7/01.webp"],
                    "marked_at": "2009-07-01",
                },
                user={"cover": "covers/7/user-01.webp"},
                user_raw="",
                meta={"detail_synced_at": "2026-09-27"},
            ),
        ],
    )
    (covers / "7").mkdir(parents=True)
    (covers / "7" / "user-01.webp").write_bytes(b"d" * 50)

    monkeypatch.setattr(
        up, "load_config", lambda: FakeConfig(data_dir=data_dir, cover_dir=cover_root)
    )
    monkeypatch.setattr(up, "REPO_ROOT", root)
    monkeypatch.setattr(up, "load_env_files", lambda: None)
    return root


def cover_root(root: Path) -> Path:
    return root / "docs" / "assets" / "bucket" / "film-tv"


def covers_dir(root: Path) -> Path:
    return cover_root(root) / "covers"


def test_referenced_covers_maps_keys_to_subject_ids(tree):
    referenced = up.referenced_covers()
    assert referenced == {
        "covers/1292052/01.webp": "1292052",
        "covers/1292052/02.webp": "1292052",
        "covers/42/01.webp": "42",
        "covers/7/01.webp": "7",
        "covers/7/user-01.webp": "7",
    }


def test_collect_pending_only_returns_cached_and_referenced_files(tree):
    referenced = up.referenced_covers()

    files = up.collect_pending(cover_root(tree), referenced, only="")

    names = sorted(path.name for path in files)
    # the orphan under covers/999/ and the not-yet-cached covers/42/ are excluded
    assert names == ["01.webp", "02.webp", "user-01.webp"]
    assert all(path.is_file() for path in files)


def test_collect_pending_filters_by_id_and_slug(tree):
    referenced = up.referenced_covers()

    by_id = up.collect_pending(cover_root(tree), referenced, only="1292052")
    assert len(by_id) == 2
    # the slug resolves through the archive (users think in slugs, not ids)
    by_slug = up.collect_pending(cover_root(tree), referenced, only="shawshank-redemption")
    assert [path.name for path in by_slug] == ["01.webp", "02.webp"]
    # a subject with no cached cover yields nothing (not an error)
    assert up.collect_pending(cover_root(tree), referenced, only="no-cover") == []


def test_collect_pending_rejects_unknown_slug(tree):
    referenced = up.referenced_covers()
    with pytest.raises(up.UploadError, match="no stored record"):
        up.collect_pending(cover_root(tree), referenced, only="not-a-slug")


def test_slug_to_id(tree):
    assert up.slug_to_id("shawshank-redemption") == "1292052"
    assert up.slug_to_id("nope") is None


def test_main_dry_run_lists_pending_without_uploading(tree, monkeypatch, capsys):
    monkeypatch.setattr(up, "load_paths", lambda: (cover_root(tree), MAPPING))
    monkeypatch.setattr(up, "resolve_remote", lambda cli, label="x": "r2")
    monkeypatch.setattr(up, "remote_listing", lambda path: {"covers/1292052/02.webp"})
    calls: list[list[str]] = []
    monkeypatch.setattr(up.subprocess, "call", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr(
        sys,
        "argv",
        ["film-tv-upload-covers", "--only", "1292052"],
    )

    assert up.main() == 0

    out = capsys.readouterr().out
    assert "1 already on the bucket" in out
    assert "1 to upload" in out
    assert "+ covers/1292052/01.webp" in out
    assert "remote: r2:web-assets/data/film-tv/covers/" in out
    assert "dry-run: re-run with --confirm" in out
    assert calls == []  # nothing was uploaded


def test_main_confirm_uploads_with_copy_only(tree, monkeypatch, capsys):
    monkeypatch.setattr(up, "load_paths", lambda: (cover_root(tree), MAPPING))
    monkeypatch.setattr(up, "resolve_remote", lambda cli, label="x": "r2")
    monkeypatch.setattr(up, "remote_listing", lambda path: set())
    calls: list[list[str]] = []
    monkeypatch.setattr(up.subprocess, "call", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr(sys, "argv", ["film-tv-upload-covers", "--confirm", "--limit", "1"])

    assert up.main() == 0

    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "rclone"
    assert cmd[1] == "copy"  # never sync/delete on the bucket side
    assert cmd[2].endswith("film-tv/covers")
    # the remote target keeps the `covers/` segment: the key is archive-root
    # relative, and dropping it would 404 every cover URL
    assert cmd[3] == "r2:web-assets/data/film-tv/covers"
    assert "--checksum" in cmd
    assert "--limit" not in " ".join(cmd)  # the cap is applied to the file list, not rclone
    assert "film-tv-check --check-remote" in capsys.readouterr().out


def test_main_reports_nothing_to_upload(tree, monkeypatch, capsys):
    empty = cover_root(tree) / "empty"
    empty.mkdir()
    monkeypatch.setattr(up, "load_paths", lambda: (empty, MAPPING))
    monkeypatch.setattr(sys, "argv", ["film-tv-upload-covers"])

    assert up.main() == 0
    assert "nothing to upload" in capsys.readouterr().out


def test_main_refuses_when_the_bucket_cannot_be_listed(tree, monkeypatch):
    monkeypatch.setattr(up, "load_paths", lambda: (cover_root(tree), MAPPING))
    monkeypatch.setattr(up, "resolve_remote", lambda cli, label="x": "r2")
    monkeypatch.setattr(up, "remote_listing", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["film-tv-upload-covers", "--confirm"])

    with pytest.raises(SystemExit, match="cannot list the bucket"):
        up.main()
