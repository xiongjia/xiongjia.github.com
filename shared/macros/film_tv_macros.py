"""Macros for the Film & TV archive pages (movies / tv / index).

The pages themselves carry only a heading plus a macro call; the list, its
filters and the month calendar are rendered client-side from the committed JSON
shards (``notes/film-tv/assets/``), while the index page's statistics are
rendered here at build time from ``stats.yml``.

Registered as a second module in mkdocs.yml's ``macros`` plugin config; the
health module keeps owning the health pages.
"""

from __future__ import annotations

import html
import json
import os
import sys
from urllib.parse import quote

import yaml

_dir = os.path.dirname(os.path.abspath(__file__))
_MKDOCS_YML = "mkdocs.yml"
SECTION_PREFIX = "notes/film-tv/"


def _find_repo_root(start: str) -> str:
    """Walk up from *start* until a directory holding mkdocs.yml is found.

    Same trick as the health macros: a hardcoded ``parents[N]`` silently points
    at the wrong directory if the module moves, and the failure surfaces much
    later as a confusing ModuleNotFoundError.
    """
    candidate = start
    while True:
        if os.path.isfile(os.path.join(candidate, _MKDOCS_YML)):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            return os.getcwd()
        candidate = parent


_REPO_ROOT = _find_repo_root(_dir)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.mkdocs_yaml import load_extra  # noqa: E402

CATEGORY_LABELS = {
    "feature": "电影",
    "series": "剧集",
    "variety": "综艺",
    "anime": "动漫",
    "documentary": "纪录片",
    "other": "其他",
}


def _local_prefix() -> str:
    """``extra.film_tv.local_prefix`` (site-root relative, trailing slash)."""
    value = str(load_extra("film_tv", label="film-tv-macros").get("local_prefix") or "")
    return (value or "assets/bucket/film-tv/").strip("/") + "/"


def _page_prefix(page_url: str, base: str) -> str:
    """Relative prefix from the current page to a site-root-relative *base*.

    Directory URLs mean a subpage like ``notes/film-tv/movies/`` needs one more
    ``../`` than the section index (``notes/film-tv/``).
    """
    remainder = (page_url or "").removeprefix(SECTION_PREFIX).strip("/")
    return "../" * (1 if remainder else 0) + base


def _assets_base(page_url: str) -> str:
    """Relative path from the current page to ``notes/film-tv/assets/``."""
    return _page_prefix(page_url, "assets/")


def _load_asset(name: str):
    """Read one derived asset (``stats.yml`` / ``people.yml``); {} when missing."""
    path = os.path.join(_REPO_ROOT, "docs", SECTION_PREFIX, "assets", name)
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_stats() -> dict:
    return _load_asset("stats.yml")


ROLE_LABELS = {"director": "导演", "actor": "演员", "writer": "编剧"}


def _up_prefix(page_url: str) -> str:
    """Relative prefix from the current page back to the archive index."""
    return _page_prefix(page_url, "")


