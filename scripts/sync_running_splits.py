"""Upload .running/splits.json to R2 bucket.

This script is the upload counterpart of ``sync_running.py``: the sync script
now fetches data directly from Garmin API (including splits + polyline) and
writes both ``running.yml`` and ``.running/splits.json``. This script only
uploads the splits file to R2.

Usage:
    uv run poe sync-running-splits              # dry-run
    uv run poe sync-running-splits --confirm    # actually upload
    SYNC_RUNNING_CONFIRM=true uv run poe sync-running-splits  # env var
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import _rclone_path, _run, resolve_remote
from shared.env import load_env_files
from shared.mkdocs_yaml import load_extra

CACHE_FILE = Path(__file__).resolve().parent.parent / ".running" / "splits.json"


def _resolve_mapping(cfg: dict) -> dict:
    for m in cfg.get("mappings") or []:
        if "running" in str(m.get("prefix", "")):
            return dict(m)
    raise SystemExit("sync-running-splits: no running mapping in extra.bucket.mappings")


def main() -> int:
    load_env_files()

    if not CACHE_FILE.is_file():
        print(f"Error: {CACHE_FILE} not found — run `poe sync-running` first", file=sys.stderr)
        return 1

    cfg = load_extra("bucket", label="sync-running-splits")
    running_cfg = cfg.get("running") or {}
    data_key = running_cfg.get("data_key", "splits.json")

    mapping = _resolve_mapping(cfg)
    remote = resolve_remote(None, label="sync-running-splits")
    bucket = mapping.get("bucket") or remote
    remote_prefix = mapping.get("remote_prefix", "")
    rpath = _rclone_path(remote, bucket, remote_prefix)

    confirm = "--confirm" in sys.argv or os.environ.get("SYNC_RUNNING_CONFIRM", "").lower() in (
        "1",
        "true",
    )

    cmd = [
        "rclone",
        "copyto",
        str(CACHE_FILE),
        f"{rpath}{data_key}",
        "--progress",
        "--verbose",
        "--s3-no-check-bucket",
    ]
    if not confirm:
        cmd.append("--dry-run")

    print(
        f"sync-running-splits: upload {CACHE_FILE} -> {rpath}{data_key}"
        + (" (dry-run)" if not confirm else "")
    )
    return _run(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
