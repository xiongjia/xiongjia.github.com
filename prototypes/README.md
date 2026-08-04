# Prototypes

Experimental mini-projects live under `prototypes/<name>/` at the repo root so
ideas can be validated quickly and captured in place, without disturbing the
main MkDocs build, formatting, or lint workflow.

Each prototype is one subdirectory (kebab-case naming), committed to the repo,
with its own `README.md` (purpose, usage, current status) and its own
`.gitignore` (ignoring its build artifacts, e.g. Rust `target/`,
Python `.venv/`, Node `node_modules/`).

## Index

- **[go-cli-urfave](./go-cli-urfave/README.md)** — Go CLI built with
  urfave/cli v2: `greet` command with `--name` flag (originally under
  `research/experiments/`, migrated here; `go.sum` tracked for reproducible
  builds) · created 2026-08-03 · status `experimental`
- **[ali-oss-client](./ali-oss-client/README.md)** — Aliyun OSS client in
  TypeScript (official `ali-oss` SDK, pnpm): config via env vars, bucket/object
  listing, upload, download, signed URLs, delete · created 2026-08-01 · status
  `working`
- **[supabase-storage-client](./supabase-storage-client/README.md)** —
  Supabase Storage client in TypeScript (official `@supabase/supabase-js`,
  pnpm): local `supabase start` project config included, anon key auto-read
  from the CLI, bucket/object listing, create bucket, upload, download,
  signed URLs, public URL, delete · created 2026-08-04 · status
  `experimental`
- **[prototype-example](./prototype-example/README.md)** — Minimal Rust
  hello-world **example** validating the prototype mechanism (not a practical
  prototype) · created 2026-08-01 · status `experimental`

## Convention

- Directory, gitignore, and fmt/lint skip rules: see the Prototype Convention in `AGENTS.md`
- Keep this index in sync when a prototype is added/removed
