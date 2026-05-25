# recycle.bin

Personal notes & research log — built with [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/), deployed to GitHub Pages.

## Directory Structure

```
.
├── .github/workflows/        # CI: MkDocs deploy to GitHub Pages
├── docs/
│   ├── notes/                # Blog posts (English)
│   │   └── posts/
│   ├── tech/                 # Tech reference pages
│   ├── research/             # Open-source reading notes
│   │   ├── docs/             # Research docs (per-project markdown)
│   │   ├── external/         # Cloned external repos (gitignored)
│   │   └── experiments/      # Hands-on experiments
│   └── assets/               # Static assets (images, etc.)
├── overrides/                # MkDocs theme overrides
├── mkdocs.yml                # MkDocs configuration
├── pyproject.toml            # Python project & PDM config
└── site/                     # Built output (gitignored)
```

## Environment

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.13 | Runtime |
| **PDM** | latest | Package & dependency manager |
| **MkDocs** | ≥1.6 | Static site generator |
| **Material for MkDocs** | ≥9.6 | Theme |

## Local Development

### Prerequisites (Conda)

```bash
# Create conda environment with Python 3.13
conda create -n mkdocs-env python=3.13 -y
conda activate mkdocs-env

# Install PDM
pip install pdm
```

### Setup & Run

```bash
# Install dependencies
pdm install

# Start dev server (hot-reload)
pdm run server
# or: mkdocs serve

# Build static site
pdm run build
# or: mkdocs build
```

## CI / Deployment

GitHub Actions workflow: `.github/workflows/deploy.yml`

- Trigger: push to `master`
- Build: `pdm install` → `mkdocs gh-deploy --force`
- Deploy target: GitHub Pages (`gh-pages` branch via [mkdocs gh-deploy](https://www.mkdocs.org/user-guide/deploying-your-docs/))
- Site URL: [https://xiongjia.github.io](https://xiongjia.github.io)
