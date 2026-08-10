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
- Uploading/management is done with **PicList** (GUI) and **rclone** (CLI);
  no custom upload logic.
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

- **Read-only by design** (matches the read-only R2 token; uploads happen in
  PicList): only `pull` exists.

- `pull` — `rclone sync {remote}:{bucket}/{remote_prefix}/ → docs/assets/bucket/`
  (one-way mirror, **deletes local extras**); **dry-run by default**, requires
  `--confirm` to apply (protects un-uploaded local files).

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

### poe tasks

- `poe server-bucket` — `mkdocs serve` + `MKDOCS_BUCKET_ENABLED=true`, preview
  the rewrite locally (src already points at the bucket).
- `poe bucket-sync pull [--confirm]` — pull the bucket asset dir down.

## Usage Flow

1. Developer creates the bucket + API token in the R2 console; enable public
   read (or a custom domain).
1. Configure PicList R2 image host: endpoint / credentials / **store path =
   `remote_prefix`** (e.g. `web-assets/img/`).
1. Drop large files into `docs/assets/bucket/` (git-ignored); reference them
   from md with relative paths.
1. Upload via PicList (keys match `remote_prefix`).
1. `poe server-bucket` previews the rewrite; `poe build` builds production.
1. Switching buckets/domains: change `base_url` in mkdocs.yml + rebuild; md
   untouched.

## Testing the sync script

### 1. Automated (no bucket needed)

```bash
uv run poe test                    # tests/test_bucket_sync.py: rclone command construction,
                                   # subdirectory scope, CLI > env > config order (rclone mocked)
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

## Developer Verification Steps

These steps need the developer's bucket configuration (credentials never go
into the repo). Once verified, set `extra.bucket.enabled: true`.

1. **Configure the rclone remote** (once, from `.env` — non-interactive):
   ```bash
   # .env: R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY (read-only token)
   uv run poe rclone-config-init                # creates/updates the `r2` remote
   uv run poe rclone-config-init --verify-bucket <bucket>  # object-level check
   # (or manual: rclone config create r2 s3 provider=Cloudflare ...)
   ```
1. **Upload a test image** (PicList or rclone):
   ```bash
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
1. **Migration drill**: change `base_url`, rebuild, confirm md untouched and
   built links switch.
1. When all pass: `mkdocs.yml` → `bucket.enabled: true`, production enabled.

## Known Limitations & Risks

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
