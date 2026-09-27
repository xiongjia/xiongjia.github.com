"""Douban HTML parsing for the Film & TV archive.

**Every selector for Douban's pages lives in this module** (list / subject /
photo album) so markup drift has exactly one place to be fixed, and the HTML
fixtures in ``tests/fixtures/film_tv/`` exercise all of it.

Observations baked into these parsers (see ``internal/film-tv-design.md`` §1):

- the last item of a list page is ``class="item last"`` — matching only
  ``class="item"`` silently drops one item per page;
- an unrated item has **no** rating span, but still has a date;
- an item whose subject was deleted on Douban is ``class="item-show deleted"``
  (title may be the ``未知电影`` placeholder) and has no date;
- the ``.comment`` div only exists on the *在看* (``do``) list, never on
  ``collect`` — the user's short comment comes from the subject page instead;
- ``#interest_sect_level`` (subject page, logged in) carries my status, my
  marked date, ``#n_rating``, my tags and my short comment.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from html import unescape

# --- list page ---------------------------------------------------------------

LIST_ITEM_RE = re.compile(r'<li id="list(\d+)" class="item[^"]*">(.*?)</li>', re.S)
LIST_TITLE_RE = re.compile(
    r'<div class="title">\s*<a href="https://movie\.douban\.com/subject/(\d+)/"[^>]*>\s*(.*?)\s*</a>',
    re.S,
)
# rated: <span class="rating4-t"></span>&nbsp;&nbsp;2026-09-25
# unrated: 2019-12-01 (no span at all — 14 of the 4292 items are like this)
LIST_DATE_RE = re.compile(
    r'<div class="date">\s*'
    r'(?:<span class="rating(\d)-t"></span>\s*(?:&nbsp;)*)?'
    r"\s*([\d-]{10})?\s*</div>",
    re.S,
)
LIST_TAGS_RE = re.compile(r'<span class="tags">\s*标签\s*:\s*(.*?)\s*</span>', re.S)
LIST_COMMENT_RE = re.compile(r'<div class="comment">\s*(.*?)\s*</div>', re.S)
LIST_INTRO_RE = re.compile(r'<span class="intro">(.*?)</span>', re.S)
LIST_TOTAL_RE = re.compile(
    r'<span class="subject-num">\s*[\d-]+\s*&nbsp;/\&nbsp;([\d,]+)\s*</span>'
)

# --- subject page ------------------------------------------------------------

SUBJECT_TITLE_RE = re.compile(r'<span property="v:itemreviewed">(.*?)</span>', re.S)
SUBJECT_H1_YEAR_RE = re.compile(r'<span class="year">\s*\(?(\d{4})\)?\s*</span>')
SUBJECT_MAINPIC_RE = re.compile(r'<div id="mainpic">.*?<img[^>]*>', re.S)
MAINPIC_SRC_RE = re.compile(r'src="([^"]+)"')
MAINPIC_ALT_RE = re.compile(r'alt="([^"]*)"')
SUBJECT_SCORE_RE = re.compile(r'property="v:average">\s*([\d.]+)\s*<')
SUBJECT_VOTES_RE = re.compile(r'property="v:votes">\s*(\d+)\s*<')
SUBJECT_GENRE_RE = re.compile(r'property="v:genre">([^<]*)<')
SUBJECT_RELEASE_RE = re.compile(r'property="v:initialReleaseDate"[^>]*content="([^"]*)"')
SUBJECT_INFO_ROW_RE = re.compile(r"['\"]pl['\"]>(.*?)</span>\s*:?\s*(.*)$", re.S)
SUBJECT_RUNTIME_ATTR_RE = re.compile(r'property="v:runtime"[^>]*content="(\d+)"')

# 演职员 block: each person link carries `title="中文名 原文名"` — the only place
# the page exposes the original (usually Latin) name, and it costs no extra request
CELEBRITIES_BLOCK_RE = re.compile(r'<div id="celebrities".*?</ul>', re.S)
CELEBRITY_TITLE_RE = re.compile(
    r'<a href="https://www\.douban\.com/personage/(\d+)/"\s+title="([^"]*)"'
)
# credit rows in `#info` carry the same personage id, which is how a Chinese-only
# credit can be matched to its `title` (Douban sometimes spells the Chinese name
# differently in the two blocks, e.g. 卞成贤 vs 边圣铉 for the same person)
INFO_PERSON_LINK_RE = re.compile(
    r'<a href="https://www\.douban\.com/personage/(\d+)/"[^>]*>(.*?)</a>', re.S
)

INTEREST_BLOCK_RE = re.compile(r'<div id="interest_sect_level".*?</div>\s*</div>', re.S)
INTEREST_STATUS_RE = re.compile(r'<span class="mr10">\s*(.*?)\s*(?:<span|</span>)', re.S)
INTEREST_DATE_RE = re.compile(r'class="collection_date"[^>]*>([\d-]+)<')
INTEREST_RATING_RE = re.compile(r'id="n_rating"[^>]*value="(\d+)"')
INTEREST_TAGS_RE = re.compile(r'<span class="color_gray">\s*标签\s*:\s*([^<]*?)\s*</span>')
INTEREST_COMMENT_RE = re.compile(r"<br\s*/?>\s*<span>\s*(.*?)\s*<span")

# --- photo album -------------------------------------------------------------

PHOTO_ITEM_RE = re.compile(r'<li data-id="(\d+)"[^>]*>(.*?)</li>', re.S)
PHOTO_IMG_RE = re.compile(r"/view/photo/[a-z_]+/public/(p\d+\.(?:jpg|webp))")
PHOTO_NAME_RE = re.compile(r'<div class="name">\s*(.*?)\s*</div>', re.S)

PHOTO_HOST = "https://img3.doubanio.com"
TAG_RE = re.compile(r"<[^>]+>")

#: image size tokens Douban accepts in ``/view/photo/<token>/public/...``
PHOTO_LARGE = "l"


def text(html: str) -> str:
    """Tag-stripped, whitespace-collapsed, entity-decoded text."""
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub("", html))).strip()


def split_values(value: str) -> list[str]:
    """Split a Douban ``a / b / c`` value list, dropping blanks."""
    return [part.strip() for part in value.split("/") if part.strip()]


@dataclass
class ListItem:
    """One row of a collection list page (``collect`` / ``do``)."""

    id: str
    title: str
    user_rating: int | None = None
    marked_at: str | None = None
    tags: list[str] = field(default_factory=list)
    comment: str = ""
    intro: str = ""
    deleted: bool = False


@dataclass
class ListPage:
    """A parsed collection list page."""

    total: int | None
    items: list[ListItem]


@dataclass
class Interest:
    """The logged-in user's own data on a subject page (``#interest_sect_level``)."""

    status: str | None = None
    status_word: str = ""
    marked_at: str | None = None
    user_rating: int | None = None
    tags: list[str] = field(default_factory=list)
    comment: str = ""


