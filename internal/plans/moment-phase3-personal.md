---
title: Moment Plugin — Phase 3 Personal Features
created: 2026-07-30
updated: 2026-08-22
status: in-progress
tags: [moment, plugin, location, map, gallery, search, stats]
---

# Moment Plugin — Phase 3: Personal Features

## Goal

Add location-aware moments, map timeline, photo gallery, search
integration, and personal statistics to the Moment plugin.

## Status (2026-08-22)

**Location + Map done** (see `internal/moment-design.md` → Geo / Map Features;
implementation details were iterated in the git-ignored
`internal/moment-map-draft.md`, now folded back here).

| Area                   | State                                                                          |
| ---------------------- | ------------------------------------------------------------------------------ |
| Location + Map         | ✅ done                                                                        |
| Multi-image + captions | ✅ done (Phase 2); Grid/Masonry **cancelled** (G1)                             |
| Lightbox grouping      | ✅ done (G2) — per-moment `data-gallery`                                       |
| EXIF camera/date       | ✅ done (G3) — `meta.camera` / `meta.photo_date`, never overrides `date:`      |
| Stats page             | ✅ done (G4) — `/moments/stats/` (Mermaid + HTML bars + heatmap)               |
| Search indexing        | ✅ done — moment detail pages already in the search index                      |
| Search filter          | 🅿️ parked (G6) — needs custom JS; tag/archive cover browsing                   |
| City Activity Log      | 🅿️ parked (G5) — waits for the City Log PWA (Phase 0) export                   |
| JSON Feed              | ⬜ not started — RSS exists, JSON Feed v1 is a small follow-up                 |
| Auto-tag by location   | ⬜ not started — small (region probing exists)                                 |
| Streak statistics      | ⬜ not started — stats heatmap exists; longest-streak stat is a small addition |

Phase 3 remaining work is small and non-blocking: **JSON Feed**, **auto-tag
by location**, **longest-streak stat** (the two parked areas G5/G6 stay
parked until their triggers fire).

## Tasks

### Location Support ✅

- [x] Add `place`, `lng`, `lat`, `crs`, `region` fields to moment frontmatter
  (the original `location` field was split into `place` + coordinates)
- [x] Store location data in `Moment` dataclass (`has_geo` property)
- [x] Coordinate conversion: `crs: gcj02` → WGS-84 at parse time
  (`shared/gcj02.py`, ported from vine maps-cli)
- [x] Region auto-probing by bbox from the configured `regions` table
- [x] Display location badge on timeline + detail page (📍 place + tag emoji)
- [x] ~~Add location to RSS feed items~~ — **cancelled** (user: RSS must not
  contain map/geo info)

### Map Timeline ✅

- [x] Generate map page at `/moments/map/` showing moments with geo data
- [x] Use the **vine embeddable widget** (MapLibre + pmtiles) instead of
  Leaflet — fully static, no API keys
- [x] Cluster markers by location: repeated coords merge into `×N` markers
  (configurable `cluster.precision`); popup tabs recent `popup_max`
  moments and expands all same-coords moments in place
- [x] Link markers to moment detail pages
- [x] Region switching: buttons per region (with moments), `setBasemap` +
  per-region markers; `label` display names (shanghai → 上海)
- [x] Quantity control: per-region default `region_limit` (50) with a
  `加载全部` button
- [x] Detail-page popup dialog map (lazy widget import, fresh host per open)

### City Activity Log

- [ ] Integrate with city activity log data — **parked (G5)** until the City
  Log app (`city-log-project.md`, a separate PWA in Phase 0) ships an
  export; re-scoping to derive the log from moment geo data is an option
  if it ever gets prioritised
- [ ] Auto-tag moments based on location (region probing already implemented)
- [ ] Show activity streaks on calendar heatmap (CSS grid; no blocker)

### Multi-Image Gallery

- [x] Support multiple images in a single moment (repeatable `--image` +
  per-image captions → markdown images → thumbnail row; caption support
  from Phase 2)
- [x] ~~Grid / Masonry layout~~ — **cancelled** (Phase 2 decision 2026-08:
  keep the inline thumbnail row; see `arch/moment-phase2-usability.md`
  → Image Presentation). Reviving it needs a new decision
