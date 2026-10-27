# web-harvester

TypeScript / NestJS prototype of a browser-driven harvester: a **demo
self-check** (offline page + a controller that drives a real browser at it) plus
Xiaohongshu **QR login** and the account's **following list**. Engine-agnostic:
**Camoufox** (patched Firefox) is the default, **patchright** (installed Chrome)
is the zero-download fallback. No Python is written here.

Status: `working` — verified on a real account (QR scan, session reuse, following
list collected). Development stops here; see the roadmap below.

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
| `pnpm test`                              | Vitest unit tests (19 cases, no browser)          |
| `pnpm lint` / `pnpm format`              | ESLint 10 / Prettier (`:fix`, `--write`)          |
| `pnpm check`                             | typecheck + lint + format:check + test — the gate |

## Routes

| Route                         | Does                                                        |
| ----------------------------- | ----------------------------------------------------------- |
| `GET /api/v1/demo`            | Self-check page (inline HTML, zero network)                 |
| `GET /api/v1/demo/visit`      | Opens it: DOM read, click, delayed wait, screenshot, timing |
| `GET /api/v1/demo/screenshot` | Same visit, replies `image/png`                             |
| `GET /api/docs`               | Swagger UI (`.json` via `/api/docs-json`)                   |

Feature routes are versioned under `/api/v1`; Swagger is not.

## How to test

All commands from `prototypes/web-harvester/`.

1. **Gate, no server**: `pnpm check` → `ESLint: No issues found`, `All matched
files use Prettier code style!`, `Test Files 4 passed / Tests 18 passed`.
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
   Xvfb display in containers). The same switch works for the Xiaohongshu
   endpoints — `curl .../xhs/following` then shows the profile page scrolling. Compare UAs:
   `curl -s localhost:8765/api/v1/demo/visit | grep -o 'Chrome/[0-9.]*'` —
   headless Chromium reports `HeadlessChrome/156`, headed reports `Chrome/156`
   (Camoufox reports a normal Firefox UA either way).
7. **Swagger**: <http://127.0.0.1:8765/api/docs> lists the three
   `/api/v1/demo*` routes; "Try it out" works.
8. **Watch mode**: edit a string in `src/demo/demo.page.ts` — server restarts
   and `/api/v1/demo/visit` shows it (revert after).
9. **Isolation / validation**: `HARVEST_PORT=8800 HARVEST_PROFILE_DIR=.cache/p2
pnpm dev` serves on the new port; `HARVEST_BROWSER=chrome pnpm dev` must fail
   with `Invalid environment`.
10. **Cleanup**: `rm -rf data .cache` (screenshots + profile, both gitignored).

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

- One long-lived page (`xhs-login`) holds the QR between calls; the session is
  detected by the `web_session` cookie, then written to
  `HARVEST_XHS_COOKIES` (default `.cache/xhs-cookies.json`, mode 0600).
- Saved sessions are injected on the first `status` call, so a restart does not
  need another scan.
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

  A stale or revoked cookie yields `loggedIn: true, verified: false,
account: null` — that is the signal to scan again. Verification is cached for
  60 s so polling does not open a page per call, and only the nickname and public
  user id are returned (no personal fields).

- Xiaohongshu rejects some source IPs with its risk-control page
  (`安全限制` / `error_code=300012`). That is reported as `503` (or
  `blocked: true` in the status payload) instead of a useless screenshot —
  retry from another network.

### Following (关注)

The accounts the signed-in account follows.

```bash
curl -s 'localhost:8765/api/v1/xhs/following?limit=200&scrolls=6' | jq '{count, outputPath, items}'
```

Opens the account's own profile, clicks the `关注 N` counter, waits for the
relation panel (`.xhs-relation-panel`), then scrolls **the panel's own container**
(`.xhs-following-scroll`, not the window) and reads every `.xhs-relation-item`.
Rows are plain divs — no profile link — so the scraped fields are the nickname,
the row description and the avatar; there is no user id in this panel. Output:

```json
{
  "profileId": "6807cfdf000000000a03c453",
  "count": 2,
  "items": [
    {
      "nickname": "财经不眠姐",
      "desc": "1篇笔记未看",
      "avatarUrl": "https://sns-avatar-qc.xhscdn.com/avatar/…"
    },
    {
      "nickname": "NASA宇宙",
      "desc": "8件商品上新",
      "avatarUrl": "https://sns-avatar-qc.xhscdn.com/avatar/…"
    }
  ],
  "triggerUsed": ".clickable:has-text('关注')",
  "rowsSeen": 2,
  "outputPath": "data/xhs-following-2026-10-27T17-33-11-132Z.jsonl",
  "elapsedMs": 9143
}
```

One JSON object per line, first line is a comment header
(`# profile=… count=… at=…`), duplicate ids and the account itself are dropped.

The response also carries `triggerUsed` (which selector opened the panel) and
`rowsSeen` (rows the DOM held). `count: 0` with `triggerUsed: null` means the
panel never opened — run the debug endpoint below and compare its
`selectorCounts`/`followCandidates` with `src/xhs/selectors.ts`.

