# r2-client

TypeScript prototype demonstrating **basic Cloudflare R2** usage from Node.js
via R2's **S3-compatible API**, using the official
[`@aws-sdk/client-s3`](https://www.npmjs.com/package/@aws-sdk/client-s3) (AWS
SDK for JavaScript v3) plus
[`@aws-sdk/s3-request-presigner`](https://www.npmjs.com/package/@aws-sdk/s3-request-presigner)
for presigned URLs. Package manager: **pnpm**.

Status: `working` (validated end-to-end — see the Cloudflare R2 Setup and
Local test sections below)

## Features

- Configuration via environment variables (no secrets in code)
- List buckets
- Create bucket if it does not exist yet (R2 buckets are private by default)
- List objects under a demo prefix
- Put object (upload)
- Get object (download)
- Generate presigned URL for GET (time-limited download access)
- Generate presigned URL for PUT upload (time-limited upload access)
- Delete object + delete demo bucket (cleanup: demo object always removed;
  bucket deleted only when this run created it — pre-existing buckets are
  left in place)

## Cloudflare R2 Setup (test environment)

R2 exposes a plain **S3-compatible** API: the client signs SigV4 requests
with an R2 API token and talks to the endpoint
`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. The SDK parts are exactly
the standard AWS SDK for JavaScript v3 — only the endpoint, region and
credentials differ.

### 1. Create a Cloudflare account

Sign up at <https://dash.cloudflare.com> (or use an existing account). R2
needs a billing profile: Cloudflare asks you to add a payment method even
though the free tier itself does not charge for the demo's usage (the demo
is well within the free limits).

### 2. Create a bucket

1. In the dashboard, open **R2 Object Storage**.
1. **Create bucket** → pick a name (e.g. `my-demo-bucket`). R2 buckets are
   **private** by default, which is what the demo expects — access goes
   through presigned URLs only.

### 3. Create an R2 API token

1. In **R2 Object Storage** → **Manage R2 API Tokens** → **Create API Token**.
1. Set the **Permission** to **Admin Read & Write** — the demo lists buckets,
   creates the demo bucket, and deletes it again; an object-only token
   ("Object Read & Write") cannot do those bucket-management steps and the
   demo fails with 403 (see Notes).
1. Optionally scope the token to just the demo bucket.
1. Copy the generated **Access Key ID** and **Secret Access Key** (shown only
   once).

> Store the secret safely. Anyone holding it can read and write your R2
> objects — never commit it to git.

### 4. Configure the prototype

The demo loads `.env.dev.local` first, falling back to `.env` when it is
missing (see `dotenv.config({ path: [".env.dev.local", ".env"] })` in
`src/index.ts`). Copy the example and fill in your values:

```bash
cp .env.example .env.dev.local
```

```bash
# .env.dev.local
R2_ACCOUNT_ID=your-cloudflare-account-id   # dashboard → right sidebar "Account ID"
R2_ACCESS_KEY_ID=your-access-key-id         # R2 API token (Admin Read & Write)
R2_SECRET_ACCESS_KEY=your-secret            # R2 API token secret
R2_BUCKET=my-demo-bucket
```

Optional: `R2_REGION` (default `auto` — R2 ignores the region string, `auto`
is what Cloudflare's own examples use), `R2_ENDPOINT` (override the
account-derived endpoint, e.g. a custom domain or a local MinIO), and
`R2_DEMO_PREFIX` to control where demo objects are written
(`demo/r2-client/` by default; the prefix must end with `/` — leaving it
empty writes to the bucket root). Set `R2_KEEP_DEMO_OBJECT=true` to skip the
demo's automatic cleanup (needed for the curl test below).

`.env`, `.env.local` and `.env.*.local` are gitignored — only `.env.example`
is committed.

## Local test without a Cloudflare account (MinIO)

There is no official local R2 emulator, but MinIO implements the same S3 API
R2 exposes, so the demo runs against it **unchanged** (SigV4 signing and
presigned URLs included). Requires Docker:

```bash
pnpm minio:start   # start MinIO — S3 API on :9000, console on :9001
```

then point the demo at it (the workspace's local, gitignored
`.env.dev.local` is already pre-filled with this config; otherwise put it in
`.env.dev.local` yourself):

```bash
# .env.dev.local
R2_ENDPOINT=http://127.0.0.1:9000
R2_FORCE_PATH_STYLE=true       # MinIO has no DNS for virtual-hosted buckets
R2_REGION=us-east-1            # MinIO's default region
R2_ACCESS_KEY_ID=minioadmin    # MinIO's root credentials (dev only!)
R2_SECRET_ACCESS_KEY=minioadmin
R2_BUCKET=r2-client-demo
```

Stop it again with `pnpm minio:stop`. The `--rm` container is removed on
stop, but the test data (a **named Docker volume**, `r2-client-minio-data`)
is kept so a restart starts where you left off. To fully wipe the local
MinIO, two separate entries (see `scripts/`):

```bash
pnpm minio:clean-volumes   # stop + delete the named Docker volume (MinIO objects + buckets)
pnpm minio:clean-images    # stop + remove dangling and minio/minio images (next start re-pulls them)
```

`clean-volumes` wipes the test data; `clean-images` additionally removes the
MinIO image (and dangling leftovers), so the next `minio:start` behaves like
a fresh first run.

Once it is up, MinIO ships a web console (also printed by `minio:start`):

| Web UI        | URL                     | Purpose                                                                                                               |
| ------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------- |
| MinIO Console | <http://127.0.0.1:9001> | Management console (`minioadmin` / `minioadmin`) — browse/create/delete buckets & objects, view them after `pnpm dev` |

## Usage

```bash
pnpm install             # install dependencies
pnpm dev                 # run TypeScript directly, no build step (tsx src/index.ts)
pnpm build && pnpm demo  # compile to dist/ first, then run the artifact
```

- **`pnpm dev`** runs the source directly — edits take effect on the next
  run without ever building.
- `pnpm demo` runs the compiled `dist/index.js` — it does **not** pick up
  `.ts` edits until you re-run `pnpm build`.

Without credentials the demo prints the setup instructions above (dry-run).
With configured credentials it runs through: list buckets → ensure bucket →
list objects → put → get → presigned URL (GET) → presigned URL (PUT upload)
→ cleanup (the demo object is removed afterwards; if this run created the
bucket it is deleted too — set `R2_KEEP_DEMO_OBJECT=true` to keep the object
and bucket).

## Testing a presigned upload URL with curl

The demo prints a presigned **PUT** upload URL for the demo object. An
S3-style presigned URL is credential-free: the signature is carried in the
query string and binds the HTTP method and the object key. Unlike some other
services' signed URLs (e.g. OSS), `Content-Type` is **not** part of the
signature — a plain curl PUT works without any special headers:

```bash
# 1. run the demo and keep the demo object
R2_KEEP_DEMO_OBJECT=true pnpm dev

# 2. within the 60 s expiry shown in the section title, copy the URL printed
#    under the "Presigned upload URL (PUT, ...)" heading and PUT content to it
curl -X PUT \
  --data-binary "hello from curl" \
  "<presigned upload URL>"

# 3. verify with the presigned GET URL printed by the demo
curl "<presigned GET URL>"
```

`--data-binary` is used instead of `--data` so curl does not strip trailing
newlines. curl sends `Content-Type: application/x-www-form-urlencoded` for a
data PUT by default — harmless for the signature, but pass
`-H "Content-Type: text/plain"` if you want the uploaded object's metadata
to match the demo object. The URLs expire 60 s after they are printed, so
run steps 2–3 promptly; re-running the demo prints fresh ones (the curl PUT
overwrites the existing demo object, so the test is repeatable).

## Debugging with VS Code

The repo-root `.vscode/launch.json` carries a configuration for this
prototype (**Debug r2-client (tsx)**) on this machine — but that file is
**gitignored** (the global `~/.gitignore_global` ignores `.vscode/`), so it
is not committed. On a fresh clone, create or extend `.vscode/launch.json`
with:

```jsonc
{
  "name": "Debug r2-client (tsx)",
  "type": "node",
  "request": "launch",
  "cwd": "${workspaceFolder}/prototypes/r2-client",
  "program": "${workspaceFolder}/prototypes/r2-client/src/index.ts",
  "runtimeExecutable": "${workspaceFolder}/prototypes/r2-client/node_modules/.bin/tsx",
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen",
  "sourceMaps": true,
  "skipFiles": ["<node_internals>/**", "${workspaceFolder}/prototypes/r2-client/node_modules/**"],
}
```

This is tsx's officially documented debug setup
(<https://tsx.hirok.io/vscode>): the `tsx` CLI is the debugged executable
instead of `node --import tsx`, so breakpoints reliably map back to the
`.ts` sources. Then:

1. Make sure dependencies are installed: `pnpm install`.
1. Point the demo somewhere: `pnpm minio:start` + the MinIO env config
   (above), or real R2 credentials in `.env.dev.local`.
1. Open the **repo root** in VS Code, go to the **Run and Debug** panel,
   select **Debug r2-client (tsx)**, and press F5.

Every F5 launches a fresh process that reads the current `.ts` files, so
breakpoints always hit your latest edits. `cwd` is the prototype directory,
so dotenv resolves `.env.dev.local` from there. To override environment
variables without touching `.env.dev.local`/`.env`, add an `env` block to
the configuration (e.g. `"env": { "R2_BUCKET": "my-other-bucket" }`).

## Project Layout

```
r2-client/
├── .env.example        # env template (credentials are never committed)
├── .gitignore          # typical TS project ignore (node_modules, dist, .env*, ...)
├── package.json        # pnpm-managed
├── pnpm-workspace.yaml # pnpm 11 allowBuilds (esbuild via tsx)
├── tsconfig.json
├── scripts/
│   ├── minio_start.sh      # start local MinIO (Docker) for testing without R2
│   ├── minio_stop.sh       # stop it again (--rm container; named data volume kept)
│   ├── clean_volumes.sh    # minio:clean-volumes — wipe the named data volume
│   └── clean_images.sh     # minio:clean-images — remove minio/minio images + dangling
└── src/
    ├── config.ts       # env-based configuration
    └── index.ts        # demo operations
```

## Notes

- SDK docs: <https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/client/s3/>
  and Cloudflare's official example:
  <https://developers.cloudflare.com/r2/examples/aws/aws-sdk-js-v3/>
- **R2 API token permissions**: the demo's bucket-management steps (list
  buckets / create / delete) need **Admin Read & Write**; an **Object Read &
  Write** token (per-object ops only) makes `ListBuckets`/`CreateBucket`/
  `DeleteBucket` fail with 403. In production, scope the token to one bucket
  and prefer per-object permissions where possible.
- **R2 ignores the region string** — `auto` (the default) is what
  Cloudflare's own examples use; MinIO wants `us-east-1`.
- **`forcePathStyle`** is required for MinIO (path-style addressing;
  localhost has no DNS for virtual-hosted buckets) but not for real R2.
- **Newer AWS SDKs stamp a CRC32 header on `PutObject`** by default
  (`requestChecksumCalculation: "WHEN_SUPPORTED"`); this demo sets
  `WHEN_REQUIRED` so uploads stay plain and work on every S3-compatible
  endpoint.
- **Deleting a non-empty bucket fails** — the demo removes the demo object
  before deleting the bucket, and only deletes buckets it created itself (a
  pre-existing `R2_BUCKET` is never deleted — the demo touches only keys
  under the demo prefix inside it). Both cleanups are best-effort (the
  object cleanup failing makes the bucket deletion fail too, but that is
  reported, not fatal). A bucket left behind by an `R2_KEEP_DEMO_OBJECT` run
  is not auto-removed by later runs — delete it manually if you want it gone.
- **S3-style deletion is idempotent** — deleting a missing object also
  succeeds, so the demo's object cleanup never errors on a missing key.
- **Not part of GitHub CI**: this prototype is not built or tested by the
  repo's GitHub Actions workflow (CI only covers the main MkDocs site and
  Python toolchain). Verify it locally with `pnpm typecheck` / `pnpm build`
  (see [AGENTS.md](../../AGENTS.md) → Prototype Convention).
