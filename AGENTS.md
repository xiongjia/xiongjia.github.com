## Project Structure (first-level)

```
xiongjia.github.com/
├── .github/          # CI workflow
├── docs/             # Site content (notes, research, knowledge, health, etc.)
├── external/         # External research data (source clones, books, etc.; never committed)
├── internal/         # Dev docs & plans: design docs, architecture.md,
│   └── plans/        #   plan-index.md; archived plans in plans/arch/
├── plugins/          # Custom MkDocs hooks (draft_filter, mermaid_assets, mkdocs_moment)
├── prototypes/       # Experimental mini-projects (committed; per-prototype .gitignore, see Convention)
├── scripts/          # Utility scripts (create_post, sync_running, update_health_summary, etc.)
├── shared/           # Shared utilities for plugins & scripts (strings, frontmatter, date, io)
├── tests/            # Unit & integration tests (pytest)
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
uv sync                            # install dependencies
uv run poe server                  # dev server WITH drafts (hot reload)
uv run poe server-prod             # dev server WITHOUT drafts (mirrors production)
uv run poe server-bucket           # dev server WITH bucket prefix rewrite (test bucket link replacement)
uv run poe build                   # production build
uv run poe build-drafts            # build including drafts (MKDOCS_INCLUDE_DRAFTS=true)
uv run poe build-selfhost          # self-hosted build
uv run poe create-post "Title"     # new blog post (default: draft)
uv run poe create-moment "Text"    # new Moment micro-post (--draft hides in prod; --image auto-WebP+bucket)
uv run poe fmt                     # format Python + Markdown
uv run poe lint-py                 # Python lint check (ruff)
uv run poe test                    # run unit tests (pytest, tests/)
uv run poe optimize-images <path>  # convert PNG/JPG/JPEG to WebP
uv run poe add-weight-week [n]     # add empty week(s) to weight data
uv run poe update-weight 82 [date] # record daily weight (default: today)
uv run poe update-health-summary   # regenerate health index summary (calls local pi)
uv run poe sync-running            # sync running data from the Garmin CN API (incremental)
uv run poe sync-running-splits     # upload running splits/polyline to R2 (dry-run; --confirm or SYNC_RUNNING_CONFIRM=true)
uv run poe bucket-sync pull       # pull docs/assets/bucket/ from R2/S3 via rclone (incremental: checksum + fast-list by default; read-only, dry-run by default; uploads happen in PicList)
uv run poe bucket-check [--check-remote] # cross-check bucket assets vs markdown references (orphans to clean + broken links; --check-remote checks against the bucket)
uv run poe bucket-upload img.png --confirm  # upload an image to the bucket as WebP (rename rule from mkdocs.yml; dry-run by default, --confirm uploads; needs a read-write R2 token in .env)
uv run poe md2wechat [path]        # convert post to WeChat HTML
```

Site runs at `http://localhost:8000` by default.

Note: the dev servers bind 0.0.0.0 (`poe server*` on :8000, `poe api-server*` on :8100); the API has **no auth** — keep it on a trusted
network or pin `BOT_API_HOST=127.0.0.1` for local-only.

**Bot scheduled jobs (cron)**: configured in `mkdocs.yml` → `extra.bot.cron`
(schedule / spec / handoff per job; text DOW names like `SAT` — APScheduler
maps numeric DOW 0=Monday…6=Sunday). Runs inside the API process
(`poe api-server` must be up) via `poe bot` handoff draft PRs; runtime
disable/enable persisted in `.bot-api/cron-state.json`, kill switch
`BOT_API_CRON_ENABLED=false`. See `internal/plans/arch/bot-cronjob.md`
and `internal/commands.md` → Bot Remote API.

## Bucket-hosted assets (R2/S3)

Large site files (mainly WebP images) live outside git on an R2/S3 bucket.

