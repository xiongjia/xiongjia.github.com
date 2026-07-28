# recycle.bin

Personal notes & research log — built with [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/), deployed to GitHub Pages.

## Structure

```
docs/
├── index.md              # Home page
├── notes/
│   ├── posts/{category}/ # Timeline posts (bits, dev, thought)
│   └── study/            # Long-form study notes (multi-day)
├── collection/           # Curated links by domain
├── research/             # Deep-dive source code analysis
├── projects/             # Tangible project outputs
└── health/               # Personal health tracking
    ├── index.md          # Health dashboard (weight, later running, etc.)
    ├── data/
    │   └── weight.yml    # Weight data (the only file to maintain)
    └── macros/
        └── weight_macros.py  # Jinja2 macros for tables & charts
```

**Knowledge pipeline**: Notes → Collection → Research → Projects.

## Quick Start

```bash
uv sync                                    # install dependencies
GIT_HASH=$(git rev-parse --short HEAD) uv run poe server  # start dev server (with drafts)
```

## Commands

| Command                              | Description                                           |
| ------------------------------------ | ----------------------------------------------------- |
| `uv run poe server`                  | Dev server WITH drafts (hot-reload)                   |
| `uv run poe server-prod`             | Dev server WITHOUT drafts (mirrors production)        |
| `uv run poe build`                   | Build static site (excludes drafts)                   |
| `uv run poe build-selfhost`          | Build self-hosted version (excludes drafts)           |
| `uv run poe create-post "Title"`     | Create a new timeline post (defaults to draft)        |
| `uv run poe fmt`                     | Format Python & Markdown files                        |
| `uv run poe lint-py`                 | Python lint check (ruff)                              |
| `uv run poe optimize-images <path>`  | Convert PNG/JPG/JPEG → WebP and update .md references |
| `uv run poe add-weight-week [count]` | Add empty week(s) to health weight data               |

## Writing Posts

### Timeline Posts (short, single-day)

```bash
# Default category: bits, as draft
uv run poe create-post "Your Title"

# Publish immediately (skip draft)
uv run poe create-post "Your Title" --no-draft

# Specify category and tags
uv run poe create-post "Your Title" --category dev --tags go,testing

# Custom slug (for Chinese titles)
uv run poe create-post "中文标题" --category thought --slug my-thought
```

Creates `docs/notes/posts/{category}/YYYYMMDD-slug.md` with frontmatter, RSS, and category archive support.

New posts default to **draft** (`draft: true` in frontmatter). They appear in `uv run poe server` (local dev) but are **excluded** from `uv run poe build` / CI deployment. Remove `draft: true` from the frontmatter or pass `--no-draft` to publish immediately.

### Drafts

#### Blog posts (via blog plugin)

Add `draft: true` to the frontmatter:

```yaml
---
title: My Draft Post
draft: true
---
```

- `mkdocs serve --drafts` / `uv run poe server` — **includes** drafts
- `mkdocs build` / `uv run poe build` — **excludes** drafts

#### Non-blog pages (research, tech, health, etc.)

This project uses a **custom MkDocs hook** (`plugins/draft_filter.py`) that
works the same way as the blog plugin — just add `draft: true` to any page's
frontmatter:

```yaml
---
title: WIP Research
draft: true
---
```

- `uv run poe server` (with `--drafts`) — **includes** draft pages
- `uv run poe build` / `uv run poe server-prod` (without `--drafts`) — **excludes** draft pages

The hook skips blog posts (`notes/posts/`), which are already handled by the
blog plugin's built-in draft support.

**Manual alternatives** (if you prefer not to use the hook):

1. **Don't add to `nav`** — file still builds at its `docs/` path, but won't appear in navigation. Useful for quick experiments.

1. **Add `robots: noindex`** to prevent search indexing:

   ```yaml
   ---
   title: Draft
   robots: noindex, nofollow
   ---
   ```

1. **Rename with `-draft.md` suffix** — already gitignored per project convention (see `.gitignore`), so it won't be committed.

### Optimize Images

Convert PNG/JPG/JPEG images to WebP for smaller file sizes:

```bash
# Single image
uv run poe optimize-images docs/path/to/img.png

# Multiple images or a directory
uv run poe optimize-images docs/research/docs/lux/*.png

# Everything under docs/
uv run poe optimize-images --all
```

This converts each image to WebP (quality=85) and updates all `.md` files that reference it.
Originals are left untouched.

### Study Notes (long-form, multi-day)

For topics that evolve over multiple days (e.g. English learning, system design):

```bash
# Create a study note manually
touch docs/notes/study/english.md
```

Study notes live under `docs/notes/study/` as plain MkDocs pages:

- No date frontmatter required
- No RSS (they are not blog posts)
- Add to nav in `mkdocs.yml` if desired:

```yaml
nav:
  - NOTES:
    - notes/index.md
    - English: notes/study/english.md
```

They coexist with timeline posts — `posts/` is managed by the blog plugin, `study/` is just regular pages.

## Health Tracking

Weight tracking with macros-generated tables and Mermaid trend charts.

### Structure

```
docs/health/
├── index.md              # Dashboard — auto-populated by macros
├── data/
│   └── weight.yml        # Weight data (the only file to maintain)
└── macros/
    └── weight_macros.py  # Jinja2 macros for tables & charts
```

### Daily Use

Open `docs/health/data/weight.yml` and fill in today's weight:

```yaml
weeks:
  # Week 4 — Mon 2026-08-17
  - days: [null, null, null, null, 69.0, null, null]
```

Keep `null` for skipped days. `mkdocs serve` auto-refreshes the page.

To start a new week:

```bash
uv run poe add-weight-week        # add 1 week
uv run poe add-weight-week -- 3   # add 3 weeks at once
```

## CI / Deployment

`.github/workflows/ci.yml` — lint all branches, deploy to GitHub Pages on push to `master`.

Set `GIT_HASH` env var to embed the current commit hash into the page HTML.
