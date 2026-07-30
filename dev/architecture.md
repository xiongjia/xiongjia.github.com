# Architecture

> Personal notes & research log — built with MkDocs + Material for MkDocs,
> deployed to GitHub Pages.

## Project Positioning

A personal knowledge base with a knowledge pipeline:

```
Notes → Collection → Research → Projects
```

- **Notes** (`docs/notes/`): Blog posts (timeline-based, RSS feed) and study notes (long-form)
- **Collection** (`docs/collection/`): Curated links by domain (database, dev tools, AI, etc.)
- **Research** (`docs/research/`): Deep-dive source code analysis (open-source projects)
- **Projects** (`docs/projects/`): Tangible project outputs
- **Health** (`docs/health/`): Personal health tracking (weight, retirement countdown)
- **Discuss** (`docs/discuss/`): Giscus-powered comment page

## Directory Structure

```
xiongjia.github.com/
├── .github/workflows/ci.yml        # CI: lint & deploy to GitHub Pages
├── mkdocs.yml                     # MkDocs configuration
├── pyproject.toml                 # Python project config & dependencies
├── dev/                           # Design documents & plans
│   └── plans/                     # Implementation plans / task tracking (see plan-index.md)
├── docs/                          # All site content (Markdown)
│   ├── index.md                   # Home page
│   ├── notes/                     # Blog posts (MkDocs blog plugin)
│   │   └── posts/
│   ├── research/                  # Research notes
│   │   ├── research.md            # Index of research topics
│   │   └── docs/
│   │       ├── better-auth/
│   │       ├── jellyfin/
│   │       ├── lux/
│   │       ├── nestjs/
│   │       ├── nest-commander/
│   │       └── trip/
│   ├── tech/                      # Tech reference pages
│   ├── health/                    # Personal health tracking
│   │   ├── index.md               # Health dashboard
│   │   ├── weight.md              # Weight tracking (macros-generated)
│   │   ├── retire.md              # Retirement countdown (macros-generated)
│   │   ├── data/
│   │   │   ├── weight.yml         # Weight data
│   │   │   └── retire.yml         # Retirement config
│   │   └── macros/
│   │       ├── health_macros.py   # Aggregate macros module
│   │       ├── weight_macros.py   # Weight tracking macros
│   │       └── retire_macros.py   # Retirement countdown macros
│   └── discuss/
│       └── index.md               # Dedicated comment page
├── scripts/                       # Utility scripts
│   ├── create-post.py             # Blog post scaffolding
│   ├── optimize_images.py         # PNG/JPG/JPEG → WebP converter
│   ├── add_weight_week.py         # Add empty week to weight data
│   └── md2wechat.py               # MkDocs → WeChat HTML converter
├── plugins/                       # Custom MkDocs hooks
│   ├── draft_filter.py            # Draft page filter
│   └── mermaid_assets.py          # Mermaid JS local downloader
├── overrides/                     # MkDocs Material theme overrides
│   ├── main.html                  # Extra meta tags & external link handling
│   ├── 404.html                   # Custom 404 page
│   └── partials/
│       ├── comments.html          # Giscus comment integration
│       └── source.html            # Source link override
├── docs/assets/
│   ├── stylesheets/
│   │   ├── retire.css             # Retirement grid/card styles
│   │   └── weight.css             # Weight tracker styles
│   └── javascripts/
│       └── retire.js              # Monthly grid dynamic fill
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
- **`mermaid_assets.py`** — Downloads & injects self-hosted Mermaid JS bundle

### MkDocs Plugins (`mkdocs.yml` → `plugins`)

- **`minify`** — Minifies HTML output (`minify_html: true`). `mkdocs-minify-plugin` (third-party)
- **`search`** — Full-text site search via lunr.js. Built-in
- **`macros`** — Jinja2 template engine (runs `health_macros.py`). Config: `module_name: docs/health/macros/health_macros`, `render_by_default: false`, `force_render_paths: "health/*"`. `mkdocs-macros-plugin` (third-party)
- **`mermaid2`** — Renders Mermaid diagrams from fenced code blocks. Config: `version: 10.9.0`, `javascript: assets/javascripts/mermaid.min.js`. `mkdocs-mermaid2-plugin` (third-party)
- **`drawio`** — Embeds drawio diagrams via `![alt](file.drawio)`. `mkdocs-drawio` (third-party)
- **`glightbox`** — Lightbox image viewer. `mkdocs-glightbox` (third-party)
- **`meta`** — Frontmatter metadata for page title, description, nav hiding, etc. Built-in
- **`rss`** — RSS & JSON feeds for blog posts. Config: `match_path: "notes/posts/.*"`, `use_git: true`, `pretty_print: true`. `mkdocs-rss-plugin` (third-party)
- **`tags`** — Tag index pages with scope-based grouping. Built-in
- **`blog`** — Full blogging engine (pagination, archives, drafts). Config: `blog_dir: notes`, `pagination_per_page: 5`. Built-in

**Load order**: hooks (`on_*` events) → plugins (in `mkdocs.yml` order) → markdown_extensions (during Markdown rendering).

**Note**: `markdown_extensions` (e.g. `pymdownx.superfences`, `admonition`,
`footnotes`) are Python-Markdown extensions, **not** MkDocs-level plugins,
and operate at the Markdown rendering layer.

## Environment Variables

| Variable                | Purpose                                              | Default                      |
| ----------------------- | ---------------------------------------------------- | ---------------------------- |
| `MKDOCS_INCLUDE_DRAFTS` | Include draft pages in dev server (`true`/`1`/`yes`) | unset (exclude)              |
| `SITE_NAME`             | Override site name in HTML title                     | `recycle.bin`                |
| `SITE_URL`              | Override canonical URL                               | `https://xiongjia.github.io` |
| `GIT_HASH`              | Embed current commit hash in page meta               | empty                        |

