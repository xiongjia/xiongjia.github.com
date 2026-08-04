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
