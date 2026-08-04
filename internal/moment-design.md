# Moment Plugin — Design Document

> Short-form micro-posts (like Twitter/X) powered by MkDocs + Markdown, fully
> static with zero runtime dependencies. Part of the recycle.bin personal site.

## Overview

Moment is a MkDocs hook that provides a personal micro-blog timeline alongside
the existing blog system. Each Moment is a single Markdown file. The plugin
discovers, parses, renders, and generates static HTML pages — no database, no
CMS, no JavaScript runtime.

````
Markdown                         Static HTML
  │                                  │
```text
Source (docs/moments/)
├── moment-data.yaml        ← UI labels
├── index.md                ← Timeline placeholder
└── 2026-07/
    ├── 30-2136.md          ← One moment

Built (site/moments/)
├── moment.css
├── index.html              ← Timeline
├── 2026-07/
│   └── 30-1430/
│       └── index.html      ← Detail
├── page/2/index.html       ← Pagination
├── tag/
│   ├── rust/index.html     ← Tag filter
│   └── general/index.html
├── archive/index.html      ← Year/month archive
├── 2026/07/index.html      ← Per-month page
└── feed.xml                ← RSS
````

````

## File Format

### Moment file

```markdown
---
date: 2026-07-30 14:30
tags:
  - rust
  - homelab
---

今天用 Rust 写了一个 TUI 工具，效果不错。

![Screenshot](./screenshot.webp)
````

| Field   | Required | Format                                     |
| ------- | -------- | ------------------------------------------ |
| `date`  | ✅       | `YYYY-MM-DD HH:MM`, `YYYY-MM-DD`, ISO 8601 |
| `tags`  | ❌       | YAML list (displayed as `#tag` links)      |
| `draft` | ❌       | `true` — hidden in production builds       |

Draft moments follow the same `MKDOCS_INCLUDE_DRAFTS` env convention as
`plugins/draft_filter.py`: excluded in production builds, kept in dev
(`MKDOCS_INCLUDE_DRAFTS=true mkdocs serve`).

### File naming

```
docs/moments/YYYY-MM/DD-HHMM.md                  # standard
docs/moments/YYYY-MM/DD-HHMM-slug.md             # with optional slug
docs/moments/YYYY-MM/DD-HHMM-SS.md               # precise to seconds
docs/moments/YYYY-MM/DD.md                        # pure date (one per day)
```

Year and month come from the directory name; filename only contains
`DD-HHMM`. This avoids repeating the year/month in the filename while
keeping the directory per-month for manageable file counts.

### Image placement

Images go in the same month directory, referenced with `./` paths.
Plugin auto-converts relative paths to site-absolute URLs during
Markdown -> HTML rendering.

A caption is added by putting a plain-text line right after the image
line — the plugin's custom markdown extension wraps the pair in
`<figure><figcaption>` (inline text on the same line is not a caption).

```
moment/2026-07/
├── 30-1430.md
├── 30-1430-screenshot.webp    ← unique naming to avoid conflicts
└── 30-2130-photo.jpg
```

## Architecture

### Component layout

```
plugins/
├── __init__.py                      # makes plugins/ a package
├── draft_filter.py
├── mermaid_assets.py
└── mkdocs_moment/
    ├── __init__.py                  # hook entry point, delegates to plugin
    ├── plugin.py                    # MomentPlugin class
    ├── models.py                    # Moment, Pagination, PageType dataclasses
    ├── assets/
    │   └── css/
    │       └── moment.css
    └── templates/
        ├── moment_timeline.html     # Timeline / tag / pagination page
        ├── moment_detail.html       # Single moment detail page
        └── moment_pagination.html   # Pagination nav fragment
```

### Registration

Registered as a MkDocs **hook** (not a plugin) to avoid packaging
overhead:

```yaml
# mkdocs.yml
hooks:
  - plugins/moment_hook.py
```

Config is read from `extra.moment`:

```yaml
extra:
  moment:
    path: moments
    posts_per_page: 20
    timeline_title: Moment
    timeline_description: 日常记录
    sort: desc
    feed: true              # RSS feed at /moments/feed.xml (default: true)
    feed_description: ''    # RSS channel description (falls back to timeline_description)
    timezone: Asia/Shanghai # RSS pubDate tz; wall-clock times are authored in this zone
```

### UI Labels (Chinese/English separation)

No Chinese text in Python code. All UI strings are in
`docs/moments/moment-data.yaml`:

```yaml
labels:
  timeline_title: Moment
  timeline_description: 日常记录
  empty_state: 暂无内容
  older: ← Older
  newer: Newer →
  back_to_timeline: ↑ Timeline
```

Labels are loaded in `on_config` and injected into template context.

## MkDocs Lifecycle

| Event              | Role                                                             |
| ------------------ | ---------------------------------------------------------------- |
| `on_config`        | Read config, register templates + CSS, load labels, init state   |
| `on_files`         | Scan `moment/` recursively, parse all `.md` files (skip drafts)  |
| `on_page_markdown` | Classify page type, strip frontmatter, render HTML, hide sidebar |
| `on_page_context`  | Inject pagination / moment / feed / archive / OG data            |
| `on_post_build`    | Generate pagination/tag/archive pages + RSS feed, copy CSS       |

### Classifying pages (in `on_page_markdown`)

```
moment/index.md                   → PageType.TIMELINE
moment/2026-07/30-1430.md         → PageType.MOMENT_DETAIL
any other file                    → PageType.UNRELATED
```

### Rendering pipeline

```
Markdown file
    │
    ▼
on_page_markdown
    ├── Strips YAML frontmatter
    ├── Converts Markdown → HTML via markdown library
    │   (same extensions as mkdocs.yml)
    ├── Auto-rewrites relative image paths → absolute URLs
    │   (./screenshot.webp → /moments/2026-07/screenshot.webp)
    └── Stores HTML in Moment.html for Timeline/tag reuse
```

## Pages

### Timeline (`/moments/`)

- Sorted by date DESC (newest first)
- Shows time → content → tags per entry
- Tag cloud at top showing all available tags
- RSS icon link next to the title (when the feed is enabled)
- Pagination at bottom when count > posts_per_page

### Detail (`/moments/YYYY-MM/DD-HHMM/`)

- Single moment view with prev/next navigation
- Tags displayed below content
- Giscus comments via `{% include "partials/comments.html" %}`
- Sidebar hidden via `page.meta.hide = ["navigation"]`
- OpenGraph meta in `<head>` (`og:title` / `og:description` / `og:image` when
  the moment has one, `twitter:card`: `summary_large_image` or `summary`)

### Tag filter (`/moments/tag/{tag}/`)

- Generated in `on_post_build` for each unique tag
- Reuses `moment_timeline.html` template with filtered items
- Shows only moments with that tag

### Pagination (`/moments/page/N/`)

- Generated in `on_post_build` when total > posts_per_page
- Reuses `moment_timeline.html` with paginated items
- Uses cached `_jinja_env` from `on_page_context`

### Archive

- `moment_archive.html` index at `/moments/archive/`, groups moments by
  year/month (newest first)
- Per-month pages at `/moments/<YYYY>/<MM>/` reuse `moment_timeline.html`;
  the slash-separated path does not collide with hyphenated detail URLs
  (`/moments/2026-07/30-1430/`)
- Entry link shown under the tag cloud on the Timeline page

## Template System

All templates extend Material's `main.html` via `{% extends "main.html" %}`,
ensuring theme consistency (header, footer, search, palette).

```
main.html (Material)
    │
    ├── moment_timeline.html    (Timeline, tag, pagination, month pages)
    │       └── moment_pagination.html  (included fragment)
    │
    ├── moment_archive.html     (Archive index)
    │
    └── moment_detail.html      (Detail page)
            └── partials/comments.html  (Giscus)
```

Templates are registered by setting `page.meta["template"]` in
`on_page_markdown`. The plugin's template directory is registered in
`config.theme.dirs` during `on_config`.

## CSS

