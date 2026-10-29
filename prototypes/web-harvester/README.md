# web-harvester

TypeScript / NestJS prototype of a browser-driven harvester. Two halves:

- **A flow engine**: a scraping script is a `.jsonc` file (`flows/*.jsonc`) with
  typed input, ordered steps and an output map; the host validates it, runs it on
  a real browser, and returns JSON through a submit/poll API. Swapping a script is
  editing a file, not rebuilding the host.
- **Xiaohongshu operations on top of it**: the following list
  (`flows/xhs-following.jsonc`), the login QR (`flows/xhs-login-qr.jsonc`) and the
  session proof (`flows/xhs-login-check.jsonc`) are flows; the host keeps the HTTP
  contract — a PNG body, a 0600 cookie jar, the 60s verification cache.

Engine-agnostic: **Camoufox** (patched Firefox) is the default, **patchright**
(installed Chrome) is the zero-download fallback. Both run **in-process** — no
separate engine service. No Python is written here.

Status: `working` — the demo flow and the profile/runs layer are verified against
the live host; Xiaohongshu login + following were verified on a real account.
Moving XHS onto the DSL is the next milestone (see the roadmap).

## Quick start

```bash
pnpm install
cp .env.example .env      # optional; defaults work
pnpm dev                  # http://127.0.0.1:8765
```

Engines: `HARVEST_BROWSER=camoufox` (default) needs its Firefox build once.
There is **no Homebrew package** — `brew search camoufox` returns nothing, and
`brew install --cask firefox` is stock Firefox, not Camoufox. Pick one:

```bash
# macOS dev — fetch it yourself, resumable, mirror-aware
pnpm camoufox:download                                   # 1.3 GB, 8 parallel chunks
CONCURRENCY=16 CHUNK_MB=8 pnpm camoufox:download         # tune if the mirror allows
CAMOUFOX_MIRROR=https://gh-proxy.com/ pnpm camoufox:download

# already have the zip (fast network / another machine)?
CAMOUFOX_ZIP=~/Downloads/camoufox-156.0.1-beta.36-mac.arm64.zip pnpm camoufox:fetch

# no download at all — installed Chrome
HARVEST_BROWSER=patchright pnpm dev
```

Docker fetches it at **build** time, never at run time:

```bash
docker build -t web-harvester .                                   # patchright only
docker build --target camoufox \
  --build-arg CAMOUFOX_MIRROR=https://ghfast.top/ \
  -t web-harvester:camoufox .                                     # bakes the build in
```

Measured here: one connection is capped near 1.3 MB/s, `github.com` release
downloads are dropped outright, and chunks resume if the link dies — so expect
~15–25 min on this network, minutes on a good one. Without a build the server
answers `503` with the command to run.

| Command                                  | What it does                                      |
| ---------------------------------------- | ------------------------------------------------- |
| `pnpm dev` / `pnpm build` + `pnpm start` | watch mode / compile + run                        |
| `pnpm test`                              | Vitest unit tests (no browser)                    |
| `pnpm lint` / `pnpm format`              | ESLint 10 / Prettier (`:fix`, `--write`)          |
| `pnpm check`                             | typecheck + lint + format:check + test — the gate |
| `pnpm flow:schema`                       | rebuild + regenerate `flows/flow.schema.json`     |

## Routes

**Demo** (offline self-check):

| Route                         | Does                                                        |
| ----------------------------- | ----------------------------------------------------------- |
| `GET /api/v1/demo`            | Self-check page (inline HTML, zero network)                 |
| `GET /api/v1/demo/visit`      | Opens it: DOM read, click, delayed wait, screenshot, timing |
| `GET /api/v1/demo/screenshot` | Same visit, replies `image/png`                             |

**Flows and runs** (the flow engine):