- [x] Lightbox prev/next **within one moment** — `_wrap_glightbox` adds
  `data-gallery="<source path without .md>"` per moment; GLightbox groups
  by that key, so prev/next only cycles the moment's own images
- [x] EXIF camera/date extraction — GPS already done (`exif_gps` fills
  `lng`/`lat`); `exif_camera_date` in `scripts/create_moment.py` reads
  Make/Model + DateTimeOriginal from the source at create time → stored
  in `meta.camera` / `meta.photo_date` (never the moment `date:` — the
  auto-meta path; `--time-from-exif` is the explicit opt-in to use that
  EXIF date as `date:`; explicit `--meta` wins). WebP preserves EXIF
  (verified; orientation is now baked into the pixels)

### Search Integration

- [x] Include moment content in MkDocs search index — already working: moment
  detail pages are normal build pages, so full text is indexed
  (`site/search/search_index.json` has 16 moment docs). Polish
  opportunity: the page title is the bare filename ("01 1530"); could
  default to the first content line
- [ ] Add moment-specific search filter — Material search has no built-in
  structured filter; needs custom JS (cost/benefit decision vs the tag
  page + archive already covering tag browsing)
- [ ] Search by tag, date range, content — same custom-JS dependency; the
  date-range part is the non-trivial one

### Statistics Page ✅

- [x] Generate `/moments/stats/` page (site base path is `/moments/` — the
  original plan wrote `/moment/stats/`, a typo)
  Generated in `on_post_build` like the map/archive pages; mermaid
  handling: div.mermaid (NOT pre.mermaid — Material's bundle owns
  pre.mermaid and would clash with the manual init) + the `pre` htmlmin
  attribute keeps newlines (mermaid's parser needs them); mermaid.min.js
  is injected by the template when present in site assets
- [x] Yearly/monthly posting frequency chart (Mermaid xychart-beta) —
  gap-filled (zero-activity months stay as empty bars), capped at the last
  24 months; re-renders with the dark theme when the site's color scheme
  toggles (Material sets the scheme on <body> — the MutationObserver and
  the heatmap dark CSS read/observe body's data-md-color-scheme)
- [x] Top tags bar chart (pure HTML bars — no mermaid dependency)
- [x] Posting streak calendar (per-year month×day heatmap grid, uniform
  31-day rows — short months keep empty gray cells; fixed-width rows keep
  grid auto-placement aligned)
- [x] Total moments, most active month, etc. (summary cards: total, with-
  image count, active years, most active month, date span)

### JSON Feed (Phase 2 companion)

- [ ] Generate `/moments/feed.json` alongside RSS (`/moments/feed.xml`)
- [ ] Follow JSON Feed v1 spec

## Notes

- Phase 3 is exploratory — features depend on actual usage patterns
- Map support should remain fully static (no API keys, no backend)
- Gallery layout may reuse existing `glightbox` integration
- Statistics can use Mermaid charts (already configured in theme)
- Reference: `local-draft.md` Section 20 for original specs

## Open Decisions (2026-08-22; G1/G5/G6 still open, G2–G4 resolved)

| #   | Topic                           | Status / Recommendation                                                                                       |
| --- | ------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| G1  | Grid/Masonry layout             | **Resolved — keep cancelled** (Phase 2 decision: inline thumbnail row kept)                                   |
| G2  | Lightbox group key              | **Implemented** — `data-gallery` = moment source path in `_wrap_glightbox`                                    |
| G3  | EXIF DateTimeOriginal semantics | **Implemented** — stored in `meta.camera`/`meta.photo_date`; `--time-from-exif` opts into using it as `date:` |
| G4  | Stats page Mermaid injection    | **Implemented** — div.mermaid (avoids Material's pre.mermaid component) + `pre` htmlmin                       |
|     |                                 | attr keeps newlines; mermaid.min.js injected by the template                                                  |
| G5  | City-Log data source            | **Parked** — revisit when the City Log PWA (Phase 0) ships an export                                          |
| G6  | Search filter scope             | **Parked** — tag/archive already cover browsing; revisit if search demand appears                             |
