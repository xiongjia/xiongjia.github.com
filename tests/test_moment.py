"""Unit tests for the Moment plugin foundation fixes (Phase 2).

Covers the three base bugs fixed before Phase 2 feature work:
  1. `on_post_build` early return skipped tag pages when moments <= posts_per_page
  2. templates hardcoded `/moment` instead of the config-driven path
  3. tag dirs used percent-encoding instead of literal names
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from xml.etree import ElementTree as ET

# the plugin package lives under plugins/ (the mkdocs hook loader puts it on
# sys.path at build time); tests must add it explicitly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins"))

from mkdocs_moment.models import Moment, PageType  # noqa: E402
from mkdocs_moment.plugin import (  # noqa: E402
    _HTMLMIN_OPTS,
    MomentPlugin,
    _first_text_line,
    _Page,
    _resolve_htmlmin_opts,
    _tag_segment,
    _valid_htmlmin_value,
)


def _moment(i: int, tags=("general",)) -> Moment:
    """Build a distinct moment with a deterministic date/time."""
    date = datetime(2026, 7, 30) + timedelta(minutes=i)
    stem = date.strftime("%d-%H%M")
    return Moment(
        id=f"2026-07-{stem}",
        date=date,
        slug=stem.split("-", 1)[1],
        source_path=f"moments/2026-07/{stem}.md",
        permalink=f"/moments/2026-07/{stem}/",
        content="content",
        tags=list(tags),
    )


def _make_plugin(moments, posts_per_page=20, **extra):
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments", "posts_per_page": posts_per_page, **extra})
    plugin._moments = moments
    plugin._labels = {}
    plugin._nav = None
    plugin._base_url = ""
    template = MagicMock()
    template.render.return_value = "<html>rendered</html>"
    env = MagicMock()
    env.get_template.return_value = template
    plugin._jinja_env = env
    return plugin, template


# ---------------------------------------------------------------------------
# _tag_segment (foundation fix #3)
# ---------------------------------------------------------------------------


def test_generated_page_hides_navigation_sidebar():
    """Generated pages (pagination/tag/archive/month) must not show the nav
    sidebar, matching the Timeline/Detail pages."""
    page = _Page("Title", "/moments/page/2/")
    assert page.title == "Title"
    assert page.url == "/moments/page/2/"
    assert page.meta == {"hide": ["navigation"]}


def test_tag_segment_keeps_utf8_literal():
    assert _tag_segment("中文") == "中文"
    assert _tag_segment("hello-world") == "hello-world"
    assert _tag_segment("general") == "general"


def test_tag_segment_replaces_path_unsafe_chars():
    assert _tag_segment("a/b") == "a_b"
    assert _tag_segment("foo#bar") == "foo_bar"
    assert _tag_segment("foo?bar") == "foo_bar"
    assert _tag_segment("50%") == "50_"
    assert _tag_segment("  spaced  ") == "spaced"


def test_tag_segment_rejects_dot_segments():
    # a literal "." / ".." / empty segment would escape the tag dir
    assert _tag_segment("..") == "_"
    assert _tag_segment(".") == "_"
    assert _tag_segment("") == "_"
    assert _tag_segment("   ") == "_"


# ---------------------------------------------------------------------------
# on_post_build (foundation fixes #1, #2, #3)
# ---------------------------------------------------------------------------


def test_tag_pages_generate_below_pagination_threshold(tmp_path):
    """Tags must still generate when moments <= posts_per_page (fix #1)."""
    moments = [
        _moment(0, tags=["general", "hello-world"]),
        _moment(1, tags=["general", "ai"]),
    ]
    plugin, template = _make_plugin(moments, posts_per_page=20)
    plugin.on_post_build({"site_dir": str(tmp_path)})

    for tag in ("general", "hello-world", "ai"):
        assert (tmp_path / "moments" / "tag" / tag / "index.html").exists()
    # single page → no pagination pages
    assert not (tmp_path / "moments" / "page" / "2" / "index.html").exists()
    # CSS is copied
    assert (tmp_path / "moments" / "moment.css").exists()

    # every generated page is rendered with the config-driven base + tag helper
    for _, kwargs in template.render.call_args_list:
        assert kwargs["moment_base"] == "/moments"
        assert kwargs["tag_segment"] is _tag_segment


def test_tag_pages_and_pagination_generate_above_threshold(tmp_path):
    moments = [_moment(i) for i in range(45)]  # 45 > 20 → 3 pages
    plugin, _ = _make_plugin(moments, posts_per_page=20)
    plugin.on_post_build({"site_dir": str(tmp_path)})

    assert (tmp_path / "moments" / "page" / "2" / "index.html").exists()
    assert (tmp_path / "moments" / "page" / "3" / "index.html").exists()
    assert not (tmp_path / "moments" / "page" / "4" / "index.html").exists()
    assert (tmp_path / "moments" / "tag" / "general" / "index.html").exists()


def test_dotdot_tag_does_not_overwrite_timeline(tmp_path):
    """A `..` tag must not resolve outside the tag dir (regression)."""
    moments = [_moment(0, tags=[".."])]
    plugin, _ = _make_plugin(moments)
    plugin.on_post_build({"site_dir": str(tmp_path)})

    assert (tmp_path / "moments" / "tag" / "_" / "index.html").exists()
    # the timeline page must not be clobbered by tag/../index.html
    assert not (tmp_path / "moments" / "index.html").exists()


def test_chinese_tag_uses_literal_dir(tmp_path):
    """Fix #3: tag dirs use the literal tag name, not percent-encoding."""
    moments = [_moment(0, tags=["中文"])]
    plugin, _ = _make_plugin(moments)
    plugin.on_post_build({"site_dir": str(tmp_path)})

    assert (tmp_path / "moments" / "tag" / "中文" / "index.html").exists()
    assert not (tmp_path / "moments" / "tag" / "%E4%B8%AD%E6%96%87" / "index.html").exists()


# ---------------------------------------------------------------------------
# Minification (generated pages + moment.css bypass the minify plugin)
# ---------------------------------------------------------------------------


def test_generated_pages_are_minified(tmp_path):
    """Generated pages (tag/archive/month) are minified: the minify plugin's
    on_post_build runs before this hook's, so these files never pass through
    it — the plugin must minify them itself. Inline <script> bodies keep
    their whitespace (htmlmin never rewrites script content), matching how
    the minify plugin treats regular pages."""
    moments = [_moment(0, tags=["general"])]
    plugin, template = _make_plugin(moments, posts_per_page=20)
    template.render.return_value = (
        "<html>\n\n<body>\n<p>hi</p>\n<script>\n  var x = 1;\n</script>\n</body>\n</html>"
    )
    plugin.on_post_build({"site_dir": str(tmp_path)})

    for rel in ("tag/general/index.html", "2026/07/index.html", "archive/index.html"):
        html = (tmp_path / "moments" / rel).read_text(encoding="utf-8")
        # htmlmin keeps <script> bodies verbatim (their whitespace is
        # preserved), so strip them before asserting everything else
        # collapsed to a single line
        non_script = re.sub(r"<script>.*?</script>", "", html, flags=re.S)
        assert "\n" not in non_script
        assert "<body> <p>hi</p> " in html
        assert "var x = 1;" in html  # script content untouched


def test_moment_css_is_minified(tmp_path):
    """moment.css is copied minified: the source keeps a leading comment and
    line breaks, the site copy must be a single compressed line."""
    moments = [_moment(0)]
    plugin, _ = _make_plugin(moments)
    plugin.on_post_build({"site_dir": str(tmp_path)})

    css = (tmp_path / "moments" / "moment.css").read_text(encoding="utf-8")
    assert "\n" not in css
    assert css.startswith(".moment-timeline{")  # leading comment stripped


def test_htmlmin_opts_passthrough(tmp_path):
    """extra.moment.htmlmin_opts overrides the mirrored minify defaults."""
    plugin, template = _make_plugin(
        [_moment(0, tags=["general"])], htmlmin_opts={"remove_comments": True}
    )
    template.render.return_value = "<html>\n\n<body>\n<!-- note -->\n<p>hi</p>\n\n</body>\n</html>"
    plugin.on_post_build({"site_dir": str(tmp_path)})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "note" not in html  # comment stripped via override
    assert "<body> <p>hi</p> </body>" in html


def test_htmlmin_opts_unknown_key_warns(tmp_path, caplog):
    """Unknown htmlmin_opts keys are ignored with a warning, not a crash."""
    plugin, template = _make_plugin(
        [_moment(0, tags=["general"])], htmlmin_opts={"bogus_option": True}
    )
    template.render.return_value = "<html>\n<body>\n<p>hi</p>\n</body>\n</html>"
    plugin.on_post_build({"site_dir": str(tmp_path)})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "<body> <p>hi</p> </body>" in html  # defaults still applied
    assert any("bogus_option" in r.message for r in caplog.records)


def test_htmlmin_opts_non_dict_ignored(tmp_path, caplog):
    """A non-dict htmlmin_opts must not crash the build."""
    plugin, template = _make_plugin([_moment(0, tags=["general"])], htmlmin_opts="oops")
    template.render.return_value = "<html>\n<body>\n<p>hi</p>\n</body>\n</html>"
    plugin.on_post_build({"site_dir": str(tmp_path)})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "<body> <p>hi</p> </body>" in html
    assert any("must be a dict" in r.message for r in caplog.records)


def test_htmlmin_opts_invalid_value_type_warns(tmp_path, caplog):
    """Ill-typed htmlmin_opts values (pre_tags as a string, numeric boolean)
    are ignored with a warning instead of being handed to htmlmin and
    breaking the build."""
    plugin, template = _make_plugin(
        [_moment(0, tags=["general"])],
        htmlmin_opts={"pre_tags": "pre", "remove_comments": 1},
    )
    template.render.return_value = "<html>\n<body>\n<p>hi</p>\n</body>\n</html>"
    plugin.on_post_build({"site_dir": str(tmp_path)})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "<body> <p>hi</p> </body>" in html  # defaults still applied
    assert any("invalid value type" in r.message for r in caplog.records)


def test_valid_htmlmin_value():
    """Type guard for htmlmin_opts overrides: bool flags need real booleans,
    pre_tags a container, pre_attr a string."""
    assert _valid_htmlmin_value("pre_tags", ("pre",)) is True
    assert _valid_htmlmin_value("pre_tags", ["pre"]) is True
    assert _valid_htmlmin_value("pre_tags", frozenset(["pre"])) is True
    assert _valid_htmlmin_value("pre_tags", "pre") is False
    assert _valid_htmlmin_value("pre_attr", "pre") is True
    assert _valid_htmlmin_value("pre_attr", 1) is False
    assert _valid_htmlmin_value("keep_pre", True) is True
    assert _valid_htmlmin_value("keep_pre", 1) is False


def test_minify_disabled_via_config(tmp_path):
    """extra.moment.minify: false leaves generated pages and CSS uncompressed."""
    plugin, template = _make_plugin([_moment(0, tags=["general"])], minify=False)
    template.render.return_value = "<html>\n\n<body>\n<p>hi</p>\n\n</body>\n</html>"
    plugin.on_post_build({"site_dir": str(tmp_path)})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert html == "<html>\n\n<body>\n<p>hi</p>\n\n</body>\n</html>"
    css = (tmp_path / "moments" / "moment.css").read_text(encoding="utf-8")
    assert css.startswith("/* moment.css")  # copied verbatim


def test_minify_follows_site_minify_plugin_config(tmp_path):
    """When the site minify plugin disables minify_html, moment pages follow;
    moment.css independently follows minify_css. The plugin is detected by
    its config keys, not its registration name (registered under an alias)."""
    plugin, template = _make_plugin([_moment(0, tags=["general"])])
    template.render.return_value = "<html>\n\n<body>\n<p>hi</p>\n\n</body>\n</html>"
    minify_plugin = SimpleNamespace(config={"minify_html": False, "minify_css": True})
    plugin.on_post_build({"site_dir": str(tmp_path), "plugins": {"aliased-minify": minify_plugin}})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "\n" in html  # minify_html off → page uncompressed
    css = (tmp_path / "moments" / "moment.css").read_text(encoding="utf-8")
    assert "\n" not in css  # minify_css on → css still compressed


def test_minify_follows_site_minify_css_off(tmp_path):
    """The inverse: minify_css off keeps moment.css verbatim while HTML stays
    minified — each asset kind follows its own site flag (alias-registered)."""
    plugin, template = _make_plugin([_moment(0, tags=["general"])])
    template.render.return_value = "<html>\n\n<body>\n<p>hi</p>\n\n</body>\n</html>"
    minify_plugin = SimpleNamespace(config={"minify_html": True, "minify_css": False})
    plugin.on_post_build({"site_dir": str(tmp_path), "plugins": {"aliased-minify": minify_plugin}})

    html = (tmp_path / "moments" / "tag" / "general" / "index.html").read_text(encoding="utf-8")
    assert "\n" not in html  # minify_html on → page compressed
    css = (tmp_path / "moments" / "moment.css").read_text(encoding="utf-8")
    assert css.startswith("/* moment.css")  # minify_css off → css verbatim


def test_resolve_htmlmin_opts_merge_and_defaults():
    """Overrides merge over the minify defaults; unknown keys are dropped."""
    opts = _resolve_htmlmin_opts({"remove_comments": True, "bogus_option": 1})
    assert opts["remove_comments"] is True
    assert "bogus_option" not in opts
    assert opts["keep_pre"] is False  # untouched default retained
    assert _resolve_htmlmin_opts(None) == _HTMLMIN_OPTS  # None → defaults


# ---------------------------------------------------------------------------
# RSS feed
# ---------------------------------------------------------------------------


def _rss_moment(mid, date, permalink, content, html, title=""):
    return Moment(
        id=mid,
        date=date,
        slug=mid.split("-")[-1],
        source_path=f"moments/2026-07/{mid}.md",
        permalink=permalink,
        content=content,
        html=html,
        title=title,
        tags=[],
    )


def test_build_rss_structure_and_title_fallback():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moments = [
        _rss_moment(
            "2026-07-30-2136",
            datetime(2026, 7, 30, 21, 36),
            "/moments/2026-07/30-2136/",
            "First text line\nmore",
            "<p>First text line</p>",
        ),
        # image-only moment → title falls back to the date
        _rss_moment(
            "2026-07-31-0900",
            datetime(2026, 7, 31, 9, 0),
            "/moments/2026-07/31-0900/",
            "![Screenshot](./deepseek.webp)",
            '<a class="glightbox" href="/moments/2026-07/deepseek.webp">'
            '<img src="/moments/2026-07/deepseek.webp" /></a>',
        ),
    ]
    xml = plugin._build_rss(moments, "https://example.com", "/nonexistent/docs")
    root = ET.fromstring(xml)

    assert root.tag == "rss"
    assert root.find("channel/link").text == "https://example.com/moments/"
    items = root.findall(".//item")
    assert [i.findtext("title") for i in items] == [
        "First text line",
        "2026-07-31 09:00",  # image-only → date fallback
    ]
    assert [i.findtext("link") for i in items] == [
        "https://example.com/moments/2026-07/30-2136/",
        "https://example.com/moments/2026-07/31-0900/",
    ]

    # description: site-absolute src/href rewritten to absolute URLs
    desc = items[1].findtext("description")
    assert 'src="https://example.com/moments/2026-07/deepseek.webp"' in desc
    assert 'href="https://example.com/moments/2026-07/deepseek.webp"' in desc
    # enclosure skipped: local image file does not exist
    assert root.findall(".//enclosure") == []


def test_build_rss_enclosure_with_local_image(tmp_path):
    img = tmp_path / "moments" / "2026-07" / "deepseek.webp"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(b"1234")

    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        '<img src="/moments/2026-07/deepseek.webp" />',
    )
    xml = plugin._build_rss([moment], "https://example.com", str(tmp_path))
    enc = ET.fromstring(xml).findall(".//enclosure")
    assert len(enc) == 1
    assert enc[0].get("url") == "https://example.com/moments/2026-07/deepseek.webp"
    assert enc[0].get("length") == "4"
    assert enc[0].get("type") == "image/webp"


