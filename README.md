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

| Command                             | Description                                    |
| ----------------------------------- | ---------------------------------------------- |
| `uv run poe server`                 | Dev server WITH drafts                         |
| `uv run poe server-prod`            | Dev server WITHOUT drafts (mirrors production) |
| `uv run poe build`                  | Production build (excludes drafts)             |
| `uv run poe fmt`                    | Format Python & Markdown                       |
| `uv run poe lint-py`                | Python lint check (ruff)                       |
| `uv run poe create-post "Title"`    | New blog post (defaults to draft)              |
| `uv run poe create-moment "Text"`   | New Moment entry (short micro-post)            |
| `uv run poe optimize-images <path>` | PNG/JPG/JPEG → WebP                            |
| `uv run poe add-weight-week [n]`    | Add empty week(s) to weight data               |
| `uv run poe md2wechat [path]`       | Convert post to WeChat HTML                    |

## CI / Deployment

`.github/workflows/ci.yml` — lint (ruff + mdformat) on all branches, deploy
to GitHub Pages on push to `master`. Set `GIT_HASH` env var to embed commit
hash into the page HTML.

## Design Documents

Detailed documentation moved to `dev/`:

- [Moment Design](dev/moment-design.md) — Micro-post timeline plugin (hooks, templates, tags, pagination, RSS planned)
- [Architecture](dev/architecture.md) — project structure, plugins, hooks, env vars, draft system
- [md2wechat Design](dev/md2wechat-design.md) — WeChat HTML converter
- [optimize-images Design](dev/optimize-images-design.md) — WebP conversion pipeline
- [Weight Tracker Design](dev/weight-tracker-design.md) — weight data format, macros, tooling
- [Discuss System Design](dev/discuss-design.md) — Giscus comment system setup & configuration
- [Retirement Countdown Design](dev/retirement-countdown-design.md) — retirement policy calculator & visualization

## Structure (top-level)

```
docs/
├── index.md         # Redirect → /notes/
├── moments/         # Short micro-posts (Moment plugin)
├── notes/
│   ├── index.md     # Landing page (mermaid + about)
│   ├── collection/  # Curated links by domain
│   ├── research/    # Source code analysis
│   ├── health/      # Weight & retirement tracking
│   └── posts/       # Blog archive (MkDocs blog plugin)
├── projects/        # Project outputs
└── discuss/         # Giscus comment page
```
