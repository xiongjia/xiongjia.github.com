"""MkDocs Moment Plugin — short-form timeline for personal micro-posts."""

import logging
import os
import re
import shutil
import sys
from datetime import timedelta, timezone
from email.utils import format_datetime
from math import ceil
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

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

        # copy CSS
        css_src = Path(__file__).parent / "assets" / "css" / "moment.css"
        css_dst = site_dir / self.config["path"] / "moment.css"
        css_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(css_src, css_dst)

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

            html = template.render(
                page=page_proxy,
                config=config,
                nav=self._nav,
                base_url=self._base_url,
                pagination=pagination,
                labels=self._labels,
                **helpers,
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
            html = template.render(
                page=page_proxy,
                config=config,
                nav=self._nav,
                base_url=self._base_url,
                pagination=tag_pagination,
                labels=self._labels,
                **helpers,
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
            html = timeline_template.render(
                page=page_proxy,
                config=config,
                nav=self._nav,
                base_url=self._base_url,
                pagination=pagination,
                labels=self._labels,
                **helpers,
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
        html = archive_template.render(
            page=page_proxy,
            config=config,
            nav=self._nav,
            base_url=self._base_url,
            archive_groups=archive_groups,
            labels=self._labels,
            **helpers,
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