@dataclass
class Subject:
    """A parsed subject (item detail) page."""

    id: str
    title: str
    original_title: str | None = None
    year: int | None = None
    genres: list[str] = field(default_factory=list)
    regions_raw: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    runtime: int | None = None
    episodes: int | None = None
    first_aired: str | None = None
    release_dates: list[str] = field(default_factory=list)
    douban_score: float | None = None
    douban_score_count: int | None = None
    directors: list[str] = field(default_factory=list)
    writers: list[str] = field(default_factory=list)
    casts: list[str] = field(default_factory=list)
    #: display label → Douban personage id (``27253735``); feeds the person
    #: directory so later enrichment (original name / avatar / birthday) can fetch
    #: ``www.douban.com/personage/<id>/`` without re-matching by name
    person_ids: dict[str, str] = field(default_factory=dict)
    cover_url: str | None = None
    aliases: list[str] = field(default_factory=list)
    info_keys: list[str] = field(default_factory=list)
    interest: Interest = field(default_factory=Interest)


@dataclass
class Photo:
    """One poster candidate from the photo album."""

    photo_id: str
    url: str
    name: str = ""


def parse_list_page(html: str) -> ListPage:
    """Parse a collection list page into items (+ the displayed total).

    The same markup serves both the 看过 and 在看 lists, so nothing here needs to
    know which one was fetched (the caller passes the status to the model).
    """
    total_match = LIST_TOTAL_RE.search(html)
    total = int(total_match.group(1).replace(",", "")) if total_match else None
    items: list[ListItem] = []
    for list_id, block in LIST_ITEM_RE.findall(html):
        title_match = LIST_TITLE_RE.search(block)
        subject_id = title_match.group(1) if title_match else list_id
        raw_title = text(title_match.group(2)) if title_match else ""
        date_match = LIST_DATE_RE.search(block)
        tags_match = LIST_TAGS_RE.search(block)
        comment_match = LIST_COMMENT_RE.search(block)
        intro_match = LIST_INTRO_RE.search(block)
        items.append(
            ListItem(
                id=subject_id,
                title=title_part(raw_title),
                user_rating=int(date_match.group(1))
                if date_match and date_match.group(1)
                else None,
                marked_at=date_match.group(2) if date_match else None,
                tags=tags_match.group(1).split() if tags_match else [],
                comment=text(comment_match.group(1)) if comment_match else "",
                intro=text(intro_match.group(1)) if intro_match else "",
                deleted="item-show deleted" in block,
            )
        )
    return ListPage(total=total, items=items)


