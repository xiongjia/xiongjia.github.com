---
title: Moment Plugin — Phase 3 Personal Features
created: 2026-07-30
tags: [moment, plugin, location, map, gallery, search, stats]
---

# Moment Plugin — Phase 3: Personal Features

## Goal

Add location-aware moments, map timeline, photo gallery, search
integration, and personal statistics to the Moment plugin.

## Tasks

### Location Support

- [ ] Add `location`, `lat`, `lng` fields to moment frontmatter
- [ ] Store location data in `Moment` dataclass
- [ ] Display location badge on detail page (e.g. "📍 Shanghai")
- [ ] Add location to RSS feed items

### Map Timeline

- [ ] Generate map page at `/moment/map/` showing moments with geo data
- [ ] Use Leaflet.js (static map tiles via PMTiles or similar)
- [ ] Cluster markers by location/time
- [ ] Link markers to moment detail pages

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