def test_build_rss_escapes_description_html():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        "<p>a &amp; b <b>bold</b></p>",
    )
    xml = plugin._build_rss([moment], "https://example.com", "/none")
    # valid XML (parses) and raw HTML is escaped in the serialized feed
    assert "&lt;p&gt;" in xml
    # round-trip: reader unescapes back to the original HTML string
    desc = ET.fromstring(xml).findall(".//item")[0].findtext("description")
    assert desc == "<p>a &amp; b <b>bold</b></p>"


def test_on_post_build_generates_feed_xml(tmp_path):
    plugin, _ = _make_plugin([_moment(0), _moment(1)])
    plugin.on_post_build(
        {
            "site_dir": str(tmp_path),
            "docs_dir": str(tmp_path),
            "site_url": "https://example.com",
        }
    )
    feed = tmp_path / "moments" / "feed.xml"
    assert feed.exists()
    xml = feed.read_text(encoding="utf-8")
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<item>" in xml


def test_feed_disabled_via_config(tmp_path):
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments", "feed": False})
    plugin._moments = [_moment(0)]
    plugin._labels = {}
    plugin._nav = None
    plugin._base_url = ""
    template = MagicMock()
    template.render.return_value = "<html>rendered</html>"
    env = MagicMock()
    env.get_template.return_value = template
    plugin._jinja_env = env
    plugin.on_post_build(
        {
            "site_dir": str(tmp_path),
            "docs_dir": str(tmp_path),
            "site_url": "https://example.com",
        }
    )
    assert not (tmp_path / "moments" / "feed.xml").exists()


