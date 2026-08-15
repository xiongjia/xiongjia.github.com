"""Browser-upload staging for the console.

Files arrive as base64 JSON (no python-multipart dependency) and land in
``<BOT_API_LOG_DIR>/uploads/`` — git-ignored runtime data, the slot the
history module already reserves for upload staging. The console references
the returned absolute paths as ``--image`` values; create_moment reads them
via absolute host paths, so worktree runs work unchanged.

Files keep the **uploaded (sanitized) name — no timestamp/uuid prefix** —
so the image key stem stays the author's filename (create_moment sanitizes
it again for the bucket key). A re-upload of the same name **overwrites**
the staging file (the moment flow converts + uploads to R2 immediately, so
staging is transient) and stale files older than ``STALE_DAYS`` are pruned
on each save.

No auth by design (matches the rest of the API) — bind to a trusted network.
"""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path

from api.history import LOG_DIR

UPLOAD_DIR = LOG_DIR / "uploads"

# accepted image types (create_moment's own set, incl. .webp sources)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# decoded-size guard per file: bucket-upload's default limit is 10 MB; keep
# headroom while bounding the request body
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# staging is transient — prune upload files untouched for this long
STALE_DAYS = 30

_FILENAME_SAFE = re.compile(r"[^a-z0-9._-]+")


def _sanitize_name(name: str) -> str:
    """Basename → safe stem: lowercase, non-alnum chars → ``_``, keep ext.

    ``My Photo.JPG`` → ``my_photo.jpg``; the saved path stays space-free so
    it survives the bot spec format (which re-splits on whitespace). The
    extension must be one of ``create_moment``'s accepted image types.

    Deliberately NOT reusing ``bucket_upload.sanitize_filename``: that one
    normalizes a bucket key *stem* (falls back to ``noname`` when no ASCII
    alphanumerics), while this one must keep a usable local filename with
    its original extension — different contracts, keep them apart.
    """
    raw = Path(name).name.strip().lower() or "upload"
    p = Path(_FILENAME_SAFE.sub("_", raw).strip("._"))
    if p.suffix.lower() not in _IMAGE_EXTS:
        raise ValueError(f"unsupported image type: {p.suffix or '(none)'} (png/jpg/jpeg/webp)")
    return f"{p.stem}{p.suffix.lower()}"


def _prune_stale() -> None:
    """Delete staging files untouched for ``STALE_DAYS``.

    Uploads are transient: after a moment run the md references the bucket
    URL, not the staging file — leftover files would accumulate forever.
    """
    cutoff = time.time() - STALE_DAYS * 86400
    if not UPLOAD_DIR.is_dir():
        return
    for p in UPLOAD_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def save_uploads(items: list[dict]) -> list[str]:
    """Decode base64 files into ``uploads/``; return absolute paths.

    Each file is saved under its sanitized original name — a duplicate name
    **overwrites** the previous staging file, and two same-name files inside
    one batch collapse to a single path (last one wins). Raises
    ``ValueError`` on any invalid/oversized file (the endpoint maps it to a
    400). Nothing is written when a file fails, so a bad batch leaves no
    partial files behind.
    """
    if not items:
        return []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _prune_stale()
    decoded: dict[str, bytes] = {}
    for item in items:
        name = _sanitize_name(str(item.get("name", "")))
        try:
            raw = base64.b64decode(str(item.get("data", "")), validate=True)
        except Exception as exc:
            raise ValueError(f"{name}: invalid base64 data") from exc
        if not raw:
            raise ValueError(f"{name}: empty file")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError(
                f"{name}: {len(raw) / 1e6:.1f}MB exceeds the "
                f"{MAX_UPLOAD_BYTES / 1e6:.0f}MB upload limit"
            )
        decoded[name] = raw
    paths: list[str] = []
    for name, raw in decoded.items():
        dest = UPLOAD_DIR / name
        dest.write_bytes(raw)  # duplicate name → overwrite (staging is transient)
        paths.append(str(dest))
    return paths