| Route                                  | Does                                                         |
| -------------------------------------- | ------------------------------------------------------------ |
| `GET /api/v1/flows`                    | Every flow with `kind` and its `includes` edges              |
| `GET /api/v1/flows/schema`             | JSON Schema of the DSL (same document as the file)           |
| `POST /api/v1/flows/:name/runs`        | Submit a run; `?wait=<ms>` bounds the wait (max 60s)         |
| `POST /api/v1/flows/:name/run`         | `sync: true` flows only — result in one call, `?artifact=`   |
| `GET /api/v1/runs`                     | Recent runs (`?state=running,queued`, `?profile=`, `?flow=`) |
| `GET /api/v1/runs/:id`                 | One run: state, input, error, `meta.steps`                   |
| `GET /api/v1/runs/:id/output`          | The flow's output JSON                                       |
| `GET /api/v1/runs/:id/artifacts`       | Names of the run's artifacts                                 |
| `GET /api/v1/runs/:id/artifacts/:name` | One artifact (`visit.png`, `qr.png`, `failure.png`)          |
| `GET /api/v1/runs/:id/events`          | Server-sent events: state updates until it is terminal       |
| `POST /api/v1/runs/:id/cancel`         | Cancel (queued at once, running before its next step)        |

**Profiles** (one browser identity each):

| Route                              | Does                                                    |
| ---------------------------------- | ------------------------------------------------------- |
| `GET /api/v1/profiles`             | Profiles on disk — never the preset                     |
| `PATCH /api/v1/profiles/:name`     | Update locale/timezone/viewport/proxy/preset            |
| `DELETE /api/v1/profiles/:name`    | Delete one and its browser dir (the default is refused) |
| `GET /api/v1/profiles/:name/queue` | What it is running and what waits behind it             |

**Xiaohongshu** (thin host layer over the xhs flows):

| Route                          | Does                                                            |
| ------------------------------ | --------------------------------------------------------------- |
| `GET /api/v1/xhs/login/qrcode` | Login QR as `image/png`, produced by `flows/xhs-login-qr.jsonc` |
| `GET /api/v1/xhs/login/status` | `loggedIn` / `verified` / `blocked` / `account`, 60s cache      |
| `DELETE /api/v1/xhs/login`     | Clear the session (cookies + jar)                               |

Swagger UI: `GET /api/docs` (JSON at `/api/docs-json`). Feature routes are versioned
under `/api/v1`; Swagger is not.

## Profiles

A profile is one browser identity: its own browser directory (cookies,
localStorage), locale, timezone, viewport, optional proxy and a **frozen** Camoufox
preset — so the same account keeps the same fingerprint across restarts.

```
.cache/profiles/<name>/profile.json   # engine, os, locale, timezone, viewport, proxy, preset
.cache/profiles/<name>/browser/       # persistent browser profile — except for the default
.cache/profile/                       # ← the *default* profile's browser directory
```

Concretely, with the defaults (`HARVEST_PROFILES_DIR=.cache/profiles`,
`HARVEST_PROFILE=main`, `HARVEST_PROFILE_DIR=.cache/profile`):

| What                                | Where                                                                  |
| :---------------------------------- | :--------------------------------------------------------------------- |
| config of the default profile       | `.cache/profiles/main/profile.json`                                    |
| browser data of the default profile | `.cache/profile/` (111 MB here: cookies, cache, the logged-in session) |
| config of any other profile         | `.cache/profiles/<name>/profile.json`                                  |
| browser data of any other profile   | `.cache/profiles/<name>/browser/`                                      |
| runs (output, screenshots)          | `data/runs/<id>/`                                                      |

The asymmetry is deliberate: `main` keeps `HARVEST_PROFILE_DIR` so the existing
logged-in Xiaohongshu session survives the move to named profiles. Everything under
`.cache/` and `data/` is gitignored.

- Created on first use, from `HARVEST_*` defaults; the preset is drawn once and
  written back (a fresh preset per launch would look like a new device). Once the
  file exists it is the source of truth for `engine`/`os`/`locale`/`timezone`/
  `viewport`/`proxy` — edit it (or delete it) rather than changing the env.
- The **default** profile (`HARVEST_PROFILE`, `main`) keeps using
  `HARVEST_PROFILE_DIR` (`.cache/profile`), so an existing logged-in browser
  profile — the Xiaohongshu session — is not thrown away.
- `proxy` is validated as an `http(s)://` URL when the file is written, and
  `PATCH /api/v1/profiles/<name>` edits a profile without touching the rest.