def test_on_page_context_injects_feed_url():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = [_moment(0)]
    plugin._labels = {}
    page = SimpleNamespace(meta={"moment_type": PageType.TIMELINE})
    config = SimpleNamespace(
        theme=SimpleNamespace(get_env=lambda: None), site_url="https://example.com"
    )
    context = {}
    plugin.on_page_context(context, page, config, None)
    assert context["feed_url"] == "https://example.com/moments/feed.xml"
    assert context["moment_base"] == "/moments"


def test_absolute_html_preserves_protocol_relative_url():
    plugin = MomentPlugin()
    html = '<img src="//cdn.example.com/x.webp" /><a href="/moments/2026-07/y.webp">link</a>'
    out = plugin._absolute_html(html, "https://example.com")
    assert 'src="//cdn.example.com/x.webp"' in out  # protocol-relative untouched
    assert 'href="https://example.com/moments/2026-07/y.webp"' in out


def test_first_text_line_handles_image_and_markers():
    # pure image line is skipped, next text line wins
    assert _first_text_line("![Screenshot](./x.webp)\nCaption text") == "Caption text"
    # image + text on the same line keeps the text
    assert _first_text_line("![img](./x.webp) note text") == "note text"
    # leading block markers and emphasis are stripped
    assert _first_text_line("> **bold** *em* text") == "bold em text"
    # empty content → no title
    assert _first_text_line("") == ""


def test_build_rss_pubdate_uses_fixed_timezone():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})  # default timezone Asia/Shanghai
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        "<p>x</p>",
    )
    xml = plugin._build_rss([moment], "https://example.com", "/none")
    root = ET.fromstring(xml)
    # reproducible regardless of the build host's local timezone
    assert root.find("channel/lastBuildDate").text == "Thu, 30 Jul 2026 21:36:00 +0800"
    assert root.findall(".//item")[0].findtext("pubDate") == "Thu, 30 Jul 2026 21:36:00 +0800"


def test_first_image_accepts_single_quotes():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        "<img src='/moments/2026-07/x.webp' />",
    )
    assert plugin._first_image(moment) == "/moments/2026-07/x.webp"


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def test_on_post_build_generates_archive_pages(tmp_path):
    moments = [
        _moment(0),  # 2026-07
        _moment(1),  # 2026-07
        _rss_moment(
            "2026-06-30-1200",
            datetime(2026, 6, 30, 12, 0),
            "/moments/2026-06/30-1200/",
            "june",
            "<p>june</p>",
        ),
    ]
    plugin, _ = _make_plugin(moments)
    plugin.on_post_build(
        {
            "site_dir": str(tmp_path),
            "docs_dir": str(tmp_path),
            "site_url": "https://example.com",
        }
    )

    assert (tmp_path / "moments" / "archive" / "index.html").exists()
    assert (tmp_path / "moments" / "2026" / "07" / "index.html").exists()
    assert (tmp_path / "moments" / "2026" / "06" / "index.html").exists()
    # slash-separated archive URLs do not collide with hyphenated detail dirs
    assert not (tmp_path / "moments" / "2026-07" / "archive").exists()


def test_on_page_context_injects_archive_url():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = [_moment(0)]
    plugin._labels = {}
    page = SimpleNamespace(meta={"moment_type": PageType.TIMELINE})
    config = SimpleNamespace(
        theme=SimpleNamespace(get_env=lambda: None), site_url="https://example.com"
    )
    context = {}
    plugin.on_page_context(context, page, config, None)
    assert context["archive_url"] == "/moments/archive/"


def test_on_page_context_skips_archive_url_when_no_moments():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = []
    plugin._labels = {}
    page = SimpleNamespace(meta={"moment_type": PageType.TIMELINE})
    config = SimpleNamespace(
        theme=SimpleNamespace(get_env=lambda: None), site_url="https://example.com"
    )
    context = {}
    plugin.on_page_context(context, page, config, None)
    assert "archive_url" not in context


def test_archive_groups_ordered_newest_first():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = [
        _moment(0),  # 2026-07
        _rss_moment(
            "2026-06-30-1200",
            datetime(2026, 6, 30, 12, 0),
            "/moments/2026-06/30-1200/",
            "june",
            "<p>june</p>",
        ),
        _rss_moment(
            "2025-12-31-2300",
            datetime(2025, 12, 31, 23, 0),
            "/moments/2025-12/31-2300/",
            "dec",
            "<p>dec</p>",
        ),
    ]
    groups = plugin._archive_groups()
    assert list(groups.keys()) == [(2026, 7), (2026, 6), (2025, 12)]


# ---------------------------------------------------------------------------
# Draft support
# ---------------------------------------------------------------------------


def _write_moment_file(tmp_path, name="30-1000.md", draft=False):
    month = tmp_path / "moments" / "2026-07"
    month.mkdir(parents=True, exist_ok=True)
    draft_line = "draft: true\n" if draft else ""
    (month / name).write_text(
        f"---\ndate: 2026-07-30 10:00\n{draft_line}tags:\n  - general\n---\n\ncontent\n",
        encoding="utf-8",
    )
    return month / name


