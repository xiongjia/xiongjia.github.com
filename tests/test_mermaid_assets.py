"""Unit tests for mermaid_assets.on_post_page (pure HTML processing, no network).

The download path (on_pre_build) makes real HTTP requests and is intentionally
not covered here; see test_hooks.py for the original exclusion rationale.
"""

from bs4 import BeautifulSoup

import plugins.mermaid_assets as mermaid_assets

HTML_WITH_MERMAID = """<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"/><title>t</title></head>
  <body>
    <h1>hello</h1>
    <pre class="mermaid"><code>flowchart LR</code></pre>
    <script async="" src="assets/javascripts/mermaid.min.js"></script>
    <script>window.mermaidConfig = {default: {startOnLoad: false}};</script>
  </body>
</html>"""


def _find_script(soup, src_part):
    script = soup.find("script", src=lambda s: s and src_part in s)
    assert script is not None, f"expected a script tag with src containing {src_part!r}"
    return script


def _mermaid_script(soup):
    return _find_script(soup, "mermaid.min.js")


def test_on_post_page_adds_defer_and_moves_to_head():
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script.has_attr("defer")
    assert not script.has_attr("async")
    assert script.parent is soup.head


def test_on_post_page_returns_unchanged_without_mermaid_script():
    html = "<html><body><p>no diagram</p></body></html>"
    out = mermaid_assets.on_post_page(html, page=None, config={})
    assert out == html


def test_on_post_page_keeps_other_scripts_untouched():
    html = (
        "<html><head><title>t</title></head><body>"
        '<script src="assets/javascripts/other.js"></script>'
        '<script src="assets/javascripts/mermaid.min.js"></script>'
        "</body></html>"
    )
    out = mermaid_assets.on_post_page(html, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    other = _find_script(soup, "other.js")
    assert other.parent is soup.body
    mermaid = _mermaid_script(soup)
    assert mermaid.parent is soup.head


def test_on_post_page_without_head_keeps_script_in_body():
    """Graceful degradation: if the page has no <head>, the defer-only script
    stays in <body>. Defer ordering is independent of tag placement for the
    initial load (the CDN-failure fallback still carries the timing caveat
    documented in the hook)."""
    html = '<html><body><script src="assets/javascripts/mermaid.min.js"></script></body></html>'
    out = mermaid_assets.on_post_page(html, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script.has_attr("defer")
    assert not script.has_attr("async")
    assert script.parent is soup.body


def test_on_post_page_ignores_page_without_injected_script():
    """A page with pre.mermaid but no mermaid2-injected library script is left
    untouched (the hook only rewrites the tag mermaid2 appends)."""
    html = (
        "<html><head></head><body>"
        '<pre class="mermaid"><code>flowchart LR</code></pre>'
        "</body></html>"
    )
    out = mermaid_assets.on_post_page(html, page=None, config={})
    assert out == html


def test_cdn_primary_with_local_fallback_by_default():
    """CDN is on by default: script src points at the China CDN, keeps defer,
    and carries an onerror that falls back to the page-relative local copy;
    a preconnect hint for the CDN origin is added to <head>."""
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script["src"].startswith("https://registry.npmmirror.com/mermaid/")
    assert script["src"].endswith("/dist/mermaid.min.js")
    assert script.has_attr("defer")
    assert script["onerror"] == 'this.onerror=null;this.src="assets/javascripts/mermaid.min.js"'
    preconnect = soup.find("link", rel="preconnect")
    assert preconnect is not None
    assert preconnect["href"] == "https://registry.npmmirror.com"
    # preconnect must not displace <meta charset>
    charset_meta = soup.head.find("meta", charset=True)
    assert charset_meta is not None
    children = [c for c in soup.head.contents if getattr(c, "name", None)]
    assert children.index(charset_meta) < children.index(preconnect)


def test_on_post_page_is_idempotent():
    """Re-processing an already-rewritten output must not replace the local
    fallback with the CDN URL, nor duplicate the preconnect hint (guard
    against double invocation)."""
    once = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    twice = mermaid_assets.on_post_page(once, page=None, config={})
    soup = BeautifulSoup(twice, "html.parser")
    script = _mermaid_script(soup)
    assert script["onerror"] == 'this.onerror=null;this.src="assets/javascripts/mermaid.min.js"'
    assert len(soup.find_all("link", rel="preconnect")) == 1


def test_cdn_custom_template_substitutes_version(monkeypatch):
    """A custom MERMAID_CDN_URL template gets {version} substituted."""
    monkeypatch.setattr(
        mermaid_assets,
        "MERMAID_CDN_URL",
        "https://cdn.jsdelivr.net/npm/mermaid@{version}/dist/mermaid.min.js",
    )
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script["src"].startswith("https://cdn.jsdelivr.net/npm/mermaid@")
    assert script["src"].endswith("/dist/mermaid.min.js")
    preconnect = soup.find("link", rel="preconnect")
    assert preconnect is not None
    assert preconnect["href"] == "https://cdn.jsdelivr.net"


def test_cdn_disabled_keeps_pure_self_hosted(monkeypatch):
    """MERMAID_CDN_URL="" disables the CDN: script keeps the local src, no
    onerror, no preconnect (old behaviour)."""
    monkeypatch.setattr(mermaid_assets, "MERMAID_CDN_URL", "")
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script["src"] == "assets/javascripts/mermaid.min.js"
    assert not script.has_attr("onerror")
    assert soup.find("link", rel="preconnect") is None


def test_cdn_malformed_template_does_not_crash(monkeypatch):
    """A template with stray braces must not crash the build: the hook falls
    back to the raw template and the browser-side onerror fallback still
    applies (graceful degradation, same as on_pre_build's stub file)."""
    monkeypatch.setattr(mermaid_assets, "MERMAID_CDN_URL", "https://example.com/assets/a{b}.js")
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    # the src no longer contains "mermaid.min.js", so locate the script by its onerror
    script = soup.find("script", onerror=lambda v: v and "this.src=" in v)
    assert script is not None
    assert script["src"] == "https://example.com/assets/a{b}.js"
    assert script["onerror"] == 'this.onerror=null;this.src="assets/javascripts/mermaid.min.js"'
    preconnect = soup.find("link", rel="preconnect")
    assert preconnect["href"] == "https://example.com"


def test_cdn_scheme_less_template_gets_no_preconnect(monkeypatch):
    """A scheme-less template is kept as src (the onerror fallback still
    applies) but yields no preconnect — the origin is unusable."""
    monkeypatch.setattr(
        mermaid_assets,
        "MERMAID_CDN_URL",
        "cdn.example.com/mermaid/{version}/dist/mermaid.min.js",
    )
    out = mermaid_assets.on_post_page(HTML_WITH_MERMAID, page=None, config={})
    soup = BeautifulSoup(out, "html.parser")
    script = _mermaid_script(soup)
    assert script["src"].startswith("cdn.example.com/mermaid/")
    assert script["src"].endswith("/dist/mermaid.min.js")
    assert soup.find("link", rel="preconnect") is None