def _people_rows(people: list[dict], *, limit: int = 50, link_base: str = "./") -> str:
    """Ranking table: 作品数 desc, then name. Each name links to the archive
    filtered by that person (``?person=``)."""
    rows = list(people)[:limit]
    if not rows:
        return '<p class="film-tv-stat__empty">暂无数据（先跑一次同步与派生）。</p>'
    body = []
    for position, person in enumerate(rows, start=1):
        raw_name = person.get("name") or ""
        # a Douban name is free text: escape it for the HTML and quote it for the
        # ?person= link, or a name with &/" breaks both
        name = html.escape(raw_name)
        works = person.get("works") or 0
        average = person.get("avg_rating")
        first, last = person.get("first_year"), person.get("last_year")
        span = f"{first}–{last}" if first and last else (first or last or "—")
        roles = "/".join(ROLE_LABELS.get(role, role) for role in person.get("roles") or [])
        person_id = str(person.get("douban_id") or "")
        douban = (
            f'<a href="https://www.douban.com/personage/{person_id}/" target="_blank" '
            'rel="noopener" title="豆瓣影人页">豆瓣</a>'
            if person_id
            else ""
        )
        body.append(
            "<tr>"
            f'<td class="film-tv-people__rank">{position}</td>'
            f'<td><a href="{link_base}?person={quote(raw_name, safe="")}">{name}</a></td>'
            f'<td class="film-tv-people__num">{works}</td>'
            f'<td class="film-tv-people__num">{average if average is not None else "—"}</td>'
            f'<td class="film-tv-people__span">{span}</td>'
            f'<td class="film-tv-people__roles">{roles}</td>'
            f'<td class="film-tv-people__douban">{douban}</td>'
            "</tr>"
        )
    header = (
        "<thead><tr><th>#</th><th>影人</th><th>作品</th><th>平均分</th>"
        "<th>观看年份</th><th>角色</th><th></th></tr></thead>"
    )
    return (
        '<div class="film-tv-people__scroll"><table class="film-tv-people">'
        + header
        + "<tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _month_total(kind: str) -> int:
    """Total records in the derived month index (kind-scoped), for the summary."""
    path = os.path.join(_REPO_ROOT, "docs", SECTION_PREFIX, "assets", "index.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return 0
    months = (data or {}).get("months")
    if not isinstance(months, dict):
        return 0
    total = 0
    for month, info in months.items():
        if month == "undated" or not isinstance(info, dict):
            continue
        if kind:
            total += int((info.get("by_type") or {}).get(kind) or 0)
        else:
            total += int(info.get("count") or 0)
    return total


def _stat_block(title: str, body: str) -> str:
    """One distribution block inside the single collapsible statistics block."""
    return f'<section class="film-tv-stat"><h3>{title}</h3>{body}</section>'


def _bar_rows(counts: dict, *, limit: int = 12, labels: dict | None = None) -> str:
    """Horizontal bar rows for a ``name → count`` mapping, **sorted by count**.

    ``stats.yml`` is written with ``sort_keys=True`` (deterministic diffs), so the
    mapping arrives alphabetically — sorting here is what makes the "top N" lists
    actually be the top N.
    """
    labels = labels or {}
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    top = max(int(value) for _, value in ordered) or 1
    rows = []
    for name, value in ordered[:limit]:
        width = round(int(value) * 100 / top)
        rows.append(
            '<li class="film-tv-stat__row">'
            f'<span class="film-tv-stat__name">{labels.get(name, name)}</span>'
            f'<span class="film-tv-stat__bar" style="--film-tv-bar:{width}%"></span>'
            f'<span class="film-tv-stat__value">{value}</span>'
            "</li>"
        )
    return '<ul class="film-tv-stat__rows">' + "".join(rows) + "</ul>"


def define_env(env) -> None:
    """Register the film & TV macros."""

    def page_url() -> str:
        return getattr(getattr(env, "page", None), "url", "") or ""

    def page_assets() -> str:
        return _assets_base(page_url())

    def local_cover_base() -> str:
        """Page-relative path to the local cover mirror (``docs/assets/bucket/...``).

        Covers live on R2 in the published site; when R2 has no object yet (or the
        developer is offline) the front end falls back to this local mirror, which
        `poe bucket-sync pull` keeps around for preview.
        """
        depth = len([part for part in page_url().split("/") if part])
        return "../" * depth + _local_prefix()

    @env.macro
    def film_tv_page(kind: str = "") -> str:
        """The interactive archive view (list + filters + calendar + detail dialog).

        ``kind`` scopes the page to ``movie`` / ``tv``; an empty kind shows
        everything (index page).
        """
        base = page_assets()
        parts = [
            f'<div class="film-tv" data-kind="{kind}" data-json-base="{base}"'
            f' data-cover-local-base="{local_cover_base()}">',
            '<p class="film-tv__banner" role="status" aria-live="polite"></p>',
            # navigation sits *above* the content (month/page controls first, then the
            # month picker), so nothing has to be hunted for below the list
            '<nav class="film-tv__pager" aria-label="分页 / 按月份浏览"></nav>',
            '<nav class="film-tv__calendar" aria-label="按月选择"></nav>',
            '<div class="film-tv__filters"></div>',
            '<div class="film-tv__chips" hidden></div>',
            '<p class="film-tv__count"></p>',
            '<div class="film-tv__list"></div>',
            "</div>",
            _dialog_markup(),
        ]
        return "\n\n".join(parts) + "\n"

    @env.macro
    def film_tv_stats() -> str:
        """Build-time statistics cards (totals, ratings, year/category/region mix)."""
        stats = _load_stats()
        if not stats:
            return (
                '<p class="film-tv-stat__empty">暂无统计数据 —— 先跑 '
                "`poe sync-film-tv` + `poe film-tv-derive`。</p>"
            )
        total = stats.get("total") or 0
        average = stats.get("average_rating")
        by_type = stats.get("by_type") or {}
        # no "已评分" card: every record is rated, so it carried no information
        hours = stats.get("hours")
        cards = [
            ("归档条目", f"{total}"),
            ("电影 / 剧集", f"{by_type.get('movie', 0)} / {by_type.get('tv', 0)}"),
            ("平均分", f"{average}" if average is not None else "—"),
            # no 影人 card: casts are stored as the first 10 names per record, so a
            # people count would be an artifact of that cut-off, not a real number
            ("总时长", f"{hours} 小时" if hours else "—"),
        ]
        card_html = "".join(
            f'<div class="film-tv-stat__card"><span class="film-tv-stat__label">{label}</span>'
            f'<span class="film-tv-stat__number">{value}</span></div>'
            for label, value in cards
        )
        type_labels = {"movie": "电影", "tv": "剧集", "unknown": "未知"}
        by_category = stats.get("by_category") or {}
        by_year = stats.get("by_year") or {}
        by_region = stats.get("by_region") or {}
        distributions = "".join(
            [
                _stat_block("🎬 按分类", _bar_rows(by_category, labels=CATEGORY_LABELS)),
                _stat_block("📅 按年份（观看年）", _bar_rows(by_year, limit=8)),
                _stat_block("🌏 按地区", _bar_rows(by_region, limit=10)),
                _stat_block("🎞️ 按类型", _bar_rows(by_type, labels=type_labels)),
            ]
        )
        # ONE collapsible block for every distribution (same <details> pattern as
        # running.md), collapsed by default so the overview stays short
        hint = f"{len(by_category)} 类 · {len(by_year)} 个年份 · {len(by_region)} 个地区"
        details = (
            '<details class="film-tv-stat"><summary>📊 统计分布'
            f'<span class="film-tv-stat__hint">{hint}</span></summary>'
            f'<div class="film-tv-stat__grid">{distributions}</div>'
            "</details>"
        )
        blocks = [f'<div class="film-tv-stat__cards">{card_html}</div>', details]
        return "\n\n".join(blocks) + "\n"

    @env.macro
    def film_tv_people(*, limit: int = 50) -> str:
        """Director / actor / writer boards, rendered at build time from people.yml."""
        link_base = _up_prefix(getattr(getattr(env, "page", None), "url", "") or "")
        people = _load_asset("people.yml").get("people") or []
        if not people:
            return (
                '<p class="film-tv-stat__empty">暂无影人统计 —— 先跑 '
                "`poe sync-film-tv` + `poe film-tv-derive`。</p>"
            )
        blocks = []
        for role in ("director", "actor", "writer"):
            subset = [person for person in people if role in (person.get("roles") or [])]
            blocks.append(
                f'<section class="film-tv-people__board">'
                f"<h3>{ROLE_LABELS[role]} · 作品最多 Top {limit}</h3>"
                f"{_people_rows(subset, limit=limit, link_base=link_base)}</section>"
            )
        return "\n\n".join(blocks) + "\n"

    @env.macro
    def film_tv_chart(kind: str = "") -> str:
        """Container for the watch-volume chart (rendered client-side: last 12
        months / by year / custom range).

        The chart is client-side because it has range controls; it reads the same
        derived month index as the list, so the two can never disagree. The macro
        only emits the container (plus the asset base), keeping the build free of
        chart logic.
        """
        base = page_assets()
        scope = {"movie": "电影", "tv": "剧集"}.get(kind, "影视")
        total = _month_total(kind)
        # "归档共 N 条" (not a bare "共 N 条"): this is the whole archive, while the
        # chart's own summary line reports the *window* it drew — two different
        # numbers in one block must not look like a contradiction
        hint = f"归档共 {total} 条" if total else ""
        hint_html = f'<span class="film-tv-chart__hint">{hint}</span>' if hint else ""
        # collapsible (collapsed by default, like the 统计分布 block): the chart is
        # tall, so it stays out of the way until asked for; the summary carries the
        # headline number so the closed state is still informative
        return (
            f'<details class="film-tv-chart" data-kind="{kind}" data-json-base="{base}"'
            f' aria-label="{scope}观影量统计">'
            f"<summary>📈 观影量（{scope}）{hint_html}</summary>"
            '<div class="film-tv-chart__controls"></div>'
            '<p class="film-tv-chart__summary"></p>'
            '<div class="film-tv-chart__canvas"></div>'
            "</details>"
        )

    @env.macro
    def film_tv_note() -> str:
        """A one-line status note: how many records still need their details."""
        stats = _load_stats()
        if not stats:
            return (
                '<p class="film-tv-note">归档还没有数据（先跑一次 '
                "<code>poe sync-film-tv</code>）。</p>"
            )
        pending = stats.get("pending")
        if not pending:
            return '<p class="film-tv-note">归档已补齐（全部条目都有详情）。</p>'
        return (
            '<p class="film-tv-note">还有 '
            f"<strong>{pending}</strong> 条待补详情（列表骨架已存，"
            "跑 <code>poe sync-film-tv --limit 300</code> 分批补齐）。</p>"
        )


def _dialog_markup() -> str:
    """Shared detail dialog (one per page; the JS fills it in)."""
    return (
        '<dialog class="film-tv-dialog">'
        '<div class="film-tv-dialog__body">'
        '<div class="film-tv-dialog__cover"></div>'
        '<div class="film-tv-dialog__main">'
        '<h3 class="film-tv-dialog__title"></h3>'
        '<p class="film-tv-dialog__original"></p>'
        '<dl class="film-tv-dialog__facts"></dl>'
        '<div class="film-tv-dialog__comment"></div>'
        '<p class="film-tv-dialog__actions">'
        '<a class="film-tv-dialog__link" target="_blank" rel="noopener">在豆瓣打开</a>'
        "</p>"
        "</div>"
        "</div>"
        '<button type="button" class="film-tv-dialog__close" aria-label="关闭">×</button>'
        "</dialog>"
    )