def test_parse_moment_skips_drafts_by_default(tmp_path):
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    f = _write_moment_file(tmp_path, draft=True)
    rel = f.relative_to(tmp_path).as_posix()
    assert plugin._parse_moment(f, rel) is None


def test_parse_moment_keeps_drafts_when_include_drafts(tmp_path, monkeypatch):
    monkeypatch.setenv("MKDOCS_INCLUDE_DRAFTS", "true")
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    f = _write_moment_file(tmp_path, draft=True)
    rel = f.relative_to(tmp_path).as_posix()
    moment = plugin._parse_moment(f, rel)
    assert moment is not None
    assert moment.content == "content"


def test_on_files_excludes_draft_moments(tmp_path):
    _write_moment_file(tmp_path, "30-1000.md", draft=False)
    _write_moment_file(tmp_path, "30-1100.md", draft=True)
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = []
    plugin.on_files(SimpleNamespace(), {"docs_dir": str(tmp_path)})
    assert len(plugin._moments) == 1
    assert plugin._moments[0].slug == "1000"


def test_create_moment_draft_flag(tmp_path, monkeypatch, capsys):
    """create_moment.py --draft writes draft: true into the frontmatter."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["create_moment", "hello", "--draft"])
    from scripts import create_moment

    create_moment.main()
    capsys.readouterr()
    created = list((tmp_path / "docs" / "moments").rglob("*.md"))
    assert len(created) == 1
    assert "draft: true" in created[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Caption (custom markdown extension)
# ---------------------------------------------------------------------------


def _render_config():
    return {"markdown_extensions": [], "mdx_configs": {}}


def test_render_content_caption_figure():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    html = plugin._render_content(
        "![Alt](./x.webp)\n图注文字", _render_config(), "moments/2026-07/30-1000.md"
    )
    assert "<figure>" in html
    assert "<figcaption>图注文字</figcaption>" in html
    assert 'src="/moments/2026-07/x.webp"' in html


def test_render_content_no_figure_without_caption():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    # image is the last line → no caption
    html = plugin._render_content(
        "![Alt](./x.webp)", _render_config(), "moments/2026-07/30-1000.md"
    )
    assert "<figure>" not in html
    # next block is a list, not a caption
    html = plugin._render_content(
        "![Alt](./x.webp)\n\n- a\n- b", _render_config(), "moments/2026-07/30-1000.md"
    )
    assert "<figure>" not in html


def test_render_content_caption_glightbox_wrapped():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    html = plugin._render_content(
        "![Alt](./x.webp)\ncaption", _render_config(), "moments/2026-07/30-1000.md"
    )
    assert '<a class="glightbox" href="/moments/2026-07/x.webp">' in html
    assert "<figcaption>caption</figcaption>" in html


def test_render_content_multiple_captioned_images():
    """Each image + caption pair becomes a figure, not just the first one."""
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    html = plugin._render_content(
        "![A](./1.webp)\n图A\n\n![B](./2.webp)\n图B",
        _render_config(),
        "moments/2026-07/30-1000.md",
    )
    assert "<figcaption>图A</figcaption>" in html
    assert "<figcaption>图B</figcaption>" in html
    assert html.count("<figure>") == 2


# ---------------------------------------------------------------------------
# OpenGraph
# ---------------------------------------------------------------------------


def test_og_meta_title_and_description():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments", "timeline_description": "日常记录"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "Hello world\nmore",
        "<p>Hello world</p>",
    )
    meta = plugin._og_meta(
        moment, {"site_url": "https://example.com", "site_description": "site desc"}
    )
    assert meta["title"] == "Hello world"
    assert meta["description"] == "Hello world"
    assert meta["card"] == "summary"
    assert "image" not in meta  # no image → no og:image


def test_og_meta_with_image():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        '<img src="/moments/2026-07/x.webp" />',
    )
    meta = plugin._og_meta(moment, {"site_url": "https://example.com"})
    assert meta["image"] == "https://example.com/moments/2026-07/x.webp"
    assert meta["card"] == "summary_large_image"


def test_og_meta_remote_image_kept_as_is():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "x",
        '<img src="https://cdn.example.com/x.webp" />',
    )
    meta = plugin._og_meta(moment, {"site_url": "https://example.com"})
    # remote image is used as-is, not prefixed with site_url
    assert meta["image"] == "https://cdn.example.com/x.webp"
    assert meta["card"] == "summary_large_image"


def test_moment_title_falls_back_to_frontmatter_title():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "![Screenshot](./x.webp)",
        "<p>x</p>",
        title="My Title",
    )
    # image-only content → frontmatter title (middle of the fallback chain,
    # before the date fallback)
    assert plugin._moment_title(moment) == "My Title"


def test_og_meta_description_fallback():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments", "timeline_description": ""})
    moment = _rss_moment(
        "2026-07-30-2136",
        datetime(2026, 7, 30, 21, 36),
        "/moments/2026-07/30-2136/",
        "![Screenshot](./x.webp)",
        "<p>x</p>",
    )
    meta = plugin._og_meta(
        moment, {"site_url": "https://example.com", "site_description": "site desc"}
    )
    # image-only moment → no text line → site_description fallback
    assert meta["description"] == "site desc"


def test_on_page_context_detail_injects_og():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    plugin._moments = [_moment(0)]
    plugin._labels = {}
    page = SimpleNamespace(
        meta={"moment_type": PageType.MOMENT_DETAIL},
        file=SimpleNamespace(src_path="moments/2026-07/30-0000.md"),
    )
    config = SimpleNamespace(
        theme=SimpleNamespace(get_env=lambda: None), site_url="https://example.com"
    )
    context = {}
    plugin.on_page_context(context, page, config, None)
    assert context["og"]["title"] == "content"
    assert context["og"]["card"] == "summary"
    assert context["moment_base"] == "/moments"


# ---------------------------------------------------------------------------
# geo / map feature (extra.moment.map)
# ---------------------------------------------------------------------------


def test_gcj02_to_wgs84_conversion():
    """Ported GCJ-02 -> WGS-84 matches the verified vine value
    (Amap picker 121.48, 31.16 -> 121.475504, 31.161994)."""
    from shared.gcj02 import gcj02_to_wgs84

    lng, lat = gcj02_to_wgs84(121.48, 31.16)
    assert abs(lng - 121.475504) < 1e-5
    assert abs(lat - 31.161994) < 1e-5


def _geo_plugin(map_cfg=None):
    plugin = MomentPlugin()
    cfg = {
        "enabled": True,
        "default_region": "shanghai",
        "regions": {
            "shanghai": {"bbox": [120.8, 30.6, 122.2, 31.8], "center": [121.5, 31.2], "zoom": 12},
            "tokyo": {"bbox": [139.4, 35.4, 140.2, 35.9], "center": [139.8, 35.65], "zoom": 12},
        },
        "tag_emoji": {"film": "🎬", "food": "🍽️"},
    }
    if map_cfg is not None:
        cfg.update(map_cfg)
    plugin._load_config({"path": "moments", "map": cfg})
    return plugin


def _write_moment(tmp_path, name, *fm_lines):
    d = tmp_path / "moments" / "2026-08"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("---\n" + "\n".join(fm_lines) + "\n---\ncontent\n", encoding="utf-8")
    return p


def test_parse_moment_geo_wgs84(tmp_path):
    plugin = _geo_plugin()
    p = _write_moment(
        tmp_path,
        "01-1200.md",
        "date: 2026-08-01 12:00",
        "place: 徐汇滨江",
        "lng: 121.4602",
        "lat: 31.1850",
        "region: shanghai",
        "tags: [general, food]",
    )
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert m.has_geo
    assert m.lng == 121.4602
    assert m.lat == 31.1850
    assert m.crs == "wgs84"
    assert m.place == "徐汇滨江"
    assert m.region == "shanghai"
    assert m.emoji == "🍽️"  # food tag -> emoji


def test_parse_moment_gcj02_converts(tmp_path):
    plugin = _geo_plugin()
    p = _write_moment(
        tmp_path,
        "01-1200.md",
        "date: 2026-08-01 12:00",
        "lng: 121.48",
        "lat: 31.16",
        "crs: gcj02",
        "tags: [general]",
    )
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert m.has_geo
    assert abs(m.lng - 121.475504) < 1e-4
    assert abs(m.lat - 31.161994) < 1e-4
    assert m.crs == "gcj02"


def test_parse_moment_geo_pair_validation(tmp_path, caplog):
    plugin = _geo_plugin()
    p = _write_moment(tmp_path, "01-1200.md", "date: 2026-08-01 12:00", "lng: 121.46")
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert not m.has_geo
    assert any("must be a pair" in r.message for r in caplog.records)


def test_parse_moment_geo_out_of_range_ignored(tmp_path, caplog):
    plugin = _geo_plugin()
    p = _write_moment(tmp_path, "01-1200.md", "date: 2026-08-01 12:00", "lng: 500", "lat: 31.16")
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert not m.has_geo
    assert any("Out-of-range" in r.message for r in caplog.records)


def test_parse_moment_region_probe(tmp_path):
    plugin = _geo_plugin()
    sh = _write_moment(
        tmp_path, "01-1200.md", "date: 2026-08-01 12:00", "lng: 121.47", "lat: 31.23"
    )
    assert plugin._parse_moment(sh, "moments/2026-08/01-1200.md").region == "shanghai"

    tokyo = _write_moment(
        tmp_path, "02-1200.md", "date: 2026-08-02 12:00", "lng: 139.7", "lat: 35.68"
    )
    assert plugin._parse_moment(tokyo, "moments/2026-08/02-1200.md").region == "tokyo"


def test_parse_moment_map_disabled_ignores_geo(tmp_path):
    plugin = _geo_plugin({"enabled": False})
    p = _write_moment(
        tmp_path,
        "01-1200.md",
        "date: 2026-08-01 12:00",
        "lng: 121.47",
        "lat: 31.23",
        "tags: [film]",
    )
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert not m.has_geo
    assert m.emoji == ""
    assert m.region == ""


def test_load_config_map_defaults_disabled():
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    assert plugin.map_cfg["enabled"] is False
    assert plugin.map_cfg["regions"] == {}


def test_on_config_map_validation_missing_resources():
    from unittest.mock import MagicMock

    from mkdocs.exceptions import PluginError

    plugin = MomentPlugin()
    config = MagicMock()
    config.get.return_value = {
        "moment": {
            "path": "moments",
            "map": {
                "enabled": True,
                "widget_js": "https://x/widget.js",
                "pmtiles_prefix": "",  # missing required URL
                "glyphs_url": "https://x/{fontstack}/{range}.pbf",
                "default_region": "shanghai",
                "regions": {"shanghai": {"bbox": [120.8, 30.6, 122.2, 31.8]}},
            },
        }
    }
    try:
        plugin.on_config(config)
        raise AssertionError("expected PluginError")
    except PluginError as e:
        assert "pmtiles_prefix" in str(e)


def test_on_config_map_validation_bad_default_region():
    from unittest.mock import MagicMock

    from mkdocs.exceptions import PluginError

    plugin = MomentPlugin()
    config = MagicMock()
    config.get.return_value = {
        "moment": {
            "path": "moments",
            "map": {
                "enabled": True,
                "widget_js": "https://x/widget.js",
                "pmtiles_prefix": "pmtiles://https://x/",
                "glyphs_url": "https://x/{fontstack}/{range}.pbf",
                "default_region": "paris",  # not in regions
                "regions": {"shanghai": {"bbox": [120.8, 30.6, 122.2, 31.8]}},
            },
        }
    }
    try:
        plugin.on_config(config)
        raise AssertionError("expected PluginError")
    except PluginError as e:
        assert "default_region" in str(e)


def test_has_geo_property():
    m = _moment(0)
    assert not m.has_geo
    m.lng, m.lat = 121.47, 31.23
    assert m.has_geo


def test_on_page_context_injects_map_url_only_with_geo(tmp_path):
    plugin = _geo_plugin()
    plugin._moments = []
    plugin._labels = {}
    page = SimpleNamespace(meta={"moment_type": PageType.TIMELINE})
    config = SimpleNamespace(
        theme=SimpleNamespace(get_env=lambda: None), site_url="https://example.com"
    )
    context = {}
    plugin.on_page_context(context, page, config, None)
    assert "map_url" not in context  # no geo moments -> no map entry

    geo = _moment(0)
    geo.lng, geo.lat, geo.region = 121.47, 31.23, "shanghai"
    plugin._moments = [geo]
    plugin.on_page_context(context, page, config, None)
    assert context["map_url"] == "/moments/map/"


def test_on_page_context_detail_injects_map_cfg():
    plugin = _geo_plugin({"attribution": "© test", "hide_attribution": True})
    m = _moment(0)
    m.lng, m.lat = 121.47, 31.23
    plugin._moments = [m]
    plugin._labels = {}
    page = SimpleNamespace(
        meta={"moment_type": PageType.MOMENT_DETAIL},
        file=SimpleNamespace(src_path="moments/2026-07/30-0000.md"),
    )
    context = {}
    plugin.on_page_context(
        context,
        page,
        SimpleNamespace(theme=SimpleNamespace(get_env=lambda: None), site_url="x"),
        None,
    )
    assert context["map_cfg"]["enabled"] is True
    assert context["map_cfg"]["default_region"] == "shanghai"
    assert context["map_cfg"]["attribution"] == "© test"
    assert context["map_cfg"]["hide_attribution"] is True


def test_load_config_map_hide_attribution_default_false():
    plugin = _geo_plugin()
    assert plugin.map_cfg["hide_attribution"] is False


def test_render_map_page_generates_markers(tmp_path):
    plugin = _geo_plugin()
    geo = _moment(0)
    geo.lng, geo.lat, geo.region, geo.place, geo.emoji = 121.47, 31.23, "shanghai", "徐汇滨江", "🎬"
    geo.tags = ["film"]
    plugin._moments = [geo]
    plugin._labels = {}
    plugin._nav = None
    plugin._base_url = ""
    template = MagicMock()
    template.render.return_value = "<html>map</html>"
    env = MagicMock()
    env.get_template.return_value = template
    plugin._jinja_env = env
    plugin.on_post_build({"site_dir": str(tmp_path)})

    assert (tmp_path / "moments" / "map" / "index.html").exists()
    _, kwargs = template.render.call_args
    assert kwargs["page"].url == "/moments/map/"
    groups = kwargs["region_groups"]
    assert len(groups) == 1
    assert groups[0]["region"] == "shanghai"
    assert len(groups[0]["default_markers"]) == 1
    assert groups[0]["default_markers"][0]["lng"] == 121.47
    assert groups[0]["default_markers"][0]["permalink"] == geo.permalink
    assert kwargs["show_load_all"] is False
    assert kwargs["map_cfg"]["enabled"] is True
    assert kwargs["categories"] == [{"key": "film", "label": "🎬 film"}]
    assert kwargs["moment_list"] == [
        {
            "time_label": "Jul 30, 2026 · 00:00",
            "date": "2026-07-30 00:00",
            "permalink": geo.permalink,
            "category": "film",
            "html": "",  # helper moment has no rendered content
            "meta_items": [],  # no meta_fields schema in _geo_plugin
            "tags": [{"name": "film", "url": "/moments/tag/film/"}],
        }
    ]


def test_cluster_moments_merges_repeated_coords():
    plugin = _geo_plugin()
    a = _moment(0)  # 2026-07-30 00:00
    a.lng, a.lat = 121.4371, 31.1945
    b = _moment(1)  # 00:01 — same snapped coords
    b.lng, b.lat = 121.43715, 31.19455
    c = _moment(2)  # 00:02 — different place
    c.lng, c.lat = 139.7, 35.68
    clusters = plugin._cluster_moments([a, b, c])
    assert len(clusters) == 2
    assert clusters[0]["count"] == 1  # newest moment (c) → its cluster first
    assert clusters[1]["count"] == 2
    merged = clusters[1]
    assert abs(merged["lng"] - b.lng) < 1e-9  # latest merged moment's coords
    assert abs(merged["lat"] - b.lat) < 1e-9
    assert merged["count"] == 2


def test_cluster_moments_carries_all_items():
    """Cluster items carry EVERY moment at the coords (newest first); the
    template tabs the first popup_max and expands the rest in place."""
    plugin = _geo_plugin()
    ms = []
    for i in range(10):  # 10 moments at the same coords
        m = _moment(i)
        m.lng, m.lat = 121.4371, 31.1945
        ms.append(m)
    clusters = plugin._cluster_moments(ms)
    assert len(clusters) == 1
    assert clusters[0]["count"] == 10
    assert len(clusters[0]["items"]) == 10  # all items, not truncated
    assert clusters[0]["items"][0]["date"] > clusters[0]["items"][-1]["date"]  # newest first


def test_moment_category_derives_from_tag_emoji():
    """Category = first tag present in tag_emoji (mirrors emoji derivation)."""
    plugin = _geo_plugin()
    m = _moment(0, tags=("general", "food", "film"))
    assert plugin._moment_category(m) == "food"
    assert plugin._moment_category(_moment(1, tags=("film",))) == "film"


def test_moment_category_defaults_to_other():
    """A geo moment with no tag_emoji tag falls into the default 其他 bucket
    (machine key ``_other``; the display label lives in ``_map_categories``)."""
    plugin = _geo_plugin()
    assert plugin._moment_category(_moment(0, tags=("general",))) == "_other"
    assert plugin._moment_category(_moment(1, tags=())) == "_other"


def test_map_categories_lists_used_categories_in_order():
    """Filter list follows tag_emoji config order; unused tags stay hidden;
    其他 is appended last when any geo moment is uncategorized."""
    plugin = _geo_plugin()  # tag_emoji: film, food
    used = [
        _moment(0, tags=("film",)),
        _moment(1, tags=("general",)),  # uncategorized -> 其他
    ]
    cats = plugin._map_categories(used)
    assert cats == [
        {"key": "film", "label": "🎬 film"},
        {"key": "_other", "label": "其他"},
    ]
    # no uncategorized moments -> no 其他 entry, and unused food stays hidden
    only_film = plugin._map_categories([_moment(0, tags=("film",))])
    assert only_film == [{"key": "film", "label": "🎬 film"}]


def test_map_categories_reserves_other_key():
    """A config tag literally named ``_other`` must not collide with the
    default bucket: the key appears exactly once (labeled 其他), and the tag's
    own emoji label is not duplicated."""
    plugin = _geo_plugin({"tag_emoji": {"film": "🎬", "_other": "⭐"}})
    # moment tagged literally "_other"
    assert plugin._map_categories([_moment(0, tags=("_other",))]) == [
        {"key": "_other", "label": "其他"}
    ]
    # same bucket for a real "_other" tag and an uncategorized moment
    mixed = plugin._map_categories([_moment(0, tags=("_other",)), _moment(1, tags=("general",))])
    assert mixed == [{"key": "_other", "label": "其他"}]


def test_cluster_carries_category_and_items_carry_category():
    """Clusters and their items expose the category so the client can filter
    by checkbox; a merged cluster keeps the newest item's category."""
    plugin = _geo_plugin()
    a = _moment(0, tags=("general",))  # older, uncategorized
    b = _moment(1, tags=("food",))  # newer, same coords
    for m in (a, b):
        m.lng, m.lat = 121.4371, 31.1945
    b.emoji = "🍽️"  # emoji is derived at parse time; simulate a parsed moment
    clusters = plugin._cluster_moments([a, b])
    assert len(clusters) == 1
    merged = clusters[0]
    assert merged["count"] == 2
    assert merged["category"] == "food"  # newest item's category
    assert [it["category"] for it in merged["items"]] == ["food", "_other"]
    assert merged["items"][0]["emoji"] == "🍽️"
    assert merged["items"][0]["place"] == ""
    assert merged["items"][0]["lng"] == 121.4371  # precise coords for re-centering


