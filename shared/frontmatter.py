"""Frontmatter utilities shared by MkDocs hooks.

Two distinct APIs on purpose (see internal/plans/plugins-scripts-shared-module.md,
Open Questions #3):

- ``has_draft_flag`` — cheap string scan, no YAML parse. Used by ``on_files``
  hooks that walk every file; full YAML parsing would slow the build.
- ``parse_frontmatter`` — full YAML parse returning ``(meta, body)``. Used by
  plugins that need real fields (date, tags, …).

Both take raw text; file I/O stays with the caller.
"""

import yaml

_DRAFT_TRUE = ("true", "yes", "1")


def has_draft_flag(text: str) -> bool:
    """Fast check (no YAML parse): does the frontmatter declare ``draft: true``?

    Handles spacing variants (``draft : true``) and truthy values
    (``true`` / ``yes`` / ``1``). The first 2KB of a file is enough.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return False

    end = stripped.find("---", 3)
    if end == -1:
        return False

    frontmatter = stripped[3:end]
    for line in frontmatter.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() == "draft":
            if value.strip().lower() in _DRAFT_TRUE:
                return True
    return False


def parse_frontmatter(text: str) -> tuple[dict, str] | None:
    """Split and fully parse YAML frontmatter → ``(meta, body_without_frontmatter)``.

    Returns ``None`` when the text has no frontmatter, an unclosed delimiter,
    invalid YAML, or a non-dict / empty mapping. Callers that need to
    distinguish these cases inspect ``text`` features (``startswith("---")``,
    ``find("---", 3)``) around a ``None`` result.
    """
    if not text.startswith("---"):
        return None

    end = text.find("---", 3)
    if end == -1:
        return None

    fm_text = text[3:end]
    body = text[end + 3 :].strip()

    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return None

    if not fm or not isinstance(fm, dict):
        return None

    return fm, body
