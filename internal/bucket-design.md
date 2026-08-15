# Bucket Assets — Design Document

> External storage for large site files: keep big files (mainly WebP images
> today) on an R2/S3 bucket instead of committing them to git. md files keep
> local relative links (so VSCode preview renders real files), and the build
> rewrites matching prefixes to a configurable bucket `base_url` — switching
> buckets is a config change, md untouched.
>
> Requirements: `internal/local-draft.md`; plan: `internal/plans/bucket-assets.md`.

## Background & Goals

- The site is a static MkDocs build; large images are committed to git and
  bloat the repo (`.git` was 21M).
- New large files go to a bucket (R2 / S3-compatible); **existing files are
  not migrated** for now.
- Uploading/management is done with **PicList** (GUI), **rclone** (CLI) and
  **`poe bucket-upload`** (CLI, converts to WebP + rename + upload);
  `bucket-sync` stays a read-only mirror.
- Core requirement: never hard-code bucket URLs in md; switching buckets /
  domains is a one-line config change.

## Link Scheme (core)

1. **md always uses local relative links** (relative to the referencing page):
   `![img](../../assets/bucket/food-004.webp)`.
1. Local copies stay in `docs/assets/bucket/` (**git-ignored**) so VSCode
   preview renders real files — normal daily authoring.
1. Build-time rewrite: paths matching the `assets/bucket/` prefix →
   `{base_url}/{remaining}`; **files outside the prefix are not rewritten**
   (existing images / internal links are unaffected).
1. Migration = change `base_url` in mkdocs.yml + rebuild; md untouched.

Example:

```
md:        ../../assets/bucket/food-004.webp   (VSCode preview: local file ✓)
built:     http://xxx.r2.dev/web-assets/img/food-004.webp
not touched: ../../moments/2026-08/xxx.webp     (outside assets/bucket/)
```

## Configuration (mkdocs.yml `extra.bucket`)

```yaml
extra:
  bucket:
    enabled: false            # turn on rewriting; env override for testing (below)
    mappings:                 # multiple entries = multiple buckets / directories
      - prefix: assets/bucket/          # local path prefix under docs/ (md link match)
        remote_prefix: web-assets/img   # object prefix inside the bucket (PicList store path)
        base_url: ""                    # public URL prefix; migration changes this only
```

Path layers:

| Layer         | Example                            | Meaning                                   |
| ------------- | ---------------------------------- | ----------------------------------------- |
| local prefix  | `assets/bucket/`                   | md link match; `docs/assets/bucket/`      |
| remote_prefix | `web-assets/img`                   | bucket object prefix (PicList store path) |
| base_url      | `http://xxx.r2.dev/web-assets/img` | public URL prefix                         |

After upload the object key is `web-assets/img/food.webp`; the public URL is
`base_url + food.webp`, matching the build-time rewrite.

## Environment Files (.env)

Developer-local settings are loaded from git-ignored env files at the repo
root (via `shared/env.py`, powered by `python-dotenv`). Template committed as
`.env.example`:

```
cp .env.example .env        # shared defaults
# .env.local overrides (machine/user specific) — optional
```

**Precedence (highest first):**

1. **shell / CI environment variables** — never overridden
1. `.env.local` — machine/user-specific overrides
1. `.env` — shared defaults

Later files win within the `.env` universe; already-exported variables always
win over both files. Loading happens early in every entrypoint that needs it:
build hooks (`plugins/bucket_url.py` at import time) and scripts
(`scripts/bucket_sync.py` at startup).

> Note: mkdocs.yml `!ENV` tags are resolved while the config is parsed —
> before hooks are imported — so `.env` does **not** feed `!ENV` values
> (e.g. `SITE_URL`, `CF_ANALYTICS_TOKEN` keep their mkdocs.yml defaults /
> shell values). `.env` does feed everything read at hook/script runtime:
> `MKDOCS_BUCKET_ENABLED`, `MKDOCS_BUCKET_BASE_URL`, R2 credentials.
>
> **Config layering for buckets**: build settings (prefixes, base_url) live in
> **mkdocs.yml** `extra.bucket` — committed, so CI builds read them. The
> **rclone remote name is local-only** (`BUCKET_SYNC_REMOTE` in `.env`, default
> `r2`) — CI only builds, it never syncs. The R2 API **endpoint** lives only in
> rclone.conf / PicList. `.env` holds secrets (R2 keys) and local overrides.
> The sync script resolves each parameter as **CLI arg > env (`.env`) >
> mkdocs.yml** (remote: CLI > `BUCKET_SYNC_REMOTE` > default `r2`); the
> `BUCKET_SYNC_*` env vars (see `.env.example`) are for local overrides, never CI.

