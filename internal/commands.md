# Commands — Command Reference

> All commands run via `uv run poe` from the repo root.
> Environment & architecture details: [architecture.md](./architecture.md).

## Outline

- **Dev & Build** — `server` / `server-prod` / `server-bucket` / `build` / `build-drafts` / `build-selfhost`
- **Quality** — `fmt` / `lint-py` / `test`
- **Content** — `create-post` / `create-moment` / `enu add`
- **Health** — `update-weight` / `add-weight-week` / `update-health-summary` / `sync-running`
- **Bot** — `bot <task>` / `bot --plan` / `bot list` / `bot submit` / `bot abort` / `bot cleanup`
- **Assets & Conversion** — `optimize-images` / `md2wechat` / `bucket-sync pull` / `bucket-upload` / `rclone-config-init`
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

| Command                    | Description                                                                                                                                   |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `poe create-post "Title"`  | New blog post (draft by default; `--no-draft` publish; `--time` backdate; `--category`/`--tags`)                                              |
| `poe create-moment "Text"` | New Moment micro-post (`--image` auto-WebP + bucket upload; `--tags`; geo `--place/--lng/--lat`; `--draft` hidden in prod; `--time` backdate) |
| `poe enu add "scrap"`      | English Scraps: append a scrap to the inbox (auto date; `--date` backdate)                                                                    |

## Health

| Command                       | Description                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `poe update-weight 82 [date]` | Record a daily weight (default: today; date accepts `yesterday`, full dates) |
| `poe add-weight-week [n]`     | Pre-add empty week(s) to weight data                                         |
| `poe update-health-summary`   | Regenerate the health index summary (calls local pi AI)                      |
| `poe sync-running`            | Sync running data from the deployed running_page                             |

## Bot (auto PR)

Local bot: runs task scripts in an isolated `git worktree` and publishes the
result as a PR (format → local CI checks → commit → push → draft PR →
optional auto-merge). Design: [bot-auto-pr-design.md](./bot-auto-pr-design.md).

Tasks are registered in `mkdocs.yml` → `extra.bot.tasks` (template tasks:
`args` / `cmd` / `commit` / `body` format strings); builtins like `weight` /
`enu` live in `scripts/git_bot.py` and can be overridden by name.

| Command                                 | Description                                                                                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `poe bot "weight 82" "text-moment ..."` | Run task(s) and publish — one-step `--now` (default) or `--preview` (stop before commit)                                                               |
| `poe bot "text-moment 内容"`            | Text-only moment (content from the user); `--preview` to stop early                                                                                    |
| `poe bot "enu cumbersome"`              | English Scraps: append a scrap to the inbox via the bot (free-text content auto-joined; `--date`/`--dir` stay options)                                 |
| `poe bot "weight 81.5" --auto-merge`    | One step + auto squash-merge when CI is green                                                                                                          |
| `poe bot "weight 81.5" --handoff`       | Draft PR then clean up locally — dev handles the PR (default)                                                                                          |
| `poe bot --plan morning 81.5`           | Run a local plan file (`.bot/plans/morning.yml`, git-ignored, created by you — format in the design doc); vars via positional args / `--var key=value` |
| `poe bot list`                          | List bot instances (bot name / worktree path / state / start time)                                                                                     |
| `poe bot submit <name>`                 | Submit a `ready` (previewed) instance: commit + push + draft PR                                                                                        |
| `poe bot abort <name>`                  | Discard an unfinished instance (close PR + delete branches if already pushed)                                                                          |
| `poe bot cleanup [<name>]`              | Clean merged instances (skips active ones; `--force` removes stale)                                                                                    |

Needs `BOT_GH_TOKEN` (fine-grained PAT) in `.env` — see the design doc's
Credential Strategy for the one-time token setup.

## Assets & Conversion