- Editing a flow file under `HARVEST_FLOWS_DIR` takes effect on the next request:
  the loader re-reads a file whose mtime changed (no restart).
- `?profile=<name>` on a run selects one; `GET /api/v1/profiles` lists them and
  `GET /api/v1/profiles/<name>/queue` shows what that profile is running.
- Contexts are per profile and serial work is **per profile**, so two profiles may
  browse at once while one profile never runs two flows at the same time.
- The engine stays **in-process** on purpose (no separate engine process, no
  `HARVEST_ENGINE_WS`). That is why identity lives in each profile's browser
  directory instead of a `storageState` file: with a remote engine — which cannot
  serve a persistent context — the snapshot would be the only option.

## Flow DSL

A flow is one JSON file: typed `input`, ordered `steps`, an `output` map. It is
data, not code — swapping a scraping script means editing a file, not rebuilding.
Flow files are **`.jsonc`**, so they can explain themselves with `//` comments
(and trailing commas are accepted); `.json` still loads if you prefer no comments.
VS Code treats `.jsonc` as JSON-with-comments, so `"$schema"` validation keeps
working without "comments not permitted" errors.

| Action             | Does                                     | Needs                  |
| :----------------- | :--------------------------------------- | :--------------------- |
| `goto`             | open a URL                               | `url`                  |
| `wait`             | wait for a selector, or for `ms`         |                        |
| `click`            | click the first matching selector        | `selector`             |
| `fill`             | type into a field                        | `selector`, `value`    |
| `press`            | press a key                              | `key`                  |
| `text`             | read an element's text                   | `selector`, `as`       |
| `extract`          | collect rows as JSON objects             | `item`, `fields`, `as` |
| `scroll`           | scroll a container to its end            | `target`               |
| `screenshot`       | save a PNG under `artifacts/`            |                        |
| `assertNotBlocked` | fail as `blocked` on a risk-control page | `patterns`             |
| `include`          | insert another flow file's steps here    | `flow`                 |
| `if`               | branch on a selector                     | `selector`, `then`     |