## Implementation

### `shared/bucket.py` (pure logic, unit-tested)

- `is_enabled(bucket_cfg)` — `extra.bucket.enabled`; `MKDOCS_BUCKET_ENABLED`
  env (`true/1/yes`) overrides (same pattern as `MKDOCS_INCLUDE_DRAFTS`).
- `load_mappings(bucket_cfg)` — normalize mappings to `[{prefix, base_url}]`;
  `MKDOCS_BUCKET_BASE_URL` env overrides every `base_url` (testing).
- `rewrite_url(url, mappings)` — relative URLs only (scheme/netloc untouched);
  first matching prefix; `{base_url}/{key}` with query/anchor preserved;
  requires a path boundary before the prefix (no `myassets/bucket/` matches).
- `rewrite_html(html, mappings)` — applies `rewrite_url` to `src`/`href`.
- `local_dir_for_prefix(prefix)` — `assets/bucket/` → `docs/assets/bucket/`.

### `shared/env.py`

- `load_env_files()` — merges `.env` then `.env.local` into `os.environ`
  (see precedence above); missing files ignored.

### `plugins/bucket_url.py` (build hook)

- Imports `shared.env.load_env_files()` at module load (before any env reads).
- `on_page_content`: when `extra.bucket` is enabled, applies `rewrite_html` to
  the page HTML. At this stage MkDocs has already resolved relative links to
  site-root-relative forms (possibly with `../`); substring prefix matching
  covers md-relative, site-root, and absolute forms.
- Disabled or no match → output unchanged; dev server / CI behave exactly as
  before.

### Moment plugin integration (`plugins/mkdocs_moment/plugin.py`)

- `on_config` caches `extra.bucket` (enabled + mappings).
- `on_page_markdown`: applies `bucket_rewrite_html` to the rendered
  `moment.html` (moment bodies never pass through `on_page_content`).
- `_first_image`: relative paths matching a bucket prefix are rewritten to
  absolute URLs (popup_image / OG meta / timeline / map data chain).

### `scripts/bucket_sync.py` (thin rclone wrapper, `poe bucket-sync`)

- Loads `.env` at startup (R2 credentials / test overrides).

- **Read-only by design** (matches the read-only R2 token): only `pull`
  exists — **uploads go through `poe bucket-upload`** (needs a read-write
  token, see below) or PicList.

- `pull` — `rclone sync {remote}:{bucket}/{remote_prefix}/ → docs/assets/bucket/`
  (one-way mirror, **deletes local extras**); **dry-run by default**, requires
  `--confirm` to apply (protects un-uploaded local files).

- **Incremental by default**: `rclone sync` compares size + checksum (S3 ETag
  = MD5 for single-part uploads) and only transfers files that differ — a
  second `pull` with no changes transfers nothing (verified against the real
  bucket: 0 B re-transferred). Two flags make the repeated sync fast:
  `--checksum` (default on; compare ETag instead of modtime, so locally-
  dropped-then-PicList-uploaded files with mismatched mtimes are NOT
  re-downloaded) and `--fast-list` (default on; one recursive listing instead
  of per-directory listings — matters for buckets with many objects).
  `--no-checksum` / `--no-fast-list` opt out (multipart-uploaded objects have
  non-MD5 ETags and would always transfer under `--checksum`).

- **Proxy**: `RCLONE_HTTP_PROXY` in `.env` (rclone's native `--http-proxy` env
  var) is inherited by the rclone subprocess — use it when R2 is only
  reachable through a proxy. Standard `HTTP(S)_PROXY` works too.

- Defaults read from mkdocs.yml `extra.bucket` (first mapping's remote_prefix /
  prefix); the rclone remote name comes from `BUCKET_SYNC_REMOTE` env or the
  hardcoded default `r2` (local-only, not in mkdocs.yml). All overridable via
  `--remote`/`--prefix`/`--remote-prefix`.

- **Subdirectory scope**: `--remote-prefix` selects one subdirectory inside the
  bucket (`rclone sync` targets `{bucket}/{remote_prefix}/` only — files under
  it are synced, every other bucket directory is ignored). Example:

  ```bash
  # sync only bucket1:/abc/123/** into docs/assets/bucket/, ignore the rest
  uv run poe bucket-sync pull --bucket bucket1 --remote-prefix abc/123
  ```

### `scripts/bucket_check.py` (`poe bucket-check`)

