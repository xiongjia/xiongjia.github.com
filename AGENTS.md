## Project Structure (first-level)

```
xiongjia.github.com/
├── .github/          # CI workflow
├── dev/              # Design documents & plans (see dev/plans/)
├── docs/             # Site content (notes, research, health, etc.)
├── plugins/          # Custom MkDocs hooks (draft_filter, mermaid_assets, mkdocs_moment)
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
uv run poe create-moment "Text"  # new Moment micro-post
uv run poe fmt                   # format Python + Markdown
uv run poe lint-py               # Python lint check (ruff)
uv run poe optimize-images <path> # convert PNG/JPG/JPEG to WebP
uv run poe add-weight-week [n]   # add empty week(s) to weight data
uv run poe md2wechat [path]      # convert post to WeChat HTML
```

Site runs at `http://localhost:8000` by default.

See [dev/architecture.md](dev/architecture.md) for full command reference.

## Coding Principles

- **Never switch or create branches**: AI must not `git checkout`, `git switch`, `git branch`, `git rebase`, or create any new branch without explicit developer approval. Work only on the current branch.
- **Developer approval required before executing a plan**: AI must not initiate any execution plan (batch edits, refactoring, multi-file changes, or state-altering commands) without explicit developer approval. Simple Q&A, file inspection, or single edits (e.g., fixing a typo) are exempt.
- **Developer approval required before committing**: AI must not execute `git commit` unless the developer explicitly approves. All changes must remain in the working directory for developer review first.
- **Never push**: AI **must never** execute `git push` or any equivalent remote push operation. Push can only be performed manually by the developer.
- **Code review required before push**: All changes must be reviewed and approved by a human before pushing to remote branches.
- **Research notes use AI assistance disclaimer**: All files under `docs/notes/research/` must include the AI-generated disclaimer frontmatter.
- **Chinese content for research docs**: Research notes are written in Chinese; blog posts and tech reference pages may be in either language.
- **Use relative links**: All internal links between docs pages should use relative paths (e.g. `./docs/lux/00-lux.md`).
- **Frontmatter required for research docs**: Each research doc must have `title`, `tags`, and `categories` frontmatter.
- **Conventional commits**: Follow `type(scope): description` format (e.g. `docs: add Jellyfin research notes`).
- **Local draft files are ephemeral**: Files matching `*-draft.md` are local AI collaboration plans and must not be committed or referenced in any committed documentation. They are already git-ignored (see `.gitignore`).
- **Plans live in `dev/plans/`**: Task/feature tracking goes in `dev/plans/<plan-name>.md`. See `dev/plans/plan-index.md` for template and status conventions.
