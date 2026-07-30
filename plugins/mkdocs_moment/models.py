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
    permalink: str  # e.g. "/moment/2026-07/30-1430/"
    content: str  # raw markdown (no frontmatter)
    html: str = ""  # rendered HTML, filled during on_page_markdown
    tags: list[str] = field(default_factory=list)
    has_images: bool = False


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