Local dev aid that cross-checks bucket assets against markdown references in
both directions (dry-run by design — nothing deleted/written; exit 1 when
issues are found):

- **`[unreferenced]`** — local bucket files no md/html references (cleanup
  candidates; safe to delete once verified they are not pending uploads).
- **`[missing]`** — md/html links whose bucket file is absent locally (broken
  link: the pull hasn't run, the file was never uploaded, or the link is a
  typo).
- **`--check-remote`** — checks against the actual bucket objects via `rclone lsf`:
  `[missing-remote]` = md links whose key is absent from the bucket;
  `[not-uploaded]` = local files absent from the bucket (pending upload —
  `bucket-sync pull --confirm` would delete them). `--remote` / `--bucket` /
  `--remote-prefix` imply `--check-remote` (a bucket-sync-style `--remote r2`
  never silently degrades to a local-only check).

Reference scope: every `*.md` under `docs/` (drafts included by default — a
file referenced only by a draft is still referenced; `--no-drafts` to exclude
them) plus `*.html` under `docs/`/`overrides/`. Links are found by scanning
for tokens containing the bucket prefix (md link targets, frontmatter image
fields, inline HTML attributes) and resolved relative to the referencing file
(site-root `/assets/bucket/…` forms resolve against `docs/`). Tokens that
resolve outside the bucket local dir are ignored. Filters/output:
`--only-unreferenced` / `--only-missing` / `--json`.

```bash
uv run poe bucket-check                 # local mirror check
uv run poe bucket-check --check-remote  # also check against the bucket
uv run poe bucket-check --json          # machine-readable output
```

### `scripts/bucket_upload.py` (`poe bucket-upload`)

The write-side counterpart of `bucket-sync`: converts images to WebP, renames
with a configured rule and uploads to the bucket. **Requires a read-write R2
token** (Admin Read & Write, or Object Read + Object Write + List Bucket) in
`.env` — the pull path only needs read. Update the token and re-run
`poe rclone-config-init`; credentials never leave `.env` / rclone.conf.

**Flow per image**: convert to WebP (quality from
`extra.optimize_images.quality`, default 90) → render the object key → stage
in the temp dir → `rclone copyto` → copy into `docs/assets/bucket/` (VSCode
preview copy, git-ignored) → delete the temp file (kept on failure, path
printed for retry).

**Safety**: the script is **dry-run by default** — nothing is written or
uploaded unless `--confirm` is passed (same guard as `bucket-sync pull`).
Source files larger than `extra.bucket.upload.max_size_mb` (default 10 MB)
fail immediately; override with `--max-size-mb` / `BUCKET_UPLOAD_MAX_SIZE_MB`.

**Key rule** (`extra.bucket.upload.rule`, default
`img/{Y}/{m}/{d}_{h}{i}{s}_{filename}`) — the rendered rule is joined to the
mapping's `remote_prefix`, so with `remote_prefix: data/img` the object key is
`data/img/img/2026/08/16_101112_myphoto.webp` (`img` is an image-category
directory inside the bucket; change the rule to `{Y}/{m}/...` for a flatter
tree). Tokens: `{Y}` year (4), `{m}/{d}/{h}/{i}/{s}` month/day/hour/minute/
second (2), `{filename}` = original stem lowercased and reduced to ASCII
letters+digits, spaces become `_` (Chinese/punctuation removed); an empty
result (pure Chinese, no ASCII alphanumerics) → `fallback_name` (`noname`).
A `.webp`
suffix is appended unless the rule already ends in one. Same-second uploads of
the same filename get a `-2`/`-3`… suffix.

**Temp / staging dir**: `--tmp-dir` > `BUCKET_UPLOAD_TMP_DIR` >
`extra.bucket.upload.tmp_dir` > `.bucket` at the repo root (git-ignored, same
pattern as `.bot-api/`); converted WebP files land there before the upload.

**Parameter resolution** mirrors `bucket-sync`: CLI arg > env (`.env`) >
mkdocs.yml. The rclone remote name is **auto-detected from
`rclone listremotes`** (prefers `r2`, else the single/first configured
remote) — `--remote` / `BUCKET_SYNC_REMOTE` override it, stale values warn
and fall back, and several remotes without an explicit choice warn before
picking the first; CI never uploads. Upload-specific envs:
`BUCKET_UPLOAD_RULE` / `BUCKET_UPLOAD_FALLBACK_NAME` /
`BUCKET_UPLOAD_TMP_DIR` / `BUCKET_UPLOAD_MAX_SIZE_MB` (see `.env.example`).