- md always uses **local relative paths** (e.g. `../../assets/bucket/food.webp`);
  the build rewrites `assets/bucket/` → `base_url` (see
  [internal/bucket-design.md](internal/bucket-design.md)). Switching buckets =
  changing `extra.bucket.mappings[].base_url` in mkdocs.yml, md untouched.
- Local copies stay in `docs/assets/bucket/` (git-ignored) so VSCode preview works.
- Upload via **PicList** (store path = `remote_prefix`, e.g. `web-assets/img/`) or
  `poe bucket-upload` (auto WebP + rename + upload, dry-run by default, `--confirm` to upload, needs a read-write R2
  token);
  pull back with `poe bucket-sync pull` (read-only rclone sync, dry-run default).
- **Credentials (R2 access keys) are developer-local only** (rclone.conf / PicList)
  — never commit them; env test hooks: `MKDOCS_BUCKET_ENABLED`,
  `MKDOCS_BUCKET_BASE_URL`.

## Network / Proxy tips

访问 GitHub 等外部资源失败时，优先使用环境变量中已有的代理：

```bash
curl -x "$https_proxy" ...   # 或 $http_proxy / $HTTPS_PROXY
```

若 `$http_proxy` / `$https_proxy` 未设置，可尝试默认本地代理 `http://127.0.0.1:1095`：

```bash
curl -x http://127.0.0.1:1095 ...
```

See [internal/architecture.md](internal/architecture.md) for full command reference.

## Prototype Convention

- **Location**: experimental mini-projects live in `prototypes/<name>/`
  (kebab-case), one subdirectory per prototype, each with its own `README.md`
  (purpose, usage, current status) and its own environment (Rust cargo,
  Python `.venv`, Node, etc.)

- **English content**: everything under `prototypes/` (index README,
  per-prototype READMEs, code comments) is written in English; the site
  listing page `docs/notes/prototypes.md` is in Chinese (it is a `docs/`
  page, not prototype content)

- **Prototypes are committed**: unlike agent-tool dirs (`.claude/*`, `.pi/*`),
  prototype code goes into the repo — no root-level ignore rules for
  `prototypes/`

- **Per-prototype `.gitignore`**: each prototype ignores its own build
  artifacts (e.g. Rust `/target`, Python `.venv/`, Node `node_modules/`)
  inside its own `.gitignore`

- **Index**: `prototypes/README.md` lists all prototypes (name, description,
  created, status) — always update it when a prototype is added/removed.
  Status vocabulary: `experimental` (initial, not validated), `working`
  (validated locally and usable) — avoid inventing new status words.

- **fmt / lint skip**: `prototypes` is in ruff's `extend-exclude`
  (`pyproject.toml`), so the main Python toolchain never formats/lints
  prototype code; mdformat already skips it via explicit path args

- **AI / dev tooling still works on prototypes**: the exclude only affects
  repo-wide automation (`poe fmt`, `poe lint-py`, CI). Reading, editing, and
  building prototype code (AI or manual) is unaffected. For a Python
  prototype that needs manual lint/format, pass explicit paths —
  `extend-exclude` does not block them:

  ```bash
  uv run ruff check prototypes/<name>/        # lint one prototype
  uv run ruff format prototypes/<name>/       # format one prototype
  uv run mdformat prototypes/<name>/README.md # format its markdown
  ```

  A prototype may also carry its own `pyproject.toml`/config to override
  repo-wide rules for its own code.

- **Prototypes are not part of the MkDocs build** (not registered in
  `mkdocs.yml`); a validated prototype can be promoted to a real project
  (plan in `internal/plans/` or a standalone repo)

- **No GitHub CI for prototypes**: CI (`.github/workflows/ci.yml`) only runs
  the main repo checks — pytest, ruff, format checks, and the MkDocs build.
  Prototypes are excluded by design and never built or tested by CI; verify
  them locally (e.g. `cargo build` / `cargo test` for Rust, `pnpm build` /
  `pnpm test` for Node) in the prototype's own environment

