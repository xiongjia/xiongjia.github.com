# Prototypes

Experimental mini-projects live under `prototypes/<name>/` at the repo root so
ideas can be validated quickly and captured in place, without disturbing the
main MkDocs build, formatting, or lint workflow.

Each prototype is one subdirectory (kebab-case naming), committed to the repo,
with its own `README.md` (purpose, usage, current status) and its own
`.gitignore` (ignoring its build artifacts, e.g. Rust `target/`,
Python `.venv/`, Node `node_modules/`).

## Object Storage

- **[ali-oss-client](./ali-oss-client/README.md)** — Aliyun OSS client in
  TypeScript (official `ali-oss` SDK, pnpm): config via env vars, bucket/object
  listing, upload, download, signed URLs, delete · created 2026-08-01 · status
  `working`
- **[supabase-storage-client](./supabase-storage-client/README.md)** —
  Supabase Storage client in TypeScript (official `@supabase/supabase-js`,
  pnpm): local `supabase start` project config included, anon key auto-read
  from the CLI, bucket/object listing, create bucket, upload, download,
  signed URLs, public URL, delete · created 2026-08-04 · status
  `working`
- **[r2-client](./r2-client/README.md)** — Cloudflare R2 client in
  TypeScript (S3-compatible AWS SDK v3 `@aws-sdk/client-s3`, pnpm): config
  via env vars, bucket/object listing, create bucket, upload, download,
  presigned URLs, delete; local MinIO test included (no Cloudflare account
  needed to try it) · created 2026-08-05 · status `working`

## Job Queue

- **[pg-boss-demo](./pg-boss-demo/README.md)** — NestJS 12 + pg-boss 12 job
  queue prototype (pnpm): REST API to enqueue/inspect/cancel/retry jobs, three
  demo queues (echo / flaky-retry / slow-concurrency), Swagger docs, unit + e2e
  tests, Postgres 18 via docker compose, @pg-boss/dashboard debug UI
  (`pnpm dashboard`) · created 2026-08-30 · status `working`

## ETL

- **[etl-dbt](./etl-dbt/README.md)** — Minimal dbt call-chain demo with
  **dbt-core + DuckDB** (no server): fixed 10-row CSV → `dbt seed` → one staging
  view (`stg_test_data`, filters cancelled + adds `line_total`), tests, and the
  full command walkthrough (seed/run/test/build/compile) · created 2026-08-26 ·
  status `working`

## Utilities

- **[go-cli-urfave](./go-cli-urfave/README.md)** — Go CLI built with
  urfave/cli **v3** (migrated from v2): root command with global `--name` flag,
  subcommands (`hello`, `bye` alias `b`), nested commands (`team add/remove`),
  per-command flags, strict arg validation with exit code 2; `Justfile` recipes
  (`just build`/`run`/`fmt`/`vet`/`test`/`clean`); originally under
  `research/experiments/`, migrated here; `go.sum` tracked for reproducible
  builds · created 2026-08-03 · status `working`

## Others

- **[protomaps-map-view](./protomaps-map-view/README.md)** — React + Vite + TS
  generic map view component on a local Protomaps basemap (MapLibre GL JS +
  pmtiles + @protomaps/basemaps): env-configured local cache (gitignored
  `.cache/pmtiles/` + `.cache/glyphs/` served by inline Vite dev/preview
  plugins, no CDN), center HUD, markers (emoji or dots + labels/popups), track
  lines, runtime basemap switching, 5 demos with tab switching, embeddable
  widget (build:widget, plain-HTML / S3 distribution) · created 2026-08-07 ·
  status `working`
- **[prototype-example](./prototype-example/README.md)** — Minimal Rust
  hello-world **example** validating the prototype mechanism (not a practical
  prototype) · created 2026-08-01 · status `experimental`

## Convention

- Directory, gitignore, and fmt/lint skip rules: see the Prototype Convention in `AGENTS.md`
- Keep this index in sync when a prototype is added/removed