def test_build_map_region_data_applies_region_limit():
    plugin = _geo_plugin({"cluster": {"region_limit": 3}})
    ms = []
    for i in range(6):  # 6 moments, all different coords in shanghai
        m = _moment(i)
        m.lng, m.lat = 121.4 + i * 0.01, 31.2
        m.region = "shanghai"
        ms.append(m)
    groups = plugin._build_map_region_data(ms)
    assert len(groups) == 1
    assert groups[0]["region"] == "shanghai"
    assert groups[0]["label"] == "shanghai"  # no label configured → falls back to name
    assert groups[0]["total"] == 6
    assert groups[0]["has_more"] is True
    assert len(groups[0]["default_markers"]) == 3  # newest 3, unclustered
    assert len(groups[0]["all_markers"]) == 6
    assert groups[0]["default_markers"][0]["date"] > groups[0]["default_markers"][-1]["date"]


def test_build_map_region_data_uses_configured_label():
    plugin = _geo_plugin(
        {
            "regions": {
                "shanghai": {"bbox": [1, 2, 3, 4], "label": "上海"},
                "tokyo": {"bbox": [5, 6, 7, 8]},
            }
        }
    )
    m = _moment(0)
    m.lng, m.lat, m.region = 121.47, 31.23, "shanghai"
    t = _moment(1)
    t.lng, t.lat, t.region = 139.7, 35.68, "tokyo"
    groups = plugin._build_map_region_data([m, t])
    labels = {g["region"]: g["label"] for g in groups}
    assert labels["shanghai"] == "上海"
    assert labels["tokyo"] == "tokyo"  # unlabeled region → name fallback