| Command                             | Description                                                                                                                                                          |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `poe optimize-images <path>`        | PNG/JPG/JPEG → WebP                                                                                                                                                  |
| `poe md2wechat [path]`              | Convert blog post to WeChat HTML                                                                                                                                     |
| `poe bucket-sync pull [--confirm]`  | Pull `docs/assets/bucket/` from R2/S3 via rclone (incremental: `--checksum` + `--fast-list` on by default; read-only, dry-run by default; uploads happen in PicList) |
| `poe bucket-check [--check-remote]` | Cross-check bucket assets vs md references: unreferenced local files (cleanup) + md links missing from the bucket (details below)                                    |
| `poe bucket-upload <images>`        | Convert PNG/JPG/JPEG → WebP, rename + upload to R2 (details below)                                                                                                   |
| `poe rclone-config-init`            | Configure rclone R2 remote from `.env` (local credentials only)                                                                                                      |

`poe bucket-upload` details:

- **Safety**: **dry-run by default** — nothing is written/uploaded without `--confirm`. Source files larger than `extra.bucket.upload.max_size_mb` (default 10 MB) fail immediately (`--max-size-mb` / `BUCKET_UPLOAD_MAX_SIZE_MB` override).
- **Flow**: convert to WebP (`--quality 1-100`, default from `extra.optimize_images.quality`) → render the key → stage in the temp dir → `rclone copyto` → save a local copy under `docs/assets/bucket/` → print the md link.
- **Key rule** (`extra.bucket.upload.rule`, default `img/{Y}/{m}/{d}_{h}{i}{s}_{filename}`): `img` = image category dir in the bucket; `{Y}` year(4), `{m}`/`{d}`/`{h}`/`{i}`/`{s}` month/day/hour/min/sec (2); `{filename}` = original stem, lowercased, ASCII letters+digits only, spaces → `_`, pure-Chinese → `fallback_name` (`noname`); a `.webp` suffix is appended automatically. Key = `remote_prefix` + rendered rule, e.g. `data/img/img/2026/08/16_101112_myphoto.webp`.
- **Options**: `--confirm` (actually upload) / `--rule` / `--fallback-name` / `--max-size-mb` / `--tmp-dir` (staging dir, default `.bucket/` at repo root, git-ignored) / `--remote` (auto-detected from `rclone listremotes` when omitted) / `--bucket` / `--prefix` / `--remote-prefix` (priority: CLI arg > env > mkdocs.yml).
- **Permission**: needs a **read-write** R2 token (Object Read + Object Write + List Bucket) in `.env` — `bucket-sync pull` only needs read. Update `R2_*` and re-run `poe rclone-config-init`.

`poe bucket-sync` details:

- **Incremental by default**: `rclone sync` compares size + checksum (S3 ETag = MD5 for single-part uploads) and transfers only what changed — a second `pull` with no changes transfers nothing. `--checksum` (default on) skips modtime, so files whose local mtime differs from the remote LastModified (dropped in locally, uploaded via PicList) are not re-downloaded; `--fast-list` (default on) collapses recursive listing into one API call. `--no-checksum` / `--no-fast-list` fall back to legacy size+modtime / per-directory listings (multipart-uploaded objects have non-MD5 ETags and always transfer under `--checksum`).

Examples:

```bash
uv run poe bucket-sync pull                       # dry-run preview (safe default)
uv run poe bucket-sync pull --confirm             # apply: mirror bucket → docs/assets/bucket/ (deletes local extras)
uv run poe bucket-sync pull --remote b2 --prefix assets/bucket   # other remote / local prefix
uv run poe bucket-sync pull --no-checksum         # multipart-uploaded objects? fall back to size+modtime
```

`poe bucket-check` details:

- **Dry-run by design** — nothing deleted/written; exit 1 when issues found.
- **`[unreferenced]`** — local bucket files no md/html references (cleanup candidates; drafts count as references by default, `--no-drafts` to exclude them).
- **`[missing]`** — md/html bucket links whose local file is absent (broken link / never uploaded / typo). Links are found by scanning every `*.md` under `docs/` + `*.html` under `docs/`/`overrides/` for `assets/bucket/` tokens, resolved relative to the referencing file.
- **`--check-remote`** — checks md links against the actual bucket objects (`rclone lsf`): `[missing-remote]` = links absent from the bucket; `[not-uploaded]` = local files absent from the bucket (pending upload; `bucket-sync pull --confirm` would delete them). `--remote`/`--bucket`/`--remote-prefix` imply `--check-remote`.
- **Filters / output**: `--only-unreferenced` / `--only-missing` / `--json` (machine-readable).

Example output (stale local file + a broken link):

```text
bucket-check: prefix 'assets/bucket/' — local dir docs/assets/bucket (3 file(s)), 3 reference(s) from md/html (drafts included)

[missing] 1 md/html link(s) → no local bucket file:
  2026/08/nonexistent_zzz.webp
    ← docs/moments/2026-08/14-0000.md

[unreferenced] 1 local bucket file(s) not referenced by md/html (cleanup candidates):
  2026/08/orphan.webp  (0.0 KiB)

Summary: 2 issue(s) found → exit 1
```

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

| Variable                                                                                                     | Purpose                                                                                                   |
| ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`                                                | R2 API credentials for `poe rclone-config-init` (token scope: see `bucket-upload` notes above)            |
| `BUCKET_SYNC_REMOTE` / `BUCKET_SYNC_BUCKET` / `BUCKET_SYNC_PREFIX` / `BUCKET_SYNC_REMOTE_PREFIX`             | rclone / bucket-sync overrides (priority: CLI arg > env > mkdocs.yml)                                     |
| `BUCKET_UPLOAD_RULE` / `BUCKET_UPLOAD_FALLBACK_NAME` / `BUCKET_UPLOAD_TMP_DIR` / `BUCKET_UPLOAD_MAX_SIZE_MB` | `bucket-upload` rename rule / fallback name / staging dir / size limit overrides (reuses `BUCKET_SYNC_*`) |
| `RCLONE_HTTP_PROXY`                                                                                          | rclone proxy (e.g. `http://127.0.0.1:1095`; needed when R2 unreachable directly)                          |
| `MKDOCS_BUCKET_ENABLED` / `MKDOCS_BUCKET_BASE_URL`                                                           | Force bucket prefix rewrite / override `base_url` for testing                                             |
| `SITE_NAME` / `SITE_URL` / `GIT_HASH`                                                                        | Site title / canonical URL / commit hash overrides                                                        |
| `CF_ANALYTICS_TOKEN` / `MERMAID_CDN_URL`                                                                     | Analytics beacon token (empty disables the beacon) / mermaid JS CDN fallback                              |
| `BOT_GH_TOKEN` / `BOT_WORKTREE_DIR`                                                                          | Bot PAT (personal account) / bot worktree base dir                                                        |
| `BOT_BASE_BRANCH`                                                                                            | Bot fork base branch (default: `master`)                                                                  |
| `BOT_SKIP_TESTS`                                                                                             | Skip the python unittest step in the bot's local CI gate (default: off)                                   |
| `BOT_HTTP_PROXY`                                                                                             | Bot proxy for GitHub API / git push / mermaid download (GitHub unreachable directly)                      |

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

# Moment — short-form micro-posts → docs/moments/YYYY-MM/DD-HHMM.md
uv run poe create-moment "Hello 👋"
uv run poe create-moment "Draft idea" --draft                    # hidden in production builds
uv run poe create-moment "Backfill" --time "9pm"                # backdate (same syntax as create-post)

# Images — --image auto-converts to WebP (PNG/JPG/JPEG; quality from extra.optimize_images)
# and uploads to the bucket (key = extra.bucket.upload.rule); the md link uses a relative
# assets/bucket/ path that the build rewrites to the bucket URL. Repeat for multiple photos.
# Needs a read-write R2 token in .env + rclone; on failure the WebP stays staged locally.
uv run poe create-moment "With image" --image photo.jpg
uv run poe create-moment "Trip photos" --image a.jpg --image b.png
uv run poe create-moment "Staged only" --image photo.jpg --no-upload   # convert + local stage, skip upload

