## Project Structure (first-level)

```
xiongjia.github.com/
├── .github/          # CI workflow
├── dev/              # Design documents
├── docs/             # Site content (notes, research, health, etc.)
├── plugins/          # Custom MkDocs hooks (draft_filter, mermaid_assets)
├── scripts/          # Utility scripts (create-post, md2wechat, optimize-images, etc.)
├── overrides/        # Theme overrides (comments, meta tags, external links)
└── site/             # Build output (gitignored)
```

## Tech Stack

- **Static site generator**: [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- **Python**: 3.13
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **CI/CD**: GitHub Actions → GitHub Pages
- **Key plugins**: macros (jinja2 templates), mermaid2 (diagrams), drawio (diagrams), rss (feed), glightbox (images), minify

## DEV environment tips

```bash
uv sync                          # install dependencies
uv run poe server                # dev server WITH drafts (hot reload)
uv run poe server-prod           # dev server WITHOUT drafts (mirrors production)
uv run poe build                 # production build
uv run poe build-selfhost        # self-hosted build
uv run poe create-post "Title"   # new blog post (default: draft)
uv run poe fmt                   # format Python + Markdown
uv run poe lint-py               # Python lint check (ruff)
uv run poe optimize-images <path> # convert PNG/JPG/JPEG to WebP
uv run poe add-weight-week [n]   # add empty week(s) to weight data
uv run poe md2wechat [path]      # convert post to WeChat HTML
```

Site runs at `http://localhost:8000` by default.

See [dev/architecture.md](dev/architecture.md) for full command reference.

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
1. **Local draft files are ephemeral**: Files matching `*-draft.md` are local AI collaboration plans and must not be committed or referenced in any committed documentation. They are already git-ignored (see `.gitignore`).