def test_render_map_page_skipped_when_no_geo(tmp_path):
    plugin = _geo_plugin()
    plugin._moments = [_moment(0)]  # no geo
    plugin._labels = {}
    plugin._nav = None
    plugin._base_url = ""
    env = MagicMock()
    env.get_template.return_value = MagicMock()
    plugin._jinja_env = env
    plugin.on_post_build({"site_dir": str(tmp_path)})
    assert not (tmp_path / "moments" / "map").exists()
    assert env.get_template.call_args_list[0][0][0] == "moment_timeline.html"


def test_parse_moment_unknown_region_falls_back_to_probe(tmp_path, caplog):
    plugin = _geo_plugin()
    p = _write_moment(
        tmp_path,
        "01-1200.md",
        "date: 2026-08-01 12:00",
        "lng: 121.47",
        "lat: 31.23",
        "region: paris",
    )
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert m.region == "shanghai"
    assert any("Unknown region" in r.message for r in caplog.records)


def test_on_config_map_validation_cluster_negative():
    """Negative / zero cluster values must fail fast (precision <= 0 would
    corrupt the grid, negative region_limit would mis-slice)."""
    from unittest.mock import MagicMock

    from mkdocs.exceptions import PluginError

    for bad in ({"precision": -0.5}, {"region_limit": -1}, {"popup_max": -1}):
        plugin = MomentPlugin()
        config = MagicMock()
        config.get.return_value = {
            "moment": {
                "path": "moments",
                "map": {
                    "enabled": True,
                    "widget_js": "https://x/widget.js",
                    "pmtiles_prefix": "pmtiles://https://x/",
                    "glyphs_url": "https://x/{fontstack}/{range}.pbf",
                    "default_region": "shanghai",
                    "regions": {"shanghai": {"bbox": [120.8, 30.6, 122.2, 31.8]}},
                    "cluster": {"precision": 0.001, "popup_max": 3, "region_limit": 50, **bad},
                },
            }
        }
        try:
            plugin.on_config(config)
            raise AssertionError(f"expected PluginError for cluster {bad}")
        except PluginError as e:
            assert "cluster" in str(e)