def title_part(raw: str) -> str:
    """``中文名 / 原名`` → ``中文名`` (the detail page gives the exact split)."""
    return split_values(raw)[0] if raw else ""


def parse_subject_page(html: str, *, subject_id: str = "", person_style: str = "hint") -> Subject:
    """Parse a subject page (title / info block / score / my interest)."""
    info = parse_info(html)
    genres = [text(g) for g in SUBJECT_GENRE_RE.findall(html)]
    title_html = SUBJECT_TITLE_RE.search(html)
    title = text(title_html.group(1)) if title_html else ""
    cover = SUBJECT_MAINPIC_RE.search(html)
    cover_tag = cover.group(0) if cover else ""
    src_match = MAINPIC_SRC_RE.search(cover_tag)
    cover_url = src_match.group(1) if src_match else None
    original_title = None
    alt = MAINPIC_ALT_RE.search(cover_tag)
    alt_value = unescape(alt.group(1)).strip() if alt else ""
    if alt_value and alt_value != title and title.endswith(alt_value):
        original_title = alt_value
        title = title[: -len(alt_value)].strip()

    release_dates = SUBJECT_RELEASE_RE.findall(html)
    years = [int(y) for y in re.findall(r"(\d{4})", " ".join(release_dates))]
    if not years:
        h1_year = SUBJECT_H1_YEAR_RE.search(html)
        years = [int(h1_year.group(1))] if h1_year else []

    _credits, _person_ids = parse_credits(
        html, info, parse_celebrities(html), person_style=person_style
    )
    score = SUBJECT_SCORE_RE.search(html)
    votes = SUBJECT_VOTES_RE.search(html)
    runtime_attr = SUBJECT_RUNTIME_ATTR_RE.search(html)
    runtime = int(runtime_attr.group(1)) if runtime_attr else minutes(info.get("片长", ""))

    return Subject(
        id=subject_id,
        title=title,
        original_title=original_title,
        year=min(years) if years else None,
        genres=genres,
        regions_raw=split_values(info.get("制片国家/地区", "")),
        languages=split_values(info.get("语言", "")),
        runtime=runtime if runtime is not None else minutes(info.get("单集片长", "")),
        episodes=parse_int(info.get("集数", "")),
        first_aired=_first_date(info.get("首播", "")),
        release_dates=release_dates,
        douban_score=float(score.group(1)) if score else None,
        douban_score_count=int(votes.group(1)) if votes else None,
        **_credits,
        person_ids=_person_ids,
        cover_url=cover_url,
        aliases=split_values(info.get("又名", "")),
        info_keys=sorted(info),
        interest=parse_interest(html),
    )


