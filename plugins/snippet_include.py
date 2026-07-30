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

log = logging.getLogger("mkdocs.plugins.snippet_include")

_INCLUDE_PATTERN = re.compile(r"<!--\s*include:\s*(.+?)\s*-->")


def on_page_markdown(markdown, page, config, **kwargs):
    """Replace <!-- include: path --> markers with file content."""
    docs_dir = config["docs_dir"]

    def _replace(match):
        rel_path = match.group(1).strip()
        abs_path = os.path.normpath(os.path.join(docs_dir, rel_path))

        # Security: ensure the resolved path is within docs_dir
        # Append os.sep to prevent prefix matching attacks (e.g. /docs vs /docs-extra)
        docs_dir_norm = os.path.normpath(docs_dir) + os.sep
        if not abs_path.startswith(docs_dir_norm):
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

        with open(abs_path, encoding="utf-8") as f:
            content = f.read()

        log.debug("Included snippet: %s into %s", rel_path, page.file.src_uri)
        return content

    return _INCLUDE_PATTERN.sub(_replace, markdown)
