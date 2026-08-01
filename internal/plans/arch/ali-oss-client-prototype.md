---
title: Aliyun OSS Client Prototype
created: 2026-08-01
archived: 2026-08-01
status: completed
tags: [prototype, aliyun-oss, typescript, pnpm, cloud-storage]
---

# Aliyun OSS Client Prototype

> **Archived** — `archived: 2026-08-01`, `status: completed` (all 8 tasks done,
> prototype committed as `46c5682`).
> Location: `internal/plans/arch/ali-oss-client-prototype.md`.

## Goal

Prototype an Aliyun Object Storage Service (OSS) client in TypeScript under
`prototypes/ali-oss-client/` to validate basic OSS usage from Node.js using the
official `ali-oss` SDK: configuration via environment variables, bucket /
object listing, upload, download, signed URLs, and deletion. The project is
managed with **pnpm** and the README documents the basic Aliyun OSS setup
steps (RAM user, AccessKey, bucket, region/endpoint, `.env`).

## Tasks

- [x] **Plan**: create this plan file under `internal/plans/` and register it
  in the Plan List of `internal/plans/plan-index.md`
- [x] **Scaffold** `prototypes/ali-oss-client/` as a pnpm TypeScript project
  \- `package.json` (pnpm as package manager, `ali-oss` SDK dependency,
  `typescript` / `@types/node` / `tsx` dev deps)
  \- `tsconfig.json` (strict, NodeNext)
  \- Typical TS-project `.gitignore` (`node_modules/`, `dist/`, `.env`,
  logs, etc.)
- [x] **Config**: load credentials/region/bucket from environment variables;
  provide `.env.example` (gitignored `.env` stays out of the repo)
- [x] **Demo operations** in `src/index.ts`:
  list buckets, list objects (demo prefix), put object, get object,
  generate signed URL, delete object (with cleanup)
- [x] **README.md** with basic Aliyun OSS configuration:
  RAM user + AccessKey, bucket creation, region/endpoint, `.env` setup,
  security notes; usage (`pnpm install` / `pnpm build` / `pnpm demo`)
- [x] **Dependencies**: install with pnpm and verify `pnpm typecheck` /
  `pnpm build`; demo runs in dry-run mode (prints setup instructions) when
  no credentials are configured
- [x] **Index**: update `prototypes/README.md` and `docs/notes/prototypes.md`
  (site listing)

## Notes

- Official SDK: `ali-oss` (npm). Node.js SDK docs:
  https://help.aliyun.com/zh/oss/developer-reference/use-the-oss-node-js-sdk
- `ali-oss` does not bundle type declarations — use `@types/ali-oss`
  (DefinitelyTyped); note its signatures: `listBuckets(query)` returns
  `Bucket[]` directly, and `list()` requires a `RequestOptions` second arg
- pnpm 11 ignores the `pnpm.onlyBuiltDependencies` field in `package.json`;
  per-package build approval lives in `pnpm-workspace.yaml` under the new
  `allowBuilds` key (`esbuild: true` for tsx)
- Credentials must never be committed — only `.env.example` is tracked; `.env`
  is ignored by the prototype's own `.gitignore`
- The demo only touches keys under `ALIYUN_OSS_DEMO_PREFIX` so it never
  clobbers unrelated objects
- A validated prototype can later be promoted to a real project (plan under
  `internal/plans/` or a standalone repo)
