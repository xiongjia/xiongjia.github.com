"""Sync the bucket-managed asset dir from R2/S3 via rclone (thin wrapper).

Bucket-managed assets live under ``docs/assets/bucket/`` (git-ignored, local
copies kept for VSCode preview). Uploads are done with PicList; this script
only mirrors the bucket down to the local dir through rclone:

- ``pull`` — bucket -> local, ``rclone sync`` (single-direction mirror,
  **deletes local files not present in the bucket**). Defaults to a dry-run;
  pass ``--confirm`` to actually apply.

Read-only by design (matches the read-only R2 token): no push/upload path —
uploading is PicList's job. Defaults are read from ``extra.bucket`` in
mkdocs.yml (``remote_prefix``, first mapping's ``prefix``); the rclone remote
name is **auto-detected from ``rclone listremotes``** (prefers ``r2``, else
the single/first configured remote) — ``--remote`` CLI / ``BUCKET_SYNC_REMOTE``
env override it, stale override values warn and fall back.

**Incremental by default**: ``rclone sync`` compares size + checksum (S3 ETag
= MD5 for single-part uploads) and only transfers files that differ — a
second ``pull`` with no changes transfers nothing. ``--checksum`` (default
on) skips the modtime comparison, so files whose local mtimes differ from the
remote LastModified (e.g. manually dropped into ``docs/assets/bucket/`` then
uploaded via PicList) are NOT re-downloaded. Objects uploaded as multipart
have non-MD5 ETags and would always transfer under ``--checksum`` — pass
``--no-checksum`` (size + modtime comparison) for buckets with such objects.
``--fast-list`` (default on) collapses recursive listing into one API call,
which matters for buckets with many objects; ``--no-fast-list`` disables it.

**Proxy**: set ``RCLONE_HTTP_PROXY`` in .env (rclone's native env var for
``--http-proxy``) when R2 is only reachable through a proxy (e.g. mainland
China). load_env_files() merges it into the process env and the rclone
subprocess inherits it; standard ``HTTP(S)_PROXY`` also works.

rclone must be installed and the remote configured locally (credentials stay
in ``~/.config/rclone/`` — never committed; use a read-only token for
``pull``: Object Read + List Bucket).

Usage:
    uv run poe bucket-sync pull            # dry-run preview
    uv run poe bucket-sync pull --confirm  # apply (deletes local extras)
    uv run poe bucket-sync pull --remote b2 --prefix assets/files
    uv run poe bucket-sync pull --no-checksum --no-fast-list  # legacy mode
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.env import load_env_files
from shared.mkdocs_yaml import load_extra

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bucket_config() -> dict:
    """Read ``extra.bucket`` from mkdocs.yml (empty dict when absent)."""
    return load_extra("bucket", label="bucket-sync")


def _pick(cli: str | None, env_key: str, cfg_value: str) -> str:
    """Resolve a sync parameter: CLI arg > env var (from .env) > mkdocs.yml.

    mkdocs.yml ``extra.bucket`` is the committed source of truth for build
    settings (CI reads it); the rclone remote name is local-only (see
    ``DEFAULT_REMOTE`` / ``BUCKET_SYNC_REMOTE``) — CI never syncs.
    """
    if cli:
        return cli
    env = os.environ.get(env_key, "")
    if env:
        return env
    return cfg_value


def _first_mapping(cfg: dict) -> dict:
    mappings = cfg.get("mappings") or []
    if not mappings:
        raise SystemExit("bucket-sync: no mappings in extra.bucket")
    return dict(mappings[0])


DEFAULT_REMOTE = "r2"  # last-resort remote name when rclone has no remotes


def available_remotes() -> list[str]:
    """Configured rclone remote names (sorted; [] when none or rclone errors)."""
    try:
        out = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, check=False)
    except OSError:
        return []
    return sorted({line.strip().rstrip(":") for line in out.stdout.splitlines() if line.strip()})


def resolve_remote(cli: str | None, label: str = "bucket") -> str:
    """Pick the rclone remote: ``--remote`` CLI > ``BUCKET_SYNC_REMOTE`` env > auto-detect.

    Auto-detect prefers ``r2`` when configured, else the single available
    remote, else the first one; with several remotes and no explicit choice it
    warns (uploads must not silently go to the wrong account). An explicit
    (CLI/env) name that is not in ``rclone listremotes`` is warned about and
    ignored — a stale env value must not break uploads. With no remotes at
    all ``DEFAULT_REMOTE`` is used so the rclone call itself still reports
    the real error.
    """
    available = available_remotes()
    explicit = cli or os.environ.get("BUCKET_SYNC_REMOTE", "").strip()
    if explicit:
        if explicit in available:
            return explicit
        print(
            f"{label}: WARNING rclone remote {explicit!r} is not configured "
            f"(listremotes: {available or 'none'}) — auto-selecting instead",
            file=sys.stderr,
        )
    if "r2" in available:
        pick = "r2"
    elif available:
        pick = available[0]
    else:
        pick = ""
    if len(available) > 1 and not explicit:
        print(
            f"{label}: WARNING multiple rclone remotes {available} — using {pick!r}; "
            "set BUCKET_SYNC_REMOTE (env) or --remote (CLI) to pin",
            file=sys.stderr,
        )
    if pick:
        return pick
    print(
        f"{label}: WARNING no rclone remotes configured (rclone listremotes is empty)",
        file=sys.stderr,
    )
    return DEFAULT_REMOTE


def _rclone_path(remote: str, bucket: str, remote_prefix: str) -> str:
    """``r2:bucket/remote_prefix/`` — remote:path understood by rclone."""
    prefix = remote_prefix.strip("/")
    path = f"{remote}:{bucket}".rstrip("/")
    if prefix:
        path += f"/{prefix}"
    return path + "/"


def _local_dir(prefix: str) -> Path:
    """Local directory backing a prefix, relative to repo root."""
    local = REPO_ROOT / "docs" / prefix.strip("/")
    if not local.is_dir():
        print(
            f"bucket-sync: local dir {local} does not exist (create it or "
            "upload via PicList first)",
            file=sys.stderr,
        )
    return local


def _run(cmd: list[str]) -> int:
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    # load git-ignored .env files (precedence: shell > .env.local > .env) so
    # R2 credentials / bucket test overrides work from .env
    load_env_files()

    parser = argparse.ArgumentParser(
        prog="bucket-sync",
        description="Pull docs/assets/bucket/ from an R2/S3 bucket via rclone "
        "(read-only; uploads happen in PicList).",
    )
    parser.add_argument(
        "action",
        choices=("pull",),
        help="pull = bucket->local (rclone sync, deletes local extras, dry-run by default)",
    )
    parser.add_argument(
        "--remote",
        help="rclone remote name (default: auto-detected from `rclone listremotes`; "
        "BUCKET_SYNC_REMOTE env overrides, stale values fall back with a warning)",
    )
    parser.add_argument(
        "--bucket",
        help="bucket name (default: first mapping's 'bucket'; falls back to the "
        "remote name with a warning if unset)",
    )
    parser.add_argument(
        "--prefix",
        help="local prefix under docs/ (default: first mapping's 'prefix', e.g. assets/bucket/)",
    )
    parser.add_argument(
        "--remote-prefix",
        help="object subdirectory inside the bucket to sync (e.g. abc/123 = "
        "bucket://abc/123/**; only files under it are synced, other bucket "
        "directories are ignored). Default: first mapping's 'remote_prefix'",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="pull: actually apply (without it pull is a dry-run preview)",
    )
    parser.add_argument(
        "--checksum",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="compare size + checksum (S3 ETag = MD5 for single-part uploads) instead of "
        "size + modtime (default: on). Skips re-downloads when local mtimes differ from "
        "the remote LastModified; multipart-uploaded objects have non-MD5 ETags and "
        "always transfer under this mode — pass --no-checksum for those",
    )
    parser.add_argument(
        "--fast-list",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="one recursive listing instead of per-directory listings (default: on; "
        "much faster on S3/R2 with many objects; --no-fast-list disables)",
    )
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        raise SystemExit("bucket-sync: rclone not found — install it first (brew install rclone)")

    cfg = _bucket_config()
    mapping = _first_mapping(cfg)  # raises SystemExit when no mappings
    remote = resolve_remote(args.remote, label="bucket-sync")
    bucket = _pick(args.bucket, "BUCKET_SYNC_BUCKET", str(mapping.get("bucket") or ""))
    if not bucket:
        # falling back to the remote name is almost always wrong and silently
        # produces 403 AccessDenied against R2 — warn loudly instead
        bucket = remote
        print(
            f"bucket-sync: WARNING bucket name fell back to remote name {remote!r} — "
            "set BUCKET_SYNC_BUCKET (.env) or mappings[].bucket (mkdocs.yml) "
            "to the real bucket name (R2 console); a wrong bucket returns 403.",
            file=sys.stderr,
        )
    prefix = _pick(
        args.prefix,
        "BUCKET_SYNC_PREFIX",
        str(mapping.get("prefix") or "assets/bucket/"),
    )
    remote_prefix = _pick(
        args.remote_prefix, "BUCKET_SYNC_REMOTE_PREFIX", str(mapping.get("remote_prefix") or "")
    )

    local = _local_dir(prefix)
    rpath = _rclone_path(remote, bucket, remote_prefix)

    # read-only by design — only pull (rclone sync) exists
    dry_run = not args.confirm
    cmd = [
        "rclone",
        "sync",
        rpath,
        str(local),
        "--progress",
        "--verbose",
    ]
    if args.checksum:
        cmd.append("--checksum")
    if args.fast_list:
        cmd.append("--fast-list")
    if dry_run:
        cmd.append("--dry-run")
    print(f"bucket-sync: pull {rpath} -> {local}" + (" (dry-run)" if dry_run else ""))
    return _run(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