## Coding Principles

- **Never switch or create branches**: AI must not `git checkout`, `git switch`, `git branch`, `git rebase`, or create any new branch without explicit developer approval. Work only on the current branch.
- **Developer approval required before executing a plan**: AI must not begin executing any plan — whether a plan file under `internal/plans/`, or any multi-step execution (batch edits, refactoring, multi-file changes, or state-altering commands) — without explicit developer approval. Creating or updating a plan file is exempt; executing it is not. Simple Q&A, file inspection, or single edits (e.g., fixing a typo) are exempt.
- **Developer approval required before committing**: AI must not execute `git commit` unless the developer explicitly approves. All changes must remain in the working directory for developer review first.
- **Never push**: AI **must never** execute `git push` or any equivalent remote push operation. Push can only be performed manually by the developer.
- **Code review required before push**: All changes must be reviewed and approved by a human before pushing to remote branches.
- **AI assistance disclaimer (Notes-level)**: The Notes landing page (`docs/notes/_index_content.md`) carries a single "部分内容由 AI 生成" disclaimer; per-page disclaimers under `docs/notes/research/` and `docs/notes/knowledge/` are not required.
- **Chinese content for research docs**: Research notes and knowledge docs are written in Chinese; blog posts and tech reference pages may be in either language.
- **Knowledge topic structure**: Knowledge docs (`docs/notes/knowledge/`) are a long-term knowledge base organized as Topics. A Topic = a directory with an `index.md` entry (e.g. `infrastructure/`); sub-topics are subdirectories or docs inside it, and a topic may evolve into multiple files/layers over time. Each knowledge point is its own doc file under the topic dir (e.g. `object-storage/signed-url.md`), never the topic's `index.md`. Topics can incubate from Collection link pages or settle from Research reading notes.
- **Use relative links**: All internal links between docs pages should use relative paths (e.g. `./topics/lux/`).
- **Frontmatter required for research docs**: Each research doc must have `title`, `tags`, and `categories` frontmatter.
- **Conventional commits**: Follow `type(scope): description` format (e.g. `docs: add Jellyfin research notes`).
- **Commit messages in English**: Write git commit messages in English by default; use Chinese only when it is necessary to describe special terms or names (e.g. proper nouns without a natural English equivalent).
- **Vision verification — prefer DOM over screenshots**: The AI model cannot view images by default (screenshots and other image attachments fail to be read). When visual verification is needed (rendered page layout, map controls, markers, etc.), verify via DOM instead: headless Chrome `--dump-dom` with injected JS that reports state through `document.title` or visible text, `curl` + grep on generated HTML, or unit tests asserting on the built output. Do not rely on `--screenshot` / reading PNG files.
- **Local draft files are ephemeral**: Files matching `*-draft.md` are local AI collaboration plans and must not be committed or referenced in any committed documentation. They are already git-ignored (see `.gitignore`).
- **Plans live in `internal/plans/`**: Task/feature tracking goes in `internal/plans/<plan-name>.md`. See `internal/plans/plan-index.md` for template and status conventions. Done/cancelled plans are archived to `internal/plans/arch/` (git mv) with `archived` + `status: completed|cancelled` frontmatter.
- **Python file naming — snake_case**: Python files/modules use lowercase with underscores
  (PEP 8), e.g. `create_post.py`, `add_weight_week.py`, `draft_filter.py`. Hyphenated
  names (`create-post.py`) are forbidden — they cannot be imported with a regular
  `import` statement. This applies to `scripts/`, `plugins/`, and `tests/`.
- **CLI / poe task naming — kebab-case**: Command names (poe tasks, CLI entrypoints)
  keep hyphens, e.g. `poe create-post`, `poe optimize-images`. The hyphenated CLI
  name maps to a snake_case script (`poe create-post` → `scripts/create_post.py`).