# Tags — comma-separated and/or repeatable; `general` always stays first
uv run poe create-moment "Lunch" --tags food,ramen --tags shanghai

# Geo — place + coordinates (WGS-84 default; --crs gcj02 converts Amap/Baidu coords)
# EXIF GPS embedded in the photo auto-fills --lng/--lat when omitted
uv run poe create-moment "Riverfront" --place "徐汇滨江" --lng 121.47 --lat 31.16 --region shanghai
uv run poe create-moment "Map pin" --image photo.jpg            # lng/lat auto-filled from EXIF (WGS-84)

# Structured metadata — schema driven by extra.moment.meta_fields (e.g. food: name / rating)
uv run poe create-moment "Lunch" --tags food --meta name="Old Shanghai Noodle House" --meta rating=4

# All together
uv run poe create-moment "Trip" --image photo.jpg --tags travel,shanghai \
    --place "徐汇" --lng 121.47 --lat 31.16 --meta name="Museum" --meta rating=5

# English Scraps — jot down English learning scraps
uv run poe enu add "cumbersome"
uv run poe enu add "The implementation is cumbersome to maintain." --date 2026-08-08

# Weight
uv run poe update-weight 82
uv run poe update-weight 81.6 2026-08-05
uv run poe update-weight 82 --date yesterday
uv run poe add-weight-week 2               # pre-add empty weeks

# Bucket upload — dry-run by default; --confirm to actually upload
uv run poe bucket-upload photo.png                      # preview only (safe default)
uv run poe bucket-upload photo.png --confirm            # convert + rename + upload, prints md link
uv run poe bucket-upload "~/Work/tmp/My Photo.png" --confirm   # ~ and spaces are fine
uv run poe bucket-upload a.png b.jpg --quality 80 --confirm    # multiple files, quality override
uv run poe bucket-upload --max-size-mb 20 photo.png --confirm  # raise the size limit (default 10MB)
# needs a read-write R2 token in .env (update R2_* + poe rclone-config-init)

# Bucket sync — pull the bucket mirror down (incremental: checksum+fast-list on; dry-run by default)
uv run poe bucket-sync pull                      # preview what would change (safe default)
uv run poe bucket-sync pull --confirm            # apply — mirror bucket → docs/assets/bucket/ (deletes local extras)
uv run poe bucket-sync pull --no-checksum        # multipart objects? fall back to size+modtime compare

# Bucket check — cross-check bucket assets vs md references (dry-run; exit 1 on issues)
uv run poe bucket-check                          # unreferenced local files (cleanup) + broken md links
uv run poe bucket-check --check-remote            # also verify md links exist in the R2 bucket itself
uv run poe bucket-check --only-missing           # just broken links
uv run poe bucket-check --only-unreferenced      # just cleanup candidates
uv run poe bucket-check --json                   # machine-readable report
uv run poe bucket-check --no-drafts              # ignore draft pages in the reference scan

# Bot auto PR — run in an isolated worktree, publish as a PR
uv run poe bot "weight 81.5" "text-moment 晨跑5km"   # one-step draft PR
uv run poe bot "enu cumbersome"                     # English scrap via bot (one-step draft PR)
uv run poe bot "enu cumbersome --date 2026-08-11"  # with backdate
uv run poe bot "weight 81.5" "enu cumbersome" "health-summary"  # composed daily check-in
uv run poe bot "text-moment 测试内容" --preview  # text-only moment, stop before commit
uv run poe bot "weight 81.5" --auto-merge        # + auto merge when CI green
uv run poe bot "weight 81.5" --handoff        # draft PR then clean local, dev handles PR (default)
uv run poe bot --plan morning 81.5               # local plan file (create .bot/plans/morning.yml first)
uv run poe bot list
uv run poe bot abort bot/weight/20260811-213000
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
