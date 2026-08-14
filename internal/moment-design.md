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

Wrote a TUI tool in Rust today — works nicely.

![Screenshot](./screenshot.webp)
````

| Field       | Required | Format                                                                                   |
| ----------- | -------- | ---------------------------------------------------------------------------------------- |
| `date`      | ✅       | `YYYY-MM-DD HH:MM`, `YYYY-MM-DD`, ISO 8601                                               |
| `tags`      | ❌       | YAML list (displayed as `#tag` links)                                                    |
| `draft`     | ❌       | `true` — hidden in production builds                                                     |
| `place`     | ❌       | Location display text (geo, see Geo/Map)                                                 |
| `lng`/`lat` | ❌       | WGS-84 coordinates, must be a pair (geo)                                                 |
| `crs`       | ❌       | `wgs84` (default) or `gcj02` (auto-converted, geo)                                       |
| `region`    | ❌       | Basemap region; auto-probed by bbox (geo)                                                |
| `meta`      | ❌       | Freeform metadata dict rendered via `extra.moment.meta_fields` (see Structured Metadata) |

Example with metadata:

```markdown
---
date: 2026-08-01 12:00
tags:
  - food
meta:
  name: Old Shanghai Noodle House
  rating: 4
---

Had the scallion-oil noodles today — pretty good.
```

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
    timeline_description: Daily life
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
  timeline_description: Daily life
  empty_state: Nothing yet
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

## Structured Metadata

Moments can carry a small freeform metadata dict in frontmatter, rendered as
label/value pairs on the timeline, detail, archive and map-page feed entries
(and in map marker popups). The schema is
driven by `extra.moment.meta_fields` in `mkdocs.yml` — keyed by category tag,
so adding a new category later only means adding one config block (no code
changes).

```yaml
meta_fields:
  food:
    - { key: name, label: Restaurant, type: text }  # restaurant name
    - { key: rating, label: Rating, type: rating }   # 1–5 stars
  film:
    - { key: name, label: Cinema, type: text }
    - { key: rating, label: Rating, type: rating }
```

- `key` — frontmatter key inside the moment's `meta:` block.
- `label` — display label (Chinese OK); falls back to the key when empty.
- `type` — `text` (default) or `rating` (renders 1–5 stars, amber-filled).

### Rating system

Ratings use a **1–5 integer star scale** (Dianping-style).
Suggested semantics — adjust freely, the site only validates the range:

| Rating | Meaning                              |
| ------ | ------------------------------------ |
| ★      | Avoid — not recommended              |
| ★★     | Mediocre — only if you're passing by |
| ★★★    | Average — okay, no strong opinion    |
| ★★★★   | Recommended — worth a visit          |
| ★★★★★  | Highly recommended — would go again  |

**Recording granularity: one visit = one moment.** Each restaurant/cinema
visit gets its own moment carrying that visit's rating; going back to the
same place with a different rating means writing another moment (moments at
the same coordinates automatically cluster into a ×N marker on the map).

**Marking** — two equivalent ways:

1. Frontmatter (hand-written / `poe server` editing):

   ```markdown
   ---
   date: 2026-08-15 12:00
   tags:
     - food
   meta:
     name: Old Shanghai Noodle House
     rating: 4
   ---
   ```

1. CLI: `--meta KEY=VALUE`, repeatable — integer strings stay ints in YAML,
   other values are double-quoted automatically:

   ```bash
   uv run poe create-moment "Scallion-oil noodles were good" --meta name="Old Shanghai Noodle House" --meta rating=4
   ```

**Rules / display**:

- `rating` must be an integer in 1..5 (numeric strings like `"4"` are
  coerced). Anything else — `0`, `6`, `3.5`, `abc` — is hidden with a build
  warning instead of rendering garbage stars.
- The field is optional: omit `meta.rating` and nothing renders for it.
- Display: filled stars `★★★` are amber, the remainder `☆☆` gray (theme
  variables, auto dark-mode); `title`/`aria-label` carry `N/5` for
  accessibility.
- A moment without a `rating` key in the schema or without `meta` renders no
  metadata block at all.

### Examples

**1. Restaurant visit with rating (hand-written frontmatter)**

```markdown
---
date: 2026-08-15 12:00
tags:
  - food
meta:
  name: Old Shanghai Noodle House
  rating: 4
---

Scallion-oil noodles were great — chewy noodles, but the queue was long.
```

