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
│   └── tech/                      # Tech reference pages
├── overrides/                     # MkDocs Material theme overrides
└── site/                          # Build output (gitignored)
```

## Tech Stack

- **Static site generator**: [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- **Python**: 3.13
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **CI/CD**: GitHub Actions → GitHub Pages
- **Key plugins**: mermaid2 (diagrams), drawio (diagrams), rss (feed), glightbox (images), minify

## DEV environment tips

```bash
# Install dependencies
uv sync

# Start local dev server (hot reload)
uv run poe server

# Build for production
uv run poe build

# Build self-hosted version
uv run poe build-selfhost
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
