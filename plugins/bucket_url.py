"""Bucket URL rewrite hook.

Rewrites image/link URLs whose path contains a configured bucket prefix
(``extra.bucket.mappings[].prefix``, e.g. ``assets/bucket/``) to the remote
``base_url`` during ``on_page_content`` (after markdown conversion, before
minify). Local relative links in md keep working in VSCode preview; the built
site points at the bucket.

Config (mkdocs.yml)::

    hooks:
      - plugins/bucket_url.py
    extra:
      bucket:
        enabled: true
        mappings:
          - prefix: assets/bucket/
            base_url: http://xxx.r2.dev/web-assets/img

Env overrides for local testing (see ``poe server-bucket``):

- ``MKDOCS_BUCKET_ENABLED`` (true/1/yes) — force-enable the rewrite
- ``MKDOCS_BUCKET_BASE_URL`` — override every mapping's base_url
"""

import logging
import sys
from pathlib import Path

# bootstrap repo root so `shared/` is importable regardless of how this runs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.bucket import is_enabled, load_mappings, rewrite_html
from shared.env import load_env_files

log = logging.getLogger("mkdocs.hooks.bucket_url")

# load git-ignored .env files (precedence: shell > .env.local > .env) before
# reading any env overrides below
load_env_files()


def on_page_content(html, page, config, files):
    """Replace matched bucket-prefix links with their remote base_url."""
    bucket_cfg = config.get("extra", {}).get("bucket", {})
    if not is_enabled(bucket_cfg):
        return html
    mappings = load_mappings(bucket_cfg)
    if not mappings:
        return html
    rewritten = rewrite_html(html, mappings)
    if rewritten != html:
        log.debug("bucket: rewrote links in %s", page.file.src_uri)
    return rewritten
