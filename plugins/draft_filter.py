"""
Draft Filter Hook

Filters out non-blog pages with `draft: true` in frontmatter during production
builds, while keeping them visible during local dev (`MKDOCS_INCLUDE_DRAFTS=true mkdocs serve`).

Blog posts under the blog_dir (e.g., notes/posts/) are already handled by the
blog plugin's built-in draft support — this hook only targets regular pages.

Usage in mkdocs.yml:
  hooks:
    - plugins/draft_filter.py

To mark any regular page as draft, add to frontmatter:
  ---
  title: My WIP Page
  draft: true
  ---
"""

import logging
import os
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.frontmatter import has_draft_flag

log = logging.getLogger("mkdocs.hooks.draft_filter")

# Default blog directory (Material for MkDocs blog plugin default)
_DEFAULT_BLOG_DIR = "notes/posts"


def _has_draft_frontmatter(abs_path: str) -> bool:
    """Check if a file has `draft: true` in its YAML frontmatter (first 2KB)."""
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            head = f.read(2048)
    except (IOError, OSError) as e:
        log.warning("Cannot read %s: %s", abs_path, e)
        return False
    return has_draft_flag(head)


def _get_blog_dir(config) -> str:
    """Read blog_dir from blog plugin config, falling back to default."""
    try:
        blog_plugin = config["plugins"].get("blog")
        if blog_plugin is not None and hasattr(blog_plugin, "config"):
            return blog_plugin.config.get("blog_dir", _DEFAULT_BLOG_DIR)
    except Exception:
        pass
    return _DEFAULT_BLOG_DIR


def on_files(files, config, **kwargs):
    """Remove draft pages unless MKDOCS_INCLUDE_DRAFTS env var is set."""
    include_drafts = os.environ.get("MKDOCS_INCLUDE_DRAFTS", "").lower() in ("true", "1", "yes")

    if include_drafts:
        log.info("Draft mode enabled — keeping draft pages visible")
        return files

    log.info("Draft mode disabled — draft pages will be excluded")

    blog_dir = _get_blog_dir(config)

    to_remove = []
    for file in files:
        if not file.is_documentation_page():
            continue
        # Skip blog posts — blog plugin handles its own draft logic
        if file.src_path.startswith(blog_dir):
            continue
        if _has_draft_frontmatter(file.abs_src_path):
            to_remove.append(file)

    for file in to_remove:
        log.info("Excluding draft: %s", file.src_path)
        files.remove(file)

    return files
