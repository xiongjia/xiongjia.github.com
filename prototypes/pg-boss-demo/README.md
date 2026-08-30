# pg-boss-demo

NestJS 12 + [pg-boss](https://github.com/timgit/pg-boss) 12 job-queue prototype:
a small REST API to enqueue jobs, watch them flow through states, control
per-queue concurrency, trigger retries, and query job results — with Swagger
docs, unit and e2e tests. PostgreSQL 18 runs in Docker Compose (pg-boss 12 requires >= 13).

Status: `working` (validated end-to-end against Postgres 18 in Docker — jobs flow
created → active → completed/failed with retries; unit + e2e tests green).

## Features

- **pg-boss as a NestJS service** — `PgBossService` owns the `PgBoss` lifecycle
  (`start()` on module init, `stop()` on shutdown via `enableShutdownHooks`),
  reads config through `@nestjs/config` (env vars, no committed credentials),
  and listens to the `error` event with the Nest logger.
- **Three demo queues** (registered from a handler registry at startup):
  - `echo` — completes immediately, stores the message as the job result.
  - `flaky` — fails randomly (`failProbability` in the payload), demonstrating
    retries (`retryLimit` / `retryDelay` / `retryBackoff`).
  - `slow` — sleeps `delayMs` per job, demonstrating **concurrency control**
    (`localConcurrency` per queue: enqueue several, watch them run in batches).
- **Handlers are @Injectable() classes with real DI** — each handler is resolved
  through the Nest container (`ModuleRef.get`) and can inject any other service
  in its constructor (see `NotificationService` used by all three handlers).
- **REST API** to enqueue (`POST /jobs`), list by state (`GET /jobs?queue=&state=`),
  inspect a job and its result (`GET /jobs/:id`), cancel/retry
  (`POST /jobs/:id/cancel|retry`), and read live queue stats (`GET /queues`).
- **Swagger UI** with manually-decorated DTOs (`@ApiProperty`, ...), served at
  `/api/docs`.
- **Unit tests** for `PgBossService` following the official NestJS testing
  guide (`Test.createTestingModule` + `useValue` provider mocks — no DB, no
  module-level mocks). The PgBoss instance is constructor-injected so tests
  swap it for a mock; `unplugin-swc` makes Vitest emit decorator metadata
  (`emitDecoratorMetadata`), which NestJS DI needs.

## Quick start

```bash
pnpm install
pnpm db:start        # start Postgres 18 (docker compose) — run by the developer
cp .env.example .env.dev.local   # defaults match docker-compose.yml; edit if needed
pnpm start:dev       # or: pnpm build && pnpm start
```

- API: `http://localhost:3000`
- Swagger UI: `http://localhost:3000/api/docs`

Stop the database with `pnpm db:stop`; wipe it with `pnpm db:reset`
(`docker compose down -v` — removes the named volume and all data).

### Try it

```bash
# enqueue an echo job (completes immediately, result stored as `output`)
curl -X POST localhost:3000/jobs -H 'content-type: application/json' \
  -d '{"type":"echo","payload":{"message":"hello"},"options":{"priority":5}}'

# watch states flow: created → active → completed
curl 'localhost:3000/jobs?queue=echo&state=completed'
```

#### slow — concurrency control

`slow` sleeps `delayMs` (default 2000 ms) before completing. Enqueue several
at once: the queue runs at most `localConcurrency` (default 3) in parallel.

```bash
# enqueue 6 two-second jobs
for i in 1 2 3 4 5 6; do
  curl -s -X POST localhost:3000/jobs -H 'content-type: application/json' \
    -d '{"type":"slow","payload":{"delayMs":2000}}' > /dev/null
done

# activeCount stays at localConcurrency (3) → queuedCount drains in batches
curl -s localhost:3000/queues | python3 -m json.tool
```

Watch the Nest log for each completion:
`[NotificationService] [slow] job <id>: slept 2000ms`.

#### flaky — retries

`flaky` fails randomly with `failProbability` (default 0.5) by throwing from
the handler, then pg-boss retries it up to `retryLimit` (default 2) with
`retryDelay` (default 5 s) + `retryBackoff`.

```bash
# 100% failure → retries exhaust → job ends failed
curl -X POST localhost:3000/jobs -H 'content-type: application/json' \
  -d '{"type":"flaky","payload":{"failProbability":1}}'

# 0% failure → succeeds on the first attempt
curl -X POST localhost:3000/jobs -H 'content-type: application/json' \
  -d '{"type":"flaky","payload":{"failProbability":0}}'
```

Observe the state transitions (created → retry → active → failed/completed):

```bash
curl 'localhost:3000/jobs?queue=flaky'                 # all states
curl 'localhost:3000/jobs?queue=flaky&state=failed'    # only failed
curl localhost:3000/jobs/<id>                          # retryCount / retryLimit / timestamps
```

> Tip: `pnpm dashboard` (`http://localhost:3001`) shows all queues, jobs and
> states in a UI, handy while poking at retries and concurrency.

## Tests

```bash
pnpm test        # unit tests (Vitest + NestJS Test.createTestingModule, pg-boss mocked, no DB)
pnpm test:e2e    # end-to-end against the real Postgres (docker compose must be up)
```

- **Unit** (`src/pg-boss/pg-boss.service.spec.ts`, colocated with the service)
  covers lifecycle, queue registration, handler DI, delegations, SQL queries,
  config assembly and health.
- **E2E** (`test/jobs.e2e-spec.ts`) boots the real app on a random port,
  enqueues an echo job, polls it to `completed` and checks the result — plus
  `/health` and an unknown-queue-type 400. It deletes **only the jobs it
  created** afterwards (`PgBossService.deleteJob`), so anything you enqueued
  manually is left untouched.

## pg-boss Dashboard (debugging UI)

[@pg-boss/dashboard](https://www.npmjs.com/package/@pg-boss/dashboard) is a
web UI for browsing queues, inspecting/acting on jobs and reviewing warnings.
It is wired up as a dev tool: `pnpm dashboard` reads the same `DB_*` /
`PGBOSS_SCHEMA` values from `.env.dev.local` as the app, builds the
`DATABASE_URL`, and serves the dashboard on `http://localhost:3001`
(override with `DASHBOARD_PORT=3100 pnpm dashboard`).

```bash
pnpm dashboard    # requires the pg-boss schema: start the app once first
```

Prerequisite: the dashboard connects to the same Postgres, so the pg-boss
schema must exist (the app creates it on `start()` — run the app briefly, or
keep `pnpm start:dev` running alongside). The dashboard itself does not need
the Nest app to be up once the schema exists.

Optional HTTP basic auth: `PGBOSS_DASHBOARD_AUTH_USERNAME` /
`PGBOSS_DASHBOARD_AUTH_PASSWORD`.

## REST API

| Method | Path                         | Description                                                                                                                             |
| ------ | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/jobs`                      | Enqueue `{ type, payload?, options? }` → `201 { id }` (or `{ id: null, reason: 'deduplicated' }`)                                       |
| GET    | `/jobs?queue=&state=&limit=` | List jobs of a queue (`queue` **required**), optionally filtered by state (`created`/`retry`/`active`/`completed`/`cancelled`/`failed`) |
| GET    | `/jobs/:id`                  | Job detail: state, payload, result (`output`), retry count/limit, timestamps                                                            |
| POST   | `/jobs/:id/cancel`           | Cancel an unfinished job                                                                                                                |
| POST   | `/jobs/:id/retry`            | Re-queue a failed job for another attempt                                                                                               |
| GET    | `/queues`                    | Live stats per queue (v12 `getQueueStats`: deferred/queued/ready/active/failed/total)                                                   |
| GET    | `/health`                    | DB connectivity + pg-boss schema state (`installed` / `schemaVersion`)                                                                  |

The full OpenAPI spec (models, params, responses) is rendered in Swagger UI.

## pg-boss 12 notes (verified against 12.28.1 `dist/index.d.ts`)

- **Pure ESM, named exports** — `import { PgBoss } from 'pg-boss'` (no default
  export; the official README uses `const { PgBoss } = require('pg-boss')`).
  Node ≥ 22.12 required.
- **`send()` returns `string | null`** — `null` means the job was not enqueued
  (e.g. a singleton dedup); the API maps that to a 200 with `reason`.
- **Result query semantics** — completed jobs are kept for
  `deleteAfterSeconds` (default 7 days, `0` = keep forever). Set it on the
  queue (or per send) or the "query result" API finds nothing.
  `expireInSeconds` (default 900 s) is the active-job timeout: a crashed
  worker's job is retried after it. `retentionSeconds` (default 14 days) is
  how long created/retry jobs survive unconsumed — don't confuse the two.
- **Retries** — `retryLimit` (default 2), `retryDelay` (s), and v12
  `retryBackoff` is a **boolean** (exponential backoff on top of `retryDelay`),
  plus `retryDelayMax`. Throwing from a worker fails the batch and triggers
  the retry policy.
- **`findJobs()` has no state filter** — this prototype queries
  `pgboss.job` directly via `boss.getDb().executeSql` for state-filtered
  lists (column names are snake_case: `retry_count`, `output`, ...).
  `getJobById` is deprecated; `getQueueSize` is replaced by `getQueueStats`
  (which requires a queue name and returns per-queue counts).
- **Workers** — `work(queue, options, handler)`; the handler receives a
  **batch** of jobs. `batchSize` defaults to 1; per-node parallelism is
  `localConcurrency` (v12; the old `concurrency` option is gone).
- **Schema** is auto-created by `start()` (pg-boss runs its own migrations
  into the `pgboss` schema). No manual init script needed; the raw SQL can
  be exported via `getConstructionPlans()`/`getMigrationPlans()` if you ever
  need to pre-provision it.

## Project layout

```
pg-boss-demo/
├── .env.example            # env template (credentials never committed)
├── .gitignore              # node_modules, dist, .env*, logs, ...
├── docker-compose.yml      # Postgres 18 + named volume + healthcheck
├── package.json            # scripts: build / typecheck / test / db:*
├── pnpm-workspace.yaml     # pnpm 11 allowBuilds
├── tsconfig.json           # strict, nodenext, emitDecoratorMetadata
├── tsconfig.build.json     # build only src/ (no tests)
├── vitest.config.ts        # unplugin-swc (decorator metadata), unit tests
├── vitest.e2e.config.ts    # e2e config (test/**, longer timeouts)
├── nest-cli.json
├── scripts/
│   └── dashboard.mjs      # `pnpm dashboard` — reads .env.dev.local, serves :3001
├── src/
│   ├── main.ts             # NestFactory + enableShutdownHooks + Swagger
│   ├── app.module.ts       # ConfigModule (global) + feature modules
│   ├── pg-boss/
│   │   ├── pg-boss.module.ts      # @Global, exports PgBossService + handler providers
│   │   ├── pg-boss.service.ts     # lifecycle + typed delegations + SQL queries
│   │   ├── pg-boss.constants.ts   # QUEUES / QueueName / isRegisteredQueue
│   │   ├── pg-boss.types.ts       # JobState, config, row mapping (no any/!)
│   │   ├── pg-boss.config.ts      # buildPgBossConfig / buildConnectionString (shared)
│   │   ├── pg-boss.service.spec.ts # NestJS-style unit tests, colocated
│   │   ├── notification.service.ts # demo cross-service dependency for handlers
│   │   └── handlers/              # handler registry + EchoJob/FlakyJob/SlowJob
│   ├── jobs/               # REST: dto.ts, jobs.service.ts, jobs.controller.ts
│   ├── queues/             # REST: queues.controller.ts (GET /queues)
│   └── health/             # REST: health.controller.ts (GET /health)
└── test/
    └── jobs.e2e-spec.ts    # e2e (real Postgres): enqueue → poll → assert → cleanup
```

## Debugging with VS Code

Configurations for all prototypes live in the **repo-root** `.vscode/launch.json`
(alongside the ones for r2-client, ali-oss-client, ...). `.vscode/` is
**gitignored** (global `~/.gitignore_global`), so the file is not committed — on
a fresh clone, add the two entries below to `.vscode/launch.json` (the
`pg-boss-demo: build (tsc)` task referenced as pre-launch already exists in
`.vscode/tasks.json`):

```jsonc
{
  "name": "Launch pg-boss-demo (compiled)",
  "type": "node",
  "request": "launch",
  "cwd": "${workspaceFolder}/prototypes/pg-boss-demo",
  "program": "${workspaceFolder}/prototypes/pg-boss-demo/dist/main.js",
  "preLaunchTask": "pg-boss-demo: build (tsc)",
  "sourceMaps": true,
  "outFiles": ["${workspaceFolder}/prototypes/pg-boss-demo/dist/**/*.js"],
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen"
},
{
  "name": "Attach pg-boss-demo (nest start --debug)",
  "type": "node",
  "request": "attach",
  "port": 9229,
  "restart": true,
  "sourceMaps": true,
  "outFiles": ["${workspaceFolder}/prototypes/pg-boss-demo/dist/**/*.js"]
}
```

Two ways to debug (the app needs Postgres up first: `pnpm db:start`):

1. **Launch (compiled)** — pick **Launch pg-boss-demo (compiled)** and press F5.
   It builds first (pre-launch task), then runs `dist/main.js`; source maps map
   breakpoints back to the `.ts` sources.
2. **Attach** — run `pnpm start:debug` in a terminal (spawns the node
   inspector on port 9229), then pick **Attach pg-boss-demo (nest start
   --debug)**. `restart: true` re-attaches on process restarts, so watch-mode
   edits keep the debugger attached.

Either way, `.env.dev.local` is read from the prototype directory (the launch
config sets `cwd` there), so the app boots with your local config.

## Notes

- **Docker is developer-run**: starting/stopping the Postgres container
  (`pnpm db:start` / `db:stop` / `db:reset`) and pulling the image is up to
  you; this project only provides the compose file and scripts.
- **No `any`, no `!` assertions** anywhere in `src/` (project convention).
- Not part of the repo's CI — prototypes are excluded by design
  (`AGENTS.md` → Prototype Convention); verify locally with
  `pnpm typecheck` / `pnpm build` / `pnpm test`.
- This prototype intentionally does **not** become a research topic; the
  learning notes live in this README.
