"""Data models for the Moment plugin."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class PageType(Enum):
    TIMELINE = auto()
    PAGINATION = auto()
    MOMENT_DETAIL = auto()
    TAG_PAGE = auto()
    UNRELATED = auto()


@dataclass
class Moment:
    id: str  # e.g. "2026-07-30-1430"
    date: datetime  # from frontmatter
    slug: str  # e.g. "1430" or "home-lab"
    source_path: str  # relative to docs/, e.g. "moment/2026-07/30-1430.md"
    permalink: str  # e.g. "/moments/2026-07/30-1430/"
    content: str  # raw markdown (no frontmatter)
    html: str = ""  # rendered HTML, filled during on_page_markdown
    title: str = ""  # optional frontmatter title (used by RSS title fallback)
    tags: list[str] = field(default_factory=list)
    has_images: bool = False
    meta: dict[str, str | int] = field(
        default_factory=dict
    )  # freeform metadata dict (rendered via extra.moment.meta_fields)
    # --- geo (extra.moment.map) ---
    place: str = ""  # display text, e.g. "徐汇滨江某咖啡店"
    lng: Optional[float] = None  # WGS-84 longitude
    lat: Optional[float] = None  # WGS-84 latitude
    crs: str = "wgs84"  # authored coordinate system: "wgs84" | "gcj02"
    region: str = ""  # basemap region; probed from lng/lat bbox when empty
    emoji: str = ""  # marker emoji derived from tags via config tag_emoji
    popup_text: str = ""  # short plain-text excerpt (map popups)
    popup_image: str = ""  # first image URL (map popups)

    @property
    def has_geo(self) -> bool:
        """True when both coordinates are valid (WGS-84, post-conversion)."""
        return self.lng is not None and self.lat is not None


@dataclass
class Pagination:
    current_page: int
    total_pages: int
    total_items: int
    page_size: int
    has_prev: bool
    has_next: bool
    prev_url: Optional[str]
    next_url: Optional[str]
    items: list[Moment]