```bash
curl -s 'localhost:8765/api/v1/xhs/debug/following' | jq '{
  url, profileId, clickedTab, tabMatches, selectorCounts,
  followCandidates, containers, screenshotPath
}'
```

## Roadmap (not implemented)

Kept short on purpose — the prototype stops at login + following list.

- **Read operations**: `GET /api/v1/xhs/feeds` (home feed), `/xhs/search?keyword=`,
  `/xhs/note?url=` (detail + comments, URL must keep `xsec_token`)
- **MCP server**: mount `/mcp` with tools mirroring the REST routes, so an AI
  client can call them directly
- **CLI**: `nest-commander` entry points (`harvest login / following / search`)
- **Publish**: `POST /api/v1/xhs/publish` with `dryRun` (write path, riskiest)
- **Stability**: proxy support (`HARVEST_PROXY`), request pacing/daily quota,
  `/healthz`, multi-profile (multi-account)
- **Ops**: build/verify the Docker image, compose + healthcheck

## Tests

`pnpm test` — seven specs, no browser and no network: `config/env.spec.ts`
(defaults, coercion, unknown engine), `demo/demo.page.spec.ts` (selectors,
stays offline), `browser/browser.service.spec.ts` (single launch, options
forwarded, serial pages, close on success/failure, screenshot path, relaunch on
destroy), `demo/demo.controller.spec.ts` (`/api/v1` self URL, loopback fallback,
DOM mapping, PNG headers), `xhs/cookie.store.spec.ts` (round-trip, 0600 mode,
corrupt/missing jar), `xhs/login.service.spec.ts` (QR selectors + viewport
fallback, risk-control detection, session save/seed/logout, login-gated proof,
stale-cookie and verify-cache cases),
`xhs/xhs.controller.spec.ts` (PNG headers, 503 mapping, status/logout,
following), `xhs/following.spec.ts` (row → item, dedupe, JSONL) and
`xhs/following.service.spec.ts` (collect, limit, panel-not-opened, explicit
profileId, no-session refusal).

Engines are injected through the `BROWSER_BACKENDS` token, so tests fake the
browser instead of launching one. `vitest.config.mts` uses `unplugin-swc`
(NestJS DI needs `emitDecoratorMetadata`).

## Environment

| Key                                        | Default                   | Notes                                    |
| ------------------------------------------ | ------------------------- | ---------------------------------------- |
| `HARVEST_HOST` / `HARVEST_PORT`            | `127.0.0.1` / `8765`      | no auth layer — keep it loopback         |
| `HARVEST_BROWSER`                          | `patchright`              | `camoufox` / `mock` reserved             |
| `HARVEST_CHANNEL`                          | `chrome`                  | or `chromium` (bundled)                  |
| `HARVEST_HEADLESS`                         | `true`                    | UA caveat above                          |
| `HARVEST_PROFILE_DIR` / `HARVEST_DATA_DIR` | `.cache/profile` / `data` | profile (fingerprint + cookies) / output |
| `HARVEST_LOCALE` / `HARVEST_TIMEZONE`      | `zh-CN` / `Asia/Shanghai` | keep aligned with the account            |

## Layout

```
src/
├── main.ts          # NestFactory + global prefix + Swagger + shutdown hooks
├── common/api.ts    # API_PREFIX ("api/v1") + SWAGGER_PATH + apiPath()
├── xhs/             # XhsModule: login + following + cookie store + selectors
├── config/env.ts    # zod-validated HARVEST_*
├── browser/         # BrowserModule (@Global) + BrowserService + backends/
└── demo/            # DemoModule + controller + inline page
```

## Notes

- `channel: "chrome"` avoids a browser download and looks like ordinary Chrome.
- Headless leaks `HeadlessChrome/156` in the UA; headed (or Xvfb) does not.
- **Chinese renders as boxes?** Camoufox draws a font list for the OS it claims.
  Until this was pinned, a macOS host advertised Windows fonts, so CJK text had
  no matching font and every page (and screenshot) looked garbled. `HARVEST_OS`
  now defaults to the host OS; override it only with a matching font setup, and
  keep `fonts-noto-cjk` in the container image.
- `addons.mozilla.org` answers 451 here, so Camoufox's automatic uBO download
  fails on first launch — `HARVEST_EXCLUDE_ADDONS=uBO` (default) skips it.
- Camoufox's Firefox build is a 1.3 GB GitHub asset with no Homebrew cask:
  `pnpm camoufox:download` (parallel + resumable) or `CAMOUFOX_ZIP=… pnpm
camoufox:fetch` for dev; the Docker `camoufox` target bakes it in. `patchright`
  is the zero-download engine.
- Unit tests never launch a browser; `.cache/` and `data/` are gitignored, and
  the repo's Python toolchain (`ruff`, `poe fmt`) ignores this directory.
