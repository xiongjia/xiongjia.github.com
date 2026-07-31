"""MkDocs Moment Plugin — short-form timeline for personal micro-posts."""

import logging
import os
import re
import shutil
import sys
from math import ceil
from pathlib import Path
from typing import Optional
from urllib.parse import quote

# bootstrap repo root so `shared/` is importable regardless of how this runs
# (mkdocs hook loader only puts plugins/ on sys.path, see shared/__init__.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import markdown as md_lib
import yaml
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin

from shared.date import parse_date_strict
from shared.frontmatter import parse_frontmatter
from shared.strings import slug_from_filename

from .models import Moment, PageType, Pagination

log = logging.getLogger("mkdocs.plugins.moment")


class MomentPlugin(BasePlugin):
    def _load_config(self, moment_cfg: dict):
        self.config = {
            "path": moment_cfg.get("path", "moment"),
            "posts_per_page": moment_cfg.get("posts_per_page", 20),
            "timeline_title": moment_cfg.get("timeline_title", "Moment"),
            "timeline_description": moment_cfg.get("timeline_description", ""),
            "sort": moment_cfg.get("sort", "desc"),
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

        elif page.meta.get("moment_type") is PageType.MOMENT_DETAIL:
            moment = self._get_moment_by_src_path(str(page.file.src_path))
            if moment:
                idx = self._moments.index(moment)
                context["moment"] = moment
                context["labels"] = self._labels
                context["timeline_url"] = f"/{self.config['path']}/"
                if idx > 0:
                    context["prev_moment"] = self._moments[idx - 1]
                if idx < len(self._moments) - 1:
                    context["next_moment"] = self._moments[idx + 1]

        return context

    def on_post_build(self, config):
        if not hasattr(self, "_jinja_env") or self._jinja_env is None:
            return

        # copy CSS
        css_src = Path(__file__).parent / "assets" / "css" / "moment.css"
        css_dst = Path(config["site_dir"]) / self.config["path"] / "moment.css"
        css_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(css_src, css_dst)

        # pagination pages
        total_pages = ceil(len(self._moments) / self.config["posts_per_page"])
        if total_pages <= 1:
            return

        site_dir = Path(config["site_dir"])
        template = self._jinja_env.get_template("moment_timeline.html")

        class _Page:
            """Minimal page-like object for rendering pagination pages."""

            def __init__(self, title, url):
                self.title = title
                self.url = url
                self.meta = {}

        for page_num in range(2, total_pages + 1):
            start = (page_num - 1) * self.config["posts_per_page"]
            end = start + self.config["posts_per_page"]
            page_items = self._moments[start:end]
            page_url = f"/{self.config['path']}/page/{page_num}/"
            page_proxy = _Page(f"Moment — Page {page_num}", page_url)

            pagination = Pagination(
                current_page=page_num,
                total_pages=total_pages,
                total_items=len(self._moments),
                page_size=self.config["posts_per_page"],
                has_prev=True,
                has_next=page_num < total_pages,
                prev_url=(
                    f"/{self.config['path']}/page/{page_num - 1}/"
                    if page_num > 2
                    else f"/{self.config['path']}/"
                ),
                next_url=(
                    f"/{self.config['path']}/page/{page_num + 1}/"
                    if page_num < total_pages
                    else None
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
            )

            output_dir = site_dir / self.config["path"] / "page" / str(page_num)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text(html, encoding="utf-8")

        # tag pages
        tag_moments: dict[str, list[Moment]] = {}
        for m in self._moments:
            for tag in m.tags:
                tag_moments.setdefault(tag, []).append(m)

        for tag, items in tag_moments.items():
            tag_slug = quote(tag, safe="")
            tag_url = f"/{self.config['path']}/tag/{tag_slug}/"
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
            )
            output_dir = site_dir / self.config["path"] / "tag" / tag_slug
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "index.html").write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _load_labels(self, config) -> dict:
        labels_path = Path(config["docs_dir"]) / self.config["path"] / "moment-data.yaml"
        if labels_path.is_file():
            with open(labels_path, encoding="utf-8") as f:
                return yaml.safe_load(f).get("labels", {})
        return {}

    def _parse_moment(self, md_path: Path, rel: str) -> Optional[Moment]:
        try:
            text = md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            log.warning("Cannot read %s: %s", rel, e)
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
        exts = config.get("markdown_extensions", [])
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
