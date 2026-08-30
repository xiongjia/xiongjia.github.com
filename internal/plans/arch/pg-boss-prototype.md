---
title: pg-boss Prototype (NestJS 12 + pnpm)
created: 2026-08-30
archived: 2026-08-30
status: completed
tags: [prototype, pg-boss, nestjs, typescript, job-queue, postgres, pnpm, unit-test]
---

# pg-boss Prototype (NestJS 12 + pnpm)

> **Archived** — `archived: 2026-08-30`, `status: completed` (all tasks done;
> prototype lives at `prototypes/pg-boss-demo/`, status `working`).

**Scope**: prototype only (`prototypes/pg-boss-demo/`) — intentionally **not** a
research topic; all learning notes live in the prototype's own README.

## Goal

Build a **pg-boss 12 + NestJS 12 + pnpm** job-queue prototype under
`prototypes/pg-boss-demo/`: pg-boss wrapped as a NestJS service (DI + Config +
Logger, config from `@nestjs/config`), a set of **REST APIs** to enqueue jobs and
query job status/results, demonstrating queue execution, concurrency control,
retries, status queries and result queries. PostgreSQL runs in **docker
compose**; the pg-boss schema is initialized by pg-boss itself. The core
service (`PgBossService`) has **unit tests** (pg-boss mocked, no real DB) and an
**e2e** suite against the real Postgres.

## Tech choices (versions verified 2026-08-30)

| Component  | Version                              | Notes                                                                                                                      |
| ---------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| pg-boss    | 12.28.1                              | Node >= 22.12; pure ESM + **named export** (`import { PgBoss }`); states: created/retry/active/completed/cancelled/failed  |
| NestJS     | 12.x                                 | `@nestjs/core` 12.0.1, `@nestjs/config` 12.0.0, `@nestjs/testing` 12.0.1                                                   |
| TypeScript | 7.0.x tried → **fell back to 6.0.x** | `@nestjs/cli` 12 needs the TS programmatic API (absent in 7.0, expected back in 7.1)                                       |
| Build      | default `nest build` (tsc)           | TS 6 path; the swc builder also gets rejected on TS 7 at CLI startup                                                       |
| Unit tests | Vitest 4 + `unplugin-swc`            | `Test.createTestingModule` + `useValue` mocks; swc emits `emitDecoratorMetadata` (esbuild does not)                        |
| E2E        | Vitest 4 + supertest                 | real Postgres; random port; deletes only the jobs it created (`deleteJob`)                                                 |
| Swagger    | `@nestjs/swagger` 12.0.1             | manual decorators (`@ApiProperty`, ...); the CLI plugin is unusable (TS API) and the `cliPlugin` option was removed in v12 |
| Postgres   | 18 (docker compose)                  | pg-boss 12 requires >= 13; named volume + healthcheck                                                                      |

### TypeScript 7 conclusion (verified)

- `tsc --noEmit` (tsgo) passes and correctly emits `emitDecoratorMetadata`
  (`design:paramtypes`), so NestJS DI works under TS 7.
- `nest build` (including `--builder swc`) is **rejected by `@nestjs/cli` 12 at
  startup**: *"The installed TypeScript version (7.0.2) does not expose the
  programmatic compiler API that the Nest CLI requires... the compiler API is
  expected to return in 7.1"*. `typescript@7.0.x` ships the `tsc` binary only.
- `ts-jest` peers require `typescript < 7`.
- **Decision**: try TS 7 first, fall back to TS 6 when Nest blocks it (confirmed
  by the user). Applied: `typescript@~6.0.2` + default tsc builder; Vitest kept
  (compiler-agnostic). Revisit TS 7.1 once the programmatic API returns.

## Key design decisions

1. **type = queue (1:1)** — the queue name is the job type name (`echo` /
   `flaky` / `slow`); `POST /jobs` rejects unknown types with 400.
1. **Queue registration driven by a handler registry** — `buildRegistry(concurrency)`
   declares `{ queue, workOptions, handlerClass }[]`; `PgBossService` creates the
   queue and registers the worker for every entry on startup.
1. **Handlers are `@Injectable()` classes with real DI** — resolved via
   `ModuleRef.get(handlerClass, { strict: false })`, so they inject any provider
   (demonstrated with `NotificationService`).
1. **`GET /jobs?state=` uses read-only SQL** via `boss.getDb().executeSql` —
   v12 `findJobs` has no state filter (only id/key/data/queued). Queries
   `pgboss.job` (snake_case columns: `retry_count`, `output`, `created_on`, ...).
1. **`GET /queues` returns `getQueueStats` as-is** — v12 needs a queue name
   (no arg-less variant; iterate `REGISTERED_QUEUES`); no completed/cancelled
   breakdown (completed jobs are cleaned up by `deleteAfterSeconds`).
