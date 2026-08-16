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
staging is transient) — note: a moment staged but not yet run would pick up
the re-uploaded content, so run it before re-uploading a same-named file.
Stale files older than ``STALE_DAYS`` are pruned on each save.

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


def sanitize_name(name: str) -> str:
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
    cleaned = _FILENAME_SAFE.sub("_", raw)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)  # photo..png → photo.png
    p = Path(cleaned.strip("._"))
    if p.suffix.lower() not in _IMAGE_EXTS:
        raise ValueError(f"unsupported image type: {p.suffix or '(none)'} (png/jpg/jpeg/webp)")
    return f"{p.stem}{p.suffix.lower()}"


def prune_stale() -> None:
    """Delete staging files untouched for ``STALE_DAYS``.

    Uploads are transient: after a moment run the md references the bucket
    URL, not the staging file — leftover files would accumulate forever.
    Called by every staging write (browser uploads AND TG photo downloads),
    so a TG-only workload still prunes.
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


def _unique_in_batch(name: str, taken: set[str]) -> str:
    """Append ``-2``/``-3``… when *name* is already taken inside ONE batch.

    Two different files renamed to the same ``save_as`` (e.g. all "123")
    must BOTH survive the upload — a suffix keeps them apart. Cross-batch
    re-uploads still overwrite (staging is transient).
    """
    if name not in taken:
        return name
    p = Path(name)
    n = 2
    while f"{p.stem}-{n}{p.suffix}" in taken:
        n += 1
    return f"{p.stem}-{n}{p.suffix}"


def save_uploads(items: list[dict]) -> list[str]:
    """Decode base64 files into ``uploads/``; return absolute paths.

    Each file is saved under its sanitized name — ``save_as`` (optional,
    per file) overrides it: a ``save_as`` without an extension keeps the
    original file's extension (``123`` + ``xxxx_abc.png`` → ``123.png``).
    Same-name files inside one batch get a ``-2``/``-3``… suffix so nothing
    is lost; a re-upload of an existing name **overwrites** (staging is
    transient). Raises ``ValueError`` on any invalid/oversized file (the
    endpoint maps it to a 400). Nothing is written when a file fails, so a
    bad batch leaves no partial files behind.
    """
    if not items:
        return []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    prune_stale()
    # validate EVERYTHING first (error messages use the clean, pre-dedupe
    # name so the client recognizes its own file), then dedupe + write
    decoded: list[tuple[str, bytes]] = []
    for item in items:
        name = sanitize_name(str(item.get("name", "")))
        save_as = str(item.get("save_as") or "").strip()
        if save_as:
            # append the original extension BEFORE sanitizing — sanitize
            # enforces the extension whitelist and would reject a bare
            # ``123`` (no suffix) otherwise
            save_as = Path(save_as).name.strip().lower()
            if not Path(save_as).suffix:
                save_as += Path(name).suffix
            name = sanitize_name(save_as)
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
        decoded.append((name, raw))
    # same-name files inside one batch (original names or a shared save_as)
    # get -2/-3… so nothing is lost; cross-batch re-uploads still overwrite
    # (staging is transient)
    taken: set[str] = set()
    paths: list[str] = []
    for name, raw in decoded:
        final = _unique_in_batch(name, taken)
        taken.add(final)
        dest = UPLOAD_DIR / final
        dest.write_bytes(raw)
        paths.append(str(dest))
    return paths
