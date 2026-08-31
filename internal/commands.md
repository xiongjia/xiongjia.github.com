# Commands — Command Reference

> All commands run via `uv run poe` from the repo root.
> Environment & architecture details: [architecture.md](./architecture.md).

## Outline

- **Dev & Build** — `server` / `server-prod` / `server-bucket` / `build` / `build-drafts` / `build-selfhost`
- **Quality** — `fmt` / `lint-py` / `test`
- **Content** — `create-post` / `create-moment` / `enu add` / `enu export`
- **Health** — `update-weight` / `add-weight-week` / `update-health-summary` / `sync-running` / `sync-running-splits`
- **Reading** — `reading-assist list` / `reading-assist run [slug]` / `--dry-run`
- **Bot** — `bot "<task>"...` / `bot --plan` / `bot list` / `bot submit` / `bot abort` / `bot cleanup`
- **Assets & Conversion** — `optimize-images` / `md2wechat` / `bucket-sync pull` / `bucket-upload` / `rclone-config-init`
- **English Scraps flow** — collect → batch-organize → review → Anki export

## Dev & Build

| Command              | Summary                                                       |
| -------------------- | ------------------------------------------------------------- |
| `poe server`         | Dev server WITH drafts (hot reload) → `http://localhost:8000` |
| `poe server-prod`    | Dev server WITHOUT drafts (mirrors production)                |
| `poe server-bucket`  | Dev server + bucket prefix rewrite (test bucket links)        |
| `poe build`          | Production build (excludes drafts)                            |
| `poe build-drafts`   | Build including drafts (`MKDOCS_INCLUDE_DRAFTS=true`)         |
| `poe build-selfhost` | Self-hosted build (separate `site-selfhost/` dir)             |

Details:

- **Debug**: `GIT_HASH=$(git rev-parse --short HEAD) uv run poe server` embeds the
  current commit hash into the page HTML meta — only needed when debugging the
  hash display; plain `uv run poe server` is fine for daily work.

## Quality

| Command       | Summary                                                         |
| ------------- | --------------------------------------------------------------- |
| `poe fmt`     | Format Python (ruff) + Markdown (mdformat, incl. `.pi/skills/`) |
| `poe lint-py` | Python lint check (ruff)                                        |
| `poe test`    | Run unit tests (pytest, `tests/`)                               |

## Content

| Command                    | Summary                                     |
| -------------------------- | ------------------------------------------- |
| `poe create-post "Title"`  | New blog post (draft by default)            |
| `poe create-moment "Text"` | New Moment micro-post                       |
| `poe enu add "scrap"`      | English Scraps: append a scrap to the inbox |
| `poe enu export`           | English Scraps: export new cards → `.apkg`  |

Details:

- `create-post`: `--no-draft` publish; `--time` backdate (`9am` / `9pm` / `21:30` /
  `yesterday` / day+time / full date); `--category` / `--tags`.
- `create-moment`: `--image` auto-WebP + bucket upload (key from
  `extra.bucket.upload.rule`; EXIF orientation baked into the pixels; EXIF GPS
  auto-fills `--lng`/`--lat`); `--tags`; geo `--place` / `--lng` / `--lat`
  (WGS-84; `--crs gcj02` converts Amap/Baidu coords); `--draft` hidden in prod;
  `--time` backdate; `--time-from-exif` = photo EXIF capture time as the moment
  date (requires `--image`, exclusive with `--time`); `--no-upload` converts +
  local stage only; `--meta name=.. rating=..` structured metadata (schema from
  `extra.moment.meta_fields`).
- `enu add`: auto date; `--date` backdate.
- `enu export`: `--format csv` fallback (UTF-8 BOM, one file per type);
  `--type` / `--tag` filter; `--all`; `--dry-run`; rewrites `new → learning` on
  success; import is manual (Anki / AnkiDroid, sync via AnkiWeb).

## Health

| Command                       | Summary                                                |
| ----------------------------- | ------------------------------------------------------ |
| `poe update-weight 82 [date]` | Record a daily weight (default: today)                 |
| `poe add-weight-week [n]`     | Pre-add empty week(s) to weight data                   |
| `poe update-health-summary`   | Regenerate the health index summary (local pi AI)      |
| `poe sync-running`            | Sync running data from the Garmin CN API (incremental) |
| `poe sync-running-splits`     | Upload running splits/polyline to R2                   |