Optional everywhere: `desc` (one sentence — the step's line in `meta.steps`),
`timeout` (ms, default 5000, max 120000), `retry: { attempts, delayMs }` and
`when` (a template; the step is skipped unless it is truthy, `!` negates).
`click`/`text`/`attribute` also take `optional: true`: a missing selector skips the
step and leaves the variable empty instead of failing the run. A step that runs out of time fails the
run with `error.code: "timeout"`, its `meta.steps` entry says `ok: false` with the
Playwright message and the elapsed `ms`, and no `output.json` is written
(`/output` answers `404`). The queue moves on to the next run.

Selectors are `string | string[]` (candidates tried in order); `{{input.x}}` /
`{{self}}` are substituted in URLs, values and selectors; `extract` fields accept
`:scope` for the row element itself, and `uniqueBy: ["name"]` drops repeated rows.
`if` branches on **visibility** by default (`state: "attached"` branches on mere
presence). `scroll` moves the **container's** own `scrollTop` (not the window)
until it stops moving (`until: "end"`) or stops growing (`until: "grow"`, for lazy
lists) — read the list afterwards with `extract`. A failed run writes
`artifacts/failure.png` before the page closes. `wait` really waits: one selector is handed to
Playwright, which waits for the element to appear _and_ to reach `state`; several
candidates are combined with `or(...)`, so the first one to show up wins.
`click`/`fill` behave the same for a single selector — with a candidate list the
pick is by existence, so `wait` first if the element shows up late.

**Two files, one scenario.** `flows/demo-visit.jsonc` is the entry point and
`flows/demo-read-page.jsonc` is the `kind: "fragment"` it includes — same page,
same variables, the caller keeps `input`/`output`. Flow files are JSONC, so the
edge is explained where it happens:

```jsonc
// flows/demo-visit.jsonc (excerpt)
"steps": [
  { "desc": "open the page", "action": "goto", "url": "{{input.url}}" },
  { "desc": "click the button", "action": "click", "selector": ["#bump", "#nope"] },

  // The reading steps live in flows/demo-read-page.jsonc. `include` splices them
  // in here: same page, same variables; this flow keeps `output` below.
  { "desc": "read the page", "action": "include", "flow": "demo-read-page" }
]
```

```jsonc
// flows/demo-read-page.jsonc (excerpt)
{
  "name": "demo-read-page",
  "kind": "fragment", // includable, not runnable on its own
  "steps": [
    { "action": "text", "selector": "#status", "as": "clickResult" },
    {
      "action": "extract",
      "item": "body p",
      "fields": { "text": ":scope" },
      "as": "paragraphs",
    },
  ],
}
```

`GET /api/v1/flows` answers the same relation without grepping:

```json
{
  "flows": [
    { "name": "demo-read-page", "kind": "fragment", "includes": [] },
    { "name": "demo-visit", "kind": "flow", "includes": ["demo-read-page"] }
  ]
}
```

A fragment may not declare `input`/`output` (a load-time error) and cannot be run
directly (`400`); `include` may nest, with cycles and depth > 5 refused. The run
log shows the splice as `4.include [demo-read-page]` followed by `4.1.text`, …

**Pacing is the flow's own business.** A flow may declare a minimum gap between its
runs, and `scope` lets several flows share one budget — all XHS flows use
`{"throttle": {"scope": "xhs", "minIntervalMs": 20000}}`, so a burst of API calls
(or a careless script) cannot look like a bot. Flows without `throttle` — the demo,
anything else — are never slowed down. The wait is recorded as `meta.throttleMs`.

**Sync flows.** A flow marked `"sync": true` (the two short login flows) can skip
the submit/poll dance entirely:

```bash
# JSON result
curl -s -X POST localhost:8765/api/v1/flows/xhs-login-check/run -d '{}' | jq '.output'
# …or the artifact itself, in the same call
curl -s -X POST 'localhost:8765/api/v1/flows/xhs-login-qr/run?artifact=qr' -o qr.png
```

Scraping flows stay async on purpose: a slow site must not turn into a held HTTP
connection. Asking for a non-sync flow here is a `400`.

**Submit, then poll:**

```bash
curl -s -X POST 'localhost:8765/api/v1/flows/demo-visit/runs?wait=15000' \
  -H 'content-type: application/json' -d '{}' | jq '{state, meta}'
```

`profile` and `input` are both optional — no body at all means "run this flow with
its own defaults", and the profile falls back to `HARVEST_PROFILE` (`main`; ask
`GET /api/v1/flows` what the default is).

Without `?wait=` (capped at 60s) the answer is `202` + `pollUrl`. A run writes
`data/runs/<id>/run.json` (state, input, error, and `meta.steps` — one entry per
step with `{ step, action, desc, ok, ms, error? }`, so "did the wait really wait"
is answerable), `output.json` and `artifacts/`; one queue per profile,
`HARVEST_QUEUE_DEPTH` deep.

Flows are validated at load — a broken one is a `400`, and
`flows/flow.schema.json` gives editors completion and hover. That file is
generated from `src/flow/schema.ts` by `pnpm flow:schema` (do not hand-edit; a test
fails when it is stale). `flows/` ships with the host, `HARVEST_FLOWS_DIR` shadows
a built-in name.

Xiaohongshu endpoints are still hand-written code — moving them onto the DSL is
the next milestone, not part of this one.

## How to test

All commands from `prototypes/web-harvester/`.

1. **Gate, no server**: `pnpm check` → `ESLint: No issues found`, `All matched
files use Prettier code style!`, `Test Files 18 passed / Tests 182 passed`.
2. **Start**: `pnpm dev` → logs `listening on http://127.0.0.1:8765`,
   `self-check page: .../api/v1/demo`, `swagger: .../api/docs`.
3. **Static page**: open <http://127.0.0.1:8765/api/v1/demo> — button flips
   `idle` → `clicked`; `delayed-ready` appears after ~1s.
4. **Browser check**: `curl -s localhost:8765/api/v1/demo/visit | jq` → expect
   `delayedText: "delayed-ready"`, `clickResult: "clicked"`, `screenshotPath`,
   `elapsedMs` (~1.5–2.5s cold, much smaller when repeated ⇒ context reused).
