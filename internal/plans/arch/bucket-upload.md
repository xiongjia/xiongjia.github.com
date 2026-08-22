---
title: Bucket Image Upload
created: 2026-08-15
archived: 2026-08-22
status: completed
tags: [bucket, r2, upload, images]
---

# Bucket Image Upload

## Goal

Add an image upload path to the bucket (R2/S3) toolchain, complementing the
existing read-only `poe bucket-sync pull`. A new `poe bucket-upload` script:

1. Takes local images (PNG/JPG/JPEG).
1. Converts them to WebP with the existing `optimize_images` conversion logic
   (quality from `extra.optimize_images.quality`, default 90).
1. Renames them with a configurable rule from mkdocs.yml (default
   `img/{Y}/{m}/{d}_{h}{i}{s}_{filename}`) and uploads to the bucket.
1. Saves a local copy under `docs/assets/bucket/` (git-ignored, VSCode
   preview works) and prints the md link.

Requires the developer to provision a **read-write** R2 API token
(Admin Read & Write, or Object Read + Object Write + List Bucket) in `.env` —
the current token is read-only (docs update only; the developer changes the
token, we never touch secrets).

## Design Decisions

- **Upload mechanism**: rclone `copyto` (same remote as `bucket-sync` /
  `rclone-config-init`, `RCLONE_HTTP_PROXY` inherited). No new dependencies,
  no boto3. **Dry-run by default** — preview mode skips the upload entirely;
  `--confirm` performs it (no rclone `--dry-run` flag involved).
- **Temp / staging dir**: converted WebP lands in a configurable temp dir
  before upload — CLI `--tmp-dir` > env `BUCKET_UPLOAD_TMP_DIR` > mkdocs.yml
  `extra.bucket.upload.tmp_dir` > default **`.bucket`** at repo root
  (git-ignored, same pattern as `.bot-api/`). After a successful upload the
  temp file is copied into `docs/assets/bucket/<key>` (VSCode preview copy,
  git-ignored) and the temp file is deleted; on failure the temp file is kept
  and its path printed so the upload can be retried.
- **Rule is relative to `remote_prefix`**: rendered key = `{remote_prefix}/`
  - rendered rule. With current config (`remote_prefix: data/img`) and the
    default rule, the object key is
    `data/img/img/2026/08/16_101112_myphoto.webp` (the literal `img/` in the
    rule is a category directory inside the bucket, kept as-is; change the rule
    to `{Y}/{m}/...` if the nested `img/` is unwanted — one-line config change).
- **Filename sanitization**: original stem → lowercase, keep ASCII
  letters+digits, spaces become `_`, everything else (Chinese, punctuation)
  removed. Empty result (pure Chinese / no ASCII alphanumerics) → fallback
  name `noname` (`extra.bucket.upload.fallback_name`).
- **Reuse**: `optimize_images.convert_to_webp` gains an optional `dst`
  parameter (backward compatible) so upload can convert straight to the final
  keyed path without intermediate files.
- **Collision**: rendered key already exists locally → numeric suffix
  (`-2`, `-3`…) before the upload (same-second uploads).

## Tasks

- [x] `scripts/bucket_upload.py` — CLI + importable functions
  - `sanitize_filename(stem, fallback)` — lowercase/ASCII-only, spaces → `_`
  - `render_rule(rule, now, filename)` — `{Y}/{m}/{d}/{h}/{i}/{s}` tokens
  - temp dir: CLI `--tmp-dir` > env `BUCKET_UPLOAD_TMP_DIR` > mkdocs.yml
    `extra.bucket.upload.tmp_dir` > `.bucket` (git-ignored)
  - main: convert → temp → `rclone copyto` → copy to `docs/assets/bucket/` →
    delete temp → print key / local path / md link
  - args: paths, `--quality`, `--confirm`, `--max-size-mb`, `--tmp-dir`,
    `--rule`, `--fallback-name`, `--remote` / `--bucket` / `--prefix` /
    `--remote-prefix` (CLI > env > mkdocs.yml, same as bucket_sync)
- [x] `tests/test_bucket_upload.py` — sanitize / render / key resolution /
  temp dir / rclone command construction / resolution order
- [x] `tests/test_scripts.py` — `convert_to_webp(..., dst=...)` coverage
- [x] `pyproject.toml` — `poe bucket-upload` task
- [x] `mkdocs.yml` — `extra.bucket.upload` (`rule`, `fallback_name`, `tmp_dir`, `max_size_mb`)
- [x] `.gitignore` — `.bucket/` (temp dir, pattern of `.bot-api/`)
- [x] `.env.example` — `BUCKET_UPLOAD_RULE` / `BUCKET_UPLOAD_FALLBACK_NAME` /
  `BUCKET_UPLOAD_TMP_DIR` + rw-token note
- [x] `internal/bucket-design.md` — upload section (flow, config, rw token
  requirement)
- [x] `internal/architecture.md` — env var table rows
- [x] AGENTS.md — `poe bucket-upload` command line

## Status (2026-08-22)

**Completed — verified in real use.** All tasks done; developer provisioned
the read-write R2 token and ran a live `poe bucket-upload … --confirm`
end-to-end (WebP conversion → rclone upload → local `docs/assets/bucket/`
copy → md link), confirmed usable. Archived per the plan-index convention.

## Notes

- Safety: **dry-run by default** (`--confirm` uploads, like `bucket-sync`);
  per-file size limit `extra.bucket.upload.max_size_mb` (default 10 MB),
  oversized sources fail immediately (`--max-size-mb` /
  `BUCKET_UPLOAD_MAX_SIZE_MB` override).
- Remote auto-detection: picked from `rclone listremotes` (prefers `r2`, else
  the single/first remote); stale `BUCKET_SYNC_REMOTE` warns and falls back.
- R2 token requirement: `bucket-sync pull` needs read-only; `bucket-upload`
  needs **write** (Object Write). Developer must replace the token in `.env`
  and re-run `poe rclone-config-init` — docs call this out explicitly.
- Uploads stay out of CI (CI never syncs/uploads).
- Inputs are PNG/JPG/JPEG only; WebP sources are rejected with a warning.
- Temp dir is repo-local scratch (converted WebP before upload); the durable
  local copy for VSCode preview stays under `docs/assets/bucket/` (git-ignored).
  Cleanup: temp deleted after successful upload, kept on failure for retry.
