"""Initialize the rclone R2 remote from .env (non-interactive).

Reads the R2 credentials from the git-ignored .env files (precedence:
shell > .env.local > .env; see shared/env.py and .env.example):

- ``R2_ACCOUNT_ID``      — Cloudflare account id (builds the default endpoint)
- ``R2_ACCESS_KEY_ID``   — R2 API token access key id (read-only is enough for
  ``bucket-sync pull``)
- ``R2_SECRET_ACCESS_KEY`` — R2 API token secret
- ``BUCKET_SYNC_REMOTE`` — remote name (default ``r2``, matching the
  ``bucket-sync`` script; ``R2_REMOTE`` accepted as an alias)
- ``R2_ENDPOINT``        — optional endpoint override (default derived from
  account id)

It then runs ``rclone config create`` (or ``config update`` when the remote
already exists) with ``provider=Cloudflare``. No secrets are printed.

**Proxy**: set ``RCLONE_HTTP_PROXY`` in .env (rclone's native env var for
``--http-proxy``) when R2 is only reachable through a proxy; the rclone
subprocess inherits it.

Usage:
    uv run poe rclone-config-init
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

R2_REMOTE_ENV = "R2_REMOTE"  # legacy alias, kept for compatibility
BUCKET_SYNC_REMOTE_ENV = "BUCKET_SYNC_REMOTE"  # canonical (shared with bucket-sync)
R2_ENDPOINT_ENV = "R2_ENDPOINT"
DEFAULT_REMOTE = "r2"

_REMOTE_ENV_KEYS = (BUCKET_SYNC_REMOTE_ENV, R2_REMOTE_ENV)


def _resolve_remote(cli_value: str | None) -> str:
    """Remote name: CLI arg > BUCKET_SYNC_REMOTE > R2_REMOTE (alias) > r2."""
    if cli_value:
        return cli_value
    for key in _REMOTE_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return DEFAULT_REMOTE


def _env_or_exit(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"rclone-config-init: missing {name} in .env "
            f"(see .env.example, R2 API token created in the R2 console)"
        )
    return value


def _existing_remotes() -> set[str]:
    out = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, check=False)
    return {line.strip().rstrip(":") for line in out.stdout.splitlines() if line.strip()}


def main() -> int:
    load_env_files()

    parser = argparse.ArgumentParser(
        prog="rclone-config-init",
        description="Non-interactively configure the rclone R2 remote from .env.",
    )
    parser.add_argument(
        "--remote", help=f"remote name (env {BUCKET_SYNC_REMOTE_ENV}, default {DEFAULT_REMOTE})"
    )
    parser.add_argument(
        "--endpoint",
        help=f"endpoint override (env {R2_ENDPOINT_ENV}; default derived from R2_ACCOUNT_ID)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-create the remote even if it already exists (default: update in place)",
    )
    parser.add_argument(
        "--verify-bucket",
        help="optional object-level verification: run `rclone lsf <remote>:<bucket>/` "
        "(object read-only tokens can't ListBuckets, so lsd would 403)",
    )
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        raise SystemExit(
            "rclone-config-init: rclone not found — install it first (brew install rclone)"
        )

    remote = _resolve_remote(args.remote)
    account_id = _env_or_exit("R2_ACCOUNT_ID")
    ak = _env_or_exit("R2_ACCESS_KEY_ID")
    sk = _env_or_exit("R2_SECRET_ACCESS_KEY")
    endpoint = (args.endpoint or os.environ.get(R2_ENDPOINT_ENV, "").strip()) or (
        f"https://{account_id}.r2.cloudflarestorage.com"
    )

    exists = remote in _existing_remotes()
    subcmd = "create" if (not exists or args.force) else "update"
    if exists and not args.force:
        print(f"rclone-config-init: remote {remote!r} exists — updating credentials/endpoint")
    else:
        print(f"rclone-config-init: creating remote {remote!r}")

    cmd = [
        "rclone",
        "config",
        subcmd,
        remote,
        "s3",
        "provider=Cloudflare",
        f"access_key_id={ak}",
        f"secret_access_key={sk}",
        f"endpoint={endpoint}",
    ]
    # never echo secrets — print a masked form only
    masked = [
        (v.split("=")[0] + "=***" if v.startswith(("access_key_id=", "secret_access_key=")) else v)
        for v in cmd
    ]
    print("+ " + " ".join(masked))
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc

    # verification is object-level only: object read-only tokens cannot
    # ListBuckets (`rclone lsd` 403s), so verify a concrete bucket instead
    if args.verify_bucket:
        bucket = args.verify_bucket.strip("/")
        print(f"rclone-config-init: verifying — rclone lsf {remote}:{bucket}/")
        return subprocess.call(["rclone", "lsf", f"{remote}:{bucket}/", "--max-depth", "1"])
    print(f"rclone-config-init: done — remote {remote!r} ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