def test_map_template_cfg_trims_regions():
    """The template-facing regions only carry center/zoom/label — bbox stays
    build-side (probing) and is not shipped to the page."""
    plugin = _geo_plugin()
    cfg = plugin._map_template_cfg()
    assert cfg["regions"]["shanghai"] == {"center": [121.5, 31.2], "zoom": 12, "label": "shanghai"}
    assert "bbox" not in cfg["regions"]["shanghai"]
    assert cfg["regions"]["tokyo"]["label"] == "tokyo"


def test_build_map_region_data_orders_by_config():
    """Region groups follow the configured regions order (default_region
    first), not the order moments appear in."""
    plugin = _geo_plugin()  # regions: shanghai, tokyo
    # insert tokyo moment first so naive insertion order would put tokyo first
    t = _moment(0)
    t.lng, t.lat, t.region = 139.7, 35.68, "tokyo"
    s = _moment(1)
    s.lng, s.lat, s.region = 121.47, 31.23, "shanghai"
    groups = plugin._build_map_region_data([t, s])
    assert [g["region"] for g in groups] == ["shanghai", "tokyo"]


def test_load_config_map_cluster_auto_open_latest():
    """auto_open_latest defaults off; configurable on."""
    assert _geo_plugin().map_cfg["cluster"]["auto_open_latest"] is False
    plugin = _geo_plugin({"cluster": {"auto_open_latest": True}})
    assert plugin.map_cfg["cluster"]["auto_open_latest"] is True


# ---------------------------------------------------------------------------
# Structured metadata (extra.moment.meta_fields + moment `meta:` frontmatter)
# ---------------------------------------------------------------------------


def test_load_config_meta_fields_defaults_empty():
    """No meta_fields config → empty schema (feature fully off)."""
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    assert plugin.meta_fields == {}
    plugin._load_config({"path": "moments", "meta_fields": None})
    assert plugin.meta_fields == {}


def test_load_config_meta_fields_normalizes():
    """Field lists are normalized: key required, label falls back to key,
    unknown types → text, non-dict definitions / non-list values dropped."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {
                "food": [
                    {"key": "name", "label": "餐馆", "type": "text"},
                    {"key": "rating", "label": "评分", "type": "rating"},
                    {"key": "x", "type": "unknown-type"},  # → text, label→key
                    {"key": ""},  # empty key dropped
                    "not-a-dict",  # dropped
                ],
                "film": {"key": "name"},  # non-list field list dropped
            },
        }
    )
    assert plugin.meta_fields == {
        "food": [
            {"key": "name", "label": "餐馆", "type": "text"},
            {"key": "rating", "label": "评分", "type": "rating"},
            {"key": "x", "label": "x", "type": "text"},
        ]
    }
    assert "film" not in plugin.meta_fields


def test_parse_moment_meta_dict(tmp_path):
    """`meta:` frontmatter dict is parsed; ints stay ints, others become str."""
    plugin = _geo_plugin()
    p = _write_moment(
        tmp_path,
        "01-1200.md",
        "date: 2026-08-01 12:00",
        "tags: [food]",
        "meta:",
        "  name: 老上海面馆",
        "  rating: 4",
        "  vibe: 'quiet, cozy'",
    )
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert m.meta == {"name": "老上海面馆", "rating": 4, "vibe": "quiet, cozy"}
    assert isinstance(m.meta["rating"], int)


def test_parse_moment_meta_non_dict_ignored(tmp_path):
    """A non-dict `meta:` value is ignored without breaking the parse."""
    plugin = _geo_plugin()
    p = _write_moment(tmp_path, "01-1200.md", "date: 2026-08-01 12:00", "meta: just a string")
    m = plugin._parse_moment(p, "moments/2026-08/01-1200.md")
    assert m.meta == {}


def test_moment_meta_items_resolves_first_matching_tag():
    """First tag matching the schema wins; label/type come from config."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {
                "food": [
                    {"key": "name", "label": "餐馆"},
                    {"key": "rating", "label": "评分", "type": "rating"},
                ],
                "film": [{"key": "name", "label": "影院"}],
            },
        }
    )
    m = _moment(0, tags=["food"])
    m.meta = {"name": "老上海面馆", "rating": 4, "extra": "ignored"}
    items = plugin._moment_meta_items(m)
    assert items == [
        {"key": "name", "label": "餐馆", "type": "text", "value": "老上海面馆"},
        {"key": "rating", "label": "评分", "type": "rating", "value": 4},
    ]


def test_moment_meta_items_skips_missing_fields():
    """Fields the moment does not supply are skipped; no match → empty list."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {
                "food": [
                    {"key": "name", "label": "餐馆"},
                    {"key": "rating", "label": "评分", "type": "rating"},
                ],
            },
        }
    )
    m = _moment(0, tags=["food"])
    m.meta = {"name": "老上海面馆"}  # no rating
    assert [i["key"] for i in plugin._moment_meta_items(m)] == ["name"]

    m2 = _moment(1, tags=["general"])  # no matching tag
    m2.meta = {"name": "x"}
    assert plugin._moment_meta_items(m2) == []


def test_moment_meta_items_rating_validation(tmp_path, caplog):
    """Ratings must be integers in 1..5; invalid values are hidden with a
    warning instead of rendering garbage stars."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {"food": [{"key": "rating", "label": "评分", "type": "rating"}]},
        }
    )
    for bad in (0, 6, -1, "3.5", "abc"):
        m = _moment(0, tags=["food"])
        m.meta = {"rating": bad}
        assert plugin._moment_meta_items(m) == [], f"rating {bad!r} should be hidden"
    assert any("out of 1..5" in r.message for r in caplog.records)
    assert any("is not a number" in r.message for r in caplog.records)

    m = _moment(1, tags=["food"])
    m.meta = {"rating": "5"}  # numeric string coerces
    assert plugin._moment_meta_items(m) == [
        {"key": "rating", "label": "评分", "type": "rating", "value": 5}
    ]


def test_moment_meta_items_no_schema():
    """No configured schema → helper returns [] for any moment."""
    plugin = MomentPlugin()
    plugin._load_config({"path": "moments"})
    m = _moment(0, tags=["food"])
    m.meta = {"name": "x", "rating": 4}
    assert plugin._moment_meta_items(m) == []