def parse_celebrities(html: str) -> dict[str, str]:
    """``personage id → "中文名 原文名"`` from the ``#celebrities`` block."""
    block = CELEBRITIES_BLOCK_RE.search(html)
    if not block:
        return {}
    return {
        person_id: unescape(title).strip()
        for person_id, title in CELEBRITY_TITLE_RE.findall(block.group(0))
    }


def split_person_title(title: str) -> tuple[str, str]:
    """``"弗兰克·德拉邦特 Frank Darabont"`` → ``("弗兰克·德拉邦特", "Frank Darabont")``.

    Returns ``("", "")`` when the string does not look like the ``中文 原文`` pair.
    """
    match = re.match(
        r"^(?P<zh>.*?[\u4e00-\u9fff·]+)\s+(?P<latin>[A-Za-z][A-Za-z.\-\' ]*)$", title or ""
    )
    if not match:
        return "", ""
    return match.group("zh").strip(), match.group("latin").strip()


#: how a person name is displayed (``extra.film_tv.person_name_style``)
PERSON_NAME_STYLES = ("hint", "latin", "zh")


def person_label(title: str, style: str = "hint") -> str:
    """Display form for a person, given Douban's ``中文名 原文名`` title.

    - ``hint`` (default): only *transliterated* names flip to ``原文（中文）``.
      Douban marks those with ``·`` (弗兰克·德拉邦特 Frank Darabont), whereas a
      CJK-script name (杨磊 Lei Yang) is the original itself and its Latin form is
      just pinyin — so it stays as-is. No language detector needed.
    - ``latin``: always prefer the Latin form when the page offers one.
    - ``zh``: always keep Douban's Chinese form.
    """
    zh, latin = split_person_title(title)
    if not zh or not latin:
        return title.strip()
    if style == "latin" or (style == "hint" and "·" in zh):
        return f"{latin}（{zh}）"
    return zh


def parse_credits(
    html: str,
    info: dict[str, str],
    celebrities: dict[str, str],
    *,
    person_style: str = "hint",
) -> tuple[dict, dict[str, str]]:
    """导演 / 编剧 / 主演 with their display labels.

    Names are matched to the celebrities block **by personage id**, so a credit row
    keeps its original-name annotation even when Douban spells the Chinese name
    differently in the two blocks.
    """
    block_key = {"导演": "directors", "编剧": "writers", "主演": "casts"}
    start = html.find('id="info"')
    info_block = html[start : html.find("</div>", start)] if start >= 0 else ""
    ids: dict[str, str] = {}

    def labels_for(row_key: str) -> list[str]:
        raw = info.get(row_key, "")
        if not raw:
            return []
        row = next((r for r in re.split(r"<br\s*/?>", info_block) if row_key in r), "")
        labels: list[str] = []
        for person_id, name_html in INFO_PERSON_LINK_RE.findall(row):
            name = text(name_html)
            title = celebrities.get(person_id, "")
            zh, latin = split_person_title(title)
            if zh and latin and name in title:
                label = person_label(title, person_style)
            else:
                label = name
            labels.append(label)
            ids.setdefault(label, person_id)
        if not labels:  # no personage links (unusual markup): keep the plain split
            labels = split_values(raw)
        return labels

    roles = {value: labels_for(key) for key, value in block_key.items()}
    return roles, ids


