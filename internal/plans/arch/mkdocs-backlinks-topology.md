---
title: MkDocs Bidirectional Links & Topology Graph
created: 2026-07-31
archived: 2026-08-02
status: completed
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

Content scale (build-time inventory):

| Area                                                                                             | Files | In graph scope            |
| ------------------------------------------------------------------------------------------------ | ----- | ------------------------- |
| `docs/notes/` (collection 11, research 10, health 3, tools 2, index/\_index_content, prototypes) | 35 md | ~28 (excl. posts/moments) |
| `docs/notes/posts/` (blog)                                                                       | 6 md  | excluded by default       |
| `docs/moments/`                                                                                  | 7 md  | excluded by default       |

So the global graph is small (~30 nodes); `max_nodes` is a safety guard, not a scale
requirement. No `draft: true` pages currently exist.

## Verified Findings (Phase 0 spike — from source code & build artifacts)

These items were investigated against the installed toolchain
(MkDocs 1.6.1, mermaid2 10.x, Material bundle, live `site/` output) and are
**resolved — not blocking**:

1. **Hook/plugin event ordering is registration order, and hooks run AFTER plugins.**
   - MkDocs `config_options.Hooks.post_validation` appends hooks to the plugin
     collection after the yaml plugins; events fire in registration order.
   - `on_files`: `draft_filter` (a hook) runs before a later-registered `backlinks`
     hook → drafts are already removed from `files` → our page map is
     automatically draft-consistent (prod excludes drafts, dev with
     `MKDOCS_INCLUDE_DRAFTS=true` includes them).
   - `on_page_markdown`: the `macros` plugin (plugins run before hooks) and the
     `snippet_include` hook run before `backlinks` → links inside `<!-- include: -->`
     snippets and macro-rendered health pages are already expanded when we extract.
   - **Consequence**: register `plugins/backlinks.py` LAST in the `hooks:` list.