Details:

- `update-weight`: date accepts `yesterday` / full dates.
- `update-health-summary`: calls the local pi CLI; the previous summary stays
  untouched if the call fails.
- `sync-running`: incremental; writes `running.yml` + `.running/splits.json`
  cache; seeds the cache from R2 on cold start.
- `sync-running-splits`: dry-run by default; `--confirm` or
  `SYNC_RUNNING_CONFIRM=true` to upload.

## Reading

| Command                                        | Summary                                                             |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| `poe reading-assist list`                      | List Reading Items entries (slug / type / state / source)           |
| `poe reading-assist cache [slug]`              | Step 1: fetch/extract the raw material into the local cache (no AI) |
| `poe reading-assist read [slug]`               | Step 2: run the AI analysis on cached sources → `reading/<slug>/`   |
| `poe reading-assist run [slug]`                | cache + read in one go (backwards compatible)                       |
| `poe reading-assist read/run [slug] --dry-run` | Preview the selected entry + prompt, no AI call                     |
| `poe reading-assist read/run [slug] --model …` | Pin the pi model (default: local config)                            |

Details:

- **Item selection**: default = first `not-started` / `reading` item; `[slug]`
  picks by slug. `## Reading Items` lives in
  `internal/plans/reading-items.md` (queue file, separate from the dev plan).
- **Validation (abort → silent, exit 0, zero output; no bot diff → no PR)**:
  no items; local file missing; pdf/epub unparseable (pymupdf/pypdf unavailable
  or corrupt); URL unreachable.
- **Pipeline**: validate source → local pi runs
  `.pi/skills/reading-assist/SKILL.md` (extract / split into chapters → write
  `reading/<slug>/` index + ch + notes, + characters/storyline for novels →
  self-review ≤ 10 rounds) → plan item → `organized` → mdformat.
- **Status semantics**: `not-started → reading → organized` = *organization*
  progress (AI produced the notes), not "user finished reading".
- **Proxy**: URL fetch uses `READING_PROXY` in `.env` (per machine, loaded via
  `shared/env.py`), falls back to `$https_proxy` → default local proxy
  `http://127.0.0.1:1095`.
- **Extraction tools**: uv-managed — `uv run --with pymupdf --with pypdf …`
  (no system packages on Linux/macOS); first run fetches + caches, later runs
  are offline.
- **Local cache**: `READING_CACHE_DIR` → `$READING_CACHE_DIR/<slug>/` (default:
  system temp `/reading-assist`, never in-repo). Sources are **kept** after the
  run so you can re-read / re-extract a pdf/epub while adjusting the notes
  (delete the dir manually when done).
- **Manual only, no scheduling**: there is no cron / bot auto-run — analysis
  quality needs the user to review and adjust the produced notes by hand, so
  run `poe reading-assist run` on demand, edit `docs/notes/reading/<slug>/`
  yourself, and commit when satisfied.

### Adding an item (How to add a Reading Item)

Opening a new book/article → add an entry to `## Reading Items` in
`internal/plans/reading-items.md` (the queue file: template comment + entries +
`## 记录（Log）` 完成/失败 sections — entry format and status semantics are
documented there in Chinese; the dev plan `internal/plans/arch/reading-assist.md`
keeps design/tasks only, so run history never mixes into it):

1. Duplicate the「模板」comment block, uncomment the copy and fill it in
   (**keep the template block itself commented** — the parser skips it).
   Entry keys are the Chinese display names (`slug` / `类型` / `出处` /
   `状态` / `原材料` / `输出`):
   - **slug**: kebab-case, only `[a-z0-9-]` (e.g. `ddia`; a Chinese book
     title goes in the page `title`, never in filenames)
   - **类型**: `book` | `novel` | `article` | `paper`
   - **出处**: Douban entry / URL / DOI (books: bibliography info only)
   - **状态**: `not-started`
   - **原材料**: book/novel = a local pdf/epub under the git-ignored `external/`
     (e.g. `{projectRoot}/external/book/ddia.epub` — never committed);
     article/paper = URL. **Multiple sources are space-separated in one field**
     — a series of articles = several URLs (each URL becomes one `part-000N`
     page), a book split into volumes = several local files (each file = one
     volume `part` page)
   - **输出**: `docs/notes/reading/<slug>/`
