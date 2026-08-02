# ali-oss-client

TypeScript prototype demonstrating **basic Aliyun Object Storage Service
(OSS)** usage from Node.js with the official [`ali-oss`](https://www.npmjs.com/package/ali-oss)
SDK. Package manager: **pnpm**.

Status: `experimental`

## Features

- Configuration via environment variables (no secrets in code)
- List buckets
- List objects under a demo prefix
- Put object (upload)
- Get object (download)
- Generate signed URL (time-limited access)
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

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

```bash
# .env
ALIYUN_OSS_REGION=oss-cn-hangzhou
ALIYUN_OSS_BUCKET=my-demo-bucket
ALIYUN_OSS_ACCESS_KEY_ID=LTAI5t...           # your AccessKey ID
ALIYUN_OSS_ACCESS_KEY_SECRET=your-secret     # your AccessKey Secret
```

Optional: set `ALIYUN_OSS_ENDPOINT` to override the region-derived endpoint
(e.g. a custom CNAME), and `ALIYUN_OSS_DEMO_PREFIX` to control where demo
objects are written (`demo/ali-oss-client-prototype/` by default; the prefix
must end with `/` — leaving it empty writes to the bucket root).

`.env` is gitignored — only `.env.example` is committed.

## Usage

```bash
pnpm install   # install dependencies
pnpm build     # compile TypeScript -> dist/
pnpm demo      # run the demo (node dist/index.js)
```

Or run directly from source without a build step:

```bash
pnpm dev       # tsx src/index.ts
```

Without credentials the demo prints the setup instructions above (dry-run).
With a configured `.env` it runs through: list buckets → list objects →
put → get → signed URL → delete (the demo object is cleaned up afterwards).

## Debugging with VS Code

The repo root already ships a launch configuration for this prototype in
`.vscode/launch.json` (named **Debug ali-oss-client (tsx)**). It runs the
source directly with `tsx` — no build step needed:

```jsonc
{
  "name": "Debug ali-oss-client (tsx)",
  "type": "node",
  "request": "launch",
  "cwd": "${workspaceFolder}/prototypes/ali-oss-client",
  "runtimeArgs": ["--import", "tsx"],
  "program": "${workspaceFolder}/prototypes/ali-oss-client/src/index.ts",
  "sourceMaps": true,
  "skipFiles": ["<node_internals>/**"]
}
```

### How it works

- `--import tsx` is the Node-native equivalent of `pnpm dev`
  (`tsx src/index.ts`); breakpoints map straight back to the TypeScript
  sources via `sourceMap: true`.
- `cwd` is the prototype directory, so `dotenv` picks up `.env` from there:
  with credentials the debugger walks through the real OSS calls, without
  them it hits the dry-run path.

### Usage

1. Make sure dependencies are installed: `pnpm install` (in
   `prototypes/ali-oss-client/`).
1. Open the **repo root** in VS Code, go to the **Run and Debug** panel,
   select **Debug ali-oss-client (tsx)**, and press F5.

To override environment variables without touching `.env` (e.g. for a
different bucket), add an `env` block to the configuration:

```jsonc
"env": { "ALIYUN_OSS_BUCKET": "my-other-bucket" }
```

## Project Layout

```
ali-oss-client/
├── .env.example      # env template (credentials are never committed)
├── .gitignore        # typical TS project ignore (node_modules, dist, .env, ...)
├── package.json      # pnpm-managed
├── tsconfig.json
└── src/
    ├── config.ts     # env-based configuration
    └── index.ts      # demo operations
```

## Notes

- SDK docs: <https://help.aliyun.com/zh/oss/developer-reference/use-the-oss-node-js-sdk>
- For production use, prefer **STS temporary credentials** or
  **RAM roles** over long-lived AccessKeys, and scope permissions per bucket.
- The demo only touches keys under `ALIYUN_OSS_DEMO_PREFIX`, so it never
  clobbers unrelated objects in the bucket.
- **Not part of GitHub CI**: this prototype is not built or tested by the
  repo's GitHub Actions workflow (CI only covers the main MkDocs site and
  Python toolchain). Verify it locally with `pnpm typecheck` / `pnpm build`
  (see [AGENTS.md](../../AGENTS.md) → Prototype Convention).
