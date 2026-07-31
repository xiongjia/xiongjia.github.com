"""
Snippet Include Hook

Replaces HTML comment markers of the form:
    <!-- include: path/to/file.md -->

with the contents of the referenced file (relative to docs_dir).
This avoids pymdownx.snippets `--8<--` syntax which conflicts with mdformat.

Usage in mkdocs.yml:
  hooks:
    - plugins/snippet_include.py
"""

import logging
import os
import re
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.io import resolve_within, safe_read

log = logging.getLogger("mkdocs.plugins.snippet_include")

_INCLUDE_PATTERN = re.compile(r"<!--\s*include:\s*(.+?)\s*-->")


def on_page_markdown(markdown, page, config, **kwargs):
    """Replace <!-- include: path --> markers with file content."""
    docs_dir = config["docs_dir"]

    def _replace(match):
        rel_path = match.group(1).strip()
        abs_path = resolve_within(docs_dir, rel_path)
        if abs_path is None:
            log.warning(
                "Snippet include path '%s' resolved outside docs_dir, skipping.",
                rel_path,
            )
            return match.group(0)

        if not os.path.isfile(abs_path):
            log.warning(
                "Snippet include file not found: %s (resolved: %s)",
                rel_path,
                abs_path,
            )
            return match.group(0)

        content = safe_read(abs_path)
        if content is None:
            log.warning("Snippet include unreadable: %s", rel_path)
            return match.group(0)

        log.debug("Included snippet: %s into %s", rel_path, page.file.src_uri)
        return content

    return _INCLUDE_PATTERN.sub(_replace, markdown)