```bash
# dry-run preview by default (nothing is uploaded)
uv run poe bucket-upload photo.png
# actually upload: converts to WebP, renames, uploads, prints the md link
uv run poe bucket-upload photo.png --confirm
# multiple images / quality / size-limit overrides
uv run poe bucket-upload a.png b.jpg --quality 80 --confirm
uv run poe bucket-upload --max-size-mb 20 photo.png --confirm
```

### poe tasks

- `poe server-bucket` — `mkdocs serve` + `MKDOCS_BUCKET_ENABLED=true`, preview
  the rewrite locally (src already points at the bucket).
- `poe bucket-sync pull [--confirm]` — pull the bucket asset dir down
  (incremental: `--checksum` + `--fast-list` on by default).
- `poe bucket-check [--check-remote]` — cross-check bucket assets vs md references
  (unreferenced local files + missing links; `--check-remote` checks against the
  bucket itself).
- `poe bucket-upload [images]` — convert to WebP, rename with
  `extra.bucket.upload.rule` and upload (needs a read-write R2 token).

## Usage Flow

1. Developer creates the bucket + API token in the R2 console; enable public
   read (or a custom domain). **Create a read-write token** (Object Read +
   Object Write + List Bucket) — `poe bucket-upload` needs write.
1. Configure PicList R2 image host: endpoint / credentials / **store path =
   `remote_prefix`** (e.g. `web-assets/img/`).
1. Drop large files into `docs/assets/bucket/` (git-ignored); reference them
   from md with relative paths — or upload with `poe bucket-upload` (auto
   WebP + rename, prints the md link).
1. Upload via PicList (keys match `remote_prefix`) or `poe bucket-upload`.
1. `poe server-bucket` previews the rewrite; `poe build` builds production.
1. Switching buckets/domains: change `base_url` in mkdocs.yml + rebuild; md
   untouched.

## Testing the sync script

### 1. Automated (no bucket needed)

```bash
uv run poe test                    # tests/test_bucket_sync.py: rclone command construction,
                                   # subdirectory scope, CLI > env > config order, incremental flags
                                   # (--checksum / --fast-list defaults + opt-outs), rclone mocked;
                                   # tests/test_bucket_check.py: unreferenced / missing / --check-remote
```

### 2. Local simulation (no credentials, no network)

Use rclone's `local` backend as a fake bucket — full pull behavior without R2:

```bash
# fake bucket with two dirs; only abc/123/ should ever sync
mkdir -p /tmp/fb-test/bucket/abc/123 /tmp/fb-test/bucket/other/x
printf a > /tmp/fb-test/bucket/abc/123/a.webp
printf c > /tmp/fb-test/bucket/other/x/c.webp
rclone config create fakebucket local --non-interactive   # root stays unset (use absolute remote paths)

# pull (dry-run preview, then apply) — absolute remote path via --bucket
mkdir -p docs/assets/bucket
echo stray > docs/assets/bucket/stray.png                 # should be deleted by pull
uv run python scripts/bucket_sync.py pull --remote fakebucket \
  --bucket /tmp/fb-test/bucket --remote-prefix abc/123            # dry-run
uv run python scripts/bucket_sync.py pull --remote fakebucket \
  --bucket /tmp/fb-test/bucket --remote-prefix abc/123 --confirm  # apply
ls docs/assets/bucket          # a.webp present; stray.png deleted; other/x/ ignored

# cleanup
rm -rf /tmp/fb-test docs/assets/bucket
rclone config delete fakebucket
```

> The `root` key on local remotes is unreliable in some rclone versions —
> pass an absolute path as the `--bucket` value instead.

### 3. Real R2 (developer config)

Follow the steps below once the fake-bucket flow passes.

## Testing the check script

```bash
uv run poe test   # tests/test_bucket_check.py: token extraction / link resolution /
                  # unreferenced + missing classification / --only-* filters / --json /
                  # draft handling / --check-remote rclone lsf (mocked)
```

Real check against the bucket:

```bash
uv run poe bucket-check            # local mirror cross-check (orphans + broken links)
uv run poe bucket-check --check-remote  # + md links vs actual bucket objects (rclone lsf)
```

## Testing the upload script

```bash
uv run poe test   # tests/test_bucket_upload.py: sanitize / rule rendering /
                  # key resolution / temp dir / rclone command construction (mocked)
```

Real upload verification (needs the read-write token):

```bash
uv run poe bucket-upload /path/to/photo.png   # preview key/command (dry-run by default)
uv run poe bucket-upload /path/to/photo.png --confirm      # convert + upload
# then check the printed link renders: poe server-bucket
```