def test_inject_template_helpers_exposes_moment_meta_items():
    """Templates can call moment_meta_items(moment) on every render path."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {"food": [{"key": "name", "label": "餐馆"}]},
        }
    )
    ctx = plugin._inject_template_helpers({})
    m = _moment(0, tags=["food"])
    m.meta = {"name": "老上海面馆"}
    assert ctx["moment_meta_items"](m) == [
        {"key": "name", "label": "餐馆", "type": "text", "value": "老上海面馆"}
    ]


def test_create_moment_meta_flag(tmp_path, monkeypatch, capsys):
    """create_moment.py --meta writes a `meta:` block: integer strings stay
    ints, other values are double-quoted (YAML-safe)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["create_moment", "hello", "--meta", "name=老上海面馆", "--meta", "rating=4"],
    )
    from scripts import create_moment

    create_moment.main()
    capsys.readouterr()
    created = list((tmp_path / "docs" / "moments").rglob("*.md"))
    assert len(created) == 1
    text = created[0].read_text(encoding="utf-8")
    assert "meta:" in text
    assert 'name: "老上海面馆"' in text
    assert "rating: 4" in text


def test_render_map_page_feed_carries_meta_items(tmp_path):
    """The map page feed (moment_list) and marker popups must carry the
    moment's structured metadata (restaurant/cinema name + rating), so the
    client can render them like the timeline entries do."""
    plugin = _geo_plugin()
    plugin.meta_fields = {
        "food": [
            {"key": "name", "label": "Restaurant", "type": "text"},
            {"key": "rating", "label": "Rating", "type": "rating"},
        ]
    }
    food = _moment(0)
    food.lng, food.lat, food.region, food.place = 121.47, 31.23, "shanghai", "徐汇滨江"
    food.tags = ["food"]
    food.meta = {"name": "Old Shanghai Noodle House", "rating": 4}
    plugin._moments = [food]
    plugin._labels = {}
    plugin._nav = None
    plugin._base_url = ""
    template = MagicMock()
    template.render.return_value = "<html>map</html>"
    env = MagicMock()
    env.get_template.return_value = template
    plugin._jinja_env = env
    plugin.on_post_build({"site_dir": str(tmp_path)})

    _, kwargs = template.render.call_args
    assert kwargs["moment_list"] == [
        {
            "time_label": "Jul 30, 2026 · 00:00",
            "date": "2026-07-30 00:00",
            "permalink": food.permalink,
            "category": "food",
            "html": "",
            "meta_items": [
                {
                    "key": "name",
                    "label": "Restaurant",
                    "type": "text",
                    "value": "Old Shanghai Noodle House",
                },
                {"key": "rating", "label": "Rating", "type": "rating", "value": 4},
            ],
            "tags": [{"name": "food", "url": "/moments/tag/food/"}],
        }
    ]
    # popup payload carries name + rating too
    marker = kwargs["region_groups"][0]["default_markers"][0]
    assert marker["name"] == "Old Shanghai Noodle House"
    assert marker["rating"] == 4


def test_cluster_moments_carries_meta_name_rating():
    """Merged-marker items keep each visit's name + rating for popup tabs."""
    plugin = _geo_plugin()
    plugin.meta_fields = {
        "food": [
            {"key": "name", "label": "Restaurant", "type": "text"},
            {"key": "rating", "label": "Rating", "type": "rating"},
        ]
    }
    ms = []
    for i, rating in enumerate((4, 3)):
        m = _moment(i)
        m.lng, m.lat = 121.4371, 31.1945
        m.tags = ["food"]
        m.meta = {"name": "Old Shanghai Noodle House", "rating": rating}
        ms.append(m)
    clusters = plugin._cluster_moments(ms)
    assert len(clusters) == 1
    items = clusters[0]["items"]
    assert [it["rating"] for it in items] == [3, 4]  # newest first
    assert all(it["name"] == "Old Shanghai Noodle House" for it in items)


def test_load_config_meta_fields_dedupes_duplicate_keys(tmp_path, caplog):
    """Duplicate field keys inside one category keep the first definition and
    warn, instead of rendering the same value twice."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {
                "food": [
                    {"key": "name", "label": "餐馆"},
                    {"key": "name", "label": "别名"},  # duplicate
                    {"key": "rating", "label": "评分", "type": "rating"},
                ],
            },
        }
    )
    assert plugin.meta_fields == {
        "food": [
            {"key": "name", "label": "餐馆", "type": "text"},
            {"key": "rating", "label": "评分", "type": "rating"},
        ]
    }
    assert any("duplicate key 'name'" in r.message for r in caplog.records)


def test_item_dict_name_prefers_key_name():
    """Popup name prefers the field whose key is `name`; other text fields
    are only used as a fallback."""
    plugin = _geo_plugin()
    plugin.meta_fields = {
        "food": [
            {"key": "dish", "label": "Dish", "type": "text"},
            {"key": "name", "label": "Restaurant", "type": "text"},
            {"key": "rating", "label": "Rating", "type": "rating"},
        ]
    }
    m = _moment(0)
    m.lng, m.lat = 121.47, 31.23
    m.tags = ["food"]
    m.meta = {"dish": "Scallion-oil noodles", "name": "Old Shanghai Noodle House", "rating": 4}
    cluster = plugin._cluster_moments([m])[0]
    assert cluster["name"] == "Old Shanghai Noodle House"
    assert cluster["rating"] == 4

    # schema without a `name` key → first text field is the fallback
    plugin.meta_fields = {"food": [{"key": "dish", "label": "Dish", "type": "text"}]}
    m.meta = {"dish": "Scallion-oil noodles"}
    assert plugin._cluster_moments([m])[0]["name"] == "Scallion-oil noodles"


def test_create_moment_meta_duplicate_key_warns(tmp_path, monkeypatch, capsys):
    """Repeated --meta with the same key warns instead of silently overwriting."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["create_moment", "hello", "--meta", "name=A", "--meta", "name=B"],
    )
    from scripts import create_moment

    create_moment.main()
    out = capsys.readouterr()
    assert "duplicate --meta key 'name'" in out.err  # warning goes to stderr
    created = list((tmp_path / "docs" / "moments").rglob("*.md"))
    text = created[0].read_text(encoding="utf-8")
    assert 'name: "B"' in text  # last value wins, consistent with dict semantics
    assert 'name: "A"' not in text


def test_moment_meta_items_falls_through_empty_tag_match():
    """A tag whose schema fields are ALL missing from `meta` falls through to
    the next matching tag instead of returning an empty list."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {
                "food": [{"key": "name", "label": "餐馆"}],  # no rating field
                "film": [{"key": "rating", "label": "评分", "type": "rating"}],
            },
        }
    )
    m = _moment(0, tags=["food", "film"])
    m.meta = {"rating": 4}  # food's `name` missing → film's rating should win
    assert plugin._moment_meta_items(m) == [
        {"key": "rating", "label": "评分", "type": "rating", "value": 4}
    ]


def test_moment_meta_items_safe_before_config():
    """Class-level default keeps the helper safe even when _load_config never
    ran (mirrors the _bucket guard)."""
    plugin = MomentPlugin()
    m = _moment(0, tags=["food"])
    m.meta = {"name": "x", "rating": 4}
    assert plugin._moment_meta_items(m) == []


def test_moment_meta_items_rating_float_hidden(tmp_path, caplog):
    """A float rating (e.g. 4.5) is hidden with a warning instead of being
    silently truncated by int() to 4."""
    plugin = MomentPlugin()
    plugin._load_config(
        {
            "path": "moments",
            "meta_fields": {"food": [{"key": "rating", "label": "评分", "type": "rating"}]},
        }
    )
    m = _moment(0, tags=["food"])
    m.meta = {"rating": 4.5}  # direct float in the dict (not the frontmatter path)
    assert plugin._moment_meta_items(m) == []
    assert any("is not an integer" in r.message for r in caplog.records)
