# ali-oss-client

TypeScript prototype demonstrating **basic Aliyun Object Storage Service
(OSS)** usage from Node.js with the official [`ali-oss`](https://www.npmjs.com/package/ali-oss)
SDK. Package manager: **pnpm**.

Status: `working`

## Features

- Configuration via environment variables (no secrets in code)
- List buckets
- List objects under a demo prefix
- Put object (upload)
- Get object (download)
- Generate signed URL for GET (time-limited download access)
- Generate signed URL for PUT upload (time-limited upload access)
- Delete object (with automatic cleanup of the demo object)

## Basic Aliyun OSS Configuration

### 1. Create a RAM user and get an AccessKey

1. Open the RAM console: <https://ram.console.aliyun.com> (sign in with your
   Alibaba Cloud account).
1. **Users** → **Create User** → give it a name (e.g. `oss-demo-user`), check
   **OpenAPI calling access**, and record the generated **AccessKey ID** and
   **AccessKey Secret** (shown only once).
1. Grant the user at least **AliyunOSSFullAccess** (or a tighter custom policy
   scoped to one bucket). For local experiments, attaching the full policy to a
   dedicated RAM user is fine.

> Store the AccessKey Secret safely. Anyone holding it can access your
> buckets — never commit it to git.

### 2. Create a bucket

1. Open the OSS console: <https://oss.console.aliyun.com>.
1. **Bucket List** → **Create Bucket**.
1. Pick a globally unique name (e.g. `my-demo-bucket`) and a **region**
   (e.g. `cn-hangzhou`). The region string used in the SDK looks like
   `oss-cn-hangzhou` (region code with the `oss-` prefix).
1. Keep the default access control (private) for a demo.

### 3. Configure the prototype

The demo loads `.env.dev.local` first, falling back to `.env` when it is
missing (see `dotenv.config({ path: [".env.dev.local", ".env"] })` in
`src/index.ts`). Copy the example and fill in your values:

```bash
cp .env.example .env.dev.local
```

```bash
# .env.dev.local
ALIYUN_OSS_REGION=oss-cn-hangzhou
ALIYUN_OSS_BUCKET=my-demo-bucket
ALIYUN_OSS_ACCESS_KEY_ID=LTAI5t...           # your AccessKey ID
ALIYUN_OSS_ACCESS_KEY_SECRET=your-secret     # your AccessKey Secret
```

Optional: set `ALIYUN_OSS_ENDPOINT` to override the region-derived endpoint
(e.g. a custom CNAME), and `ALIYUN_OSS_DEMO_PREFIX` to control where demo
objects are written (`demo/ali-oss-client-prototype/` by default; the prefix
must end with `/` — leaving it empty writes to the bucket root). Set
`ALIYUN_OSS_KEEP_DEMO_OBJECT=true` to skip the demo's automatic cleanup of
the demo object (needed for the curl test below).

`.env`, `.env.local` and `.env.*.local` are gitignored — only `.env.example`
is committed.

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
With configured credentials (in `.env.dev.local` or `.env`) it runs through:
list buckets → list objects → put → get → signed URL (GET) → signed URL
(PUT upload) → delete (the demo object is cleaned up afterwards; set
`ALIYUN_OSS_KEEP_DEMO_OBJECT=true` to keep it).

## Testing a signed upload URL with curl

The demo prints a signed **PUT** URL for the demo object. The signature binds
the HTTP method, the object key, and the `Content-Type` header — curl must
send the exact same `Content-Type` that was used when the URL was generated
(`text/plain` for the demo object), or OSS rejects the request with
`403 SignatureDoesNotMatch`.

The URL expires shortly after it is printed — the demo uses 60 seconds (the
exact value is shown in each section title, e.g. `expires in 60s`). By
default the demo deletes the object right after the run, so keep the object
around to test end to end:

```bash
# 1. run the demo and keep the demo object
ALIYUN_OSS_KEEP_DEMO_OBJECT=true pnpm dev

# 2. within the expiry shown in the section title, copy the URL printed under
#    the "Signed upload URL (PUT, ...)" heading and PUT content to it
curl -X PUT \
  -H "Content-Type: text/plain" \
  --data-binary "hello from curl" \
  "<signed upload URL>"

# 3. verify with the signed GET URL printed by the demo
curl "<signed GET URL>"
```

