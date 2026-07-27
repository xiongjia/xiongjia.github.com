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
└── side-projects/        # Tangible project outputs
```

**Knowledge pipeline**: Notes → Collection → Research → Side Projects.

## Quick Start

```bash
uv sync                                    # install dependencies
GIT_HASH=$(git rev-parse --short HEAD) uv run poe server  # start dev server
```

## Commands

| Command                          | Description                    |
| -------------------------------- | ------------------------------ |
| `uv run poe server`              | Start dev server (hot-reload)  |
| `uv run poe build`               | Build static site              |
| `uv run poe build-selfhost`      | Build self-hosted version      |
| `uv run poe create-post "Title"` | Create a new timeline post     |
| `uv run poe fmt`                 | Format Python & Markdown files |
| `uv run poe lint-py`             | Python lint check (ruff)       |
| `uv run poe optimize-images <path>` | Convert PNG/JPG/JPEG → WebP and update .md references |

## Writing Posts

### Timeline Posts (short, single-day)

```bash
# Default category: bits
uv run poe create-post "Your Title"

# Specify category and tags
uv run poe create-post "Your Title" --category dev --tags go,testing

# Custom slug (for Chinese titles)
uv run poe create-post "中文标题" --category thought --slug my-thought
```

Creates `docs/notes/posts/{category}/YYYYMMDD-slug.md` with frontmatter, RSS, and category archive support.

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

## CI / Deployment

`.github/workflows/ci.yml` — lint all branches, deploy to GitHub Pages on push to `master`.

Set `GIT_HASH` env var to embed the current commit hash into the page HTML.
