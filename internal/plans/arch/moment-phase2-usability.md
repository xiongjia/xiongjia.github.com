---
title: Moment Plugin — Phase 2 Usability
created: 2026-07-30
archived: 2026-08-01
status: completed
tags: [moment, plugin, rss, tags, archive, opengraph]
---

# Moment Plugin — Phase 2: Usability

## Goal

Extend the Moment plugin with RSS feed, tag pages, archive, OpenGraph,
and other usability improvements to make it a complete microblog system.

## Foundation Fixes (do first — Phase 1 regressions)

Fix these two blocking base bugs before any Phase 2 feature work — otherwise
the tag feature is currently broken, and Archive / RSS would inherit the same
mistakes by copying the existing pattern.

- [x] **Fix `on_post_build` early return** (`plugin.py` ~L164)
  - Current: `if total_pages <= 1: return` sits before the pagination loop and
    skips tag page generation entirely. With moments ≤ `posts_per_page`
    (currently 2 ≤ 20) no tag pages are generated, but the timeline still emits
    tag links → all 404
  - Plan: the early return must guard only the pagination loop; tag pages (and
    later archive pages) generate independently, decoupled from pagination.
    Cover the 0 / 1 / N page cases
- [x] **Make `moment_base` config-driven** (hardcoded template bug)
  - Current: `moment_timeline.html` / `moment_detail.html` hardcode
    `{% set moment_base = "/moment" %}`, but `mkdocs.yml` sets
    `moment.path: moments` → all tag links point to `/moment/tag/...` (404)
  - Plan: inject `self.config["path"]` into the template context
    (e.g. `context["moment_base"]`), remove the hardcoded `{% set %}` from the
    templates; also fix the `path: moment` drift in the design doc
- [x] **Switch tag URLs to "literal dir + literal link"**
  - Current: tag page dirs use `quote(tag, safe="")` (e.g. `%E4%B8%AD`), template
    links use raw `{{ tag }}` (`中文`). Static servers like GitHub Pages decode
    the request URL and match literal file paths → Chinese tags 404
  - Plan: use the literal tag name for the dir (`site/moments/tag/中文/`) and the
    literal tag in links — naturally consistent; only minimally escape
    path-unsafe chars like `#` (fragment delimiter)
  - Suggested tag normalization: normalize whitespace/case, reject or replace
    dangerous chars like `/`

## Tasks

### Tags (shipped in Phase 1, but depends on foundation fixes)