1. **`GET /jobs` requires `queue`** (no cross-queue query API).
1. **No DTO validation library** — simple interfaces + `@ApiProperty`; minimal
   checks in the service (registered type, state strings). No class-validator /
   ValidationPipe.
1. `main.ts` must call **`enableShutdownHooks()`**; `boss.on('error')` is wired
   to the Nest logger; compose credentials match `.env` (pgboss/pgboss).
1. **No `any`, no `!` assertions** anywhere in `src/` (project convention);
   code comments, README and Swagger descriptions in English.

## Implementation notes (pg-boss 12 facts, verified against 12.28.1)

- **Pure ESM, named exports** — `import { PgBoss } from 'pg-boss'`; the official
  README uses `const { PgBoss } = require('pg-boss')`. Node >= 22.12.
- **`send()` returns `string | null`** — `null` = not enqueued (e.g. singleton
  dedup); the API maps it to `200 { id: null, reason: 'deduplicated' }`.
- **Result-query semantics** — `deleteAfterSeconds` controls how long completed
  jobs stay queryable (default 7 days, `0` = forever); `expireInSeconds` (default
  900 s) is the active-job timeout (crashed workers get retried after it);
  `retentionSeconds` (default 14 days) governs created/retry survival — do not
  confuse the two. `retryLimit` default 2; v12 `retryBackoff` is a **boolean**.
- **`getJobById` deprecated** → use `findJobs`; **`getQueueSize` replaced** by
  `getQueueStats(name)`.
- **Workers** — `work(queue, options, handler)` receives a **batch** of jobs;
  `batchSize` defaults to 1; per-node parallelism is **`localConcurrency`**
  (v12; the old `concurrency` option is gone). Throwing from a handler fails the
  batch and triggers the retry policy.
- **Schema** is auto-created by `start()`; raw SQL available via
  `getConstructionPlans()`/`getMigrationPlans()` if pre-provisioning is ever
  needed (the prototype does not use it).

## Findings discovered during implementation (recorded in README)

- `@nestjs/swagger` 12 removed the `cliPlugin` option from
  `SwaggerDocumentOptions` — nothing to pass.
- `getQueueStats(name)` requires a queue name; `cancel`/`retry` return an empty
  `CommandResponse` (query the job first to report results).
- `pgboss.job` column names are snake_case (`deletion_seconds` is the DB column
  for the `deleteAfterSeconds` option).
- Nest 12 needs `@nestjs/platform-express` installed explicitly (default HTTP
  driver) or startup fails with "No driver (HTTP) has been selected".
- Vitest: `vi.fn()` cannot be used as a constructor for ESM-only classes (its
  implementation is invoked as the constructor and fails) — use a real class
  mock. Later switched to NestJS-style `useValue` mocks entirely.
- pnpm 11: unapproved build scripts fail the install with
  `ERR_PNPM_IGNORED_BUILDS` — run `pnpm approve-builds --all` or declare them in
  `pnpm-workspace.yaml` (`allowBuilds`).
- Environment: no blockers — Node v24.16.0, Docker/Compose available, port 5432
  free. Docker image pulls / container lifecycle are developer-run by decision.

## Outcome

- REST API: `POST /jobs`, `GET /jobs?queue=&state=&limit=`, `GET /jobs/:id`,
  `POST /jobs/:id/cancel|retry`, `GET /queues`, `GET /health` — full OpenAPI
  spec at `/api/docs`.
- Unit tests: 16 cases (lifecycle, queue registration, handler DI, delegations,
  SQL queries, config assembly, health up/down).
- E2E: real Postgres — enqueue echo → poll to completed → assert result;
  `/health`; unknown-type 400; cleans up only its own jobs (verified 0 residue).
- Dashboard: `pnpm dashboard` (scripts/dashboard.mjs reads `.env.dev.local`,
  serves on :3001, optional basic auth).
- Verified: `pnpm typecheck` / `pnpm build` / `pnpm test` / `pnpm test:e2e` all
  green; end-to-end demo run by the developer (3 job types, state transitions,
  retries) on Postgres 18.

## References

- [pg-boss](https://github.com/timgit/pg-boss) — PostgreSQL job queue (cron scheduling included)
- [@pg-boss/dashboard](https://www.npmjs.com/package/@pg-boss/dashboard) — web debugging UI
- [NestJS](https://docs.nestjs.com/) — DI / ConfigModule / Logger / [testing guide](https://docs.nestjs.com/fundamentals/testing)
- [NestJS Swagger](https://docs.nestjs.com/openapi/introduction) — manual decorator mode
- [Collection: dev-tools → Job Queue](../../docs/notes/collection/dev-tools.md) — pg-boss entry
- Prototype conventions: `AGENTS.md` → Prototype Convention