1. `poe reading-assist list` — confirm the entry is visible (validated)
1. Start organizing in two steps (or `run <slug>` for both at once):
   - `poe reading-assist cache <slug>` — step 1: fetch/extract sources into
     the local cache (no AI); sources are kept for re-reading / re-extracting
   - `poe reading-assist read <slug>` — step 2: AI analysis → `reading/<slug>/`
     (`run` alone picks the first `not-started` entry; `--dry-run` prints the
     selected entry + prompt without calling the AI)
1. After a successful read the entry state auto-set → `organized` (整理完成 —
   **not** "you finished reading"); you then adjust the notes by hand and
   commit on your own schedule (no auto PR)
1. In-reading interactions (Q&A / summary edits / marking read) go through the
   skill trigger words `ask <slug> …` / `done <slug>` (see
   `.pi/skills/reading-assist/SKILL.md`)

**Local file placement & resolution**: put pdfs/epubs anywhere under the
git-ignored `external/` (conventionally `external/book/`; never committed).
`原材料` accepts three forms: an explicit `{projectRoot}/…` path (e.g.
`{projectRoot}/external/book/1.pdf` — `{projectRoot}` is replaced with the
repo root, so it works from any checkout), a relative path (tried in order:
repo root, `external/<path>`, `external/book/<path>`), or an absolute path
(passed through).

Abort branch (silent exit, zero output — no pages): no entry (also no log
record) / local file missing / pdf·epub unparseable / URL unreachable / page
with no readable text (JS-rendered) or too large (provide a local pdf). **Outcome records**: every completed / failed / aborted run
writes one line per (slug, result) in the `## 记录（Log）` section of
`internal/plans/reading-items.md` (done → 完成; pi error / no index / mdformat
failure → 失败; unusable source → 放弃) — re-running the same slug **refreshes**
the line instead of appending, so the log never grows with repeated runs.

Full spec: `internal/plans/arch/reading-assist.md`; queue: `internal/plans/reading-items.md`;
system design: `internal/reading-assist-design.md`.

## Bot (auto PR)

Local bot: runs task scripts in an isolated `git worktree` and publishes the
result as a PR (format → local CI checks → commit → push → draft PR → optional
auto-merge). Design: [bot-auto-pr-design.md](./bot-auto-pr-design.md).

Tasks are registered in `mkdocs.yml` → `extra.bot.tasks` (template tasks:
`args` / `cmd` / `commit` / `body` format strings); builtins like `weight` /
`enu` / `reading-assist` live in `scripts/git_bot.py` and can be overridden by
name.

