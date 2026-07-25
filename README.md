# recycle.bin

Personal notes & research log — built with [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/), deployed to GitHub Pages.

## Quick Start

```bash
uv sync              # install dependencies
uv run poe server    # start dev server at http://localhost:8000
uv run poe build     # build static site
```

Format & lint: `uv run poe fmt` / `uv run poe lint-py`

## CI / Deployment

`.github/workflows/ci.yml` — lint all branches, deploy to GitHub Pages on push to `master`.