1. **Mermaid rendering chain works for injected fences (proven on live site).**
   - ```` ```mermaid ```` in `on_page_markdown` → `pymdownx.superfences` custom
     fence `fence_mermaid_custom` → `<pre class="mermaid"><code>…</code></pre>`
   - mermaid2's `on_post_page` detects `pre.mermaid code`, injects the self-hosted
     `mermaid.min.js` + `window.mermaidConfig = {default: {startOnLoad: false}}`
   - Material's own `bundle.*.js` (contains `--md-mermaid-*` theme CSS and
     `startOnLoad` handling) performs the actual render — no new JS/CSS needed.
   - **Consequence**: the graph/backlinks block MUST be injected at markdown level
     (`on_page_markdown`), never as HTML in `on_post_page` — mermaid2's
     `on_post_page` runs before hooks' `on_post_page`, so HTML-level injection would
     never receive the script tag or config and would render as raw text.
1. **`minify` (htmlmin) preserves `<pre class="mermaid">` content verbatim**
   (newlines and `&gt;` entities intact) — verified in `site/notes/index.html`.
1. **Mermaid `click node "url"` is already used in production** — the diagram at the
   top of `docs/notes/index.md` uses `click A "/notes/" …`; the pattern renders.
   Decision: our generated graphs use **relative** click URLs (AGENTS.md convention),
   computing `relpath(page.url → target.url)`.
1. **mermaid2 only injects the 3.2 MB script on pages that contain diagrams**, so
   pages without a neighborhood graph pay no extra load; `mermaid_assets.py` already
   adds `async`/`defer`.
1. **Build is a single sequential page-render pass** (`mkdocs/commands/build.py`):
   `on_files` → per-page (`on_page_markdown` → HTML → `on_post_page` → write) →
   `on_post_build`. There is **no event between “all markdown processed” and “all
   files written”**, and `on_post_build` only receives `config`. Consequences:
   - `on_post_build`-time regeneration would require manually rewriting the rendered
     HTML file (stash output in `on_post_page`, patch + write in `on_post_build`) —
     hacky, bypasses MkDocs' write logic.
   - Accumulating edges in `on_page_markdown` + reordering the global page last
     only fixes the **global** page; per-page **backlinks also depend on the full
     edge set** (a page processed later may link to an earlier page), so every page
     except the last would render incomplete backlinks — MkDocs has no deferred
     injection point.
   - → Pre-scan in `on_files` is the only clean option that satisfies both features
     (see Design).
1. **macros gap verified empty**: `notes/health/macros/*.py` only emit HTML
   tables/grids/charts (`"".join(html_parts)`), no cross-page markdown links — so a
   raw-markdown pre-scan captures the same edge set as post-render extraction.

## Design

### Link index pipeline — single pre-scan in `on_files`

**Decision: pre-scan (option A).** Alternatives rejected: accumulate-at-render +
reorder global page last (option B) — per-page backlinks need the full edge set,
so every page except the last renders incomplete backlinks; `on_post_build` manual
HTML rewrite (option C) — works but bypasses MkDocs' write logic (stash rendered
HTML + hand-write the file). Pre-scan is the only option that is complete,
order-independent, stateless after `on_files`, and deterministic under `serve`
rebuilds.

Single source of truth, order-independent, deterministic. Why pre-scan and not
accumulate-at-render: per-page backlinks **and** the global graph both need the
*complete* edge set, but MkDocs renders pages in a single sequential pass with no
deferred injection point (Verified Finding #6) — so the edge set must be complete
\*before any page renders, i.e. in `on_files`.

1. **Pass A (`on_files`, after `draft_filter`)** — build `src_uri → (title, url, section)` map from the already-filtered `config.files` (markdown documentation
   pages only), then raw-markdown pre-scan of every included page:
   - read file, expand `<!-- include: path -->` markers (same regex as
     `snippet_include.py`)
   - extract links with a **fence-aware regex** (skip \`\`\`code fences, `inline code`,
     `![alt](url)` images)
   - resolve relative links **against `src_uri`** (`posixpath.normpath(join(dirname, link))`) — identical semantics to MkDocs' own relative-link handling
   - normalize: strip `#fragment`/`?query`; `index.md` and trailing-slash URL style
     (`../collection/`) → `…/index.md`; skip external (`http(s)://`, `mailto:`),
     root-absolute (`/…` — non-page assets), and anchor-only (`#…`) links
   - target not in page map (e.g. vendored source paths
     `docs/notes/research/external/…`, `.js`/`.py`) → log + skip (tolerate stale)
   - record edge `(source src_uri → target src_uri)`
1. **Pass B (`on_page_markdown`)** — pure injection, no accumulation:
   - invert edge set → `target → [backlink sources]`, append "反向链接" section
     (hidden when empty, capped at `max_backlinks`, deduped by URL)
   - BFS the edge set for the neighborhood subgraph (depth = `graph.depth`),
     append ```` ```mermaid ```` flowchart with ASCII-safe node IDs (hash of src_uri),
     title labels, relative click URLs
1. **Consistency trade-off (accepted)**: macro-generated links are not in the
   pre-scan edge set — verified empty in practice (health macros emit no cross-page
   links, Finding #7), so no divergence on the current site. If a future macro
   emits links, per-page backlinks/graph would miss them; revisit then (hybrid
   union is only safe for the global page, see Finding #6).

### Topology graph

- **Per-page**: 1-hop neighborhood (BFS, configurable depth) around current page —
  current page + direct neighbors, clickable nodes, theme-matched via Material's
  native mermaid CSS vars (`--md-mermaid-*`).
- **Global**: `notes/link-graph.md` — **committed physical stub** (frontmatter +
  placeholder body). `on_page_markdown` returns the generated content (title + full
  graph, optionally clustered into `subgraph` per section). The file on disk stays
  mdformat-stable so `poe fmt` / CI `check-fmt` are unaffected; the stub is NOT
  gitignored (gitignore would bypass mdformat determinism and hide it from review).
  Add to `nav` manually under Research + optional link from `notes/research/index.md`.
- **Rendering**: reuses the existing mermaid2 + Material chain — no new JS.

### Config — mirror the `extra.moment` pattern (`plugins/mkdocs_moment/plugin.py` reads `config["extra"]["moment"]`)

```yaml
extra:
  backlinks:
    enabled: true
    include: ["notes/**"]       # globs relative to docs_dir
    exclude: ["notes/posts/**", "moments/**", "notes/_index_content.md"]
    max_backlinks: 20           # cap per page, "all" for unlimited
    graph:
      enabled: true
      depth: 5                  # neighborhood depth for per-page graph
      layout: "lr"              # mermaid flowchart direction
      max_nodes: 50             # safety cap (global graph ≈ 30 nodes)
      global_page: "notes/link-graph.md"
```

## Tasks

### Phase 0: Spike & Design

- [x] **Spike: event ordering & mermaid interop** — resolved by source/built-artifact
  inspection (see Verified Findings): inject at `on_page_markdown`; register hook
  last; chain superfences → mermaid2 → Material bundle confirmed
- [x] **Link extraction approach** — raw-markdown pre-scan with fence-aware regex +
  `src_uri`-based `posixpath` resolution (matches MkDocs semantics); skip
  code/inline-code/images/external/root-absolute/anchor-only
- [x] **Spike: validate pre-scan on real content** — extractor ran over all 32
  in-scope pages: 23 edges; all 48 unresolved targets are source-code refs
  (better-auth `packages/…`, redash `docs/notes/research/external/…`) — zero real
  page links missed; `<!-- include: -->` expansion works; new finding: exclude
  `notes/_index_content.md` itself (include fragment rendered as a standalone page)
- [x] **Spike: global stub page mechanics** — validated through implementation: the
  stub is committed and read by MkDocs normally, `on_page_markdown` returns
  generated content (no `File` append needed); `serve`/`--dirty` re-run `on_files`
  so the index is fresh; `draft_filter` keeps the stub (not a draft); the stub on
  disk stays mdformat-stable
- [x] **Spike: visual check** — `click` navigation with relative URLs confirmed by
  the developer in a browser; mobile layout check intentionally not done
  (see Non-Goals)
- [x] **Scope & config design** — `extra.backlinks` mirroring `extra.moment`;
  include/exclude defaults; drafts handled automatically via post-draft_filter
  `on_files` ordering
- [x] **Deliverable**: spike notes + final config spec recorded in this plan
  (Verified Findings / Implementation Notes / Config sections)

### Phase 1: Backlinks (双向链接跳转)

- [x] **Page map + pre-scan edge build (`on_files`)**
  - Build `src_uri → metadata` from filtered `config.files`; pre-scan raw markdown
    (snippet expansion, fence-aware extraction, resolution/normalization per Design)
  - Rebuild all state every `on_config`/`on_files` (hooks are modules; module-level
    state persists across `serve` rebuilds — never cache across builds)
  - Deliverable: edge set + page map
- [x] **Inject backlinks + forward links (`on_page_markdown`)**
  - Invert edges → append collapsed admonition cards: `??? info "Backlinks (N)"`
    (incoming list + neighborhood graph) and `??? info "Links (N)"` (outgoing list);
    the graph always lives inside a collapsed card; dedupe by URL; cap at
    `max_backlinks` with "… and N more"
  - No jinja escaping needed — `macros` runs before hooks, so injected content
    never passes through jinja (Verified Finding on ordering)
  - Deliverable: cards on every included page, hidden when a list is empty
- [x] **Edge cases**
  - Zero backlinks → no section; duplicate/Chinese titles → keyed by URL; links from
    multiple sections → dedupe, order by section; stale/vendored links → logged, skipped
  - Deliverable: edge-case checklist run against real content

### Phase 2: Topology Graph (双向链拓扑图)

- [x] **Per-page neighborhood graph**
  - BFS subgraph (depth configurable); ASCII-safe node IDs; title labels; relative
    click URLs; `layout` direction; theme via Material mermaid CSS vars
  - Deliverable: neighborhood graph on each page
- [x] **Global topology page**
  - Commit stub `docs/notes/link-graph.md`; override content in `on_page_markdown`
  - Section subgraphs (first path segment: collection/health/research/tools/root),
    `flowchart LR` main + `direction LR` per subgraph → portrait, no width-shrink
  - Nav entry above Collection with `icon: material/graph-outline`
  - Link from research index to the Link Graph page: intentionally **not done**
    (see Non-Goals)
  - Deliverable: site-wide topology page
- [x] **Scale guards & polish**
  - `max_backlinks` cap with "… and N more"; `max_nodes` cap (depth 5, cap 50) in
    the neighborhood BFS; `minify` verified (preserves `pre.mermaid`);
    `poe build` clean
  - `max_nodes` truncation notice, `data-search-exclude` search-noise polish, and
    the mobile layout check are intentionally **not done** (see Non-Goals)

### Phase 3: Verify & Ship

- [x] **Quality gates** — `uv run poe fmt` + `uv run poe lint-py` clean (incl. stub
  mdformat-stability); `uv run poe build` clean; full test suite (114 tests) passes
- [x] **Documentation** — config options + injection points in the hook docstring;
  final decisions in Implementation Notes. A `plugins/README.md` config reference
  is intentionally **not done** (see Non-Goals)

## Implementation Notes (Phase 1 + 2, 2026-07-31)

- **Shipped**: `plugins/backlinks.py` (Pass A pre-scan + Pass B injection), config
  under `extra.backlinks`, nav entry + committed stub `docs/notes/link-graph.md`,
  unit tests `tests/test_backlinks.py` (35 tests).
- **Config bug fixed (review round 1)**: `_load_config` used `isinstance(config, dict)`
  but the real MkDocs `Config` is a `UserDict` (a `MutableMapping`, not a `dict`) —
  `extra.backlinks` from mkdocs.yml was silently ignored. Fixed by accepting
  `collections.abc.MutableMapping`; UserDict-based regression tests added.
- **Current graph config**: `depth: 5` (per-page BFS), `max_nodes: 50` (cap; the
  ~28-node site never hits it), `global_layout: "lr"` (main + subgraph LR → portrait).
- **Titles**: many pages lack frontmatter `title:` (collection/tools/health) — resolve
  via nav (`_nav_titles`, including the `navigation.indexes` section-index rule),
  then frontmatter, then filename stem.
- **Global page**: no `File` append needed — the stub is committed to disk and read by
  MkDocs normally; `on_page_markdown` returns generated content (simpler than planned).
- **macros/jinja (B5) resolved by ordering**: `macros` is a plugin and runs before
  hooks in `on_page_markdown`, so injected content never passes through jinja — no
  escaping needed.
- **Determinism**: subgraph ids use a stable counter (not `hash()` — randomized per
  process via PYTHONHASHSEED).
- **Backlinks + Links (forward) collapsible cards**: a collapsed `??? info "Backlinks (N)"`
  card (incoming list + neighborhood graph) and a collapsed `??? info "Links (N)"`
  card (outgoing list); the graph always lives inside a collapsed card (the
  Backlinks card when backlinks exist, otherwise the Links card).
- **Global page layout — portrait to avoid shrink**: `flowchart LR` main + `direction LR`
  inside each subgraph stacks clusters top-down → 1141×1806 (h/w=1.58) instead of
  4104×576, so Material's width-fit scales it ~0.7x instead of ~0.19x (readable).
- **Link Graph page**: nav entry moved above Collection; `icon: material/graph-outline`;
  intro text says "generated by a MkDocs plugin" (no specific file).
- **Sidebar (post-archive, developer-driven)**: removed `navigation.sections` so
  Collection/Tools/Health Monitor render as collapsible accordion items (Material's
  `--section` CSS forces children visible + hides the toggle icon); default collapsed,
  active section auto-expands — a user-requested nav change, not part of the
  backlinks plan proper.
- **mermaid 10.9.0 quirk (fixed)**: `graph lr` (lowercase direction) fails to parse
  with "Lexical error" — `graph TD/TB/RL`, `graph LR`, and `flowchart LR` all work.
  Generated diagrams emit `flowchart {layout.upper()}`. Verified: all 31 diagrams in
  the built site parse cleanly with the bundled mermaid.min.js (via linkedom).
- **Verified in build**: backlinks + neighborhood graphs on notes pages (posts/moments
  excluded), global page with 5 section subgraphs / 28 nodes / 23 edges, relative
  click URLs, mermaid + mermaidConfig injected, minify preserves `pre.mermaid`
  (`>` → `&gt;` as expected by mermaid).

## Blockers & Open Questions (as of 2026-07-31)

### Resolved (verified, no longer blocking)

| #   | Item                 | Evidence / decision                                                                                                               |
| --- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Event ordering       | MkDocs hooks run after plugins, in registration order → register hook last; draft filtering already applied before our `on_files` |
| R2  | Mermaid interop      | Injection must be markdown-level; chain superfences → mermaid2 → Material bundle confirmed in built output                        |
| R3  | minify compatibility | `<pre class="mermaid">` content preserved verbatim (existing diagram in `site/notes/index.html`)                                  |
| R4  | `click` navigation   | Already used in production (`notes/index.md`); decision: relative URLs per AGENTS.md                                              |
| R5  | Config location      | `extra.backlinks`, mirroring `extra.moment`                                                                                       |

### Tracked (all resolved as of the 2026-07-31 implementation)

| #   | Block                                           | Risk / decision needed                                                                                                                                                                                                                                                                                                          |
| --- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | **Global graph data timing**                    | **Resolved — pre-scan in `on_files`** (Finding #6): accumulation+reorder only fixes the global page, while per-page backlinks also need the full edge set; `on_post_build` rewrite is hacky. Macros gap verified empty (Finding #7) — nothing left for the current site; revisit only if a future macro emits cross-page links. |
| B2  | **Link extraction correctness on real content** | **Resolved — spike-validated** on all 32 in-scope pages: 23 edges; all 48 unresolved targets are source-code refs (better-auth `packages/…`, redash `docs/notes/research/external/…`) — zero real-page links missed.                                                                                                            |
| B3  | **Virtual/global page mechanics**               | **Resolved — implemented**: committed stub read normally by MkDocs; `on_page_markdown` returns generated content (no `File` append needed). `serve`/`--dirty` re-run `on_files` so the index is fresh; stub on disk is mdformat-stable.                                                                                         |
| B4  | **Hook state across rebuilds**                  | **Resolved — implemented**: `on_files` reassigns `_PAGES/_EDGES/_BACKLINKS` every build; no cross-build caching. Note: `--dirty` serve does not re-render unchanged pages (stale injected content until full rebuild) — accepted, matches MkDocs semantics.                                                                     |
| B5  | **macros/jinja on injected HTML**               | **Resolved by ordering**: `macros` is a plugin → runs before hooks in `on_page_markdown`, so injected content never passes through jinja; no escaping needed.                                                                                                                                                                   |
| B6  | **Relative click URLs in mermaid**              | **Resolved — verified in build**: relative click URLs render in all generated graphs (per-page + global).                                                                                                                                                                                                                       |
| B7  | **Search-index noise**                          | Accepted — injected text/graph code joins already-indexed mermaid code. `data-search-exclude` polish intentionally not done.                                                                                                                                                                                                    |
| B8  | **Scale/overflow semantics**                    | `max_nodes` cap implemented in the BFS; `max_backlinks` cap with "… and N more" done. Truncation notice intentionally not done.                                                                                                                                                                                                 |
| B9  | **CI / fmt determinism**                        | Generated content is build-time only; the committed stub must be mdformat-stable so `poe fmt`/`check-fmt`/`lint-py` and the CI MkDocs build pass in both draft and non-draft modes.                                                                                                                                             |

## Non-Goals

- WYSIWYG bidirectional link editing (static site; links are authored in markdown as usual)
- Force-directed / physics graph layouts (e.g. vis-network, d3-force) — Mermaid flowchart only
- Auto-repairing stale links (only logging; fixing stays manual)
- Backlinks/graph for blog posts (`notes/posts/`) and moment pages (excluded by default)
- Search integration / link-count statistics pages
- `max_nodes` truncation notice, `data-search-exclude` search-noise polish, mobile
  layout tuning, a `plugins/README.md` reference, and a research-index link to the
  Link Graph page — intentionally not done; revisit only if users hit them

## Notes

- Prior art: `mkdocs-backlinks` plugin (ankitrgadiya) — backlinks only, no graph; custom
  hook gives us both features with repo-consistent code style
- Reuse `shared/frontmatter.py` (`parse_frontmatter` for titles; `has_draft_flag` not
  needed — drafts are already filtered by `draft_filter` before our `on_files`)
- Reuse the snippet regex from `plugins/snippet_include.py` for pre-scan expansion
- Mermaid `click` uses default `securityLevel`; verify if custom JS actions are ever needed
- `page.file.url` ends with `/` for index pages — use `os.path.relpath`/`posixpath`
  against the target's `file.url` dir for correct relative click URLs

## References

- [mkdocs.yml](../../../mkdocs.yml) — hooks & plugins list, mermaid2 config, macros force_render_paths
- [plugins/](../../../plugins/) — existing hook pattern (`draft_filter.py`, `snippet_include.py`, `mermaid_assets.py`)
- [plugins/mkdocs_moment/plugin.py](../../../plugins/mkdocs_moment/plugin.py) — `extra.moment` config pattern
- [shared/frontmatter.py](../../../shared/frontmatter.py) — `parse_frontmatter` helper
- [mermaid2 plugin](https://github.com/fralau/mkdocs-mermaid2-plugin) — mermaid rendering, click support
- [Mermaid flowchart syntax](https://mermaid.js.org/syntax/flowchart.html) — subgraphs, click events
- [internal/architecture.md](../../architecture.md) — build & server commands
