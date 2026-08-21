"""Upload images to the bucket as WebP with a configured rename rule.

The write-side counterpart of ``bucket-sync`` (which stays read-only):
converts PNG/JPG/JPEG to WebP (reusing ``optimize_images.convert_to_webp``),
renders an object key from a mkdocs.yml rule, stages the converted file in a
temp dir, uploads it through ``rclone copyto``, copies it into
``docs/assets/bucket/`` (git-ignored local copy for VSCode preview) and
deletes the temp file.

**Requires a read-write R2 token** in .env (Admin Read & Write, or Object
Read + Object Write + List Bucket) — the pull path only needs read. Update
the token and re-run ``poe rclone-config-init``.

Key rule (``extra.bucket.upload.rule`` in mkdocs.yml), default
``img/{Y}/{m}/{d}_{h}{i}{s}_{filename}``:

- ``img``           literal category directory inside the bucket
- ``{Y}``           year, 4 digits
- ``{m}`` ``{d}``   month / day, 2 digits
- ``{h}`` ``{i}`` ``{s}``  hour / minute / second, 2 digits (concatenated)
- ``{filename}``    original stem, lowercased, ASCII letters+digits only;
  spaces become ``_``, Chinese / punctuation are removed; empty result
  (pure Chinese / no ASCII alphanumerics) → ``fallback_name`` (default
  ``noname``)

The rendered rule is joined to the mapping's ``remote_prefix``, so with
``remote_prefix: data/img`` the object key is
``data/img/img/2026/08/16_101112_myphoto.webp``. A ``.webp`` suffix is
appended to the rendered rule automatically (unless the rule already ends in
one).

Temp dir: ``--tmp-dir`` > ``BUCKET_UPLOAD_TMP_DIR`` > ``extra.bucket.upload.tmp_dir``
> ``.bucket`` at the repo root (git-ignored). The temp file is deleted after a
successful upload and kept on failure (its path is printed so the upload can
be retried).

**Safety**: the script is **dry-run by default** — nothing is written or
uploaded unless ``--confirm`` is passed. Source files larger than
``extra.bucket.upload.max_size_mb`` (default 10 MB) fail immediately
(``--max-size-mb`` CLI / ``BUCKET_UPLOAD_MAX_SIZE_MB`` env override).

**R2 scoped tokens**: uploads pass ``--s3-no-check-bucket`` to rclone — R2
bucket-level ops (HeadBucket/CreateBucket) return 403 for scoped API tokens,
and without the flag rclone misreads that as "bucket missing" and tries to
CreateBucket (AccessDenied). With the flag it goes straight to PutObject.

Other parameters resolve like ``bucket-sync``: CLI arg > env (.env) >
mkdocs.yml. The rclone remote name is **auto-detected from ``rclone
listremotes``** (prefers ``r2``, else the single/first configured remote) —
``--remote`` CLI / ``BUCKET_SYNC_REMOTE`` env override it, stale override
values warn and fall back. CI never uploads.

Usage:
    uv run poe bucket-upload photo.png                  # dry-run preview only
    uv run poe bucket-upload photo.png --confirm        # actually upload
    uv run poe bucket-upload a.png b.jpg --quality 80 --confirm

Paths accept a leading ``~`` (expanded against $HOME) and spaces.
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.bucket_sync import _generic_mapping, _pick, resolve_remote
from scripts.optimize_images import (
    IMAGE_EXTENSIONS,
    _clamp_quality,
    config_quality,
    convert_to_webp,
    resolve_quality,
)
from shared.env import load_env_files
from shared.mkdocs_yaml import load_extra

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_RULE = "img/{Y}/{m}/{d}_{h}{i}{s}_{filename}"
DEFAULT_FALLBACK_NAME = "noname"
DEFAULT_TMP_DIR = ".bucket"
DEFAULT_MAX_SIZE_MB = 10

# upload-specific env keys; remote/bucket/prefixes reuse the BUCKET_SYNC_* envs
# (same settings as the pull path)
UPLOAD_RULE_ENV = "BUCKET_UPLOAD_RULE"
UPLOAD_FALLBACK_ENV = "BUCKET_UPLOAD_FALLBACK_NAME"
UPLOAD_TMP_DIR_ENV = "BUCKET_UPLOAD_TMP_DIR"
UPLOAD_MAX_SIZE_ENV = "BUCKET_UPLOAD_MAX_SIZE_MB"


def _bucket_config() -> dict:
    """Read ``extra.bucket`` from mkdocs.yml (empty dict when absent)."""
    return load_extra("bucket", label="bucket-upload")


def sanitize_filename(stem: str, fallback: str = DEFAULT_FALLBACK_NAME) -> str:
    """Sanitize an original filename stem for the key: lowercase, keep ASCII
    letters+digits, spaces become ``_``, everything else (Chinese,
    punctuation) is removed. Runs of whitespace collapse to a single ``_``;
    leading/trailing ``_`` are stripped.

    An empty result — pure Chinese or no ASCII alphanumerics at all — falls
    back to *fallback* (default ``noname``).
    """
    cleaned = re.sub(r"\s+", "_", stem.lower())
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned).strip("_")
    return cleaned or fallback


def render_rule(rule: str, now: datetime, filename: str) -> str:
    """Render the rename rule with the given timestamp and sanitized filename.

    Tokens: ``{Y}`` 4-digit year, ``{m}/{d}/{h}/{i}/{s}`` 2-digit
    month/day/hour/minute/second, ``{filename}`` the sanitized stem. Any other
    text in the rule (e.g. the ``img/`` category directory) is kept literally.
    """
    tokens = {
        "Y": f"{now.year:04d}",
        "m": f"{now.month:02d}",
        "d": f"{now.day:02d}",
        "h": f"{now.hour:02d}",
        "i": f"{now.minute:02d}",
        "s": f"{now.second:02d}",
    }
    rendered = rule
    for name, value in tokens.items():
        rendered = rendered.replace(f"{{{name}}}", value)
    return rendered.replace("{filename}", filename)


def _resolve_max_size_mb(cli: str | None, cfg_value: str) -> float:
    """Resolve the upload size limit in MB: ``--max-size-mb`` CLI > env > mkdocs.yml > 10.

    Non-numeric, non-finite (``inf``/``nan``) and non-positive values fall
    back to the default with a warning. Fractional MB are kept so the byte
    limit stays exact (e.g. ``0.5`` → 512 KiB).
    """
    raw = _pick(cli, UPLOAD_MAX_SIZE_ENV, cfg_value or str(DEFAULT_MAX_SIZE_MB))
    try:
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(raw)
    except (TypeError, ValueError):
        print(
            f"bucket-upload: WARNING invalid max_size_mb {raw!r} — using {DEFAULT_MAX_SIZE_MB}MB",
            file=sys.stderr,
        )
        value = float(DEFAULT_MAX_SIZE_MB)
    return value


def _unique_relative_path(rel: str, local_dir: Path) -> str:
    """Append ``-2``/``-3``… to the rendered relative path when the local
    target already exists (same-second uploads of the same filename).

    Only the local preview copy is consulted (no per-file remote check); if
    ``docs/assets/bucket/`` was wiped, a same-key upload overwrites the remote
    object instead — see internal/bucket-design.md → Known Limitations.
    """
    target = local_dir / rel
    if not target.exists():
        return rel
    p = Path(rel)
    stem, suffix = p.stem, p.suffix
    n = 2
    while (local_dir / p.parent / f"{stem}-{n}{suffix}").exists():
        n += 1
    return str(p.parent / f"{stem}-{n}{suffix}")


def _resolve_tmp_dir(raw: str | None) -> Path:
    """Repo-root-relative or absolute temp dir (default ``.bucket`` at repo root)."""
    raw = (raw or DEFAULT_TMP_DIR).strip()
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def _cleanup_tmp(tmp: Path) -> None:
    """Delete the staged WebP and prune now-empty parent dirs up to the repo
    root (or the first non-empty dir, for absolute tmp dirs outside it)."""
    tmp.unlink(missing_ok=True)
    parent = tmp.parent
    while parent != REPO_ROOT:
        try:
            parent.rmdir()  # only removes empty directories
        except OSError:
            break
        parent = parent.parent


def _run(cmd: list[str]) -> int:
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    # load git-ignored .env files (precedence: shell > .env.local > .env) so
    # R2 credentials / bucket overrides work from .env
    load_env_files()

    parser = argparse.ArgumentParser(
        prog="bucket-upload",
        description="Convert images to WebP, rename with a configured rule and "
        "upload to the bucket via rclone (needs a read-write R2 token in .env).",
    )
    parser.add_argument(
        "paths", nargs="+", metavar="IMAGE", help="one or more PNG/JPG/JPEG files to upload"
    )
    parser.add_argument(
        "--quality",
        type=int,
        metavar="1-100",
        help="WebP quality (default: extra.optimize_images.quality in mkdocs.yml, else 90)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually upload (without it the run is a dry-run preview — safe default)",
    )
    parser.add_argument(
        "--max-size-mb",
        metavar="MB",
        help=f"upload size limit per file in MB (default: extra.bucket.upload.max_size_mb, "
        f"else {DEFAULT_MAX_SIZE_MB}); larger files fail",
    )
    parser.add_argument(
        "--rule",
        help=f"key rename rule (default: extra.bucket.upload.rule, else {DEFAULT_RULE!r})",
    )
    parser.add_argument(
        "--fallback-name",
        help=f"filename when the stem has no ASCII alphanumerics (default: "
        f"extra.bucket.upload.fallback_name, else {DEFAULT_FALLBACK_NAME!r})",
    )
    parser.add_argument(
        "--tmp-dir",
        help=f"temp dir for the converted WebP before upload (default: "
        f"extra.bucket.upload.tmp_dir, else {DEFAULT_TMP_DIR!r} at repo root)",
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
        help="object prefix inside the bucket (default: first mapping's 'remote_prefix')",
    )
    args = parser.parse_args()

    if shutil.which("rclone") is None:
        raise SystemExit("bucket-upload: rclone not found — install it first (brew install rclone)")

    cfg = _bucket_config()
    # Image uploads target the most general mapping (assets/bucket/), not the
    # more specific running-data mapping (which is listed first for URL rewrite).
    mapping = _generic_mapping(cfg)  # raises SystemExit when no mappings
    upload_cfg = cfg.get("upload") or {}
    rule = _pick(args.rule, UPLOAD_RULE_ENV, str(upload_cfg.get("rule") or DEFAULT_RULE))
    fallback = _pick(
        args.fallback_name,
        UPLOAD_FALLBACK_ENV,
        str(upload_cfg.get("fallback_name") or DEFAULT_FALLBACK_NAME),
    )
    tmp_dir = _resolve_tmp_dir(
        _pick(args.tmp_dir, UPLOAD_TMP_DIR_ENV, str(upload_cfg.get("tmp_dir") or ""))
    )
    remote = resolve_remote(args.remote, label="bucket-upload")
    bucket = _pick(args.bucket, "BUCKET_SYNC_BUCKET", str(mapping.get("bucket") or ""))
    if not bucket:
        bucket = remote
        print(
            f"bucket-upload: WARNING bucket name fell back to remote name {remote!r} — "
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

    quality = _clamp_quality(resolve_quality(args.quality, config_quality()))
    max_size_mb = _resolve_max_size_mb(args.max_size_mb, str(upload_cfg.get("max_size_mb") or ""))
    max_bytes = int(max_size_mb * 1024 * 1024)
    dry_run = not args.confirm
    local_dir = REPO_ROOT / "docs" / prefix.strip("/")
    now = datetime.now()

    mode = " (dry-run)" if dry_run else ""
    print(
        f"bucket-upload: {len(args.paths)} image(s), rule={rule!r}, WebP quality={quality}, "
        f"max size={max_size_mb:g}MB{mode}"
    )

    failed = 0
    for raw in args.paths:
        src = Path(raw).expanduser()
        if not src.exists():
            print(f"  [WARN]  path not found: {raw}", file=sys.stderr)
            failed += 1
            continue
        if src.suffix.lower() not in IMAGE_EXTENSIONS:
            print(f"  [WARN]  unsupported image type: {src.suffix} ({raw})", file=sys.stderr)
            failed += 1
            continue
        if src.stat().st_size > max_bytes:
            print(
                f"  [WARN]  {raw}: {src.stat().st_size / 1e6:.1f}MB exceeds the "
                f"{max_size_mb:g}MB upload limit — skipped",
                file=sys.stderr,
            )
            failed += 1
            continue

        stem = sanitize_filename(src.stem, fallback)
        rendered = render_rule(rule, now, stem)
        if not rendered.lower().endswith(".webp"):
            rendered += ".webp"
        rel = _unique_relative_path(rendered, local_dir)
        key = f"{remote_prefix}/{rel}" if remote_prefix else rel
        link = f"{prefix.strip('/')}/{rel}" if prefix.strip("/") else rel

        tmp = tmp_dir / rel
        if not dry_run:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.unlink(missing_ok=True)  # stale temp from a failed upload — re-convert
        dst = convert_to_webp(src, dry_run=dry_run, quality=quality, dst=tmp)
        if dst is None:
            print(f"  [SKIP]  {src}: conversion failed", file=sys.stderr)
            failed += 1
            continue

        rpath = f"{remote}:{bucket}/{key}"
        if dry_run:
            print(f"  [DRY-RUN] rclone copyto {dst} {rpath}")
            print(f"  [DRY-RUN] local copy -> {local_dir / rel}")
        else:
            rc = _run(["rclone", "copyto", str(dst), rpath, "--s3-no-check-bucket", "--progress"])
            if rc != 0:
                print(
                    f"  [ERROR] upload failed (rclone rc={rc}) — temp file kept at {dst}",
                    file=sys.stderr,
                )
                failed += 1
                continue
            local_copy = local_dir / rel
            local_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, local_copy)
            _cleanup_tmp(dst)  # temp cleanup after successful upload

        print(f"  key:   {key}")
        print(f"  local: {local_dir / rel}")
        print(f"  link:  {link}   (prefix ../ to your page depth in md)")

    if failed:
        print(f"\nDone — {failed} image(s) failed", file=sys.stderr)
        return 1
    if dry_run:
        print("\nDone. Dry-run — nothing uploaded; re-run with --confirm to upload.")
        return 0
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
