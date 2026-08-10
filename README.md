# recycle.bin

Personal notes & research log — built with [MkDocs](https://www.mkdocs.org/) +
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/), deployed
to GitHub Pages.

## Quick Start

```bash
uv sync
GIT_HASH=$(git rev-parse --short HEAD) uv run poe server
```

Site runs at `http://localhost:8000` with hot-reload (includes drafts).

## Commands

| Command                              | Description                                                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `uv run poe server`                  | Dev server WITH drafts                                                                                      |
| `uv run poe server-prod`             | Dev server WITHOUT drafts (mirrors production)                                                              |
| `uv run poe server-bucket`           | Dev server WITH bucket prefix rewrite (test bucket link replacement)                                        |
| `uv run poe build`                   | Production build (excludes drafts)                                                                          |
| `uv run poe build-drafts`            | Build including drafts                                                                                      |
| `uv run poe build-selfhost`          | Self-hosted build (separate `site-selfhost/`)                                                               |
| `uv run poe fmt`                     | Format Python & Markdown                                                                                    |
| `uv run poe lint-py`                 | Python lint check (ruff)                                                                                    |
| `uv run poe test`                    | Run unit tests (pytest, `tests/`)                                                                           |
| `uv run poe create-post "Title"`     | New blog post (defaults to draft)                                                                           |
| `uv run poe create-moment "Text"`    | New Moment entry (short micro-post)                                                                         |
| `uv run poe optimize-images <path>`  | PNG/JPG/JPEG → WebP                                                                                         |
| `uv run poe add-weight-week [n]`     | Add empty week(s) to weight data                                                                            |
| `uv run poe update-weight 82 [date]` | Record daily weight (default: today)                                                                        |
| `uv run poe update-health-summary`   | Regenerate AI health summary (local pi CLI)                                                                 |
| `uv run poe sync-running`            | Sync running data from running_page site                                                                    |
| `uv run poe bucket-sync pull`        | Pull `docs/assets/bucket/` from R2/S3 via rclone (read-only, dry-run by default; uploads happen in PicList) |
| `uv run poe md2wechat [path]`        | Convert post to WeChat HTML                                                                                 |

## Common Examples

```bash
# Blog post (draft by default, publish with --no-draft)
uv run poe create-post "My Post Title"
uv run poe create-post "My Post" --category dev --tags go,cli
uv run poe create-post "My Post" --no-draft

# Backdate a post — --time accepts 9am/9pm/21:30, yesterday, day+time, full date
uv run poe create-post "My Post" --time "9:30am"       # today 09:30
uv run poe create-post "My Post" --time "yesterday"    # yesterday, same time
uv run poe create-post "My Post" --time "yesterday 9am"
uv run poe create-post "My Post" --time "30 9am"       # this month, 30th 09:00
uv run poe create-post "My Post" --time "2026-07-30 21:36"

# Moment (short micro-post)
uv run poe create-moment "Hello 👋"
uv run poe create-moment "With image" --image photo.webp
uv run poe create-moment "Draft idea" --draft   # hidden in production

# Backdate a moment
uv run poe create-moment "Backfill" --time "9pm"
uv run poe create-moment "Backfill" --time "30 9pm"

# Daily weight (defaults to today; date optional)
uv run poe update-weight 82
uv run poe update-weight 81.6 2026-08-05   # specific date
uv run poe update-weight 82 --date yesterday
uv run poe add-weight-week 2               # pre-add empty weeks (optional)
```

## CI / Deployment

`.github/workflows/ci.yml` — `lint` job (pytest, ruff, mdformat, MkDocs
build check) on all branches and pull requests; `deploy` job publishes the
site to GitHub Pages on push to `master` as a **workflow artifact**
(`actions/deploy-pages`) — the `gh-pages` branch is not used. Set
`GIT_HASH` env var to embed the commit hash into the page HTML.

## Prototypes

Experimental mini-projects live in `prototypes/<name>/` — committed with the
repo, each with its own English `README.md` and `.gitignore`, skipped by the
main Python/markdown toolchain (`poe fmt` / `poe lint-py` / CI).

- Index: [prototypes/README.md](prototypes/README.md)
- Site page: [Prototypes](docs/notes/prototypes.md)
- Convention details: `AGENTS.md` → Prototype Convention

## Design Documents

Detailed documentation moved to `internal/`:

- [Moment Design](internal/moment-design.md) — Micro-post timeline plugin (RSS feed, archive, tags, OpenGraph, drafts)
- [Bucket Assets Design](internal/bucket-design.md) — large files on R2/S3, prefix → base_url rewrite, PicList/rclone sync
- [Architecture](internal/architecture.md) — project structure, plugins, hooks, env vars, draft system
- [md2wechat Design](internal/md2wechat-design.md) — WeChat HTML converter
- [optimize-images Design](internal/optimize-images-design.md) — WebP conversion pipeline
- [Weight Tracker Design](internal/weight-tracker-design.md) — weight data format, macros, tooling
- [Running Track Design](internal/running-track-design.md) — running data sync & rendering
- [Health Summary Design](internal/health-summary-design.md) — AI health summary via local `pi`
- [Discuss System Design](internal/discuss-design.md) — Giscus comment system setup & configuration
- [Retirement Countdown Design](internal/retirement-countdown-design.md) — retirement policy calculator & visualization

## Structure (top-level)

```
internal/          # Dev docs & plans: design docs, architecture.md,
                   #   plans/plan-index.md, archived plans in plans/arch/
prototypes/        # Experimental mini-projects (index: prototypes/README.md)
shared/            # Shared Python utilities for plugins & scripts (strings, frontmatter, date, io)
scripts/           # CLI utility scripts (create_post, create_moment, sync_running, update_health_summary, …)
plugins/           # Custom MkDocs hooks (draft_filter, mermaid_assets, mkdocs_moment)
tests/             # pytest unit & integration tests
overrides/         # Theme overrides (comments, meta tags, external links)
docs/
├── index.md         # Redirect → /notes/
├── moments/         # Short micro-posts (Moment plugin)
├── notes/
│   ├── index.md      # Landing page (mermaid + about)
│   ├── collection/   # Curated links by domain
│   ├── research/     # Deep-dive notes (source code analysis, learning plans) under topics/
│   ├── knowledge/    # Long-term knowledge base (topic dirs, sub-projects)
│   ├── prototypes.md # Prototype index page (GitHub jumps)
│   ├── health/       # Health tracking (weight, retirement, running, AI summary)
│   └── posts/        # Blog archive (MkDocs blog plugin)
├── projects/        # Project outputs
└── discuss/         # Giscus comment page

external/           # Research source clones (never committed)
```
