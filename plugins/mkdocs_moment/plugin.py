"""MkDocs Moment Plugin — short-form timeline for personal micro-posts."""

import logging
import os
import re
import sys
from datetime import timedelta, timezone
from email.utils import format_datetime
from math import ceil, floor
from pathlib import Path
from typing import Literal, Optional
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import csscompressor
import htmlmin

# bootstrap repo root so `shared/` is importable regardless of how this runs
# (mkdocs hook loader only puts plugins/ on sys.path, see shared/__init__.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import markdown as md_lib
import yaml
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin

from shared.date import parse_date_strict
from shared.frontmatter import has_draft_flag, parse_frontmatter
from shared.gcj02 import gcj02_to_wgs84
from shared.strings import slug_from_filename

from .models import Moment, PageType, Pagination

log = logging.getLogger("mkdocs.plugins.moment")

_TAG_UNSAFE = re.compile(r"[/?#%]")
_IMG_SRC = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']')
_MD_IMG = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_IMG_LINE = re.compile(r"^!\[[^\]]*\]\([^)]*\)\s*$")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HTML_TAG = re.compile(r"<[^>]+>")
_MD_LEADING_MARK = re.compile(r"^\s*[#>+\-*]\s*")
_MD_EMPHASIS = str.maketrans({"*": "", "_": "", "`": "", "~": ""})
_IMAGE_MIME = {
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def _strip_inline_markdown(text: str) -> str:
    """Strip inline markdown syntax for RSS/OG title extraction."""
    text = _MD_IMG.sub("", text)  # drop image syntax entirely (incl. alt)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_HTML_TAG.sub("", text)
    text = _MD_LEADING_MARK.sub("", text)
    return text.translate(_MD_EMPHASIS).strip()


def _first_text_line(content: str) -> str:
    """First non-empty, non-image line of a moment, stripped of inline markdown."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or _MD_IMG_LINE.match(stripped):
            continue
        text = _strip_inline_markdown(stripped)
        if text:
            return text
    return ""


# htmlmin options mirror the mkdocs-minify-plugin defaults so generated
# moment pages minify to the same degree as regular MkDocs pages; keep them
# in sync if the minify plugin's defaults change (users can still override
# per-option via extra.moment.htmlmin_opts)
_HTMLMIN_OPTS = {
    "remove_comments": False,
    "remove_empty_space": False,
    "remove_all_empty_space": False,
    "reduce_empty_attributes": True,
    "reduce_boolean_attributes": False,
    "remove_optional_attribute_quotes": True,
    "convert_charrefs": True,
    "keep_pre": False,
    "pre_tags": ("pre", "textarea"),
    "pre_attr": "pre",
}


def _valid_htmlmin_value(key: str, value) -> bool:
    """Whether an ``htmlmin_opts`` override value matches how htmlmin consumes it.

    The bool flags are truthiness-checked by htmlmin, but YAML configs should
    use real booleans; ``pre_tags`` must be a tag-name container (list/tuple/
    set/frozenset) and ``pre_attr`` a string. Anything else is surfaced as a
    warning instead of letting htmlmin fail — or silently behave oddly —
    mid-build.
    """
    if key == "pre_tags":
        return isinstance(value, (list, tuple, set, frozenset))
    if key == "pre_attr":
        return isinstance(value, str)
    return isinstance(value, bool)


def _resolve_htmlmin_opts(overrides: Optional[dict]) -> dict:
    """Merge ``extra.moment.htmlmin_opts`` over the mirrored minify defaults.

    ``None`` keeps the defaults; non-dict overrides, unknown keys and
    ill-typed values are ignored with a warning rather than crashing the
    build.
    """
    opts = dict(_HTMLMIN_OPTS)
    if overrides is None:
        return opts
    if not isinstance(overrides, dict):
        log.warning(
            "extra.moment.htmlmin_opts must be a dict, got %s — ignored", type(overrides).__name__
        )
        return opts
    for key, value in overrides.items():
        if key not in opts:
            log.warning("Unknown moment htmlmin option %r, ignored", key)
        elif not _valid_htmlmin_value(key, value):
            log.warning(
                "Moment htmlmin option %r has an invalid value type (%s), ignored",
                key,
                type(value).__name__,
            )
        else:
            opts[key] = value
    return opts


def _find_minify_plugin(config):
    """The site's loaded minify plugin, or None.

    Detected by its distinctive config keys (``minify_html`` + ``minify_css``)
    rather than its registration name, so the lookup survives renames/aliases
    in ``mkdocs.yml``.
    """
    plugins = config.get("plugins", {})
    if not hasattr(plugins, "values"):
        return None
    for plugin in plugins.values():
        cfg = getattr(plugin, "config", None)
        if cfg is not None and "minify_html" in cfg and "minify_css" in cfg:
            return plugin
    return None


def _tag_segment(tag: str) -> str:
    """Tag as a safe URL segment / directory name.

    Keeps UTF-8 chars literal (browsers percent-encode them in the request URL;
    static servers decode back to the literal path), so Chinese/emoji tags work
    as literal dirs. Replaces path-unsafe separators so generated dirs and
    emitted links stay consistent. Guards against traversal: a literal
    "." / ".." / empty segment would resolve outside the tag dir.
    """
    segment = _TAG_UNSAFE.sub("_", tag).strip()
    return segment if segment not in ("", ".", "..") else "_"


class _FigureCaptionTreeprocessor(Treeprocessor):
    """Merge an image with a following caption line into a figure.

    Markdown keeps `![alt](src)` and the next line in one paragraph, so the
    caption arrives as the ``<img>`` tail (``"\ncaption"``). A caption is
    only recognized when the tail starts on a new line — inline text after
    the image (``![alt](src) words``) is left untouched.
    """

    def run(self, root):
        for parent in list(root.iter()):
            children = list(parent)
            i = 0
            while i < len(children):
                el = children[i]
                if el.tag == "p" and len(el) == 1 and el[0].tag == "img":
                    tail = el[0].tail or ""
                    if tail.startswith("\n") and tail.strip():
                        figure = ET.Element("figure")
                        img = el[0]
                        img.tail = None  # caption text moves into <figcaption>
                        figure.append(img)
                        ET.SubElement(figure, "figcaption").text = tail.strip()
                        parent.remove(el)
                        parent.insert(i, figure)
                        children[i] = figure  # keep the snapshot in sync
                        i += 1
                        continue
                i += 1


class _MomentFigureExtension(Extension):
    """Caption extension, registered in `_render_content` only (mkdocs.yml
    is untouched; moment pages always render through the plugin)."""

    def extendMarkdown(self, md):  # noqa: N802 (markdown library API)
        md.treeprocessors.register(_FigureCaptionTreeprocessor(md), "moment_figure", 20)


class _Page:
    """Minimal page-like object for rendering generated pages.

    ``hide: ["navigation"]`` matches the Timeline/Detail pages so generated
    pages (pagination, tag, archive, month) do not show the nav sidebar.
    """

    def __init__(self, title, url):
        self.title = title
        self.url = url
        self.meta = {"hide": ["navigation"]}


class MomentPlugin(BasePlugin):
    def _load_config(self, moment_cfg: dict):
        self.config = {
            "path": moment_cfg.get("path", "moment"),
            "posts_per_page": moment_cfg.get("posts_per_page", 20),
            "timeline_title": moment_cfg.get("timeline_title", "Moment"),
            "timeline_description": moment_cfg.get("timeline_description", ""),
            "sort": moment_cfg.get("sort", "desc"),
            "feed_enabled": moment_cfg.get("feed", True),
            "feed_description": moment_cfg.get("feed_description", ""),
            "timezone": moment_cfg.get("timezone", "Asia/Shanghai"),
            "minify": moment_cfg.get("minify", True),
            "htmlmin_opts": moment_cfg.get("htmlmin_opts", None),
        }
        # resolved once per build — htmlmin_opts is static for the build
        self._htmlmin_opts = _resolve_htmlmin_opts(self.config.get("htmlmin_opts"))

        # geo / map feature config (extra.moment.map); absent or enabled=false
        # disables the feature entirely (no parsing, no badges, no map page)
        map_cfg = moment_cfg.get("map") or {}
        self.map_cfg = {
            "enabled": bool(map_cfg.get("enabled", False)),
            "widget_js": str(map_cfg.get("widget_js", "") or ""),
            "widget_css": str(map_cfg.get("widget_css", "") or ""),
            "pmtiles_prefix": str(map_cfg.get("pmtiles_prefix", "") or ""),
            "glyphs_url": str(map_cfg.get("glyphs_url", "") or ""),
            "default_region": str(map_cfg.get("default_region", "") or ""),
            "regions": dict(map_cfg.get("regions") or {}),
            "tag_emoji": dict(map_cfg.get("tag_emoji") or {}),
            "attribution": str(map_cfg.get("attribution", "") or ""),
            "hide_attribution": bool(map_cfg.get("hide_attribution", False)),
        }
        cluster_cfg = map_cfg.get("cluster") or {}
        self.map_cfg["cluster"] = {
            "precision": float(cluster_cfg.get("precision", 0.001) or 0.001),
            "popup_max": int(cluster_cfg.get("popup_max", 3) or 3),
            "region_limit": int(cluster_cfg.get("region_limit", 50) or 50),
            "auto_open_latest": bool(cluster_cfg.get("auto_open_latest", False)),
        }

    # ------------------------------------------------------------------
    # MkDocs lifecycle hooks
    # ------------------------------------------------------------------

    def on_config(self, config):
        # read config from mkdocs.yml extra.moment
        moment_cfg = config.get("extra", {}).get("moment", {})
        self._load_config(moment_cfg)
        # validate
        if self.config["posts_per_page"] < 1:
            raise PluginError("Moment plugin: posts_per_page must be >= 1")
        if self.map_cfg.get("enabled"):
            missing = [
                k for k in ("widget_js", "pmtiles_prefix", "glyphs_url") if not self.map_cfg.get(k)
            ]
            if missing:
                raise PluginError(
                    "Moment plugin: extra.moment.map is enabled but missing: " + ", ".join(missing)
                )
            regions = self.map_cfg.get("regions", {})
            if not regions or self.map_cfg.get("default_region") not in regions:
                raise PluginError(
                    "Moment plugin: extra.moment.map needs default_region listed in regions"
                )
            for name, cfg in regions.items():
                bbox = cfg.get("bbox") if isinstance(cfg, dict) else None
                if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
                    raise PluginError(
                        f"Moment plugin: region {name!r} needs bbox [minLng,minLat,maxLng,maxLat]"
                    )
            cluster = self.map_cfg.get("cluster", {})
            if cluster.get("precision", 0.001) <= 0:
                raise PluginError("Moment plugin: extra.moment.map.cluster.precision must be > 0")
            if cluster.get("popup_max", 3) < 1:
                raise PluginError("Moment plugin: extra.moment.map.cluster.popup_max must be >= 1")
            if cluster.get("region_limit", 50) < 1:
                raise PluginError(
                    "Moment plugin: extra.moment.map.cluster.region_limit must be >= 1"
                )

        # register plugin template directory
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        config.theme.dirs.insert(0, template_dir)

        # register CSS
        config["extra_css"].append(f"{self.config['path']}/moment.css")

        # load labels (Chinese UI strings)
        self._labels = self._load_labels(config)

        # internal state
        self._moments: list[Moment] = []
        self._jinja_env = None
        self._nav = None
        self._base_url = ""

        return config

    def on_files(self, files, config):
        moment_dir = Path(config["docs_dir"]) / self.config["path"]
        if not moment_dir.is_dir():
            log.warning("Moment directory not found: %s", moment_dir)
            return files

        for md_path in sorted(moment_dir.rglob("*.md")):
            if md_path.name == "index.md":
                continue
            rel = md_path.relative_to(config["docs_dir"]).as_posix()
            moment = self._parse_moment(md_path, rel)
            if moment is None:
                continue
            self._moments.append(moment)

        self._sort_moments()
        self._check_duplicate_permalinks()

        log.info("Loaded %d moment(s)", len(self._moments))
        return files

    def on_page_markdown(self, markdown, page, config, files):
        path = page.file.src_path
        if path == f"{self.config['path']}/index.md":
            page.meta["moment_type"] = PageType.TIMELINE
            page.meta["template"] = "moment_timeline.html"
            page.meta["hide"] = ["navigation"]
            return ""

        if path.startswith(f"{self.config['path']}/") and path != f"{self.config['path']}/index.md":
            page.meta["moment_type"] = PageType.MOMENT_DETAIL
            page.meta["template"] = "moment_detail.html"
            page.meta["hide"] = ["navigation"]
            page.meta["comments"] = True
            content = self._strip_frontmatter(markdown)
            moment = self._get_moment_by_src_path(str(path))
            if moment:
                moment.html = self._render_content(content, config, moment.source_path)
                moment.popup_image = self._first_image(moment) or ""
                moment.popup_text = self._popup_text(moment)
            return content

        return markdown

    def on_page_context(self, context, page, config, nav):
        # cache Jinja2 env + nav for on_post_build pagination rendering
        self._jinja_env = config.theme.get_env()
        self._nav = nav
        self._base_url = context.get("base_url", "")

        if page.meta.get("moment_type") is PageType.TIMELINE:
            total = len(self._moments)
            per_page = self.config["posts_per_page"]
            items = self._moments[:per_page]
            context["pagination"] = Pagination(
                current_page=1,
                total_pages=max(1, ceil(total / per_page)),
                total_items=total,
                page_size=per_page,
                has_prev=False,
                has_next=total > per_page,
                prev_url=None,
                next_url=f"/{self.config['path']}/page/2/" if total > per_page else None,
                items=items,
            )
            context["labels"] = self._labels
            all_tags = sorted({t for m in self._moments for t in m.tags})
            context["all_tags"] = all_tags
            self._inject_template_helpers(context)
            if self._moments:
                context["archive_url"] = f"{self._moment_base()}/archive/"
            if self.map_cfg.get("enabled") and any(m.has_geo for m in self._moments):
                context["map_url"] = f"{self._moment_base()}/map/"
                context["map_cfg"] = self._map_template_cfg()
            if self.config["feed_enabled"]:
                context["feed_url"] = self._feed_url(config)

        elif page.meta.get("moment_type") is PageType.MOMENT_DETAIL:
            moment = self._get_moment_by_src_path(str(page.file.src_path))
            if moment:
                idx = self._moments.index(moment)
                context["moment"] = moment
                context["labels"] = self._labels
                context["timeline_url"] = f"/{self.config['path']}/"
                self._inject_template_helpers(context)
                context["map_cfg"] = self._map_template_cfg()
                context["og"] = self._og_meta(moment, config)
                if idx > 0:
                    context["prev_moment"] = self._moments[idx - 1]
                if idx < len(self._moments) - 1:
                    context["next_moment"] = self._moments[idx + 1]

        return context

    def on_post_build(self, config):
        if not hasattr(self, "_jinja_env") or self._jinja_env is None:
            return

        site_dir = Path(config["site_dir"])
        template = self._jinja_env.get_template("moment_timeline.html")

        # copy CSS, minified in place: the minify plugin only handles files
        # listed in its ``css_files``, and its on_post_build runs before this
        # hook's, so moment.css never passes through it
        css_src = Path(__file__).parent / "assets" / "css" / "moment.css"
        css_dst = site_dir / self.config["path"] / "moment.css"
        css_dst.parent.mkdir(parents=True, exist_ok=True)
        css_dst.write_text(
            self._minify_css(css_src.read_text(encoding="utf-8"), config), encoding="utf-8"
        )

        # shared dialog JS (imported as a module by detail/timeline pages)
        js_src = Path(__file__).parent / "assets" / "js" / "moment-dialog.js"
        js_dst = site_dir / self.config["path"] / "moment-dialog.js"
        js_dst.parent.mkdir(parents=True, exist_ok=True)
        js_dst.write_text(js_src.read_text(encoding="utf-8"), encoding="utf-8")

        # pagination pages (only when the timeline spans multiple pages)
        total_pages = ceil(len(self._moments) / self.config["posts_per_page"])
        if total_pages > 1:
            self._render_pagination_pages(site_dir, template, config, total_pages)

        # tag pages — always generated, independent of pagination
        tag_moments: dict[str, list[Moment]] = {}
        for m in self._moments:
            for tag in m.tags:
                tag_moments.setdefault(tag, []).append(m)
        self._render_tag_pages(site_dir, template, config, tag_moments)

        # archive pages — year/month index + per-month pages
        self._render_archive_pages(site_dir, config)

        # map page — all geo moments as markers on one map (needs map enabled)
        geo_moments = [m for m in self._moments if m.has_geo]
        if self.map_cfg.get("enabled") and geo_moments:
            self._render_map_page(site_dir, config, geo_moments)

        # RSS feed
        if self.config["feed_enabled"]:
            feed_xml = self._build_rss(
                self._moments, self._site_url(config), config.get("docs_dir", "")
            )
            feed_path = site_dir / self.config["path"] / "feed.xml"
            feed_path.parent.mkdir(parents=True, exist_ok=True)
            feed_path.write_text(feed_xml, encoding="utf-8")

    def _render_pagination_pages(self, site_dir, template, config, total_pages):
        """Render /page/N/ index pages when the timeline spans multiple pages."""
        helpers = self._inject_template_helpers({})
        moment_base = helpers["moment_base"]
        for page_num in range(2, total_pages + 1):
            start = (page_num - 1) * self.config["posts_per_page"]
            end = start + self.config["posts_per_page"]
            page_items = self._moments[start:end]
            page_url = f"{moment_base}/page/{page_num}/"
            page_proxy = _Page(f"Moment — Page {page_num}", page_url)

            pagination = Pagination(
                current_page=page_num,
                total_pages=total_pages,
                total_items=len(self._moments),
                page_size=self.config["posts_per_page"],
                has_prev=True,
                has_next=page_num < total_pages,
                prev_url=(
                    f"{moment_base}/page/{page_num - 1}/" if page_num > 2 else f"{moment_base}/"
                ),
                next_url=(
                    f"{moment_base}/page/{page_num + 1}/" if page_num < total_pages else None
                ),
                items=page_items,
            )

            html = self._minify_html(
                template.render(
                    page=page_proxy,
                    config=config,
                    nav=self._nav,
                    base_url=self._base_url,
                    pagination=pagination,
                    labels=self._labels,
                    **helpers,
                ),
                config,
            )

            output_dir = site_dir / self.config["path"] / "page" / str(page_num)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text(html, encoding="utf-8")

    def _render_tag_pages(self, site_dir, template, config, tag_moments):
        """Render one timeline page per tag at /{moment_base}/tag/{tag}/."""
        helpers = self._inject_template_helpers({})
        moment_base = helpers["moment_base"]
        for tag, items in tag_moments.items():
            segment = _tag_segment(tag)
            tag_url = f"{moment_base}/tag/{segment}/"
            page_proxy = _Page(f"#{tag} — Moment", tag_url)
            tag_pagination = Pagination(
                current_page=1,
                total_pages=1,
                total_items=len(items),
                page_size=len(items),
                has_prev=False,
                has_next=False,
                prev_url=None,
                next_url=None,
                items=items,
            )
            html = self._minify_html(
                template.render(
                    page=page_proxy,
                    config=config,
                    nav=self._nav,
                    base_url=self._base_url,
                    pagination=tag_pagination,
                    labels=self._labels,
                    **helpers,
                ),
                config,
            )
            output_dir = site_dir / self.config["path"] / "tag" / segment
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text(html, encoding="utf-8")

    def _render_archive_pages(self, site_dir, config):
        """Render the year/month archive index and one page per month.

        Index at /archive/, month pages at /<YYYY>/<MM>/ (slash-separated, so
        they do not collide with hyphenated detail URLs like /2026-07/30-1430/).
        """
        groups = self._archive_groups()
        if not groups:
            return
        helpers = self._inject_template_helpers({})
        moment_base = helpers["moment_base"]
        month_dir = self.config["path"]

        # per-month pages reuse the timeline template
        timeline_template = self._jinja_env.get_template("moment_timeline.html")
        for (year, month), items in groups.items():
            month_path = f"{year}/{month:02d}"
            page_url = f"{moment_base}/{month_path}/"
            page_proxy = _Page(f"{year} · {month:02d} — Moment", page_url)
            pagination = Pagination(
                current_page=1,
                total_pages=1,
                total_items=len(items),
                page_size=len(items),
                has_prev=False,
                has_next=False,
                prev_url=None,
                next_url=None,
                items=items,
            )
            html = self._minify_html(
                timeline_template.render(
                    page=page_proxy,
                    config=config,
                    nav=self._nav,
                    base_url=self._base_url,
                    pagination=pagination,
                    labels=self._labels,
                    **helpers,
                ),
                config,
            )
            output_dir = site_dir / month_dir / month_path
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text(html, encoding="utf-8")

        # archive index page groups moments by year/month
        archive_template = self._jinja_env.get_template("moment_archive.html")
        archive_url = f"{moment_base}/archive/"
        page_proxy = _Page("Moment Archive", archive_url)
        archive_groups = [
            {
                "label": f"{year} · {month:02d}",
                "url": f"{moment_base}/{year}/{month:02d}/",
                "entries": items,
            }
            for (year, month), items in groups.items()
        ]
        html = self._minify_html(
            archive_template.render(
                page=page_proxy,
                config=config,
                nav=self._nav,
                base_url=self._base_url,
                archive_groups=archive_groups,
                labels=self._labels,
                **helpers,
            ),
            config,
        )
        output_dir = site_dir / month_dir / "archive"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text(html, encoding="utf-8")

    def _archive_groups(self) -> dict[tuple[int, int], list[Moment]]:
        """Moments grouped by (year, month), newest group first."""
        groups: dict[tuple[int, int], list[Moment]] = {}
        for m in self._moments:  # already sorted desc
            groups.setdefault((m.date.year, m.date.month), []).append(m)
        return groups

    # ------------------------------------------------------------------
    # geo / map page
    # ------------------------------------------------------------------

    def _render_map_page(self, site_dir, config, geo_moments: list[Moment]):
        """Render /{moment_base}/map/ with every geo moment as a marker.

        Marker popups link back to the moment detail page; text fields are
        escaped client-side (the widget's popupContent is trusted HTML, and
        moment titles/places come from authored markdown).
        """
        helpers = self._inject_template_helpers({})
        moment_base = helpers["moment_base"]
        map_url = f"{moment_base}/map/"
        page_proxy = _Page("Moment Map", map_url)
        template = self._jinja_env.get_template("moment_map.html")
        region_groups = self._build_map_region_data(geo_moments)
        show_load_all = any(g["has_more"] for g in region_groups)
        html = self._minify_html(
            template.render(
                page=page_proxy,
                config=config,
                nav=self._nav,
                base_url=self._base_url,
                region_groups=region_groups,
                show_load_all=show_load_all,
                map_cfg=self._map_template_cfg(),
                labels=self._labels,
                **helpers,
            ),
            config,
        )
        output_dir = site_dir / self.config["path"] / "map"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index.html").write_text(html, encoding="utf-8")

    def _build_map_region_data(self, geo_moments: list[Moment]) -> list[dict]:
        """Geo moments grouped by region, each with a default (recent N) and an
        all-clusters marker set.

        Repeated coordinates are merged into one marker (count > 1); the
        default set only includes the most recent ``region_limit`` moments per
        region so the map never renders too many DOM markers at once.
        """
        cluster_cfg = self.map_cfg.get("cluster", {})
        limit = cluster_cfg.get("region_limit", 50)
        by_region: dict[str, list[Moment]] = {}
        for m in geo_moments:
            by_region.setdefault(m.region or self.map_cfg.get("default_region", ""), []).append(m)
        # order groups by the configured regions list (default_region typically
        # first) so the default-selected region is deterministic, not dependent
        # on the order moments happen to appear in
        config_order = list(self.map_cfg.get("regions", {}).keys())
        ordered = sorted(
            by_region.items(),
            key=lambda kv: (
                config_order.index(kv[0]) if kv[0] in config_order else len(config_order)
            ),
        )
        groups = []
        for region, ms in ordered:
            ms.sort(key=lambda m: m.date, reverse=True)
            reg_cfg = self.map_cfg.get("regions", {}).get(region, {})
            label = reg_cfg.get("label") if isinstance(reg_cfg, dict) else None
            groups.append(
                {
                    "region": region,
                    "label": label or region,
                    "total": len(ms),
                    "limit": limit,
                    "has_more": len(ms) > limit,
                    "default_markers": self._cluster_moments(ms[:limit]),
                    "all_markers": self._cluster_moments(ms),
                }
            )
        return groups

    def _cluster_moments(self, moments: list[Moment]) -> list[dict]:
        """Merge moments at (nearly) the same coordinates into cluster markers.

        Coordinates are snapped to ``precision`` degrees (~100 m at 0.001)
        and grouped; each cluster keeps the latest moment's precise coords,
        emoji/place, a count, and ALL items (newest first) — the template
        tabs the first ``popup_max`` and expands the rest via a details
        toggle. Newest clusters first.
        """
        cluster_cfg = self.map_cfg.get("cluster", {})
        precision = cluster_cfg.get("precision", 0.001)
        groups: dict[tuple[int, int], list[Moment]] = {}
        for m in moments:
            # integer grid cell — no float-key ambiguity (round() is subject
            # to half-to-even boundary flips, e.g. 31.1945 / 0.001 → 31194.5)
            key = (floor(m.lng / precision), floor(m.lat / precision))
            groups.setdefault(key, []).append(m)
        clusters = []
        for items in groups.values():
            items.sort(key=lambda m: m.date, reverse=True)
            latest = items[0]
            clusters.append(
                {
                    "lng": latest.lng,
                    "lat": latest.lat,
                    "count": len(items),
                    "emoji": latest.emoji or "",
                    "place": latest.place,
                    "title": self._moment_title(latest),
                    "date": latest.date.strftime("%Y-%m-%d %H:%M"),
                    "permalink": latest.permalink,
                    "text": latest.popup_text,
                    "image": latest.popup_image,
                    "items": [
                        {
                            "title": self._moment_title(x),
                            "date": x.date.strftime("%Y-%m-%d %H:%M"),
                            "permalink": x.permalink,
                            "text": x.popup_text,
                            "image": x.popup_image,
                        }
                        for x in items
                    ],
                }
            )
        clusters.sort(key=lambda c: c["date"], reverse=True)
        return clusters

    def _map_template_cfg(self) -> dict:
        """Map feature config for templates (JSON-serializable, no plugin state).

        ``regions`` is trimmed to what the front-end scripts consume (center /
        zoom / label) — bbox probing is a build-time concern only.
        """
        regions = {
            name: {
                "center": cfg.get("center"),
                "zoom": cfg.get("zoom"),
                "label": cfg.get("label", name),
            }
            for name, cfg in self.map_cfg.get("regions", {}).items()
            if isinstance(cfg, dict)
        }
        return {
            "enabled": self.map_cfg.get("enabled", False),
            "widget_js": self.map_cfg.get("widget_js", ""),
            "widget_css": self.map_cfg.get("widget_css", ""),
            "pmtiles_prefix": self.map_cfg.get("pmtiles_prefix", ""),
            "glyphs_url": self.map_cfg.get("glyphs_url", ""),
            "default_region": self.map_cfg.get("default_region", ""),
            "regions": regions,
            "attribution": self.map_cfg.get("attribution", ""),
            "hide_attribution": self.map_cfg.get("hide_attribution", False),
            "cluster": self.map_cfg.get("cluster", {}),
        }

    def _probe_region(self, lng: Optional[float], lat: Optional[float]) -> str:
        """First configured region whose bbox contains (lng, lat); else default."""
        if lng is not None and lat is not None:
            for name, cfg in self.map_cfg.get("regions", {}).items():
                bbox = cfg.get("bbox") if isinstance(cfg, dict) else None
                if bbox and bbox[0] <= lng <= bbox[2] and bbox[1] <= lat <= bbox[3]:
                    return name
        return self.map_cfg.get("default_region", "")

    @staticmethod
    def _popup_text(moment: Moment, max_chars: int = 120) -> str:
        """Short plain-text excerpt of a moment for map popups (XSS-safe)."""
        text = _first_text_line(moment.content)
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
        return text

    # ------------------------------------------------------------------
    # RSS feed
    # ------------------------------------------------------------------

    def _build_rss(self, moments, site_url: str, docs_dir: str) -> str:
        """Build an RSS 2.0 feed for the given moments as an XML string."""
        base = site_url.rstrip("/")
        tz = self._moment_tz()
        channel_title = self.config["timeline_title"] or "Moment"
        feed_description = self.config["feed_description"] or self.config["timeline_description"]
        channel_link = f"{base}{self._moment_base()}/"

        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = channel_title
        ET.SubElement(channel, "link").text = channel_link
        ET.SubElement(channel, "description").text = feed_description
        if moments:
            ET.SubElement(channel, "lastBuildDate").text = format_datetime(
                moments[0].date.replace(tzinfo=tz)
            )

        for m in moments:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = self._moment_title(m)
            ET.SubElement(item, "link").text = f"{base}{m.permalink}"
            ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = f"{base}{m.permalink}"
            ET.SubElement(item, "pubDate").text = format_datetime(m.date.replace(tzinfo=tz))
            ET.SubElement(item, "description").text = self._absolute_html(m.html, base)
            image = self._first_image(m)
            if image:
                length, mime = self._image_info(image, docs_dir)
                if length is not None:
                    ET.SubElement(
                        item,
                        "enclosure",
                        {"url": f"{base}{image}", "length": str(length), "type": mime},
                    )

        xml = ET.tostring(rss, encoding="unicode")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml

    def _moment_title(self, moment: Moment) -> str:
        """Display title: first text line → frontmatter title → date.

        Shared by the RSS item title and OpenGraph meta.
        """
        line = _first_text_line(moment.content)
        if line:
            return line
        if moment.title:
            return moment.title
        return moment.date.strftime("%Y-%m-%d %H:%M")

    def _first_image(self, moment: Moment) -> Optional[str]:
        """First image URL in the rendered HTML (site-absolute or remote), if any."""
        match = _IMG_SRC.search(moment.html)
        if not match:
            return None
        src = match.group(1)
        if src.startswith(("/", "http://", "https://")):
            return src
        return None

    @staticmethod
    def _image_info(image: str, docs_dir: str) -> tuple[Optional[int], Optional[str]]:
        """(byte length, MIME type) for a site-absolute image, else (None, None)."""
        if not image.startswith("/"):
            return None, None  # remote image — no local file to size
        src = Path(docs_dir) / image.lstrip("/")
        if not src.is_file():
            return None, None
        mime = _IMAGE_MIME.get(src.suffix.lower())
        if mime is None:
            return None, None
        return src.stat().st_size, mime

    @staticmethod
    def _absolute_html(html: str, base: str) -> str:
        """Rewrite site-absolute src/href attributes to absolute URLs for RSS readers.

        Protocol-relative URLs (``//cdn...``) are left untouched.
        """
        return re.sub(
            r'(src|href)="/(?!/)([^"]*)"',
            lambda m: f'{m.group(1)}="{base}/{m.group(2)}"',
            html,
        )

    @staticmethod
    def _config_get(config, key: str, default: str = ""):
        """Read a config value, working for MkDocsConfig, dict and SimpleNamespace.

        Falls back to ``default`` when the key is missing or explicitly None.
        """
        value = getattr(config, key, None)
        if value is None and hasattr(config, "get"):
            value = config.get(key, default)
        return value if value is not None else default

    def _og_meta(self, moment: Moment, config) -> dict:
        """OpenGraph / twitter meta for a detail page.

        og:image is only emitted when the moment has a local or remote image;
        it never falls back to text (og:image must be a URL).
        """
        base = self._site_url(config)
        image = self._first_image(moment)
        og_image = f"{base}{image}" if image and image.startswith("/") else image
        description = _first_text_line(moment.content) or (
            self.config["timeline_description"] or self._config_get(config, "site_description")
        )
        meta = {
            "title": self._moment_title(moment),
            "description": description,
            "card": "summary_large_image" if og_image else "summary",
        }
        if og_image:
            meta["image"] = og_image
        return meta

    def _moment_tz(self):
        """Fixed timezone for moment timestamps.

        Moment dates are naive wall-clock times authored in the owner's local
        zone; pinning one tz keeps RSS pubDate reproducible across build hosts
        (CI is UTC). Falls back to UTC+08:00 when the configured zone is
        unknown.
        """
        name = self.config.get("timezone", "Asia/Shanghai")
        try:
            return ZoneInfo(name)
        except Exception:
            log.warning("Unknown moment timezone %r, falling back to UTC+08:00", name)
            return timezone(timedelta(hours=8))

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _is_minify_active(self, config, kind: Literal["html", "css"]) -> bool:
        """Whether minification is on for a generated asset kind ("html" | "css").

        Generated pages and moment.css bypass the minify plugin (its
        on_post_build runs before this hook's), so the plugin minifies them
        itself — and should follow the site-wide minify settings. The
        moment-level ``minify`` toggle (extra.moment.minify, default true)
        is an explicit override.
        """
        if not self.config.get("minify", True):
            return False
        site_plugin = _find_minify_plugin(config)
        if site_plugin is not None:
            return bool(site_plugin.config.get(f"minify_{kind}"))
        return True

    def _minify_html(self, html: str, config) -> str:
        """Minify generated page HTML with the same options the minify plugin uses.

        Pagination/tag/archive/month pages are rendered and written in
        ``on_post_build``, which runs after the minify plugin's pass, so the
        minify plugin never sees them — minify here instead. ``on_config``
        precomputes the merged options in ``self._htmlmin_opts``; fall back
        to the defaults if it never ran (defensive).
        """
        if not self._is_minify_active(config, "html"):
            return html
        opts = getattr(self, "_htmlmin_opts", None)
        if opts is None:
            opts = _HTMLMIN_OPTS
        return htmlmin.minify(html, **opts)

    def _minify_css(self, css: str, config) -> str:
        """Minify moment.css with the same compressor the minify plugin uses."""
        if not self._is_minify_active(config, "css"):
            return css
        return csscompressor.compress(css)

    def _inject_template_helpers(self, context):
        """Expose config-driven URL helpers to moment templates.

        All moment templates consume `moment_base` / `tag_segment`; keep the
        injection in one place so new rendering paths cannot miss it. Mutates
        and returns the given mapping, so it doubles as a helper-kwargs
        builder for `on_post_build` page rendering (pass `{}`).
        """
        context["moment_base"] = self._moment_base()
        context["tag_segment"] = _tag_segment
        return context

    def _moment_base(self) -> str:
        """Absolute URL prefix for moment pages, e.g. ``/moments``."""
        return f"/{self.config['path']}"

    @staticmethod
    def _site_url(config) -> str:
        """site_url from an MkDocs config, normalized without a trailing slash.

        Works for the real ``MkDocsConfig`` (attr + dict access) and for the
        dict / SimpleNamespace stand-ins used in tests.
        """
        return MomentPlugin._config_get(config, "site_url").rstrip("/")

    def _feed_url(self, config) -> str:
        """Absolute URL of the RSS feed, e.g. ``https://host/moments/feed.xml``."""
        return f"{self._site_url(config)}{self._moment_base()}/feed.xml"

    def _load_labels(self, config) -> dict:
        labels_path = Path(config["docs_dir"]) / self.config["path"] / "moment-data.yaml"
        if labels_path.is_file():
            with open(labels_path, encoding="utf-8") as f:
                return yaml.safe_load(f).get("labels", {})
        return {}

    @staticmethod
    def _include_drafts() -> bool:
        """True when MKDOCS_INCLUDE_DRAFTS is set (dev mode keeps drafts).

        Mirrors the env convention used by plugins/draft_filter.py.
        """
        return os.environ.get("MKDOCS_INCLUDE_DRAFTS", "").lower() in ("true", "1", "yes")

    def _parse_moment(self, md_path: Path, rel: str) -> Optional[Moment]:
        try:
            text = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            log.warning("Cannot read %s: %s", rel, e)
            return None

        # draft moments are excluded in production builds, following the same
        # MKDOCS_INCLUDE_DRAFTS convention as plugins/draft_filter.py; checked
        # before YAML parsing (cheap string scan) and before duplicate-
        # permalink checks so drafts never surface in timeline/tag/archive
        if not self._include_drafts() and has_draft_flag(text):
            log.info("Skipping draft moment: %s", rel)
            return None

        # split frontmatter
        parsed = parse_frontmatter(text)
        if parsed is None:
            if not text.startswith("---"):
                log.warning("No frontmatter in %s", rel)
            elif text.find("---", 3) == -1:
                log.warning("Unclosed frontmatter in %s", rel)
            else:
                log.warning("Invalid or empty frontmatter in %s", rel)
            return None

        fm, content = parsed

        # date
        date_raw = fm.get("date")
        if date_raw is None:
            log.warning("Missing date in %s", rel)
            return None
        date = parse_date_strict(date_raw)
        if date is None:
            log.warning("Unparseable date '%s' in %s", date_raw, rel)
            return None

        if not content:
            log.warning("Empty content in %s", rel)
            return None

        # slug
        stem = md_path.stem  # "30-1430" or "30-1430-home-lab"
        slug = slug_from_filename(stem)

        # id
        dir_name = md_path.parent.name  # "2026-07"
        moment_id = f"{dir_name}-{stem}"

        # permalink
        permalink = "/" + Path(rel).with_suffix("").as_posix() + "/"

        # tags
        raw_tags = fm.get("tags")
        tags = list(raw_tags) if isinstance(raw_tags, list) else []

        # optional frontmatter title (RSS title fallback)
        title = str(fm.get("title", "")).strip()

        # has_images
        has_images = "![" in content

        # geo — only parsed when the map feature is enabled (extra.moment.map)
        place = str(fm.get("place", "")).strip()
        crs = str(fm.get("crs", "wgs84")).strip().lower()
        region = str(fm.get("region", "")).strip()
        lng = lat = None
        if self.map_cfg.get("enabled"):
            lng_raw, lat_raw = fm.get("lng"), fm.get("lat")
            if (lng_raw is None) != (lat_raw is None):
                log.warning("lng/lat must be a pair in %s — geo ignored", rel)
            elif lng_raw is not None:
                try:
                    lng_f, lat_f = float(lng_raw), float(lat_raw)
                except (TypeError, ValueError):
                    log.warning(
                        "Invalid lng/lat in %s: %r, %r — geo ignored", rel, lng_raw, lat_raw
                    )
                else:
                    if not (-180 <= lng_f <= 180 and -90 <= lat_f <= 90):
                        log.warning(
                            "Out-of-range lng/lat in %s: %s, %s — geo ignored",
                            rel,
                            lng_raw,
                            lat_raw,
                        )
                    else:
                        if crs == "gcj02":
                            lng_f, lat_f = gcj02_to_wgs84(lng_f, lat_f)
                        elif crs not in ("wgs84", ""):
                            log.warning("Unknown crs %r in %s — treated as wgs84", crs, rel)
                            crs = "wgs84"
                        lng, lat = lng_f, lat_f
            if not region and lng is not None:
                region = self._probe_region(lng, lat)
            elif region and region not in self.map_cfg.get("regions", {}):
                log.warning("Unknown region %r in %s — probing by bbox", region, rel)
                region = self._probe_region(lng, lat)

        # marker emoji — first tag matching the configured tag_emoji table
        emoji = ""
        if self.map_cfg.get("enabled"):
            tag_emoji = self.map_cfg.get("tag_emoji", {})
            for tag in tags:
                if tag in tag_emoji:
                    emoji = tag_emoji[tag]
                    break

        return Moment(
            id=moment_id,
            date=date,
            slug=slug,
            source_path=rel,
            permalink=permalink,
            content=content,
            html="",
            title=title,
            tags=tags,
            has_images=has_images,
            place=place,
            lng=lng,
            lat=lat,
            crs=crs,
            region=region,
            emoji=emoji,
        )

    def _strip_frontmatter(self, markdown: str) -> str:
        if not markdown.startswith("---"):
            return markdown
        end = markdown.find("---", 3)
        if end == -1:
            return markdown
        return markdown[end + 3 :].strip()

    def _render_content(self, content: str, config, source_path: str) -> str:
        """Convert Markdown to HTML. Convert relative image paths to site-absolute."""
        src_dir = Path(source_path).parent.as_posix()

        def _fix_img_path(m):
            path = m.group(2)
            if path.startswith(("http://", "https://", "/", "data:", "#")):
                return m.group(0)
            resolved = Path(src_dir) / path
            return f"![{m.group(1)}](/{resolved.as_posix()})"

        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _fix_img_path, content)
        exts = list(config.get("markdown_extensions", [])) + [_MomentFigureExtension()]
        ext_configs = config.get("mdx_configs", {})
        html = md_lib.markdown(content, extensions=exts, extension_configs=ext_configs)
        return self._wrap_glightbox(html)

    def _wrap_glightbox(self, html: str) -> str:
        """Wrap <img> in <a class="glightbox"> so mkdocs-glightbox can open full-size.

        Moment pages render content at runtime via md_lib, bypassing glightbox's
        on_page_content post-processing, so we wrap images here ourselves.
        Images already inside a link (e.g. `[![img](src)](url)`) are left alone
        to avoid invalid nested <a> tags.
        """
        out: list[str] = []
        last = 0
        for m in re.finditer(r"<img\b[^>]*?>", html):
            out.append(html[last : m.start()])
            tag = m.group(0)
            before = html[last : m.start()]
            # if an <a ...> was opened after the last </a>, the img is inside a link
            inside_a = before.rfind("<a ") > before.rfind("</a>")
            src = re.search(r'src="([^"]+)"', tag)
            if not inside_a and src:
                url = src.group(1)
                if not url.startswith(("data:", "#", "javascript:")):
                    tag = f'<a class="glightbox" href="{url}">{tag}</a>'
            out.append(tag)
            last = m.end()
        out.append(html[last:])
        return "".join(out)

    def _sort_moments(self):
        reverse = self.config["sort"] == "desc"
        self._moments.sort(
            key=lambda m: (m.date, m.source_path),
            reverse=reverse,
        )

    def _check_duplicate_permalinks(self):
        urls: dict[str, Moment] = {}
        for m in self._moments:
            if m.permalink in urls:
                raise PluginError(
                    f"Duplicate permalink: {m.permalink}\n"
                    f"  - {m.source_path}\n"
                    f"  - {urls[m.permalink].source_path}"
                )
            urls[m.permalink] = m

    def _get_moment_by_src_path(self, src_path: str) -> Optional[Moment]:
        """Find a moment by its source file path."""
        for m in self._moments:
            if m.source_path == src_path:
                return m
        return None