- [x] Parse tags from frontmatter in `_parse_moment`
- [x] Display tags on Timeline and Detail pages
- [x] Generate tag listing pages at `/{moment_base}/tag/{tag}/` (only truly
  works after foundation fix #1)
- [x] Tag cloud on Timeline page
- [x] Regression check: tag pages still generate when `posts_per_page` exceeds
  the moment count (lock in with a test)

### RSS Feed

- [x] Implement `_build_rss(moments)` in plugin.py generating RSS 2.0 XML
- [x] Escape the HTML inside `<description>` (or use CDATA) so the feed stays
  valid XML
- [x] Title fallback: first line of content (strip markdown; fall through when
  the moment is image-only with no text line) → frontmatter `title` → date
- [x] Include full HTML in `<description>` (not an excerpt; includes
  glightbox-wrapped images)
- [x] Add `<enclosure>` for the first image in each moment
  - Extract the first image from `moment.html`, must handle the
    `<a><img>` structure produced by `_wrap_glightbox`
  - `length` from the source image file on disk
    (`docs/moments/<YYYY-MM>/...`), `type` inferred from the extension; skip
    `<enclosure>` when the source file is missing (e.g. remote images)
- [x] Generate `/{moment_base}/feed.xml` in `on_post_build` (config-driven
  path, not hardcoded)
- [x] Inject `<link rel="alternate" type="application/rss+xml">` into the
  Timeline page `<head>`: add `{% block extrahead %}` to `moment_timeline.html`
  (Material `base.html` has the block, `overrides/main.html` already uses it);
  feed URL built from `site_url` + config path
- [x] Add RSS config to the moment config schema (e.g. `feed: true` /
  `feed_description`)
- [x] All links in the RSS must be absolute URLs (`site_url` + permalink /
  image path)
- [x] Visible RSS icon link next to the Timeline title (shown only on the
  Timeline page, via the injected `feed_url`)

### Archive

- [x] Generate `/{moment_base}/archive/` page listing moments grouped by
  year/month (decoupled from pagination); dedicated `moment_archive.html`
- [x] Generate `/{moment_base}/<YYYY>/<MM>/` per-month archive pages (reuse
  `moment_timeline.html`)
  - URL naming note: moment detail dirs use a hyphenated `2026-07`
    (`/moments/2026-07/30-1430/`); the slash-style archive path
    `/<YYYY>/<MM>/` does not collide; finalized in the design doc
- [x] Add archive links to the tag cloud area on the Timeline page

### OpenGraph

- [x] Add `<meta property="og:title">`, `og:description`, `og:image` to detail
  pages: `{% block extrahead %}` on `moment_detail.html` (`{{ super() }}`
  keeps the overrides' existing meta), output only on MOMENT_DETAIL pages
  - og:title shares `_moment_title` with the RSS title fallback
    (first line stripped of markdown → frontmatter `title` → date)
- [x] Use the first line of content as og:description (strip markdown);
  fall back to timeline_description / site_description when the stripped
  first line is empty
- [x] Use the first image as og:image (if present) — absolute URL via
  `site_url`; **no og:image when there is no image** (og:image is a URL, it
  cannot fall back to text)
- [x] Add `<meta name="twitter:card">` tags: `summary_large_image` when an
  image exists, `summary` otherwise

### Previous / Next Navigation

- [x] Previous/next links in detail page template (already implemented)

### Image Presentation

- [x] Gallery layout: use glightbox lightbox (grouped prev/next already
  available via mkdocs-glightbox); **grid layout cancelled** — the existing
  inline thumbnail row is kept (decision 2026-08)
- [x] Add caption support
  - **Decision made (2026-08): option (a') custom markdown extension**
    (`pymdownx.caption` verified non-existent, do not use)
  - `_MomentFigureExtension` registered in `_render_content`'s `exts`:
    `![alt](src)` followed by a caption line → `<figure><figcaption>`;
    inline text on the same line is not treated as a caption; moment
    rendering always goes through `moment.html`, so mkdocs.yml untouched

### URL Slug Customization

- [x] **Decision made (2026-08): option (c) — drop per-moment URL slugs**
  - Background: the `slug` field is computed by `slug_from_filename` but never
    used anywhere; permalinks come from the file path (`plugin.py:305`) and the
    output URL is decided by MkDocs from `src_path`.
    ~~Option (a) mutating `file.url`/`file.dest_uri`~~ is not viable
    (`File.dest_uri`/`File.url` are read-only `cached_property` — source
    verified)
  - Option (c) scope: do not implement `fm.get("slug")` URL overrides; slug
    stays filename-only (`create_moment.py --slug` already exists);
    `_parse_moment`'s slug field stays as-is (`slug_from_filename`), no
    frontmatter override logic
  - If custom URLs are ever needed, re-evaluate (b') `File.generated`
    replacement (swap the File in `on_files`, URL changes, rendering pipeline
    kept) or (b'') generating detail pages entirely in `on_post_build`

### Draft Support

- [x] **Implemented inside the moment plugin, not just by extending
  `draft_filter.py`**
  - Background: draft_filter only removes files from the MkDocs `files`
    collection; the moment plugin `rglob`s the directory itself in its own
    `on_files` and never reads the `files` collection → a draft moment would
    show up in timeline/tag/pagination (with empty html) while its detail page
    is dropped → the link 404s
  - Plan: skip `draft: true` in `_parse_moment` / `on_files` (reuse
    `shared/frontmatter.has_draft_flag`), following the same
    `MKDOCS_INCLUDE_DRAFTS` env convention as draft_filter (visible in dev,
    excluded in prod)
  - Order: draft filtering before `_check_duplicate_permalinks` (so drafts do
    not interfere with the check)
- [x] Add a `--draft` flag to `create_moment.py` (writes `draft: true`
  frontmatter)

## Testing

- [x] Add mkdocs_moment unit/integration tests (currently `tests/` has no
  moment coverage; CI runs `pytest` + `mkdocs build`)
  - [x] `on_post_build`: tag pages still generate when moments ≤
    `posts_per_page` (locks in foundation fix #1)
  - [x] RSS: `_build_rss` output structure, title fallback chain, enclosure
    fields
  - [x] Draft: draft moment exclusion under both `MKDOCS_INCLUDE_DRAFTS`
    values
  - [x] Caption: custom extension works in `_render_content`
    (`![alt]` + caption line → figure)

## Notes

- RSS strategy: plugin-internal generation (option A), do not introduce
  mkdocs-rss-plugin (the site already has a root feed,
  `match_path: notes/posts/...`, no conflict with `/moments/feed.xml`)
- Tag/Archive pages all go through the refactored `on_post_build` (foundation
  fix #1 first)
- Template paths are driven by `moment_base` (config path injected) — no more
  hardcoded `/moment` anywhere
- The former `local-draft.md` reference (Section 19 RSS specs) is gitignored
  and was never committed — it does not exist; the inline spec above is the
  source of truth
- Decision log (2026-08): Slug = option (c) drop URL slugs; Caption =
  option (a') custom markdown extension; Gallery = keep glightbox lightbox,
  grid layout cancelled
- Design doc (`internal/moment-design.md`) drift synced (2026-08):
  `path: moments`, dropped nonexistent `on_nav` note, added RSS / archive /
  draft / caption sections
