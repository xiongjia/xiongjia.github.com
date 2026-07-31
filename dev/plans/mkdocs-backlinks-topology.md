---
title: MkDocs Bidirectional Links & Topology Graph
created: 2026-07-31
tags: [mkdocs, plugin, backlinks, graph, mermaid, python]
---

# MkDocs Bidirectional Links & Topology Graph

## Goal

Add bidirectional navigation to the MkDocs site:

1. **双向链接跳转 (Backlinks)** — every doc page shows a "反向链接" section listing all
   pages that link to it, so readers can jump between linked docs in both directions.
1. **双向链拓扑图 (Topology Graph)** — visualize the link structure as an interactive
   topology graph (Mermaid flowchart, already bundled via the `mermaid2` plugin), both
   per-page (local neighborhood) and site-wide (global overview page).

Build this as a custom MkDocs hook (`plugins/backlinks.py`), following the existing
hook pattern (`draft_filter.py`, `snippet_include.py`, `mermaid_assets.py`).

## Current State

```
mkdocs.yml
├── hooks:  mermaid_assets.py, snippet_include.py, draft_filter.py, moment_hook.py
└── plugins: minify, search, macros, mermaid2(10.9.0, self-hosted mermaid.min.js),
             drawio, glightbox, meta, rss, tags, blog
```

- **Forward links only** — MkDocs/Material resolves relative links natively, but there
  is no inverse (backlink) index; readers cannot discover which docs reference a page.
- **mermaid2 available** — self-hosted `assets/javascripts/mermaid.min.js`, so a graph
  feature needs no new JS dependency; nodes can be clickable (`click nodeId "url"`).
- **Relative links convention** — all internal links are relative paths (per AGENTS.md),
  which makes edge extraction and URL resolution straightforward.
- **Draft/blog interplay** — `draft_filter` hides drafts (except blog posts, handled by
  the blog plugin); the link index must exclude drafts so graphs never point to missing
  pages. Blog posts (`notes/posts/`) and moments should be excluded from the graph by
  default to reduce noise.

## Design

### Link index pipeline

1. **Pass 1 (`on_files`)** — collect all markdown files, read frontmatter (`title`,
   `draft`, section), build a `page_url → (title, path, section)` map, apply
   include/exclude globs (default: all of `docs/notes/*`, exclude `notes/posts/**` and
   drafts).
1. **Pass 2 (`on_page_markdown`)** — extract `[text](url)` links from raw markdown
   (regex or python-markdown tree), resolve relative URLs against `page.file.url`,
   skip external (`http://`/`https://`), anchor-only (`#…`), and self-links; record
   edge `(source → target)`.
1. **Index build** — after all pages are processed, invert edges into
   `target → [backlink sources]`.