| Command                        | Summary                                      |
| ------------------------------ | -------------------------------------------- |
| \`poe bot "<task>"... \[--now  | --preview\]\`                                |
| `poe bot --plan <name> [args]` | Run a local plan file                        |
| `poe bot list`                 | List bot instances                           |
| `poe bot submit <name>`        | Submit a previewed instance (commit+push+PR) |
| `poe bot abort <name>`         | Discard an unfinished instance               |
| `poe bot cleanup [<name>]`     | Clean merged instances                       |

Details:

- One-step by default (`--now`); `--preview` stops before commit; `--handoff`
  leaves a draft PR and cleans up locally (dev handles the PR — default);
  `--auto-merge` squash-merges when CI is green.
- Builtin tasks: `weight 82` / `health-summary` / `sync-running` /
  `reading-assist` / `enu <text>`; `enu` free text is auto-joined
  (`--date` / `--dir` stay options).
- Plan files: `.bot/plans/<name>.yml` (git-ignored, created by you — format in
  the design doc); positional args / `--var key=value`.
- Needs `BOT_GH_TOKEN` (fine-grained PAT) in `.env` — see the design doc's
  Credential Strategy for the one-time token setup.

## Bot Remote API (web console · Telegram · cron)

Thin FastAPI shell over `poe bot` (single process, no auth — bind
`BOT_API_HOST=127.0.0.1` on untrusted networks). Design:
[bot-api-design.md](./bot-api-design.md). Serves a dark web console at `/`
(run tasks, watch SSE output, history, cron panel), a Telegram bot
(allowlisted users), and scheduled jobs.

| Command / URL                              | Summary                                                                          |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| `poe api-server` / `api-server-prod`       | Start the API (default 0.0.0.0:8100; `BOT_API_HOST`/`BOT_API_PORT` override)     |
| `GET /api/cron`                            | Cron jobs (schedule / spec / `next_run_at` / `last_run` / runtime disable state) |
| `POST /api/cron/{name}/run`                | Manual run-now — fires the job's spec through the handoff flow                   |
| `POST /api/cron/{name}/disable` / `enable` | Toggle a cron job at runtime (persisted in `.bot-api/cron-state.json`)           |

Details:

- Cron jobs are configured in `mkdocs.yml` → `extra.bot.cron` (5-field cron
  string in the server-local timezone; text DOW names like `SAT` — APScheduler
  maps numeric DOW 0=Monday…6=Sunday, unlike standard cron). Each job fires a
  raw `poe bot run` spec (multi-task with `+`) → handoff draft PR.
  `BOT_API_CRON_ENABLED=false` disables scheduling. See
  [archived plan](./plans/arch/bot-cronjob.md).

## Assets & Conversion

| Command                             | Summary                                                         |
| ----------------------------------- | --------------------------------------------------------------- |
| `poe optimize-images <path>`        | PNG/JPG/JPEG → WebP                                             |
| `poe md2wechat [path]`              | Convert blog post to WeChat HTML                                |
| `poe bucket-sync pull [--confirm]`  | Pull `docs/assets/bucket/` from R2/S3 via rclone (incremental)  |
| `poe bucket-check [--check-remote]` | Cross-check bucket assets vs md references                      |
| `poe bucket-upload <images>`        | Convert to WebP, rename + upload to R2                          |
| `poe rclone-config-init`            | Configure rclone R2 remote from `.env` (local credentials only) |

`poe bucket-upload` details:

- **Safety**: **dry-run by default** — nothing is written/uploaded without
  `--confirm`. Source files larger than `extra.bucket.upload.max_size_mb`
  (default 10 MB) fail immediately (`--max-size-mb` /
  `BUCKET_UPLOAD_MAX_SIZE_MB` override).
- **Flow**: convert to WebP (`--quality 1-100`, default from
  `extra.optimize_images.quality`) → render the key → stage in the temp dir →
  `rclone copyto` → save a local copy under `docs/assets/bucket/` → print the
  md link.
- **Key rule** (`extra.bucket.upload.rule`, default
  `img/{Y}/{m}/{d}_{h}{i}{s}_{filename}`): `img` = image category dir in the
  bucket; `{Y}` year(4), `{m}`/`{d}`/`{h}`/`{i}`/`{s}` month/day/hour/min/sec
  (2); `{filename}` = original stem, lowercased, ASCII letters+digits only,
  spaces → `_`, pure-Chinese → `fallback_name` (`noname`); `.webp` appended
  automatically. Key = `remote_prefix` + rendered rule, e.g.
  `data/img/img/2026/08/16_101112_myphoto.webp`.
- **Options**: `--confirm` / `--rule` / `--fallback-name` / `--max-size-mb` /
  `--tmp-dir` (staging dir, default `.bucket/` at repo root, git-ignored) /
  `--remote` (auto-detected from `rclone listremotes` when omitted) / `--bucket`
  / `--prefix` / `--remote-prefix` (priority: CLI arg > env > mkdocs.yml).
- **Permission**: needs a **read-write** R2 token (Object Read + Object Write +
  List Bucket) in `.env` — `bucket-sync pull` only needs read. Update `R2_*` and
  re-run `poe rclone-config-init`.

`poe bucket-sync` details:

- **Incremental by default**: `rclone sync` compares size + checksum (S3 ETag =
  MD5 for single-part uploads) and transfers only what changed — a second `pull`
  with no changes transfers nothing. `--checksum` (default on) skips modtime;
  `--fast-list` (default on) collapses recursive listing into one API call.
  `--no-checksum` / `--no-fast-list` fall back to legacy size+modtime /
  per-directory listings (multipart-uploaded objects have non-MD5 ETags and
  always transfer under `--checksum`).

Examples:

```bash
uv run poe bucket-sync pull                       # dry-run preview (safe default)
uv run poe bucket-sync pull --confirm             # apply: mirror bucket → docs/assets/bucket/ (deletes local extras)
uv run poe bucket-sync pull --remote b2 --prefix assets/bucket   # other remote / local prefix
uv run poe bucket-sync pull --no-checksum         # multipart-uploaded objects? fall back to size+modtime
```

`poe bucket-check` details:

- **Dry-run by design** — nothing deleted/written; exit 1 when issues found.
- **`[unreferenced]`** — local bucket files no md/html references (cleanup
  candidates; drafts count as references by default, `--no-drafts` to exclude).
- **`[missing]`** — md/html bucket links whose local file is absent (broken
  link / never uploaded / typo). Links found by scanning every `*.md` under
  `docs/` + `*.html` under `docs/`/`overrides/` for `assets/bucket/` tokens,
  resolved relative to the referencing file.
- **`--check-remote`** — checks md links against actual bucket objects
  (`rclone lsf`): `[missing-remote]` = links absent from the bucket;
  `[not-uploaded]` = local files absent from the bucket (pending upload).
  `--remote`/`--bucket`/`--remote-prefix` imply `--check-remote`.
- **Filters / output**: `--only-unreferenced` / `--only-missing` / `--json`
  (machine-readable).

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

| Variable                                                                                                     | Purpose                                                                                  |
| ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`                                                | R2 API credentials for `poe rclone-config-init` (token scope: see `bucket-upload` notes) |
| `BUCKET_SYNC_REMOTE` / `BUCKET_SYNC_BUCKET` / `BUCKET_SYNC_PREFIX` / `BUCKET_SYNC_REMOTE_PREFIX`             | rclone / bucket-sync overrides (priority: CLI arg > env > mkdocs.yml)                    |
| `BUCKET_UPLOAD_RULE` / `BUCKET_UPLOAD_FALLBACK_NAME` / `BUCKET_UPLOAD_TMP_DIR` / `BUCKET_UPLOAD_MAX_SIZE_MB` | `bucket-upload` rename rule / fallback name / staging dir / size limit overrides         |
| `RCLONE_HTTP_PROXY`                                                                                          | rclone proxy (e.g. `http://127.0.0.1:1095`)                                              |
| `MKDOCS_BUCKET_ENABLED` / `MKDOCS_BUCKET_BASE_URL`                                                           | Force bucket prefix rewrite / override `base_url` for testing                            |
| `SITE_NAME` / `SITE_URL` / `GIT_HASH`                                                                        | Site title / canonical URL / commit hash overrides                                       |
| `CF_ANALYTICS_TOKEN` / `MERMAID_CDN_URL`                                                                     | Analytics beacon token (empty disables) / mermaid JS CDN fallback                        |
| `BOT_GH_TOKEN` / `BOT_WORKTREE_DIR`                                                                          | Bot PAT / bot worktree base dir                                                          |
| `BOT_BASE_BRANCH`                                                                                            | Bot fork base branch (default: `master`)                                                 |
| `BOT_SKIP_TESTS`                                                                                             | Skip the python unit-test step in the bot's local CI gate                                |
| `BOT_HTTP_PROXY`                                                                                             | Bot proxy for GitHub API / git push / mermaid download                                   |
| `READING_PROXY`                                                                                              | Reading-assist URL fetch proxy (per machine)                                             |
| `READING_CACHE_DIR`                                                                                          | Reading-assist extraction/pre-fetch local cache (default: system temp)                   |

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
uv run poe create-moment "Photo date" --image photo.jpg --time-from-exif
#   ^ date: = the photo's EXIF DateTimeOriginal (first photo with one wins);
#     mutually exclusive with --time; needs --image; falls back to now if none

