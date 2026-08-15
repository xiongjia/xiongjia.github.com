# Architecture

> Personal notes & research log — built with MkDocs + Material for MkDocs,
> deployed to GitHub Pages.

## Project Positioning

A personal knowledge base with a knowledge pipeline:

```
Notes → Collection → Research → Knowledge → Projects
```

- **Notes** (`docs/notes/`): Blog posts (timeline-based, RSS feed) and study notes (long-form)
- **Collection** (`docs/notes/collection/`): Curated links by domain (database, dev tools, AI, etc.)
- **Research** (`docs/notes/research/`): Deep-dive source code analysis & learning plans (per-topic dirs under `topics/`)
- **Knowledge** (`docs/notes/knowledge/`): Long-term knowledge base — big topics with sub-projects, the output of Research
- **Projects** (`docs/projects/`): Tangible project outputs
- **Health Monitor** (`docs/notes/health/`): Personal health tracking (weight, retirement countdown)
- **Discuss** (`docs/discuss/`): Giscus-powered comment page

## Directory Structure

```
xiongjia.github.com/
├── .github/workflows/ci.yml        # CI: lint & deploy to GitHub Pages
├── mkdocs.yml                     # MkDocs configuration
├── pyproject.toml                 # Python project config & dependencies
├── internal/                     # Design documents & plans
│   ├── architecture.md           # This document
│   └── plans/                    # Implementation plans / task tracking (see plan-index.md)
│       └── arch/                 # Archived (done/cancelled) plans
├── shared/                       # Shared utilities for plugins & scripts
├── external/                     # External research data (source clones, books, …; never committed)
├── docs/                          # All site content (Markdown)
│   ├── index.md                   # Redirect → /notes/
│   ├── moments/                   # Short-form timeline (Moment plugin)
│   │   ├── index.md               # Timeline archive
│   │   └── 2026-07/               # Monthly moment posts
│   ├── notes/                     # Landing page + sub-sections
│   │   ├── index.md               # Notes landing (includes _index_content.md)
│   │   ├── _index_content.md      # Notes landing content fragment (mermaid + about)
│   │   ├── link-graph.md          # Site-wide link topology (generated at build by plugins/backlinks.py)
│   │   ├── prototypes.md          # Prototype index page (GitHub jumps)
│   │   ├── collection/            # Curated links by domain
│   │   │   ├── index.md
│   │   │   ├── ai.md
│   │   │   ├── database.md
│   │   │   ├── dev-tools.md
│   │   │   ├── emoji.md
│   │   │   ├── frontend.md
│   │   │   ├── game-dev.md
│   │   │   ├── languages.md
│   │   │   ├── maps.md
│   │   │   ├── media.md
│   │   │   └── monitor.md
│   │   ├── tools/                 # Dev tool notes
│   │   │   ├── index.md
│   │   │   ├── ramen-timer.md
│   │   │   ├── med-tracker.md
│   │   │   ├── fitness.md
│   │   │   ├── coffee-flavor-wheel.md
│   │   │   └── gps-tracker.md
│   │   ├── research/              # Deep-dive source code analysis & learning plans
│   │   │   ├── index.md
│   │   │   └── topics/
│   │   │       ├── better-auth/
│   │   │       ├── english/
│   │   │       ├── jellyfin/
│   │   │       ├── lux/
│   │   │       ├── nest-commander/
│   │   │       ├── nestjs/
│   │   │       ├── redash/
│   │   │       ├── rust/
│   │   │       ├── shadcn-ui/
│   │   │       └── trip/
│   │   ├── knowledge/             # Long-term knowledge base (topic dirs, sub-projects)
│   │   │   ├── index.md
│   │   │   └── infrastructure/    # Cloud / Object Storage topics
│   │   │       └── cloud/
│   │   │           └── object-storage/
│   │   │               ├── index.md
│   │   │               └── signed-url.md
│   │   ├── health/                # Personal health tracking
│   │   │   ├── index.md           # Health Monitor dashboard (mermaid + AI summary)
│   │   │   ├── _summary.md        # AI health summary fragment (poe update-health-summary)
│   │   │   ├── weight.md          # Weight tracking (macros-generated)
│   │   │   ├── retire.md          # Retirement countdown (macros-generated)
│   │   │   ├── running.md         # Running stats (macros-generated)
│   │   │   ├── data/
│   │   │   │   ├── weight.yml     # Weight data
│   │   │   │   ├── retire.yml     # Retirement config
│   │   │   │   └── running.yml    # Running data (poe sync-running)
│   │   │   └── macros/
│   │   │       ├── health_macros.py
│   │   │       ├── weight_macros.py
│   │   │       ├── retire_macros.py
│   │   │       └── running_macros.py
│   │   └── posts/                 # Blog archive (MkDocs blog plugin)
│   │       ├── index.md           # Posts archive
│   │       └── posts/             # Blog posts (organized by category)
│   │           └── bits/
│   │               ├── 20250809-pdm-config.md
│   │               ├── 20250826-gops.md
│   │               ├── 20250830-upx.md
│   │               ├── 20250901-secure-json.md
│   │               └── 20260730-restic-backup-guide.md
│   ├── projects/
│   │   └── index.md
│   └── discuss/
│       └── index.md               # Dedicated comment page
├── scripts/                       # Utility scripts
│   ├── create_post.py             # Blog post scaffolding
│   ├── create_moment.py           # Moment micro-post scaffolding
│   ├── cleanup_gh_pages.sh        # Delete stale gh-pages branch
│   ├── optimize_images.py         # PNG/JPG/JPEG → WebP converter
│   ├── add_weight_week.py         # Add empty week to weight data
│   ├── sync_running.py            # Sync running data from running_page
│   ├── update_health_summary.py   # Regenerate AI health summary (local pi CLI)
│   ├── md2wechat.py               # MkDocs → WeChat HTML converter
│   └── md2wechat/                 # Converter assets (sample.md)
├── tests/                         # Unit tests (pytest)
│   ├── test_md2wechat.py
│   ├── test_sync_running.py
│   ├── test_update_health_summary.py
│   └── …                          # remaining test files
├── plugins/                       # Custom MkDocs hooks
│   ├── draft_filter.py            # Draft page filter
│   ├── snippet_include.py         # `<!-- include: -->` snippet expansion
│   ├── moment_hook.py             # Moment micro-post timeline (delegates to mkdocs_moment)
│   ├── backlinks.py               # Bidirectional links & topology graphs
│   ├── mermaid_assets.py          # Mermaid JS loader (CDN-first, local fallback)
│   └── mkdocs_moment/             # Moment plugin package
├── overrides/                     # MkDocs Material theme overrides
│   ├── main.html                  # Extra meta tags & external link handling
│   ├── 404.html                   # Custom 404 page
│   └── partials/
│       ├── comments.html          # Giscus comment integration
│       ├── back-link.html         # Topic/content back-link block
│       ├── toc.html               # TOC sidebar override (appends back-link, theme copy)
│       └── source.html            # Source link override
├── docs/assets/
│   ├── stylesheets/
│   │   ├── retire.css             # Retirement grid/card styles
│   │   ├── weight.css             # Weight tracker styles
│   │   ├── back-link.css          # Back-link styles
│   │   ├── hr.css                 # Horizontal rule styles
│   │   ├── nav.css                # Navigation styles
│   │   └── tools.css              # Tools page styles
│   ├── javascripts/
│   │   ├── retire.js              # Monthly grid dynamic fill
│   │   └── mermaid.min.js         # Bundled mermaid (auto-downloaded, gitignored)
│   └── running-otaku.webp         # Running track header image
└── site/                          # Build output (gitignored)
```