## Developer Verification Steps

These steps need the developer's bucket configuration (credentials never go
into the repo). Once verified, set `extra.bucket.enabled: true`.

1. **Configure the rclone remote** (once, from `.env` — non-interactive):
   ```bash
   # .env: R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY — use the
   # READ-WRITE token if you plan to `poe bucket-upload` (Object Read +
   # Object Write + List Bucket), else read-only is enough for pull
   uv run poe rclone-config-init                # creates/updates the `r2` remote
   uv run poe rclone-config-init --verify-bucket <bucket>  # object-level check
   # (or manual: rclone config create r2 s3 provider=Cloudflare ...)
   ```
1. **Upload a test image** (bucket-upload, PicList or rclone):
   ```bash
   uv run poe bucket-upload /path/to/test.png --confirm  # WebP + rename + upload + local copy
   # or manually:
   mkdir -p docs/assets/bucket
   cp /path/to/test.webp docs/assets/bucket/
   rclone copy docs/assets/bucket/ r2:<bucket>/web-assets/img/ --progress
   ```
1. **Reference it from a scratch md page**, then:
   ```bash
   MKDOCS_BUCKET_ENABLED=true MKDOCS_BUCKET_BASE_URL=http://<your-domain>/web-assets/img \
     uv run mkdocs build
   grep -r 'web-assets/img' site/          # should hit the scratch page
   ```
1. **Verify pull sync** (read-only token):
   ```bash
   uv run poe bucket-sync pull             # dry-run preview (lists files that would be deleted)
   uv run poe bucket-sync pull --confirm   # apply
   ```
1. **Verify upload** (read-write token):
   ```bash
   uv run poe bucket-upload /path/to/photo.png   # preview key + rclone command (dry-run by default)
   uv run poe bucket-upload /path/to/photo.png --confirm      # convert + upload
   ls docs/assets/bucket/                   # local preview copy is present
   ```
1. **Migration drill**: change `base_url`, rebuild, confirm md untouched and
   built links switch.
1. When all pass: `mkdocs.yml` → `bucket.enabled: true`, production enabled.

## Known Limitations & Risks

- **403 CreateBucket on upload**: rclone's S3 backend checks bucket
  existence (HeadBucket) before writing; R2 scoped API tokens return 403 for
  bucket-level ops, which rclone misreads as "bucket missing" and then
  attempts CreateBucket → AccessDenied. `poe bucket-upload` already passes
  `--s3-no-check-bucket` (goes straight to PutObject); for manual rclone
  uploads add the flag too.
- **`poe bucket-upload` needs a read-write R2 token**: the pull path only
  needs read; uploading requires Object Write (Admin Read & Write, or Object
  Read + Object Write + List Bucket). Update `.env` and re-run
  `poe rclone-config-init` when switching between read-only and read-write
  usage.
- **dedupe checks the local copy only**: `bucket-upload` appends
  `-2`/`-3`… when the same key already exists under `docs/assets/bucket/`;
  if that dir was wiped (e.g. `bucket-sync pull` deletes local extras, or
  manual cleanup) a same-second re-upload silently overwrites the remote
  object instead of getting a `-2` suffix.
- **VSCode preview depends on local copies**: `docs/assets/bucket/` is
  git-ignored; other clones of the repo have no local copies → preview breaks
  for them (the author is unaffected).
- **pull delete protection**: `rclone sync` deletes local files not in the
  bucket (including not-yet-uploaded new files); the script defaults to
  dry-run + explicit `--confirm`.
- **key consistency**: relies on the "PicList store path = `remote_prefix`"
  convention; changing image hosts changes keys only for historical direct
  links (md is written with local relative paths).
- **CI**: builds never check remote existence (no network dependency);
  bucket image targets missing locally produce not_found warnings (non-strict,
  does not fail).
- **403 AccessDenied diagnosis**: usually the bucket name — the sync script
  falls back to the remote name when `extra.bucket.mappings[].bucket` is
  unset, and accessing a wrong/nonexistent bucket returns 403. Set the real
  bucket name (mkdocs.yml `bucket:` or `BUCKET_SYNC_BUCKET` in .env). A
  proxy problem (unreachable R2) looks like timeouts, not 403.
- **endpoint lives only in rclone.conf / PicList**: the R2 API endpoint is not
  in mkdocs.yml (nothing reads it there); keep rclone.conf and PicList in
  sync when the account changes.
- **r2.dev domain instability**: for production public access, bind a custom
  domain to R2 (covered by the configurable `base_url`).
