"""File I/O and path helpers shared by MkDocs hooks."""

import os
from pathlib import Path


def safe_read(path: str | Path, *, limit: int | None = None) -> str | None:
    """Read a UTF-8 file; returns ``None`` on IOError/UnicodeDecodeError.

    ``limit`` reads at most that many characters (used by fast scans).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(limit) if limit else f.read()
    except (IOError, OSError, UnicodeDecodeError):
        return None


def resolve_within(base_dir: str, rel_path: str) -> str | None:
    """Resolve ``rel_path`` under ``base_dir``; ``None`` if it escapes.

    Prevents path traversal: the resolved path must stay inside ``base_dir``
    (the trailing separator guards against prefix attacks like
    ``/docs`` vs ``/docs-extra``).
    """
    abs_path = os.path.normpath(os.path.join(base_dir, rel_path))
    base_norm = os.path.normpath(base_dir).rstrip(os.sep) + os.sep
    if not abs_path.startswith(base_norm):
        return None
    return abs_path