## Tech Stack

| Layer                 | Technology                                                          |
| --------------------- | ------------------------------------------------------------------- |
| Static site generator | [MkDocs](https://www.mkdocs.org/)                                   |
| Theme                 | [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) |
| Language              | Python 3.13                                                         |
| Package manager       | [uv](https://docs.astral.sh/uv/)                                    |
| CI/CD                 | GitHub Actions → GitHub Pages                                       |
| Linting               | ruff (Python), mdformat (Markdown)                                  |
| Diagrams              | mermaid2, drawio                                                    |

## Plugins & Hooks

### Custom Hooks (`plugins/`)

Hooks are custom Python modules registered via `mkdocs.yml` → `hooks`. They
register callbacks on MkDocs lifecycle events (`on_files`, `on_pre_build`,
`on_post_page`).

- **`draft_filter.py`** — Filters out `draft: true` pages in production (env-driven)
- **`snippet_include.py`** — Expands `<!-- include: path -->` snippet markers
- **`moment_hook.py`** — Moment micro-post timeline (delegates to `plugins/mkdocs_moment/`)
- **`backlinks.py`** — Bidirectional links: backlinks + topology graphs (see below)
- **`bucket_url.py`** — Rewrites asset links matching `extra.bucket` prefixes
  (`assets/bucket/`) to the bucket `base_url` at build time; env overrides
  `MKDOCS_BUCKET_ENABLED` / `MKDOCS_BUCKET_BASE_URL` (see
  [bucket-design.md](./bucket-design.md))
- **`mermaid_assets.py`** — Downloads the Mermaid JS bundle locally and
  injects it CDN-first (`MERMAID_CDN_URL`, default `registry.npmmirror.com`
  for mainland-China speed) with an `onerror` fallback to the self-hosted
  copy; disables the CDN with `MERMAID_CDN_URL=""`

### MkDocs Plugins (`mkdocs.yml` → `plugins`)

- **`minify`** — Minifies HTML output (`minify_html: true`). `mkdocs-minify-plugin` (third-party)
- **`search`** — Full-text site search via lunr.js. Built-in
- **`macros`** — Jinja2 template engine (runs `health_macros.py`). Config: `module_name: docs/notes/health/macros/health_macros`, `render_by_default: false`, `force_render_paths: "notes/health/*"`. `mkdocs-macros-plugin` (third-party)
- **`mermaid2`** — Renders Mermaid diagrams from fenced code blocks. Config: `version: 10.9.0`, `javascript: assets/javascripts/mermaid.min.js`. `mkdocs-mermaid2-plugin` (third-party)
- **`drawio`** — Embeds drawio diagrams via `![alt](file.drawio)`. `mkdocs-drawio` (third-party)
- **`glightbox`** — Lightbox image viewer. `mkdocs-glightbox` (third-party)
- **`meta`** — Frontmatter metadata for page title, description, nav hiding, etc. Built-in
- **`rss`** — RSS & JSON feeds for blog posts. Config: `match_path: "notes/posts/.*"`, `use_git: true`, `pretty_print: true`. `mkdocs-rss-plugin` (third-party)
- **`tags`** — Tag index pages with scope-based grouping. Built-in
- **`blog`** — Full blogging engine (pagination, archives, drafts). Config: `blog_dir: notes`, `pagination_per_page: 5`. Built-in

**Load order**: plugins (in `mkdocs.yml` order) → hooks (registered via `hooks:`, appended after the yaml plugins) → markdown_extensions (during Markdown rendering).

**Note**: `markdown_extensions` (e.g. `pymdownx.superfences`, `admonition`,
`footnotes`) are Python-Markdown extensions, **not** MkDocs-level plugins,
and operate at the Markdown rendering layer.

## Bidirectional Links (双向链接)

Bidirectional navigation is implemented by the custom hook
[`plugins/backlinks.py`](../plugins/backlinks.py) (registered **last** in
`mkdocs.yml` → `hooks`). Two features:

1. **Backlinks (反向链接)** — pages with incoming links show a collapsed
   `??? info "Backlinks (N)"` card listing every page that links to them, plus a
   `??? info "Links (N)"` card for outgoing links when any exist (backlinks but
   no outgoing links → Backlinks card only; no backlinks → one combined card;
   no links at all → nothing) — readers can jump between linked docs in both
   directions.
1. **Topology graph (双向链拓扑图)** — interactive Mermaid flowcharts rendered by
   the existing `mermaid2` + Material chain (no new JS): a per-page
   *neighborhood* graph (BFS within `graph.depth` hops, capped by
   `graph.max_nodes`) and a site-wide overview at `notes/link-graph.md` — a
   committed stub whose content is generated at build time, with section-
   clustered subgraphs.

### Design: two passes over a single link index

- **Pass A (`on_files`)** — after `draft_filter` removes drafts, build the page
  map from the final `config.files`, then pre-scan every in-scope page's raw
  markdown: expand `<!-- include: -->` snippets, strip code fences / inline
  code / images / external & anchor-only links, resolve relative targets
  against the page's `src_uri` (same semantics as MkDocs), normalize
  (`index.md`, drop `#fragment` / `?query`), and record edges
  `(source → target)`. Output: a complete, order-independent edge set.
- **Pass B (`on_page_markdown`)** — pure injection, no accumulation: invert the
  edge set into `target → [backlink sources]`, append the collapsed cards and
  the neighborhood graph, or replace the whole global page body with the
  site-wide graph.

**Why pre-scan instead of accumulating while rendering**: MkDocs renders pages
in a single sequential pass with no deferred injection point (`on_post_build`
only receives `config`). Backlinks on an early page can depend on edges from
pages rendered later, and the global graph needs the full edge set too — so the
index must be complete *before* any page renders, i.e. in `on_files`.
Accumulate-then-reorder only fixes the global page; an `on_post_build` HTML
rewrite would bypass MkDocs' write logic. Full design, spike findings and
rejected alternatives:
[`internal/plans/arch/mkdocs-backlinks-topology.md`](./plans/arch/mkdocs-backlinks-topology.md)
(completed 2026-08-02).

### Rendering chain & ordering constraints

- Injection happens at **markdown level** — never HTML in `on_post_page`,
  because mermaid2's `on_post_page` runs before hooks' and HTML-level
  injection would miss the self-hosted script tag / `mermaidConfig` and render
  as raw text.
- Generated graphs emit `flowchart {layout.upper()}` (lowercase `graph lr` is a
  mermaid 10.9.0 parse quirk) with ASCII node ids, title labels, and
  **relative** `click` URLs (per AGENTS.md relative-link convention).
- Hook ordering: registered **last**, so `draft_filter` has already dropped
  drafts and the `macros` plugin has already rendered jinja (plugins run before
  hooks) — extracted edges are consistent with what pages actually show.
- Macro-generated links are not in the pre-scan edge set; currently verified
  empty (health macros emit no cross-page markdown links). If a future macro
  emits links, per-page backlinks/graphs would miss them — revisit then.

### Scope & non-goals

Blog posts (`notes/posts/`) and moments are excluded by default. No WYSIWYG
link editing, no force-directed layouts, no auto-repair of stale links (stale
targets are skipped). `max_backlinks` caps each list with
"… and N more"; `graph.max_nodes` caps BFS growth.

### Config (`mkdocs.yml` → `extra.backlinks`)

| Option                | Default                                                       | Purpose                                                       |
| --------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| `enabled`             | `true`                                                        | Master switch                                                 |
| `include`             | `["notes/**"]`                                                | Gitignore-style globs (relative to docs_dir)                  |
| `exclude`             | `["notes/posts/**", "moments/**", "notes/_index_content.md"]` | Pages excluded from the index                                 |
| `max_backlinks`       | `20`                                                          | Cap per list (`all` = unlimited)                              |
| `graph.depth`         | `5`                                                           | Neighborhood BFS depth (per-page graph)                       |
| `graph.layout`        | `"lr"`                                                        | Per-page flowchart direction                                  |
| `graph.global_layout` | `"lr"`                                                        | Global page: main+subgraph LR → portrait, avoids width-shrink |
| `graph.max_nodes`     | `50`                                                          | Safety cap for BFS / graph size                               |
| `graph.global_page`   | `"notes/link-graph.md"`                                       | Site-wide topology page (committed stub)                      |

## Environment Variables

| Variable                                                      | Purpose                                                                                                                           | Default                                   |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `MKDOCS_INCLUDE_DRAFTS`                                       | Include draft pages in dev server (`true`/`1`/`yes`)                                                                              | unset (exclude)                           |
| `MKDOCS_BUCKET_ENABLED`                                       | Force-enable bucket prefix rewrite (`true`/`1`/`yes`)                                                                             | unset (use `extra.bucket.enabled`)        |
| `MKDOCS_BUCKET_BASE_URL`                                      | Override every bucket mapping's `base_url` (testing)                                                                              | unset                                     |
| `BUCKET_SYNC_REMOTE`                                          | rclone remote name for `poe bucket-sync`/`poe bucket-upload` (local-only; auto-detected from `rclone listremotes`, env overrides) | auto-detect → `r2`                        |
| `BUCKET_SYNC_BUCKET`                                          | Bucket name override for `poe bucket-sync`                                                                                        | mappings[].bucket                         |
| `BUCKET_SYNC_PREFIX`                                          | Local prefix override for `poe bucket-sync`                                                                                       | mappings[].prefix                         |
| `BUCKET_SYNC_REMOTE_PREFIX`                                   | Remote prefix override for `poe bucket-sync`                                                                                      | mappings[].remote_prefix                  |
| `BUCKET_UPLOAD_RULE`                                          | Rename rule for `poe bucket-upload` (local override)                                                                              | mkdocs.yml `extra.bucket.upload.rule`     |
| `BUCKET_UPLOAD_FALLBACK_NAME`                                 | Filename when the stem has no ASCII alphanumerics (`poe bucket-upload`)                                                           | `noname`                                  |
| `BUCKET_UPLOAD_TMP_DIR`                                       | Staging dir for converted WebP before upload (`poe bucket-upload`)                                                                | `extra.bucket.upload.tmp_dir` → `.bucket` |
| `BUCKET_UPLOAD_MAX_SIZE_MB`                                   | Per-file upload size limit in MB (`poe bucket-upload`; larger files fail)                                                         | `extra.bucket.upload.max_size_mb` → `10`  |
| `RCLONE_HTTP_PROXY`                                           | Proxy URL for rclone (native `--http-proxy` env var)                                                                              | unset                                     |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | R2 API credentials for `poe rclone-config-init` (local `.env` only)                                                               | unset                                     |
| `SITE_NAME`                                                   | Override site name in HTML title                                                                                                  | `recycle.bin`                             |
| `SITE_URL`                                                    | Override canonical URL                                                                                                            | `https://xiongjia.github.io`              |
| `GIT_HASH`                                                    | Embed current commit hash in page meta                                                                                            | empty                                     |
| `BOT_GH_TOKEN`                                                | Bot PAT (personal account) for the local bot (git-ignored `.env` only)                                                            | unset                                     |
| `BOT_WORKTREE_DIR`                                            | Bot worktree base dir (overrides the default cache dir)                                                                           | `~/.cache/<repo>-bot/worktrees/`          |
| `BOT_BASE_BRANCH`                                             | Bot fork base branch (bot branches fork from origin/<this>)                                                                       | `master`                                  |
| `BOT_SKIP_TESTS`                                              | Skip the python unittest step in the bot's local CI gate (local escape hatch)                                                     | `false`                                   |
| `BOT_HTTP_PROXY`                                              | Bot proxy for GitHub API / git push / mermaid download                                                                            | unset                                     |

## Dev Workflow

```bash
uv sync                                    # install dependencies
uv run poe server                          # dev server WITH drafts (hot reload)
uv run poe server-prod                     # dev server WITHOUT drafts (mirrors production)
uv run poe build                           # production build (excludes drafts)
```

The dev server runs at `http://localhost:8000` by default.

All `poe` commands (dev / build / quality / content / health / assets) are
centralized in [commands.md](./commands.md); only the core flow is kept here.

## Draft Mechanism

Two layers of draft support:

1. **Blog posts** (`docs/notes/posts/posts/`): Handled natively by the blog plugin.
   Add `draft: true` to frontmatter. Included when `mkdocs serve --drafts` or
   `MKDOCS_INCLUDE_DRAFTS=true`, excluded in production `mkdocs build`.

1. **Non-blog pages** (research, tech, health, etc.): Handled by the custom
   `draft_filter.py` hook. Same frontmatter convention (`draft: true`).
   The hook skips blog posts to avoid double-handling.

1. **Ephemeral drafts** (`*-draft.md`): Gitignored per `.gitignore`. These
   are local AI collaboration plans (like this document) that must never be
   committed.

Manual alternatives (without hooks):

- Omit from `nav` — file still builds, but won't appear in navigation.
- Add `robots: noindex, nofollow` to frontmatter.
- Rename with `-draft.md` suffix (already gitignored).

## CI/CD

`.github/workflows/ci.yml`:

- **`lint`** — runs on push to any branch and pull requests: pytest, ruff
  format/lint check, mdformat check, MkDocs build check
- **`deploy`** — on push to `master` only: builds the site and publishes it
  to GitHub Pages as a **workflow artifact** (`actions/deploy-pages`). The
  Pages source is "GitHub Actions" (`build_type: workflow`), so the live
  site is NOT served from the `gh-pages` branch.

### No PR previews (why)

There is deliberately no PR preview deployment. An earlier `deploy-preview`
job pushed a full site copy into `gh-pages` → `pr-preview/<PR>/` on every PR
push (peaceiris/actions-gh-pages, `keep_files: true`). Because Pages is
artifact-served, those preview URLs (`https://xiongjia.github.io/pr-preview/<n>/`)
were never reachable (404), while the branch accumulated ~79 commits /
~86MB of history. The job was removed (2026-08) so CI no longer writes to
`gh-pages` at all. If PR previews are ever wanted again, use a hosting
provider with native per-PR preview deploys (Netlify / Vercel / Cloudflare
Pages) instead of the `gh-pages` branch.

### Cleaning up the legacy `gh-pages` branch

The old branch is not used by the live site and can be safely deleted.
Manual cleanup:

```bash
bash scripts/cleanup_gh_pages.sh   # checks Pages build_type, confirms, deletes branch + local refs
```

or manually: `git push origin --delete gh-pages && git fetch --prune`.
After deletion, unreachable objects are garbage-collected by GitHub within
a few days; the repo size shown in the UI drops accordingly.

## Localization / i18n

All data-layer display text is configurable via YAML `labels` sections in data
files (`weight.yml`, `retire.yml`). Currently configured for Chinese UI.
Content pages themselves are mixed Chinese/English depending on the section.

## Design Documents

- [Commands](./commands.md) — command reference
- [md2wechat Design](./md2wechat-design.md)
- [optimize-images Design](./optimize-images-design.md)
- [Bucket Assets Design](./bucket-design.md)
- [Weight Tracker Design](./weight-tracker-design.md)
- [Discuss System Design](./discuss-design.md)
- [Retirement Countdown Design](./retirement-countdown-design.md)
- [Health Summary Design](./health-summary-design.md)
- [Med Tracker Design](./med-tracker-design.md)
- [GPS Tracker Design](./gps-tracker-design.md)
- [Bot Auto PR Design](./bot-auto-pr-design.md) — local bot: worktree-isolated auto PR (weight/moment/… → draft PR → CI gate → auto-merge)

> Plans (task/feature tracking): [plans/plan-index.md](./plans/plan-index.md);
> English Scraps plan → [plans/english-scraps.md](./plans/english-scraps.md).

> This file is the architecture overview.