**2. Same restaurant, second visit, different rating (a separate moment)**

```markdown
---
date: 2026-08-22 18:30
tags:
  - food
meta:
  name: Old Shanghai Noodle House
  rating: 3
---

The braised pork was too salty this time — not as good as last visit.
```

**3. Name only, no rating yet (`rating` is optional)**

```markdown
---
date: 2026-08-30 19:00
tags:
  - food
meta:
  name: New Ramen Shop
---

Stopped by to try it — no strong opinion yet, will rate later.
```

**4. Cinema (`film` category) + geo — meta and geo compose**

```markdown
---
date: 2026-09-01 20:30
tags:
  - film
meta:
  name: Daguangming Cinema
  rating: 5
place: Nanjing West Road
lng: 121.47
lat: 31.23
---

The IMAX experience was stunning — highly recommended!
```

**5. Same content via CLI (equivalent to example 1)**

```bash
uv run poe create-moment "Scallion-oil noodles were good" --meta name="Old Shanghai Noodle House" --meta rating=4 --time "12:00"
```

### Schema rules

- The **first tag that yields metadata items** wins (same rule as the map
  `tag_emoji` table; a matching tag whose fields are all missing from `meta`
  falls through to the next tag), so a moment never renders conflicting
  schemas.
- Only configured fields are shown; extra `meta` keys the schema does not
  know are ignored.
- Duplicate field keys inside one category are dropped with a build warning
  (the first definition wins).
- Map popups show the restaurant/cinema name: the field whose `key` is
  `name` when the schema defines one, else the first text field; the rating
  comes from the first `rating`-type field.
- No schema configured, or no tag matches → nothing renders (feature fully
  off by default).

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
    timeline_description: Daily life   # Timeline page subtitle
    sort: desc                      # desc / asc
    feed: true                      # RSS feed at /moments/feed.xml (default: true)
    feed_description: ''            # RSS channel description (falls back to timeline_description)
    timezone: Asia/Shanghai         # RSS pubDate tz (default: Asia/Shanghai)
    minify: true                    # Minify generated pages + moment.css; follows the site minify plugin flags when loaded (default: true)
    htmlmin_opts: {}                # Per-option htmlmin overrides (default: mkdocs-minify-plugin defaults)
    meta_fields:                    # Structured metadata schema (see "Structured Metadata")
      food:
        - { key: name, label: Restaurant, type: text }
        - { key: rating, label: Rating, type: rating }
      film:
        - { key: name, label: Cinema, type: text }
        - { key: rating, label: Rating, type: rating }
    # --- Geo / Map (see "Geo / Map Features" below) ---
    map:
      enabled: true                 # false = whole geo feature disabled (default: absent = disabled)
      widget_js: https://…/vine/widget/map-widget-<hash>.js
      widget_css: https://…/vine/widget/map-widget-<hash>.css
      pmtiles_prefix: pmtiles://https://…/vine/pmtiles/
      glyphs_url: https://…/vine/glyphs/{fontstack}/{range}.pbf
      default_region: shanghai
      regions:
        shanghai: { bbox: [120.8, 30.6, 122.2, 31.8], center: [121.5, 31.2], zoom: 12, label: Shanghai }
        tokyo:    { bbox: [139.4, 35.4, 140.2, 35.9], center: [139.8, 35.65], zoom: 12, label: Tokyo }
      tag_emoji:
        film: 🎬
        food: 🍽️
      attribution: "© recycle.bin · Protomaps"
      hide_attribution: true        # hide the bottom-right attribution control
      cluster:
        precision: 0.001            # coords snapped for merging (~100m)
        popup_max: 3                # tabs in a merged-marker popup
        region_limit: 50            # default moments per region; "load all" past this
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
uv run poe create-moment "Content" --meta name="Old Shanghai Noodle House" --meta rating=4

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

## Geo / Map Features