5. **Screenshot**: `curl -s localhost:8765/api/v1/demo/screenshot -o shot.png`
   → `file shot.png` says `PNG image data, 1280 x 800`; open it and eyeball the
   heading, blue SVG box and `delayed-ready`.
6. **Watch the browser work**: `pnpm dev:headed` (or
   `HARVEST_HEADLESS=false HARVEST_SLOWMO=250 pnpm dev`)
   opens a real window and slows every action down ~250 ms, so navigation, clicks
   and scrolling are visible (`HARVEST_HEADLESS=virtual` does the same on an
   Xvfb display in containers). The same switch works for the flow runs — a
   `xhs-following` run then shows the profile page scrolling (mind the 20s
   throttle; do not hammer the real site). Compare UAs:
   `curl -s localhost:8765/api/v1/demo/visit | grep -o 'Chrome/[0-9.]*'` —
   headless Chromium reports `HeadlessChrome/156`, headed reports `Chrome/156`
   (Camoufox reports a normal Firefox UA either way).
7. **Swagger**: <http://127.0.0.1:8765/api/docs> lists the demo, flow, run,
   profile and XHS routes; "Try it out" works.
8. **Watch mode**: edit a string in `src/demo/demo.page.ts` — server restarts
   and `/api/v1/demo/visit` shows it (revert after).
9. **Flow run** (local demo, no external traffic): `curl -s -X POST 'localhost:8765/api/v1/flows/demo-visit/runs?wait=15000' -H 'content-type: application/json' -d '{}' | jq '.state, .meta.steps'`
   → `succeeded` and one `meta.steps` entry per step (with `desc`, `ok`, `ms`);
   `GET /api/v1/runs/<id>/output` is the flow's JSON, `/artifacts` lists
   `visit.png`. Drop `?wait=` for the async path: `202` + `pollUrl`,
   `GET /api/v1/runs?state=queued,running`, `POST /api/v1/runs/<id>/cancel`, and
   `GET /api/v1/runs/<id>/events` for a server-sent-event stream of the state.
10. **Profiles**: `curl -s localhost:8765/api/v1/profiles | jq` lists them;
    `.../runs?profile=second` creates `.cache/profiles/second/{profile.json,browser/}`
    on first use; `PATCH /api/v1/profiles/second -d '{"locale":"en-US"}'` edits one;
    `DELETE /api/v1/profiles/second` removes it (the default one is refused).
11. **Isolation / validation**: `HARVEST_PORT=8800 pnpm dev` serves on the new port;
    `HARVEST_BROWSER=chrome pnpm dev` must fail with `Invalid environment`.
12. **Cleanup**: `rm -rf data .cache` (runs, screenshots + profiles, all gitignored).

| Symptom                                            | Likely cause                                                 |
| -------------------------------------------------- | ------------------------------------------------------------ |
| `EADDRINUSE`                                       | port taken → `HARVEST_PORT=8801 pnpm dev`                    |
| `waitForSelector timeout` / 500                    | wrong URL prefix, or stale profile → `rm -rf .cache/profile` |
| `Executable doesn't exist`                         | `HARVEST_CHANNEL=chrome` without Chrome → use `chromium`     |
| `Can't resolve dependencies of the BrowserService` | an injected provider became `import type` (breaks Nest DI)   |

## Xiaohongshu login

```bash
curl -s localhost:8765/api/v1/xhs/login/qrcode -o qr.png   # scan with the app
curl -s localhost:8765/api/v1/xhs/login/status             # loggedIn: true, then it stops asking
```

- `/qrcode` runs `flows/xhs-login-qr.jsonc` on every call (so the code is never
  stale) and streams its `qr.png` artifact; there is no long-lived login page.
- The session lives in the profile's browser directory; a 0600 jar
  (`HARVEST_XHS_COOKIES`, default `.cache/xhs-cookies.json`) is kept as a portable
  copy and seeded into a fresh context on the first `status` call.
