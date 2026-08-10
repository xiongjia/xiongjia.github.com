"""Bucket asset helpers — configurable rewrite of local asset paths to bucket URLs.

Design (see ``internal/bucket-design.md``):

- Large site files (mainly WebP images) live under ``docs/assets/bucket/``,
  git-ignored, uploaded to an R2/S3 bucket (via PicList / rclone).
- md files keep **local relative links** so VSCode preview renders the local
  copies; the build rewrites links whose path contains a configured prefix
  (``extra.bucket.mappings[].prefix``, e.g. ``assets/bucket/``) to the remote
  ``base_url`` (e.g. ``http://xxx.r2.dev/web-assets/img``).
- Switching buckets = changing ``base_url`` in mkdocs.yml, md untouched.

Env overrides for local testing (see ``poe server-bucket``):

- ``MKDOCS_BUCKET_ENABLED`` (true/1/yes) — force-enable the rewrite
- ``MKDOCS_BUCKET_BASE_URL`` — override every mapping's base_url
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit, urlunsplit

MKDOCS_BUCKET_ENABLED_ENV = "MKDOCS_BUCKET_ENABLED"
MKDOCS_BUCKET_BASE_URL_ENV = "MKDOCS_BUCKET_BASE_URL"

_ENABLED_VALUES = ("true", "1", "yes")


def is_enabled(bucket_cfg: dict | None) -> bool:
    """Whether the bucket rewrite is active.

    ``extra.bucket.enabled`` from mkdocs.yml; the ``MKDOCS_BUCKET_ENABLED`` env
    var overrides it (so ``poe server-bucket`` can force it on without editing
    mkdocs.yml, mirroring ``MKDOCS_INCLUDE_DRAFTS``).
    """
    env = os.environ.get(MKDOCS_BUCKET_ENABLED_ENV, "").lower()
    if env:
        return env in _ENABLED_VALUES
    if not bucket_cfg:
        return False
    return bool(bucket_cfg.get("enabled", False))


def _effective_base_url(base_url: str) -> str:
    """``MKDOCS_BUCKET_BASE_URL`` overrides every mapping's base_url (testing)."""
    env = os.environ.get(MKDOCS_BUCKET_BASE_URL_ENV, "").strip()
    return env or base_url


def load_mappings(bucket_cfg: dict | None) -> list[dict]:
    """Normalize ``extra.bucket.mappings`` into ``[{prefix, base_url}]``.

    ``prefix`` is normalized to a trailing-slash form (``assets/bucket/``);
    mappings without a usable prefix or base_url are dropped.
    """
    if not bucket_cfg:
        return []
    result: list[dict] = []
    for m in bucket_cfg.get("mappings") or []:
        prefix = str(m.get("prefix", "")).strip("/")
        # env override applies before the emptiness check, so a config with an
        # empty base_url still works under MKDOCS_BUCKET_BASE_URL (testing)
        base_url = _effective_base_url(str(m.get("base_url", "")).strip())
        if not prefix or not base_url:
            continue
        result.append({"prefix": f"{prefix}/", "base_url": base_url.rstrip("/")})
    return result


def rewrite_url(url: str, mappings: list[dict]) -> str:
    """Rewrite a link whose path contains a mapped prefix to ``{base_url}/{key}``.

    Only relative URLs (no scheme / netloc) are inspected; external links are
    left untouched. ``key`` is everything after the first matched prefix, so
    md-relative forms like ``../../assets/bucket/food.webp`` and site-root
    forms like ``/assets/bucket/food.webp`` both work. Query/anchor are kept.
    URLs that match no mapping are returned unchanged.
    """
    if not mappings or not url:
        return url
    scheme, netloc, path, query, anchor = urlsplit(url)
    if scheme or netloc:  # external / absolute URL — never rewrite
        return url
    for m in mappings:
        prefix = m["prefix"]
        idx = path.find(prefix)
        if idx == -1:
            continue
        # require a path boundary before the prefix (don't match myassets/bucket/)
        if idx > 0 and path[idx - 1] != "/":
            continue
        key = path[idx + len(prefix) :]
        if not key:
            continue
        new_path = f"{m['base_url']}/{key}"
        return urlunsplit(("", "", new_path, query, anchor))
    return url


_ATTR_PATTERN = re.compile(r'(src|href)=(["\'])([^"\']*)\2')


def rewrite_html(html: str, mappings: list[dict]) -> str:
    """Rewrite every src/href in an HTML fragment that matches a mapping.

    Used by the build hook (``on_page_content``) and by the moment plugin for
    its own rendered HTML (``moment.html``), which never passes through
    ``on_page_content``. Handles both double- and single-quoted attributes,
    preserving the original quote style. Returns the input unchanged when
    nothing matched.
    """
    if not mappings or not html:
        return html

    def _replace(match: re.Match) -> str:
        attr, quote, value = match.group(1), match.group(2), match.group(3)
        new_value = rewrite_url(value, mappings)
        if new_value == value:
            return match.group(0)
        return f"{attr}={quote}{new_value}{quote}"

    return _ATTR_PATTERN.sub(_replace, html)