> Location-aware moments: a static map page + per-moment popup dialogs built on
> the [vine](https://github.com/xiongjia/vine) embeddable MapLibre widget
> (pmtiles basemaps served from R2). No API keys, fully static.

### Frontmatter

```yaml
---
date: 2026-08-01 15:30
place: A café by the Xuhui riverfront  # display text
lng: 121.48             # coords (system per crs)
lat: 31.16
crs: gcj02              # wgs84 (default) | gcj02 (Amap/Baidu → auto-converted to WGS-84)
region: shanghai        # optional; probed from lng/lat bbox when omitted
---
```

- `lng`/`lat` must be a pair; out-of-range values are ignored with a warning.
- `crs: gcj02` is converted at parse time by `shared/gcj02.py` (ported from
  vine's maps-cli; verified against `121.48,31.16 → 121.475504,31.161994`).
- Region bbox probing falls back to `default_region`.
- Marker emoji is derived from tags via the configured `tag_emoji` table (no
  `mark` field); `film → 🎬`, `food → 🍽️`, default `📍`.

### Rendering

- **Timeline**: geo moments show a `📍 place` + emoji **button** that opens the
  same popup dialog as the detail page (no navigation to the map page); the
  header row shows `📚 Archive · [map icon] Map` and an `All tags`
  `<details open>` panel below.
- **Detail**: a `📍` badge opens a **dialog** map (native `<dialog>` + backdrop)
  centred on the moment's marker (POI zoom). The widget is `import()`ed lazily
  and each open swaps in a fresh host element + destroys the previous instance
  (guards against duplicate maps / stacked attribution controls). The dialog
  logic lives in one shared module, `assets/js/moment-dialog.js`, used by both
  the detail and timeline pages (markers read the moment data from
  `data-map-toggle` buttons). The dialog stays robust against dead-button
  failure modes: the loading lock resets on dialog close (a mid-load close
  never strands later clicks), `import()` races a 15 s timeout so a hung CDN
  can't silently kill the button, an `isConnected` guard skips rendering into
  a host that was closed while loading, and a WebGL pre-check shows a clear
  message instead of a blank box when the browser has no WebGL.
- **Map page `/moments/map/`** (`on_post_build`): one map per page.
  - The widget is `import()`ed lazily with a 15 s timeout (like the dialog),
    so a CDN failure or a missing WebGL context shows a fallback in the
    canvas instead of killing the whole module — the category filters and
    the feed below stay functional.
  - Opens **focused on the most recent activity** (latest cluster coords,
    zoom ≥ 13) so the map is never lost; region switching re-focuses the new
    region's latest activity.
  - Region buttons (only regions with moments; `label` display names),
    switching swaps the basemap via `setBasemap` + that region's markers.
  - Repeated coordinates are **clustered** (coords floored to `precision`); a
    merged marker shows `×N` + the latest emoji; its popup tabs the most recent
    `popup_max` moments (pure-CSS radio) and expands **all** same-coords
    moments in place via a `<details>` toggle.
  - Each region renders its most recent `region_limit` moments by default; a
    `Load all` button loads the rest.
  - **Category filter**: every geo moment gets a category — the first tag in
    the configured `tag_emoji` table, else a default `Other` bucket. Checkboxes
    (all on by default) filter markers + the list client-side; a merged marker
    whose remaining items drop to one is rebuilt from that item (re-centering
    on its precise coords) so labels/counts/popups always match the filtered
    view.
  - Below the map an **All Timeline feed** (`moment_list`, newest first)
    lists EVERY geo moment across all regions — full rendered content
    (`.moment-entry` markup from moment.css, thumbnails capped at 150px like
    the timeline, glightbox anchors left as plain links since this page has
    no lightbox JS) plus structured metadata (restaurant/cinema name +
    rating stars, same `.moment-meta` block as the timeline), time link and
    `#tags` — filtered by the same category checkboxes (independent of the
    current region / load-all state). Marker popups show the name + rating
    too (single markers and cluster tabs/header). No geo/place badge: the
    location is already a marker on the map right above, and the timeline's
    clickable place button would be a dead control here.

### External resources

- Widget bundle + pmtiles + glyphs are served from the vine R2 bucket
  (`widget_js`/`widget_css` point at content-hashed files — update on vine
  release). The bundle externalizes react/maplibre/pmtiles as esm.sh URLs
  (~8 KB entry).
- CORS: the R2 allow-list must include the site origin and the dev server
  (`http://localhost:8000`); changing `SITE_URL` requires updating R2 CORS.

### Lifecycle notes

- `_parse_moment` reads geo fields only when `map.enabled`; geo is skipped
  entirely when disabled (zero regression).
- `_render_map_page` / `_build_map_region_data` / `_cluster_moments` build the
  clustered per-region marker data; templates `moment_map.html` and
  `moment_detail.html` host the widget scripts.
- `scripts/create_moment.py` supports `--place/--lng/--lat/--crs/--region`
  (`--crs gcj02` prints the converted WGS-84 coords).