- `status` returns two different things on purpose: `loggedIn` means "a
  `web_session` cookie exists", `verified` means "login-gated content was read
  back". The proof is the signed-in sidebar identity, which only renders for an
  authenticated user:

  ```json
  {
    "loggedIn": true,
    "verified": true,
    "blocked": false,
    "account": { "nickname": "阿甲", "userId": "5f8a1b2c" },
    "cookieNames": ["web_session", "a1"],
    "savedAt": "2026-10-27T16:40:00.000Z",
    "checkedAt": "2026-10-27T16:41:02.000Z"
  }
  ```

  `verified` is the result of `flows/xhs-login-check.jsonc` (which reads the
  sidebar); a stale cookie makes that run fail and yields `loggedIn: true,
verified: false, account: null` — the signal to scan again. A `blocked` failure
  becomes `blocked: true`. Verification is cached for 60 s, and only the nickname
  and public user id are returned (no personal fields).

- Xiaohongshu rejects some source IPs with its risk-control page
  (`安全限制` / `error_code=300012`). That is reported as `503` (or
  `blocked: true` in the status payload) instead of a useless screenshot —
  retry from another network.

### Following (关注)

`flows/xhs-following.jsonc` — the accounts the signed-in identity follows.

```bash
# one call, sync-free: submit and read the output
curl -s -X POST 'localhost:8765/api/v1/flows/xhs-following/runs?wait=60000' \
  -H 'content-type: application/json' -d '{}' | jq '{state, pollUrl}'
curl -s localhost:8765/api/v1/runs/<id>/output | jq '.rows | length'
```

It opens the profile (the signed-in one, or `{"input":{"profileId":"…"}}`), clicks
the `关注 N` counter, switches the panel to 关注 when it opened on 粉丝, scrolls
**the panel's own container** (`.xhs-following-scroll`, not the window) and reads
every `.xhs-relation-item` into `rows`:

```json
{
  "rows": [
    {
      "name": "财经不眠姐",
      "desc": "2篇笔记未看",
      "avatar": "https://sns-avatar-qc.xhscdn.com/avatar/…"
    },
    {
      "name": "NASA宇宙",
      "desc": "7件商品上新",
      "avatar": "https://sns-avatar-qc.xhscdn.com/avatar/…"
    }
  ]
}
```

Rows are plain divs (no profile link), so the scraped fields are nickname,
description and avatar — there is no user id in this panel. `uniqueBy: ["name",
"avatar"]` drops repeats. The former hand-written `GET /api/v1/xhs/following` and
its `/xhs/debug/following` counterpart are **retired**: the flow was verified
against them (same nicknames, same avatar URLs) and is now the only path.

## Roadmap (not implemented)

- **Retire the hand-written endpoints**: `GET /api/v1/xhs/following` (and its
  debug endpoint) still duplicate what `flows/xhs-following.jsonc` does; they stay
  as a comparison/rollback path until the flow has run for a while.
- **Read operations**: `GET /api/v1/xhs/feeds` (home feed), `/xhs/search?keyword=`,
  `/xhs/note?url=` (detail + comments, URL must keep `xsec_token`)
- **MCP server**: mount `/mcp` with tools mirroring the REST routes, so an AI
  client can call them directly
- **CLI**: `nest-commander` entry points (`harvest login / following / search`)
- **Publish**: `POST /api/v1/xhs/publish` with `dryRun` (write path, riskiest)
- **Stability**: request pacing / daily quota per profile, `/healthz`,
  run-level retry budgets
- **Ops**: build/verify the Docker image, compose + healthcheck

Explicitly **not** planned: an out-of-process engine (`launchServer` +
`HARVEST_ENGINE_WS`), remote flow distribution, JS flows, `eval` — see the profile
section for why identity lives in a browser directory instead.

## Migration notes

Recorded here on purpose: this prototype keeps no plan file under `internal/plans/`.

**XHS following → flow: done.** `flows/xhs-following.jsonc` drives the real site
(open → sidebar identity wait → risk-control check → own-profile `href` via
`attribute` → 关注 panel → tab switch inside `if` → `scroll` the panel container →
`extract` rows with `{ selector, attr }` for avatars). Verified A/B against the
hand-written endpoint on the same account: same nicknames, same avatar URLs. The
old `GET /api/v1/xhs/following` stays for comparison and rollback.