# Images — --image auto-converts to WebP (PNG/JPG/JPEG; quality from extra.optimize_images)
# and uploads to the bucket (key = extra.bucket.upload.rule); the md link uses a relative
# assets/bucket/ path that the build rewrites to the bucket URL. Repeat for multiple photos.
# Needs a read-write R2 token in .env + rclone; on failure the WebP stays staged locally.
# EXIF Orientation is baked into the WebP pixels (sideways photos stay upright in any
# viewer); EXIF GPS auto-fills --lng/--lat. Moment images target the GENERIC bucket
# mapping (assets/bucket/ -> data/img), never the specific running/ mapping.
uv run poe create-moment "With image" --image photo.jpg
uv run poe create-moment "Trip photos" --image a.jpg --image b.png
uv run poe create-moment "Staged only" --image photo.jpg --no-upload   # convert + local stage, skip upload

# Tags — comma-separated and/or repeatable; `general` always stays first
uv run poe create-moment "Lunch" --tags food,ramen --tags shanghai

# Geo — place + coordinates (WGS-84 default; --crs gcj02 converts Amap/Baidu coords)
# EXIF GPS embedded in the photo auto-fills --lng/--lat when omitted
uv run poe create-moment "Riverfront" --place "Shanghai West Bund" --lng 121.47 --lat 31.16 --region shanghai
uv run poe create-moment "Map pin" --image photo.jpg            # lng/lat auto-filled from EXIF (WGS-84)

