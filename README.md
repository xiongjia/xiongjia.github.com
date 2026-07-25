# recycle.bin

Personal notes & research log — built with [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/), deployed to GitHub Pages.

## Quick Start

```bash
uv sync                          # install dependencies
GIT_HASH=$(git rev-parse --short HEAD) uv run poe server  # start dev server
GIT_HASH=$(git rev-parse --short HEAD) uv run poe build   # build static site
```

### Commands

| Command                     | Description                   |
| --------------------------- | ----------------------------- |
| `uv run poe server`         | Start dev server (hot-reload) |
| `uv run poe build`          | Build static site             |
| `uv run poe fmt`            | Format Python files (ruff)    |
| `uv run poe lint-py`        | Python lint check (ruff)      |
| `uv run poe build-selfhost` | Build self-hosted version     |

Set `GIT_HASH` env var to embed the current commit hash into the page HTML.

## CI / Deployment

`.github/workflows/ci.yml` — lint all branches, deploy to GitHub Pages on push to `master`.