**XHS login → flow: done, host keeps the contract.** Login was the awkward one
because the QR must stay valid while a human scans (`/status` is polled between
calls). The run model does not stretch to a ten-minute run, so the page work was
cut into two short flows and the stateful parts stayed in the host:

| Endpoint                | Flow                                                         | Host keeps                                                             |
| :---------------------- | :----------------------------------------------------------- | :--------------------------------------------------------------------- |
| `GET /xhs/login/qrcode` | `xhs-login-qr` (one run per call → the code is always fresh) | serves `artifacts/qr.png` as the response body, `X-QR-Source` header   |
| `GET /xhs/login/status` | `xhs-login-check` (only on a cache miss)                     | session detection, 0600 jar, 60s verification cache, `blocked` mapping |
| `DELETE /xhs/login`     | —                                                            | `context.clearCookies()` + empty jar                                   |

A stale session and a risk-control page are distinguished by the run's failure
code (`timeout` vs `blocked`), not by a second page probe. With profiles the
browser directory is the real session store; the jar is now only a portable copy.

**Adding a primitive** is the cheap path when a site needs something the DSL lacks:
`schema.ts` (type + zod + `.describe()`), `step-runner.ts` (case), a spec case, then
`pnpm flow:schema`. `when`/`attribute`/`{ selector, attr }` were added exactly this
way for the XHS flow.

## Tests

`pnpm test` — no browser and no network: 15 specs, 171 cases.

- **Config / browser**: `config/env.spec.ts` (defaults, coercion, unknown engine),
  `browser/browser.service.spec.ts` (one launch per profile, per-profile
  directories, frozen preset/locale/proxy forwarded, serialisation per profile,
  relaunch after destroy).
- **Demo**: `demo/demo.page.spec.ts` (selectors, stays offline),
  `demo/demo.controller.spec.ts` (`/api/v1` self URL, loopback fallback, DOM
  mapping, PNG headers).
- **Flow DSL**: `flow/jsonc.spec.ts` (comments + trailing commas, `//` inside
  strings untouched), `flow/schema.spec.ts` (the shipped flows parse, strict
  fields, input coercion, generated schema in sync and every action documented),
  `flow/loader.spec.ts` (`.jsonc`/`.json` resolution, override shadowing, mtime
  re-read, include graph, broken flow stays local), `flow/step-runner.spec.ts`
  (candidate selectors, `wait`/`click` on elements that appear late,
  `text`/`extract` with `:scope` and `uniqueBy`, `scroll` end/grow, `if`
  visibility, `retry`, `include` fragments + cycles, timeout, cancel, failure
  screenshot).
- **Runs**: `run/store.spec.ts` (atomic writes, filters, prune keeps active runs,
  artifact paths), `run/queue.spec.ts` (serial per profile, parallel across, depth
  cap), `flows/flow.service.spec.ts` (demo flow end to end, async submit, fragment
  refusal, cancel while queued, queue full, profile creation, artifact serving),
  `flows/flows.controller.spec.ts` (202 vs 200, body guards, SSE stream, profile
  patch/delete, 429 mapping).
- **XHS**: `xhs/xhs.service.spec.ts` (QR artifact response, blocked → 503, session
  proof through the check flow, 60s cache, 0600 jar incl. corrupt/missing cases,
  logout) and `xhs/xhs.controller.spec.ts` (PNG headers, 503 mapping).

Engines are injected through the `BROWSER_BACKENDS` token, so tests fake the
browser instead of launching one. `vitest.config.mts` uses `unplugin-swc`
(NestJS DI needs `emitDecoratorMetadata`).

## Environment