# Structured metadata — schema driven by extra.moment.meta_fields (e.g. food: name / rating)
uv run poe create-moment "Lunch" --tags food --meta name="Old Shanghai Noodle House" --meta rating=4

# All together
uv run poe create-moment "Trip" --image photo.jpg --tags travel,shanghai \
    --place "West Bund" --lng 121.47 --lat 31.16 --meta name="Museum" --meta rating=5

# English Scraps — jot down English learning scraps
uv run poe enu add "cumbersome"
uv run poe enu add "The implementation is cumbersome to maintain." --date 2026-08-08
uv run poe enu export                      # all status:new cards → .anki/english-scraps-<date>.apkg
uv run poe enu export --format csv         # CSV fallback (UTF-8 BOM, one file per type)
uv run poe enu export --type word --tag technical   # filter: word cards with tag technical
uv run poe enu export --all --dry-run      # all statuses; generate without rewriting status
# export rewrites status: new → learning on success (not with --dry-run); import is manual (Anki / AnkiDroid, sync via AnkiWeb)

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

# Reading — the next Reading Items entry → chapter notes (see the Reading section)
uv run poe reading-assist list
uv run poe reading-assist run                      # next not-started / reading item
uv run poe reading-assist run my-slug              # specific item
uv run poe reading-assist run my-slug --dry-run    # preview only

# Bot auto PR — run in an isolated worktree, publish as a PR
uv run poe bot "weight 81.5" "text-moment Morning run 5km"   # one-step draft PR
uv run poe bot "enu cumbersome"                     # English scrap via bot (one-step draft PR)
uv run poe bot "enu cumbersome --date 2026-08-11"  # with backdate
uv run poe bot "weight 81.5" "enu cumbersome" "health-summary"  # composed daily check-in
uv run poe bot "text-moment Test content" --preview  # text-only moment, stop before commit
uv run poe bot "weight 81.5" --auto-merge        # + auto merge when CI green
uv run poe bot "weight 81.5" --handoff        # draft PR then clean, dev handles PR (default)
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
1. **Review**: `/skill:enu-organize quiz [range]` / `/skill:enu-organize review <tag>`
1. **Export (optional)**: `poe enu export` — all `status: new` cards →
   `.anki/english-scraps-<date>.apkg` (CSV fallback with `--format csv`;
   `--type`/`--tag` filter; `--all` for all statuses; `--dry-run` preview); on
   success rewrites `new → learning` in the week files; import is manual
   (Anki / AnkiDroid + AnkiWeb sync), no AnkiConnect

Full workflow & fields: `docs/notes/research/topics/english/scraps/index.md`;
skill workflow doc: `.pi/skills/enu-organize/SKILL.md`.