def parse_info(html: str) -> dict[str, str]:
    """Parse the ``#info`` block into ``{key: "value / value"}``.

    Two markup variants must both work:
    ``<span><span class='pl'>导演</span>: <span class='attrs'>…</span></span>``
    and ``<span class="pl">类型:</span> 剧情 / 犯罪``.
    """
    start = html.find('id="info"')
    if start < 0:
        return {}
    block = html[start : html.find("</div>", start)]
    rows: dict[str, str] = {}
    for row in re.split(r"<br\s*/?>", block):
        match = SUBJECT_INFO_ROW_RE.search(row)
        if not match:
            continue
        key = text(match.group(1)).rstrip(":")
        value = text(match.group(2))
        if key and value:
            rows[key] = value
    return rows


def parse_interest(html: str) -> Interest:
    """Parse ``#interest_sect_level`` — my status / date / rating / tags / comment."""
    match = INTEREST_BLOCK_RE.search(html)
    if not match:
        return Interest()
    block = match.group(0)

    interest = Interest()
    status_match = INTEREST_STATUS_RE.search(block)
    if status_match:
        status_text = text(status_match.group(1))
        for prefix, value in (("我看过", "collect"), ("我在看", "do"), ("我想看", "wish")):
            if status_text.startswith(prefix):
                interest.status = value
                interest.status_word = status_text[len(prefix) :].strip()
                break
    date_match = INTEREST_DATE_RE.search(block)
    if date_match:
        interest.marked_at = date_match.group(1)
    rating_match = INTEREST_RATING_RE.search(block)
    if rating_match:
        interest.user_rating = int(rating_match.group(1))

    tail = block[rating_match.end() :] if rating_match else block
    tags_match = INTEREST_TAGS_RE.search(tail)
    if tags_match:
        interest.tags = tags_match.group(1).split()
        tail = tail[tags_match.end() :]
    comment_match = INTEREST_COMMENT_RE.search(tail)
    if comment_match:
        interest.comment = text(comment_match.group(1))
    return interest


def parse_photos_page(html: str) -> list[Photo]:
    """Parse a ``photos?type=R`` page into poster candidates (in page order)."""
    photos: list[Photo] = []
    for _data_id, block in PHOTO_ITEM_RE.findall(html):
        img = PHOTO_IMG_RE.search(block)
        if not img:
            continue
        name_match = PHOTO_NAME_RE.search(block)
        photos.append(
            Photo(
                photo_id=img.group(1),
                url=PHOTO_HOST + img.group(0),
                name=text(name_match.group(1)) if name_match else "",
            )
        )
    return photos


def upgrade_photo_size(url: str, size: str = PHOTO_LARGE) -> str:
    """Swap the size token in a Douban CDN URL (``m``/``l``/``s_ratio_poster``)."""
    return re.sub(r"/view/photo/[a-z_]+/", f"/view/photo/{size}/", url, count=1)


def subject_to_dict(subject: Subject) -> dict:
    """Serialize a parsed subject for the local detail cache."""
    return asdict(subject)


def subject_from_dict(data: dict) -> Subject:
    """Rebuild a :class:`Subject` from :func:`subject_to_dict` output."""
    payload = dict(data)
    interest = payload.pop("interest", None)
    subject = Subject(**payload)
    if interest is not None:
        subject.interest = Interest(**interest)
    return subject


def photo_url(photo_id: str, size: str = PHOTO_LARGE) -> str:
    """CDN URL for a photo id (``p480747492.jpg``)."""
    return f"{PHOTO_HOST}/view/photo/{size}/public/{photo_id}"


def minutes(value: str) -> int | None:
    """``142分钟`` / ``60分钟(E1-E2)`` → ``142`` / ``60``."""
    match = re.search(r"(\d+)\s*分钟", value or "")
    return int(match.group(1)) if match else None


def parse_int(value: str) -> int | None:
    """``30`` / ``30集`` → ``30``."""
    match = re.search(r"(\d+)", value or "")
    return int(match.group(1)) if match else None


def _first_date(value: str) -> str | None:
    """``2023-01-15(中国大陆) / 2023-02-01(美国)`` → ``2023-01-15``."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", value or "")
    return match.group(1) if match else None