| Key                                        | Default                   | Notes                                             |
| ------------------------------------------ | ------------------------- | ------------------------------------------------- |
| `HARVEST_HOST` / `HARVEST_PORT`            | `127.0.0.1` / `8765`      | no auth layer — keep it loopback                  |
| `HARVEST_BROWSER`                          | `camoufox`                | engine of a _new_ profile (`patchright` = Chrome) |
| `HARVEST_CHANNEL`                          | `chrome`                  | or `chromium` (bundled)                           |
| `HARVEST_HEADLESS`                         | `true`                    | UA caveat above                                   |
| `HARVEST_PROFILE_DIR` / `HARVEST_DATA_DIR` | `.cache/profile` / `data` | browser dir of the default profile / output       |
| `HARVEST_LOCALE` / `HARVEST_TIMEZONE`      | `zh-CN` / `Asia/Shanghai` | keep aligned with the account                     |
| `HARVEST_PROFILES_DIR`                     | `.cache/profiles`         | one directory per profile                         |
| `HARVEST_PROFILE`                          | `main`                    | default profile (created on first use)            |
| `HARVEST_PAGE_TIMEOUT`                     | `15000`                   | default page/locator timeout (ms)                 |
| `HARVEST_FLOWS_DIR`                        | `.cache/flows`            | writable flows; shadows a built-in name           |
| `HARVEST_RUNS_DIR`                         | `data/runs`               | one directory per run                             |
| `HARVEST_RUN_KEEP`                         | `50`                      | finished runs kept (failed keep 2x)               |
| `HARVEST_QUEUE_DEPTH`                      | `8`                       | queued runs per profile before `429`              |
| `HARVEST_OS`                               | host OS                   | fingerprint OS of a _new_ profile (fonts, UA)     |
| `HARVEST_SLOWMO`                           | `0`                       | ms between browser actions (watching a run)       |
| `HARVEST_VIEWPORT_WIDTH` / `_HEIGHT`       | `1280` / `800`            | viewport of a _new_ profile                       |
| `HARVEST_XHS_COOKIES`                      | `.cache/xhs-cookies.json` | portable copy of the session (0600)               |
| `HARVEST_XHS_SETTLE_MS`                    | `8000`                    | how long the login QR may take to render          |

## Layout

```
flows/                 # *.jsonc flows (demo + xhs) + generated flow.schema.json
src/
├── main.ts          # NestFactory + global prefix + Swagger + shutdown hooks
├── common/api.ts    # API_PREFIX ("api/v1") + SWAGGER_PATH + apiPath()
├── flow/            # DSL: schema (zod) + jsonc reader + loader + step-runner
├── flows/           # FlowModule: FlowService + controller (submit/poll/cancel)
├── run/             # RunStore (run.json/output.json) + RunQueue (per profile)
├── profile/         # ProfileRegistry: profiles/<name>/{profile.json,browser/}
├── xhs/             # XhsModule: XhsService (session + jar) + controller
├── config/env.ts    # zod-validated HARVEST_*
├── browser/         # BrowserModule (@Global) + BrowserService + backends/
└── demo/            # DemoModule + controller + inline page
```

`scripts/emit-flow-schema.mjs` writes `flows/flow.schema.json` from the compiled
zod schema (`pnpm flow:schema`).

## Notes

- `channel: "chrome"` avoids a browser download and looks like ordinary Chrome.
- Headless leaks `HeadlessChrome/156` in the UA; headed (or Xvfb) does not.
- **Chinese renders as boxes?** Camoufox draws a font list for the OS it claims.
  Until this was pinned, a macOS host advertised Windows fonts, so CJK text had
  no matching font and every page (and screenshot) looked garbled. A profile's
  `os` defaults to the host OS when it is created; change it only with a matching
  font setup, and keep `fonts-noto-cjk` in the container image.
- `addons.mozilla.org` answers 451 here, so Camoufox's automatic uBO download
  fails on first launch — `HARVEST_EXCLUDE_ADDONS=uBO` (default) skips it.
- Camoufox's Firefox build is a 1.3 GB GitHub asset with no Homebrew cask:
  `pnpm camoufox:download` (parallel + resumable) or `CAMOUFOX_ZIP=… pnpm
camoufox:fetch` for dev; the Docker `camoufox` target bakes it in. `patchright`
  is the zero-download engine.
- Unit tests never launch a browser; `.cache/` and `data/` are gitignored, and
  the repo's Python toolchain (`ruff`, `poe fmt`) ignores this directory.
