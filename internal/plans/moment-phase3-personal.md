---
title: Moment Plugin — Phase 3 Personal Features
created: 2026-07-30
updated: 2026-08-09
status: in-progress
tags: [moment, plugin, location, map, gallery, search, stats]
---

# Moment Plugin — Phase 3: Personal Features

## Goal

Add location-aware moments, map timeline, photo gallery, search
integration, and personal statistics to the Moment plugin.

## Status (2026-08-09)

**Location + Map done** (see `internal/moment-design.md` → Geo / Map Features;
implementation details were iterated in the git-ignored
`internal/moment-map-draft.md`, now folded back here). Gallery / Search /
Stats / City-Activity-Log / JSON-Feed are **not started**.

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

- [ ] Integrate with city activity log data (Phase 3 expansion)
- [ ] Auto-tag moments based on location
- [ ] Show activity streaks on calendar heatmap

### Multi-Image Gallery

- [ ] Support multiple images in a single moment
- [ ] Grid / Masonry layout for image-heavy moments
- [ ] Lightbox navigation (prev/next within gallery)
- [ ] EXIF data extraction (date, camera, GPS)

### Search Integration

- [ ] Include moment content in MkDocs search index
- [ ] Add moment-specific search filter
- [ ] Search by tag, date range, content

### Statistics Page

- [ ] Generate `/moment/stats/` page
- [ ] Yearly/monthly posting frequency chart (Mermaid)
- [ ] Top tags bar chart
- [ ] Posting streak calendar
- [ ] Total moments, most active month, etc.

### JSON Feed (Phase 2 companion)

- [ ] Generate `/moment/feed.json` alongside RSS
- [ ] Follow JSON Feed v1 spec

## Notes

- Phase 3 is exploratory — features depend on actual usage patterns
- Map support should remain fully static (no API keys, no backend)
- Gallery layout may reuse existing `glightbox` integration
- Statistics can use Mermaid charts (already configured in theme)
- Reference: `local-draft.md` Section 20 for original specs
