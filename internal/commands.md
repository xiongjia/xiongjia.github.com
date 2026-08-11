# Commands — Command Reference

> All commands run via `uv run poe` from the repo root.
> Environment & architecture details: [architecture.md](./architecture.md).

## Outline

- **Dev & Build** — `server` / `server-prod` / `server-bucket` / `build` / `build-drafts` / `build-selfhost`
- **Quality** — `fmt` / `lint-py` / `test`
- **Content** — `create-post` / `create-moment` / `enu add`
- **Health** — `update-weight` / `add-weight-week` / `update-health-summary` / `sync-running`
- **Assets & Conversion** — `optimize-images` / `md2wechat` / `bucket-sync pull` / `rclone-config-init`
- **English Scraps flow** — collect → batch-organize → review

## Dev & Build

| Command              | Description                                                   |
| -------------------- | ------------------------------------------------------------- |
| `poe server`         | Dev server WITH drafts (hot reload) → `http://localhost:8000` |
| `poe server-prod`    | Dev server WITHOUT drafts (mirrors production)                |
| `poe server-bucket`  | Dev server + bucket prefix rewrite (test bucket link rewrite) |
| `poe build`          | Production build (excludes drafts)                            |
| `poe build-drafts`   | Build including drafts (`MKDOCS_INCLUDE_DRAFTS=true`)         |
| `poe build-selfhost` | Self-hosted build (separate `site-selfhost/` dir)             |

> **Debug**: `GIT_HASH=$(git rev-parse --short HEAD) uv run poe server` embeds the
> current commit hash into the page HTML meta — only needed when debugging
> the hash display; daily `uv run poe server` is enough.

## Quality

| Command       | Description                                                     |
| ------------- | --------------------------------------------------------------- |
| `poe fmt`     | Format Python (ruff) + Markdown (mdformat, incl. `.pi/skills/`) |
| `poe lint-py` | Python lint check (ruff)                                        |
| `poe test`    | Run unit tests (pytest, `tests/`)                               |

## Content

| Command                    | Description                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------ |
| `poe create-post "Title"`  | New blog post (draft by default; `--no-draft` publish; `--time` backdate; `--category`/`--tags`) |
| `poe create-moment "Text"` | New Moment micro-post (`--draft` hidden in prod; `--image`; `--time` backdate)                   |
| `poe enu add "scrap"`      | English Scraps: append a scrap to the inbox (auto date; `--date` backdate)                       |

## Health

| Command                       | Description                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `poe update-weight 82 [date]` | Record a daily weight (default: today; date accepts `yesterday`, full dates) |
| `poe add-weight-week [n]`     | Pre-add empty week(s) to weight data                                         |
| `poe update-health-summary`   | Regenerate the health index summary (calls local pi AI)                      |
| `poe sync-running`            | Sync running data from the deployed running_page                             |

## Assets & Conversion

| Command                            | Description                                                                                                 |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `poe optimize-images <path>`       | PNG/JPG/JPEG → WebP                                                                                         |
| `poe md2wechat [path]`             | Convert blog post to WeChat HTML                                                                            |
| `poe bucket-sync pull [--confirm]` | Pull `docs/assets/bucket/` from R2/S3 via rclone (read-only, dry-run by default; uploads happen in PicList) |
| `poe rclone-config-init`           | Configure rclone R2 remote from `.env` (local credentials only)                                             |

## .env Configuration

Developer-local env config, git-ignored — copy the committed template:

```bash
cp .env.example .env    # shared defaults (git-ignored)
# .env.local            # machine/user-specific overrides (git-ignored)
```

**Load order** (see `shared/env.py`): shell / CI env > `.env.local` > `.env`.
Missing files are ignored; real secrets never committed (rclone.conf / PicList
keep their own copies).

What it configures:

| Variable                                                                                         | Purpose                                                                          |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`                                    | R2 API credentials for `poe rclone-config-init`                                  |
| `BUCKET_SYNC_REMOTE` / `BUCKET_SYNC_BUCKET` / `BUCKET_SYNC_PREFIX` / `BUCKET_SYNC_REMOTE_PREFIX` | rclone / bucket-sync overrides (priority: CLI arg > env > mkdocs.yml)            |
| `RCLONE_HTTP_PROXY`                                                                              | rclone proxy (e.g. `http://127.0.0.1:1095`; needed when R2 unreachable directly) |
| `MKDOCS_BUCKET_ENABLED` / `MKDOCS_BUCKET_BASE_URL`                                               | Force bucket prefix rewrite / override `base_url` for testing                    |
| `SITE_NAME` / `SITE_URL` / `GIT_HASH`                                                            | Site title / canonical URL / commit hash overrides                               |
| `CF_ANALYTICS_TOKEN` / `MERMAID_CDN_URL`                                                         | Analytics beacon token / mermaid JS CDN fallback                                 |

Full env table (with defaults): [architecture.md](./architecture.md) →
Environment Variables; full R2/bucket setup: [bucket-design.md](./bucket-design.md).

## Common Examples

```bash
# Blog post (draft by default, --no-draft to publish)
uv run poe create-post "My Post Title"
uv run poe create-post "My Post" --category dev --tags go,cli
uv run poe create-post "My Post" --no-draft

# Backdate — --time accepts 9am / 9pm / 21:30 / yesterday / day+time / full date
uv run poe create-post "My Post" --time "9:30am"       # today 09:30
uv run poe create-post "My Post" --time "yesterday"    # yesterday, same time
uv run poe create-post "My Post" --time "30 9am"       # this month, 30th 09:00
uv run poe create-post "My Post" --time "2026-07-30 21:36"

# Moment
uv run poe create-moment "Hello 👋"
uv run poe create-moment "With image" --image photo.webp
uv run poe create-moment "Draft idea" --draft    # hidden in production
uv run poe create-moment "Backfill" --time "9pm"

# English Scraps — jot down English learning scraps
uv run poe enu add "cumbersome"
uv run poe enu add "The implementation is cumbersome to maintain." --date 2026-08-08

# Weight
uv run poe update-weight 82
uv run poe update-weight 81.6 2026-08-05
uv run poe update-weight 82 --date yesterday
uv run poe add-weight-week 2               # pre-add empty weeks
```

## English Scraps Flow

Collect → batch-organize → review (all actions are **enu-organize skill**
invocations, `/skill:enu-organize <action>`):

1. **Collect**: `poe enu add "scrap"`, or `/skill:enu-organize add <scrap>` in pi
1. **Organize**: when a batch accumulates (inbox ≥ 15 lines / ≥ 2 weeks / on demand) →
   `/skill:enu-organize arch`
1. **Review**: `/skill:enu-organize quiz [范围]` / `/skill:enu-organize review <tag>`

Full workflow & fields: `docs/notes/research/topics/english/scraps/index.md`;
skill workflow doc: `.pi/skills/enu-organize/SKILL.md`.
