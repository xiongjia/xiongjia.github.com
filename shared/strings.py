"""String utilities shared by scripts and plugins."""

import re

_RE_FILENAME_DATE = re.compile(r"^(\d{2})-(\d{4})(?:-(\S+))?$")  # 30-1430 or 30-1430-home-lab


def slugify_title(text: str, *, fallback: str = "post") -> str:
    """Build a URL-friendly slug from a title.

    Strips non-ASCII characters, lowercases, and replaces spaces with hyphens.
    If the result is empty (e.g. purely Chinese title), uses the fallback.
    """
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", " ", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    slug = slug.strip("-")
    return slug if slug else fallback


def slug_from_filename(stem: str) -> str:
    """Extract the slug part from a moment filename stem.

    ``"30-1430-home-lab"`` → ``"home-lab"``, ``"30-1430"`` → ``"1430"``.
    Returns the stem unchanged when it does not match the date pattern.
    """
    m = _RE_FILENAME_DATE.match(stem)
    if m and m.group(3):
        return m.group(3)  # e.g. "home-lab"
    if m and m.group(2):
        return m.group(2)  # e.g. "1430"
    return stem