`--data-binary` is used instead of `--data` so curl does not strip trailing
newlines. A wrong or missing `Content-Type` (or any other header change)
makes the upload fail with `403 SignatureDoesNotMatch`. Re-running the demo
overwrites the object again, so the test is repeatable.

## Debugging with VS Code

The repo root already ships a launch configuration for this prototype in
`.vscode/launch.json` (named **Debug ali-oss-client (tsx)**). It runs the
source directly with the `tsx` CLI — no build step needed:

```jsonc
{
  "name": "Debug ali-oss-client (tsx)",
  "type": "node",
  "request": "launch",
  "cwd": "${workspaceFolder}/prototypes/ali-oss-client",
  "program": "${workspaceFolder}/prototypes/ali-oss-client/src/index.ts",
  "runtimeExecutable": "${workspaceFolder}/prototypes/ali-oss-client/node_modules/.bin/tsx",
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen",
  "sourceMaps": true,
  "skipFiles": [
    "<node_internals>/**",
    "${workspaceFolder}/prototypes/ali-oss-client/node_modules/**",
  ],
}
```

This is tsx's officially documented debug setup
(<https://tsx.hirok.io/vscode>): the `tsx` CLI is the debugged executable
instead of `node --import tsx`, so breakpoints reliably map back to the
`.ts` sources.

### How it works

- **Every F5 launches a fresh process that reads the current `.ts` files**, so
  breakpoints always hit your latest edits — edit, save, press F5 (or
  `Ctrl+Shift+F5` to restart). No build step, no watch mode needed.
- Watch mode is deliberately _not_ combined with the debugger: a restarted
  process gets a new inspector session and VS Code does not auto re-attach,
  so breakpoints silently stop firing (verified with both `node --watch`
  and `tsx watch`). The debugger itself is always up to date by design —
  each run is a fresh session.
- `cwd` is the prototype directory, so `dotenv` picks up `.env.dev.local`
  (falling back to `.env`) from there: with credentials the debugger walks
  through the real OSS calls, without them it hits the dry-run path.

### Usage

1. Make sure dependencies are installed: `pnpm install` (in
   `prototypes/ali-oss-client/`).
1. Open the **repo root** in VS Code, go to the **Run and Debug** panel,
   select **Debug ali-oss-client (tsx)**, and press F5.

To override environment variables without touching `.env.dev.local`/`.env`
(e.g. for a different bucket), add an `env` block to the configuration:

```jsonc
"env": { "ALIYUN_OSS_BUCKET": "my-other-bucket" }
```

## Project Layout

```
ali-oss-client/
├── .env.example      # env template (credentials are never committed)
├── .gitignore        # typical TS project ignore (node_modules, dist, .env*, ...)
├── package.json      # pnpm-managed
├── tsconfig.json
└── src/
    ├── config.ts     # env-based configuration
    └── index.ts      # demo operations
```

## Notes

- SDK docs: <https://help.aliyun.com/zh/oss/developer-reference/use-the-oss-node-js-sdk>
- **ali-oss 6.23 gotchas** (hit while verifying the demo end-to-end):
  - `listBuckets` must be called with `{}`, not `null` — the implementation
    destructures the query (`const { subres = {} } = query`) and the default
    parameter only applies to `undefined`, so `null` crashes with
    `Cannot read properties of null`.
  - `listBuckets` returns an object, not the `Bucket[]` that
    `@types/ali-oss` declares: `{ buckets, owner, isTruncated, nextMarker }`,
    with `buckets` `null` when the account has no buckets (the demo casts
    to the real shape).
  - `DeleteObject` returns `204 No Content` even when the object did not
    exist (deletion is idempotent), so 204 means "the object is gone now",
    not "an object was deleted".
- For production use, prefer **STS temporary credentials** or
  **RAM roles** over long-lived AccessKeys, and scope permissions per bucket.
- The demo only touches keys under `ALIYUN_OSS_DEMO_PREFIX`, so it never
  clobbers unrelated objects in the bucket.
- **Not part of GitHub CI**: this prototype is not built or tested by the
  repo's GitHub Actions workflow (CI only covers the main MkDocs site and
  Python toolchain). Verify it locally with `pnpm typecheck` / `pnpm build`
  (see [AGENTS.md](../../AGENTS.md) → Prototype Convention).
