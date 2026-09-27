"""Upload the locally cached film & TV covers to the bucket (developer step).

The flow the archive is built around (design §5):

1. ``poe sync-film-tv`` fetches posters from Douban and **caches them locally**
   under ``docs/assets/bucket/film-tv/covers/<douban_id>/`` (git-ignored) — the
   sync never talks to the bucket, and it never needs R2 credentials;
2. **the developer uploads** with this script (dry-run by default, ``--confirm``
   to actually transfer) — credentials stay in the local rclone config;
3. ``poe film-tv-check --check-remote`` verifies that every referenced cover now
   exists on the bucket (and lists orphans).

To keep the baked-in cover URLs working, the remote layout mirrors the local one:
``<remote_prefix>/covers/<douban_id>/NN.webp``, i.e. the archive-root-relative
``covers/…`` key is appended to ``remote_prefix`` on both sides. Uploads are
**copy** only: nothing on the bucket is ever deleted (use ``poe bucket-sync pull``
for the mirror, which does delete locally).

Usage::

    uv run poe film-tv-upload-covers                 # dry-run: what would upload
    uv run poe film-tv-upload-covers --confirm       # upload everything pending
    uv run poe film-tv-upload-covers --limit 200     # batch (≈ 200 files)
    uv run poe film-tv-upload-covers --only 1292052  # one subject's covers
    uv run poe film-tv-upload-covers --only shawshank-redemption
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import _rclone_path, resolve_remote  # noqa: E402
from scripts.sync_film_tv import SyncError, load_config  # noqa: E402
from shared.bucket import find_mapping  # noqa: E402
from shared.env import load_env_files  # noqa: E402
from shared.film_tv_store import NON_YEAR_FILES, read_entries  # noqa: E402
from shared.mkdocs_yaml import load_extra  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LIMIT = 15
#: archive-root-relative directory the cover keys live in
COVERS_DIR = "covers"


class UploadError(RuntimeError):
    """Precondition failure (config / rclone / paths)."""


def load_paths() -> tuple[Path, dict]:
    """Local cover root (``docs/<local_prefix>``) + the film-tv bucket mapping."""
    try:
        cover_root = load_config().cover_dir
    except SyncError as exc:
        raise UploadError(str(exc)) from exc
    # uploads never build a URL, so a mapping without `base_url` is still valid
    mapping = find_mapping(
        load_extra("bucket", label="film-tv-upload-covers"),
        "film-tv",
        require_base_url=False,
    )
    if mapping is None:
        raise UploadError("mkdocs.yml has no `film-tv` bucket mapping")
    return cover_root, mapping


def referenced_covers() -> dict[str, str]:
    """``cover key → subject id`` for every cover the archive references."""
    config = load_config()
    referenced: dict[str, str] = {}
    for path in sorted(config.data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        for entry in read_entries(path):
            keys = [*(entry.machine.get("covers") or []), entry.user.get("cover")]
            for key in keys:
                if key:
                    referenced[str(key)] = entry.id
    return referenced


def collect_pending(cover_root: Path, referenced: dict[str, str], *, only: str) -> list[Path]:
    """Local cover files that belong to the archive (optionally one subject)."""
    subject_filter = None
    if only:
        subject_filter = only if only.isdigit() else slug_to_id(only)
        if subject_filter is None:
            raise UploadError(f"--only {only!r}: no stored record matches that slug")
    files: list[Path] = []
    for key, subject_id in sorted(referenced.items()):
        if subject_filter and subject_id != subject_filter:
            continue
        path = cover_root / key
        if path.is_file():
            files.append(path)
    return files


def slug_to_id(slug: str) -> str | None:
    config = load_config()
    for path in sorted(config.data_dir.glob("*.yml")):
        if path.name in NON_YEAR_FILES:
            continue
        for entry in read_entries(path):
            if entry.machine.get("slug") == slug:
                return entry.id
    return None


def run_rclone(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def remote_listing(remote_path: str) -> set[str] | None:
    """Files already on the bucket (relative keys), or ``None`` when unrunnable."""
    result = run_rclone(["rclone", "lsf", "-R", "--files-only", remote_path])
    if result.returncode != 0:
        print(f"  (rclone lsf failed: {result.stderr.strip()[:160]})", file=sys.stderr)
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="film-tv-upload-covers",
        description="Upload locally cached film & TV covers to the bucket (dry-run by default)",
    )
    parser.add_argument("--confirm", action="store_true", help="actually upload")
    parser.add_argument("--limit", type=int, default=0, help="upload at most N files (0 = all)")
    parser.add_argument("--only", default="", help="one subject: a Douban id or a slug")
    parser.add_argument("--remote", help="rclone remote name (default: auto-detected)")
    args = parser.parse_args()

    load_env_files()
    if shutil.which("rclone") is None:
        raise SystemExit("film-tv-upload-covers: rclone not found (brew install rclone)")

    try:
        cover_root, mapping = load_paths()
    except UploadError as exc:
        raise SystemExit(f"film-tv-upload-covers: {exc}") from exc
    covers_dir = cover_root / COVERS_DIR

    referenced = referenced_covers()
    try:
        files = collect_pending(cover_root, referenced, only=args.only)
    except UploadError as exc:
        raise SystemExit(f"film-tv-upload-covers: {exc}") from exc
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("film-tv-upload-covers: nothing to upload (no cached covers referenced yet)")
        return 0

    remote = resolve_remote(args.remote, label="film-tv-upload-covers")
    # the cover keys are archive-root relative (`covers/<id>/NN.webp`), so the
    # remote target keeps that segment — `rclone copy <local>/covers <remote>` would
    # strip it and every baked-in cover URL would 404
    remote_covers = (
        _rclone_path(
            remote, str(mapping.get("bucket") or ""), str(mapping.get("remote_prefix") or "")
        ).rstrip("/")
        + f"/{COVERS_DIR}"
    )
    on_remote = remote_listing(remote_covers)
    if on_remote is None:
        raise SystemExit(
            "film-tv-upload-covers: cannot list the bucket — check rclone config / credentials"
        )

    pending = [path for path in files if str(path.relative_to(cover_root)) not in on_remote]
    already = len(files) - len(pending)
    total_mb = sum(path.stat().st_size for path in pending) / 1024 / 1024
    print(
        f"film-tv-upload-covers: {len(files)} referenced+cached file(s), "
        f"{already} already on the bucket, {len(pending)} to upload ({total_mb:.1f} MB)"
    )
    print(f"  local : {covers_dir.relative_to(REPO_ROOT)}/")
    print(f"  remote: {remote_covers}/")
    for path in pending[:SAMPLE_LIMIT]:
        print(f"    + {path.relative_to(cover_root)}")
    if len(pending) > SAMPLE_LIMIT:
        print(f"    … and {len(pending) - SAMPLE_LIMIT} more")

    if not pending:
        print("nothing to do")
        return 0
    if not args.confirm:
        print("\ndry-run: re-run with --confirm to upload")
        return 0

    # `rclone copy` is incremental and never deletes: re-runs are cheap and safe.
    code = subprocess.call(
        [
            "rclone",
            "copy",
            str(covers_dir),
            remote_covers,
            "--checksum",
            "--transfers",
            str(int(os.environ.get("RCLONE_TRANSFERS", "8"))),
            "--stats-one-line",
            "--stats",
            "10s",
        ]
    )
    if code != 0:
        return code
    print(
        "\nnext: `uv run poe film-tv-check --check-remote` to verify every referenced "
        "cover is on the bucket"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
