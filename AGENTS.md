## Project Structure

```
xiongjia.github.com/
├── .github/workflows/ci.yml        # CI: lint & deploy to GitHub Pages
├── mkdocs.yml                     # MkDocs configuration
├── pyproject.toml                 # Python project config & dependencies
├── docs/                          # All content (Markdown)
│   ├── index.md                   # Home page
│   ├── notes/                     # Blog posts (MkDocs blog plugin)
│   │   └── posts/
│   ├── research/                  # Research notes (open-source code reading)
│   │   ├── research.md            # Index of research topics
│   │   └── docs/
│   │       ├── better-auth/
│   │       ├── jellyfin/
│   │       ├── lux/
│   │       ├── nestjs/
│   │       ├── nest-commander/
│   │       └── trip/
│   ├── tech/                      # Tech reference pages
│   └── health/                    # Personal health tracking
│       ├── index.md               # Dashboard (auto-populated by macros)
│       ├── data/
│       │   └── weight.yml         # Weight data (the only file to maintain)
│       └── macros/
│           └── weight_macros.py   # Jinja2 macros for tables & charts
├── scripts/                       # Utility scripts
│   ├── create-post.py             #   New blog post scaffolding
│   ├── optimize_images.py         #   PNG/JPG/JPEG → WebP converter (keeps originals)
│   └── add_weight_week.py         #   Add empty week to health weight data
├── overrides/                     # MkDocs Material theme overrides
└── site/                          # Build output (gitignored)
```

## Tech Stack

- **Static site generator**: [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- **Python**: 3.13
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **CI/CD**: GitHub Actions → GitHub Pages
- **Key plugins**: macros (jinja2 templates), mermaid2 (diagrams), drawio (diagrams), rss (feed), glightbox (images), minify

## DEV environment tips

```bash
# Install dependencies
uv sync

# Start local dev server WITH drafts (hot reload)
uv run poe server

# Start local dev server WITHOUT drafts (mirrors production)
uv run poe server-prod

# Build for production (excludes drafts)
uv run poe build

# Build self-hosted version (excludes drafts)
uv run poe build-selfhost

# Create a new blog post (defaults to draft)
uv run poe create-post "Your Title"         # as draft
uv run poe create-post "Your Title" --no-draft  # publish immediately

# Optimise images (convert PNG/JPG/JPEG to WebP, keeps originals)
#   Single:  uv run poe optimize-images docs/path/to/img.png
#   Batch:   uv run poe optimize-images docs/research/docs/lux/
#   All:     uv run poe optimize-images --all

# Health tracking — add an empty week
uv run poe add-weight-week          # add 1 week
uv run poe add-weight-week -- 3     # add 3 weeks at once
```

Site runs at `http://localhost:8000` by default.

## Coding Principles

1. **Developer approval required before executing a plan**: AI must not initiate any execution plan (batch edits, refactoring, multi-file changes, or state-altering commands) without explicit developer approval. Simple Q&A, file inspection, or single edits (e.g., fixing a typo) are exempt.
1. **Developer approval required before committing**: AI must not execute `git commit` unless the developer explicitly approves. All changes must remain in the working directory for developer review first.
1. **Never push**: AI **must never** execute `git push` or any equivalent remote push operation. Push can only be performed manually by the developer.
1. **Code review required before push**: All changes must be reviewed and approved by a human before pushing to remote branches.
1. **Research notes use AI assistance disclaimer**: All files under `docs/research/` must include the AI-generated disclaimer frontmatter.
1. **Chinese content for research docs**: Research notes are written in Chinese; blog posts and tech reference pages may be in either language.
1. **Use relative links**: All internal links between docs pages should use relative paths (e.g. `./docs/lux/00-lux.md`).
1. **Frontmatter required for research docs**: Each research doc must have `title`, `tags`, and `categories` frontmatter.
1. **Conventional commits**: Follow `type(scope): description` format (e.g. `docs: add Jellyfin research notes`).
1. **Local draft files are ephemeral**: Files matching `*-draft.md` are local AI
   collaboration plans and must not be committed or referenced in any committed
   documentation. They are already git-ignored (see `.gitignore`).