1. **Per-page injection** — append to each page's markdown:
   - a **Backlinks section** (HTML list of titles → links), hidden when empty;
   - a **neighborhood graph** (```` ```mermaid ```` flowchart, default depth 1:
     current page + direct neighbors, clickable nodes).

### Topology graph

- **Per-page**: 1-hop neighborhood around the current page — readers see where the page
  sits in the doc network and jump anywhere in one click.
- **Global**: an auto-generated virtual page `notes/link-graph.md` (added in `on_files`,
  content generated at build) showing the full graph of included sections, optionally
  clustered by section.
- **Rendering**: Mermaid flowchart (`graph LR`), ASCII-safe node IDs (URL path), labels
  = page titles; `click nodeId "url"` for navigation. Reuses the existing `mermaid2`
  plugin — no new JS/CSS framework.
- **Interop spike required**: verify event ordering (hook `on_page_markdown` vs
  `mermaid2`'s) so injected mermaid blocks are converted to `<pre class="mermaid">` and
  JS is loaded; fallback is injecting `<pre class="mermaid">` in `on_post_page` +
  `mermaid.run()`.

### Config

Hooks here have no schema; keep config simple and consistent with repo style
(`extra:` in mkdocs.yml or module constants + env vars):

```yaml
extra:
  backlinks:
    enabled: true
    include: ["notes/*"]        # globs relative to docs_dir
    exclude: ["notes/posts/**", "moment/**"]
    max_backlinks: 20           # cap per page, "all" for unlimited
    graph:
      enabled: true
      depth: 1                  # neighborhood depth for per-page graph
      layout: "lr"              # mermaid flowchart direction
      max_nodes: 60             # safety cap for large sections
      global_page: "notes/link-graph.md"
```

## Tasks

### Phase 0: Spike & Design

- [ ] **Spike: event ordering & mermaid interop**

  - Determine order of hook `on_page_markdown` vs `mermaid2` `on_page_markdown`
  - Confirm injected ```` ```mermaid ```` blocks render with self-hosted `mermaid.min.js`
  - Verify `click nodeId "url"` navigation works (target `_self`, relative URLs)
  - Decide final injection point (on_page_markdown append vs on_post_page HTML)
  - Deliverable: spike notes appended to this plan

- [ ] **Link extraction approach**

  - Compare markdown link regex vs python-markdown tree traversal
  - Confirm relative URL resolution (`os.path.relpath` against `page.file.url` dir)
  - Handle: code blocks/fences (skip), image links `![alt](url)`, link-reference style
  - Deliverable: extraction approach selected

- [ ] **Scope & config design**

  - Define include/exclude defaults; reuse draft detection from `draft_filter.py`
  - Decide config location (`extra.backlinks`) and CLI override for local dev
  - Deliverable: config spec in this plan

### Phase 1: Backlinks (双向链接跳转)

- [ ] **Build page URL map (`on_files`)**

  - Iterate `config.files`, filter markdown only, read frontmatter title/draft
  - Apply include/exclude globs; exclude drafts (non-blog) and blog posts
  - Deliverable: `page_url → metadata` map

- [ ] **Extract & resolve links (`on_page_markdown`)**

  - Extract internal links, resolve to absolute page URLs, skip external/anchor/self
  - Record edges; tolerate stale links (target not in map → log + skip)
  - Deliverable: edge list

- [ ] **Build inverse index & inject backlinks**

  - Compute `target → backlinks` after all pages processed
  - Append "反向链接" section (styled list, e.g. `assets/stylesheets/backlinks.css`);
    hide when empty; cap at `max_backlinks`
  - Deliverable: backlinks visible on every included page

- [ ] **Edge cases**

  - Page with zero backlinks → no section rendered
  - Duplicate titles / Chinese titles → still link correctly by URL
  - Links to same page from multiple sections → dedupe, order by section
  - Deliverable: edge-case test list run against real content

### Phase 2: Topology Graph (双向链拓扑图)

- [ ] **Per-page neighborhood graph**

  - Build 1-hop subgraph (configurable depth) around current page
  - Generate ```` ```mermaid ```` block: ASCII-safe ids, title labels, clickable nodes
  - Style via mermaid theme (match Material palette)
  - Deliverable: neighborhood graph on each page

- [ ] **Global topology page**

  - Auto-generate virtual page `notes/link-graph.md` (write temp file in `on_files`,
    render full graph in build)
  - Optionally cluster nodes by section (subgraphs)
  - Add page to nav / link from Research index
  - Deliverable: site-wide link topology page

- [ ] **Scale guards & polish**

  - `max_nodes` cap + "show more" or collapsed mode for huge sections
  - Ensure `minify` (minify_html) and `search` plugins don't break injected HTML
  - Verify mobile layout of backlinks + graph sections
  - Deliverable: verified on `uv run poe server-prod` and `uv run poe build`

### Phase 3: Verify & Ship

- [ ] **Quality gates**

  - `uv run poe fmt` + `uv run poe lint-py` clean
  - Manual check: drafts excluded in production build, no broken links in graph
  - Performance check on build time with full content

- [ ] **Documentation**

  - Document config options + injection points (README in `plugins/` or plan notes)
  - Update this plan's Notes with final decisions

## Non-Goals

- WYSIWYG bidirectional link editing (static site; links are authored in markdown as usual)
- Force-directed / physics graph layouts (e.g. vis-network, d3-force) — Mermaid flowchart only
- Auto-repairing stale links (only logging; fixing stays manual)
- Backlinks/graph for blog posts (`notes/posts/`) and moment pages (excluded by default)

## Notes

- Prior art: `mkdocs-backlinks` plugin (ankitrgadiya) — backlinks only, no graph; custom
  hook gives us both features with repo-consistent code style
- Mermaid `click` support is enabled by default in mermaid2; verify security config
  (`securityLevel`) if custom JS actions are ever needed
- Reuse draft-detection logic from `plugins/draft_filter.py` to avoid divergence

## References

- [mkdocs.yml](../../mkdocs.yml) — hooks & plugins list, mermaid2 config
- [plugins/](../../plugins/) — existing hook pattern (`draft_filter.py`, `snippet_include.py`)
- [mermaid2 plugin](https://github.com/fralau/mkdocs-mermaid2-plugin) — mermaid rendering, click support
- [Mermaid flowchart syntax](https://mermaid.js.org/syntax/flowchart.html) — subgraphs, click events
- [dev/architecture.md](../architecture.md) — build & server commands
