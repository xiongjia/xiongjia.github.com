"""Search-index hygiene hook.

Keeps auto-generated markup out of the site search index. Material for MkDocs'
own search plugin (the implementation this theme resolves to) skips any element
that carries a ``data-search-exclude`` attribute, together with its whole
subtree — content stays visible on the page, it just never reaches the index.

Markdown-generated markup cannot carry HTML attributes in this stack
(``attr_list`` on admonition titles is not supported by `pymdownx.details`), so
the attribute is injected here at ``on_page_content``: that event runs after
Markdown conversion and *before* the search plugin indexes ``page.content`` in
``on_page_context``, so the plugin sees the marked HTML.

Marked here:

- Mermaid diagram source — ``flowchart LR``, ``n1 --> n2``, ``click n1
  "../other/"`` — is noise in search results. Both loader shapes are covered:
  ``<pre class="mermaid">`` (the mermaid2 *custom loader* this site uses) and
  ``<code class="mermaid">`` / ``<code class="language-mermaid">`` (mermaid2's
  standard path), so a config change cannot silently put diagram source back
  into the index.
- Backlinks cards — the ``Backlinks (N)`` / ``Links (N)`` admonitions from
  ``plugins/backlinks.py``. They are recognised by the ``<!-- search-exclude
  -->`` marker that module emits, **not** by their title: indexing them would
  make a page match every neighbour's title, and matching on a marker keeps
  hand-written admonitions (even ones titled ``Links (2)``) searchable.

Synced-data blocks (film & TV archive) are marked at their source instead, in
``shared/macros/film_tv_macros.py``.

Usage in mkdocs.yml::

    hooks:
      - plugins/search_exclude.py
    extra:
      search_exclude:
        enabled: true

The toggle only covers the two HTML-level rules above (the macro marking is
unconditional, since that data is never meant to be searchable).

The `<!-- search-exclude -->` marker stays in the built HTML on purpose: it is
inert for browsers and documents *in the output* why a block is not indexed
(minify keeps comments, so it shows up in view-source).
"""

import logging
import re
from collections.abc import MutableMapping

log = logging.getLogger("mkdocs.hooks.search_exclude")

#: One pattern per mermaid2 loader shape (custom `<pre class="mermaid">` and the
#: standard `<code class="[language-]mermaid">`); the negative lookahead keeps
#: the transform idempotent.
_MERMAID_PATTERNS = (
    re.compile(r'<pre class="mermaid"(?![^>]*data-search-exclude)'),
    re.compile(r'<code class="(?:language-)?mermaid"(?![^>]*data-search-exclude)'),
)
#: A `backlinks`/`links` card: an admonition opened by the marker comment that
#: `plugins/backlinks.py` emits as its first body line.
_MARKED_CARD = re.compile(
    r'<details class="info">(\s*<summary>[^<]*</summary>\s*<!--\s*search-exclude\s*-->)'
)


def _is_enabled(config) -> bool:
    """Read `extra.search_exclude.enabled` (default on); bad values fall back."""
    extra = config.get("extra", {})
    section = extra.get("search_exclude") if isinstance(extra, MutableMapping) else None
    if isinstance(section, MutableMapping):
        enabled = section.get("enabled", True)
        if isinstance(enabled, bool):
            return enabled
        log.warning("Invalid search_exclude.enabled %r, using default %r", enabled, True)
        return True
    if section is not None:
        log.warning("Invalid search_exclude config %r, ignoring it", section)
    return True


def exclude_from_search(html: str) -> str:
    """Add `data-search-exclude` to every auto-generated block in *html*."""
    for pattern in _MERMAID_PATTERNS:
        html = pattern.sub(lambda match: f"{match.group(0)} data-search-exclude", html)
    return _MARKED_CARD.sub(r'<details class="info" data-search-exclude>\1', html)


def on_page_content(html, page, config, files):
    """Mark auto-generated blocks so the search plugin skips them."""
    if not _is_enabled(config):
        return html
    marked = exclude_from_search(html)
    if marked != html:
        log.debug("search_exclude: marked generated blocks in %s", page.file.src_uri)
    return marked
