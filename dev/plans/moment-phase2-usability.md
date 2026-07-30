---
title: Moment Plugin — Phase 2 Usability
created: 2026-07-30
tags: [moment, plugin, rss, tags, archive, opengraph]
---

# Moment Plugin — Phase 2: Usability

## Goal

Extend the Moment plugin with RSS feed, tag pages, archive, OpenGraph,
and other usability improvements to make it a complete microblog system.

## Tasks

### RSS Feed

- [ ] Implement `_build_rss(moments)` in plugin.py generating RSS 2.0 XML
- [ ] Title fallback: content first line → frontmatter title → date
- [ ] Include full HTML in `<description>` (not excerpt)
- [ ] Add `<enclosure>` for first image in each moment
- [ ] Generate `/moment/feed.xml` in `on_post_build`
- [ ] Inject `<link rel="alternate" type="application/rss+xml">` into Timeline page `<head>`
- [ ] Add RSS config to moment config schema

### Tags (已完成标 ✅)

- [x] Parse tags from frontmatter in `_parse_moment`
- [x] Display tags on Timeline and Detail pages
- [x] Generate tag listing pages at `/moment/tag/{tag}/`
- [x] Tag cloud on Timeline page

### Archive

- [ ] Generate `/moment/archive/` page listing moments grouped by year/month
- [ ] Generate `/moment/2026/07/` per-month archive pages
- [ ] Add archive links to sidebar or tag cloud area

### OpenGraph

- [ ] Add `<meta property="og:title">`, `og:description`, `og:image` to detail pages
- [ ] Use moment content first line as og:description
- [ ] Use first image as og:image (if present)
- [ ] Add `<meta name="twitter:card">` tags

### Previous / Next Navigation

- [x] Previous/next links in detail page template (already implemented)

### Image Presentation

- [ ] Improve image gallery layout (lightbox grouping, grid)
- [ ] Add caption support

### URL Slug Customization

- [ ] Support `slug:` in frontmatter to override auto slug from filename
- [ ] Update `_parse_moment` to prefer `fm.get("slug")`

### Draft Support

- [ ] Support `draft: true` in moment frontmatter
- [ ] Extend `draft_filter.py` to exclude moment drafts in production builds

## Notes

- RSS strategy: Plugin-internal generation (方案 A), not mkdocs-rss-plugin
- Tag pages already work via `on_post_build` (Phase 1 shipped this)
- Archive pages follow the same `on_post_build` pattern as tag pages
- Reference: `local-draft.md` Section 19 for detailed RSS specs