## Dev Workflow

```bash
uv sync                                    # install dependencies
uv run poe server                          # dev server WITH drafts (hot reload)
uv run poe server-prod                     # dev server WITHOUT drafts (mirrors production)
uv run poe build                           # production build (excludes drafts)
```

The dev server runs at `http://localhost:8000` by default.

Available `poe` commands:

| Command                              | Description                                       |
| ------------------------------------ | ------------------------------------------------- |
| `uv run poe server`                  | Dev server with drafts                            |
| `uv run poe server-prod`             | Dev server without drafts                         |
| `uv run poe build`                   | Production build                                  |
| `uv run poe build-selfhost`          | Self-hosted build (separate `site-selfhost/` dir) |
| `uv run poe fmt`                     | Format Python (ruff) + Markdown (mdformat)        |
| `uv run poe lint-py`                 | Python lint check (ruff)                          |
| `uv run poe create-post "Title"`     | New blog post scaffolding                         |
| `uv run poe optimize-images <path>`  | PNG/JPG/JPEG → WebP conversion                    |
| `uv run poe add-weight-week [count]` | Add empty week(s) to weight data                  |
| `uv run poe md2wechat [path]`        | Convert blog post to WeChat HTML                  |

## Draft Mechanism

Two layers of draft support:

1. **Blog posts** (`docs/notes/posts/`): Handled natively by the blog plugin.
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

- Runs on push to any branch and pull requests
- Steps: lint (ruff format check + ruff lint + mdformat check) → build → deploy
- Deploy to GitHub Pages only on push to `master`

## Localization / i18n

All data-layer display text is configurable via YAML `labels` sections in data
files (`weight.yml`, `retire.yml`). Currently configured for Chinese UI.
Content pages themselves are mixed Chinese/English depending on the section.

## Design Documents

- [md2wechat Design](./md2wechat-design.md)
- [optimize-images Design](./optimize-images-design.md)
- [Weight Tracker Design](./weight-tracker-design.md)
- [Discuss System Design](./discuss-design.md)
- [Retirement Countdown Design](./retirement-countdown-design.md)

> This file is the architecture overview.
