"""Unit tests for the search-index hygiene hook (plugins/search_exclude.py).

The hook only injects `data-search-exclude` attributes into rendered HTML; the
actual filtering is done by Material's search plugin (it skips marked subtrees
when building the index). These tests pin the transformations, the
"hand-written content stays searchable" guarantee, the coupling to
`backlinks.py`'s marker, and the film & TV macros, which mark their
synced-data output themselves.
"""

from types import SimpleNamespace

import markdown
import pathspec

import plugins.backlinks as backlinks
import plugins.search_exclude as search_exclude
from shared.mkdocs_yaml import load_document
from tests.test_film_tv_derive import load_macros


def test_mermaid_block_marked():
    html = '<p>text</p><pre class="mermaid"><code>flowchart LR\n  n1 --&gt; n2\n</code></pre>'
    out = search_exclude.exclude_from_search(html)
    assert '<pre class="mermaid" data-search-exclude>' in out
    # only the attribute is added — the diagram source stays in the page
    assert "flowchart LR" in out


def test_mermaid_standard_loader_shapes_marked():
    """mermaid2's non-custom-loader output must be covered too, not just <pre>."""
    for html in (
        '<pre><code class="mermaid">flowchart LR</code></pre>',
        '<pre><code class="language-mermaid">flowchart LR</code></pre>',
    ):
        assert "data-search-exclude" in search_exclude.exclude_from_search(html), html


def test_mermaid_block_idempotent():
    for html in (
        '<pre class="mermaid" data-search-exclude><code>x</code></pre>',
        '<code class="mermaid" data-search-exclude>x</code>',
    ):
        assert search_exclude.exclude_from_search(html) == html


def test_plain_code_block_untouched():
    html = '<pre><code>print("hi")</code></pre>'
    assert search_exclude.exclude_from_search(html) == html


def test_backlinks_card_marked():
    html = (
        '<details class="info">\n<summary>Backlinks (3)</summary>\n'
        "<!-- search-exclude -->\n<ul><li>a</li></ul>\n</details>"
    )
    out = search_exclude.exclude_from_search(html)
    assert '<details class="info" data-search-exclude>' in out
    assert "<summary>Backlinks (3)</summary>" in out


def test_links_card_marked():
    html = (
        '<details class="info">\n<summary>Links (2)</summary>\n'
        "<!-- search-exclude -->\n<ul><li>a</li></ul></details>"
    )
    assert "data-search-exclude" in search_exclude.exclude_from_search(html)


def test_handwritten_admonition_untouched():
    """A card without the marker stays searchable, however it is titled."""
    for html in (
        '<details class="info">\n<summary>Backlinks (3)</summary>\n<p>x</p></details>',
        '<details class="info">\n<summary>Links (2)</summary>\n<p>x</p></details>',
        '<details class="info">\n<summary>Notes (3)</summary>\n<p>x</p></details>',
    ):
        assert search_exclude.exclude_from_search(html) == html


def test_real_backlinks_card_is_marked():
    """Coupling test: the card `backlinks.py` actually emits carries the marker.

    A title change or a dropped marker in `_card()` must break this test instead
    of silently putting the cards back into the search index.
    """
    lines = backlinks._card("Backlinks (2)", ["- [A](a.md)", "- [B](b.md)"]).splitlines()
    assert lines[0] == '??? info "Backlinks (2)"'
    assert lines[1].strip() == backlinks._SEARCH_EXCLUDE_MARKER
    # the rendered shape Material produces for that admonition
    html = (
        '<details class="info">\n<summary>Backlinks (2)</summary>\n'
        f"{lines[1].strip()}\n<ul><li>A</li></ul>\n</details>"
    )
    assert "data-search-exclude" in search_exclude.exclude_from_search(html)


def test_card_renders_as_a_list_not_as_literal_text():
    """The marker must not swallow the card body into an HTML block.

    An HTML comment line directly followed by list lines makes Python-Markdown
    treat them as raw HTML text (the list degrades to "- a - b"), so `_card()`
    emits a blank line after the marker. Only a real render catches that.
    """
    converted = markdown.Markdown(extensions=["admonition", "pymdownx.details"]).convert(
        backlinks._card("Backlinks (2)", ["- [A](a.md)", "- [B](b.md)"])
    )
    assert "<summary>Backlinks (2)</summary>" in converted
    assert "<ul>" in converted and "<li>" in converted
    assert converted.index(backlinks._SEARCH_EXCLUDE_MARKER) < converted.index("<ul>")


def _fake_page():
    return SimpleNamespace(file=SimpleNamespace(src_uri="page.md"))


def test_on_page_content_enabled_by_default():
    html = '<pre class="mermaid"><code>x</code></pre>'
    assert "data-search-exclude" in search_exclude.on_page_content(
        html, _fake_page(), {"extra": {}}, None
    )


def test_on_page_content_disabled():
    html = '<pre class="mermaid"><code>x</code></pre>'
    config = {"extra": {"search_exclude": {"enabled": False}}}
    assert search_exclude.on_page_content(html, _fake_page(), config, None) == html


def test_on_page_content_bad_config_falls_back_to_enabled():
    html = '<pre class="mermaid"><code>x</code></pre>'
    for section in ("not-a-mapping", {"enabled": "yes"}, {"enabled": 1}):
        config = {"extra": {"search_exclude": section}}
        assert "data-search-exclude" in search_exclude.on_page_content(
            html, _fake_page(), config, None
        )


def test_film_tv_macros_mark_synced_data():
    """Every archive block is excluded from search (data present or not)."""
    macros = load_macros().macros
    for name in ("film_tv_page", "film_tv_stats", "film_tv_people", "film_tv_chart"):
        assert "data-search-exclude" in macros[name](), name
    assert "data-search-exclude" in macros["film_tv_note"](), "film_tv_note"


def test_fragments_are_excluded_from_the_build():
    """`exclude_docs` must keep `_`-prefixed fragments out of the built site.

    Without this rule a fragment becomes a real page: it shows up in the search
    index under its own URL (`notes/_index_content/`) with duplicated content.
    """
    document = load_document()
    assert document, "mkdocs.yml must be readable"
    spec = pathspec.GitIgnoreSpec.from_lines(document["exclude_docs"].splitlines())
    assert spec.match_file("notes/_index_content.md")
    assert spec.match_file("notes/health/_summary.md")
    # ... while real pages are untouched
    assert not spec.match_file("notes/link-graph.md")