Single file `moment.css`, auto-copied to `site/moments/moment.css` during
`on_post_build`. Uses `.moment-*` namespace to avoid conflicts with
Material theme. CSS variables reference Material's theme variables for
automatic light/dark mode support.

## Comments (Giscus)

Moment detail pages set `page.meta["comments"] = True`, which triggers
Giscus loading via `overrides/partials/comments.html`. Each moment gets
its own comment thread based on URL `pathname` mapping. No comment
thread = no GitHub Discussion created (zero overhead).

## Tags

- Parsed from frontmatter `tags:` list
- Displayed as `#tagname` links on Timeline and Detail pages
- Tag cloud at top of Timeline showing all tags
- Tag pages generated at `/moments/tag/{tag}/` via `on_post_build`
- Tag URLs use literal tag names (no percent-encoding) — links in templates
  use the same `tag_segment()` helper as the generator, so Chinese/emoji tags
  resolve as literal dirs

## Pagination

Generated in `on_post_build` to avoid polluting the repository with
placeholder `.md` files. Shares the same `moment_timeline.html` template
as the Timeline page, with different `pagination` context data.

Jinja2 environment is cached from `on_page_context`:

```python
self._jinja_env = config.theme.get_env()
self._nav = nav
self._base_url = context.get("base_url", "")
```

## Configuration Reference

```yaml
extra:
  moment:
    path: moments                   # Source directory under docs/
    posts_per_page: 20              # Timeline entries per page
    timeline_title: Moment          # Timeline page <h1>
    timeline_description: 日常记录  # Timeline page subtitle
    sort: desc                      # desc / asc
    feed: true                      # RSS feed at /moments/feed.xml (default: true)
    feed_description: ''            # RSS channel description (falls back to timeline_description)
    timezone: Asia/Shanghai         # RSS pubDate tz (default: Asia/Shanghai)
    minify: true                    # Minify generated pages + moment.css; follows the site minify plugin flags when loaded (default: true)
    htmlmin_opts: {}                # Per-option htmlmin overrides (default: mkdocs-minify-plugin defaults)
```

## Dependencies

| Package       | Usage                                                                                                         |
| ------------- | ------------------------------------------------------------------------------------------------------------- |
| mkdocs        | Static site generator                                                                                         |
| PyYAML        | Parse frontmatter and labels                                                                                  |
| markdown      | Runtime rendering (moment HTML) + caption extension                                                           |
| htmlmin2      | Minify generated pages (pagination/tag/archive/month)                                                         |
| csscompressor | Minify moment.css                                                                                             |
| (built-in)    | `pathlib`, `re`, `os`, `sys`, `math`, `datetime`, `email.utils`, `xml.etree`, `zoneinfo`, `logging`, `typing` |
| Giscus        | Comment system (loaded client-side)                                                                           |

## File Tree

```
docs/moments/
├── index.md                         # Timeline placeholder
├── moment-data.yaml                 # UI labels (i18n)
├── 2026-07/
│   ├── 30-2136.md
│   └── screenshot.webp
└── 2026-06/
    └── ...
```

## Development

```bash
# Create a new moment
uv run poe create-moment "Content text"
uv run poe create-moment "Content" --image photo.jpg
uv run poe create-moment "Content" --draft   # hidden in production

# Preview
uv run poe server       # http://localhost:8000/moments/

# Build
uv run poe build

# Lint
uv run poe lint-py
```

## Design Decisions

| Decision                   | Rationale                                                        |
| -------------------------- | ---------------------------------------------------------------- |
| Hook not plugin            | Avoid packaging overhead (no egg-info, no entry points)          |
| Config in `extra.moment`   | Follows existing convention (`extra.images`, `extra.comments`)   |
| Per-month directories      | 12 dirs/year vs 52 for weekly; intuitive ("July's posts")        |
| Filename without year      | Year/month already in directory, no repetition                   |
| `on_post_build` pagination | No placeholder `.md` files in repo                               |
| Absolute image paths       | `moment.html` is shared between Timeline and tag pages           |
| Chinese labels in YAML     | Zero Chinese text in Python code (follows health macros pattern) |
