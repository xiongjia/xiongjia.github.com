---
title: Bucket Assets — external storage for large site files (R2/S3)
created: 2026-08-09
archived: 2026-08-10
status: completed
tags: [bucket, r2, s3, piclist, images, mkdocs, plugin]
---

# Bucket Assets — external storage for large site files (R2/S3)

> Source requirements: `internal/local-draft.md`. Design doc: `internal/bucket-design.md`.

## Goal

Host large site files (mainly WebP images today) on an R2/S3 bucket instead of
committing them to git. md keeps local relative links (VSCode preview works),
and the build rewrites matching prefixes to a configurable bucket `base_url` —
switching buckets is a config change, md untouched. Uploading/management uses
PicList + rclone (no custom upload logic); existing files are not migrated.

## Status

Core implementation + docs done; **developer verification passed** (rclone
remote `web-assets-readonly` configured, bucket `web-assets` synced, test md
build rewrite + remote 200 verified, `base_url` fixed, `enabled: true`).
Migration drill **cancelled** (user: defer migration for now) — remaining:
plan archiving.

## Tasks

### Phase 1 — Config & link rewrite ✅

- [x] `shared/bucket.py`: `rewrite_url` / `rewrite_html` / `is_enabled` /
  `load_mappings` (enabled, mappings: prefix + base_url; env overrides)
- [x] mkdocs.yml `extra.bucket` config section (enabled / mappings)
- [x] New `plugins/bucket_url.py`: `on_page_content` rewrites paths matching a
  prefix; unmatched / disabled output unchanged
- [x] Moment plugin integration: `moment.html` rewrite + `_first_image`
  relative bucket path → popup_image / OG / timeline chain
- [x] Unit tests (24 in `tests/test_bucket_url.py`): prefix rewrite, remaining
  path join, multiple mappings, no-match unchanged, disabled fallback,
  env overrides
- [x] Minimal experiment: MkDocs `_RelativePathTreeprocessor` link shape
  (site-root relative, possibly with `../`) → substring prefix matching
  covers md-relative / site-root / absolute forms
- [x] dev server check: default build (disabled) unchanged; env-enabled build
  rewrites

### Phase 2 — Sync script & conventions

- [x] `scripts/bucket_sync.py`: thin rclone wrapper, **read-only (pull)** —
  `rclone sync` deletes local extras, dry-run by default + `--confirm`;
  uploads stay in PicList (read-only R2 token); defaults read from
  mkdocs.yml (remote name from `BUCKET_SYNC_REMOTE` in .env)
- [x] pyproject.toml registers `poe bucket-sync`, `poe server-bucket`,
  `poe rclone-config-init`
- [x] rclone / PicList conventions written into `internal/bucket-design.md`
  (endpoint, credentials local-only, read-only token for pull, store path
  = remote_prefix); `RCLONE_HTTP_PROXY` proxy support
- [x] **Developer verification** (2026-08-10, done by user): rclone remote
  configured → bucket-sync pull succeeded → test md build rewrite + remote
  200 → `base_url` fixed (`data/image`→`data/img`, md untouched) →
  `enabled: true`
- [x] ~~Migration drill (change `base_url`, rebuild, confirm md untouched)~~
  — **cancelled** (user: defer migration for now)

### Phase 3 — Design & docs delivery ✅

- [x] Design doc `internal/bucket-design.md` (scheme / config / rewrite rules /
  usage flow / developer verification steps / known limitations)
- [x] `README.md`: Commands add `server-bucket`, `bucket-sync`,
  `rclone-config-init`; Design Documents list
- [x] `AGENTS.md`: DEV commands + Bucket-hosted assets conventions (relative
  paths / gitignore / credentials not committed)
- [x] `internal/architecture.md`: Custom Hooks add `bucket_url`;
  Environment Variables add `MKDOCS_BUCKET_ENABLED` /
  `MKDOCS_BUCKET_BASE_URL`; Design Documents list
- [x] `.env.example`: R2 credentials, `MKDOCS_BUCKET_*`, `BUCKET_SYNC_*`,
  `RCLONE_HTTP_PROXY` with load-order note
- [x] This plan finalized + plan-index updated

### Phase 4 — Future extensions (recorded, not implemented)

- [ ] Migrate existing `docs/moments/*.webp` assets
- [ ] Private bucket + signed URL rendering
- [ ] CDN / custom domain / immutable key cache policy
- [ ] ~~`create-post` / `create-moment` auto-upload hook~~ — **moved to long-term
  backlog, not doing** (user: keep uploads manual via PicList)

## Notes

- Link scheme: `assets/bucket/food.webp` → `{base_url}/food.webp`; files
  outside the prefix are never rewritten.
- Migration = change `extra.bucket.mappings[].base_url` + rebuild; md untouched.
- Credentials (R2 access keys) live only in local rclone.conf / PicList —
  never committed; `RCLONE_HTTP_PROXY` for proxied access.
- References: `internal/bucket-design.md`, `internal/local-draft.md`
