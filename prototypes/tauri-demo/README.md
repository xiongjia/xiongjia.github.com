# Tauri Demo

A learning prototype for **Tauri 2**: Rust collects live system metrics, sends
them to React over the Tauri IPC bridge, and the frontend renders them with
shadcn/ui charts.

The point is the wiring (`#[tauri::command]` → `invoke()` → typed payload →
chart), not the dashboard itself.

## Status

`working` — created 2026-10-07.

Verified locally:

- `pnpm build` (TypeScript 7 type check + Vite/Rolldown build)
- `pnpm lint` (oxlint with type-aware rules)
- `pnpm test` — 63 Vitest tests over 12 files (jsdom + Testing Library, charts included)
- `cd src-tauri && cargo test` (10 tests) and `cargo clippy --all-targets -- -D warnings`
- Desktop packaging was **not** run; try `pnpm tauri dev` yourself

## Stack

| Layer           | Choice                                     | Version                                  |
| --------------- | ------------------------------------------ | ---------------------------------------- |
| Shell           | Tauri                                      | 2.12 (`tauri` crate / `@tauri-apps/cli`) |
| Backend         | Rust + `sysinfo`                           | 1.97 / 0.39                              |
| Frontend        | React + Vite (Rolldown)                    | 19.3 / 8.3                               |
| Types           | TypeScript (Go implementation)             | 7.0.2                                    |
| Styling         | Tailwind CSS (CSS-first, v4)               | 4.3                                      |
| Components      | shadcn CLI (`radix-nova` preset)           | 4.21                                     |
| Charts          | Recharts, wrapped by `components/ui/chart` | 3.8                                      |
| Lint            | oxlint + `oxlint-tsgolint` (type-aware)    | 1.87 / 7.0                               |
| Package manager | pnpm                                       | 11                                       |

Scaffolded with the Rust CLI (`cargo create-tauri-app --template react-ts --manager pnpm`), so no Node-based generator was involved.

## What it shows

- **4 KPI cards** — CPU, memory, disk, uptime (with progress bars)
- **Line chart** — CPU + memory history, fed by a ring buffer on the Rust side
- **Per-core grid** — per-logical-core load
- **Bar chart** — top 8 processes by resident memory
- **Donut + list** — used space per mount point
- **Tabs, dark mode toggle, 2 s polling, last-updated timestamp**

## Layout

```
tauri-demo/
├── index.html              # Vite entry
├── package.json
├── components.json         # shadcn config
├── vite.config.ts          # React + Tailwind plugins, "@" alias, Vitest config
├── src/                    # React frontend
│   ├── App.tsx             # header, tabs, layout
│   ├── App.test.tsx        # dashboard smoke test
│   ├── index.css           # Tailwind v4 + shadcn theme variables
│   ├── hooks/use-system-stats.ts
│   ├── hooks/use-system-stats.test.tsx
│   ├── lib/ipc.ts          # typed invoke() wrappers + browser mock
│   ├── lib/format.ts
│   ├── lib/utils.ts        # generated shadcn `cn` re-export
│   ├── components/         # stat cards, cores grid, theme toggle, meter
│   ├── components/charts/  # line / bar / donut
│   ├── components/ui/      # shadcn-generated primitives (do not hand-edit)
│   └── test/               # fixtures, jsdom shims, Recharts selectors, colour/CSS helpers
└── src-tauri/              # Rust backend
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── capabilities/default.json
    └── src/
        ├── main.rs         # thin desktop entry point
        ├── lib.rs          # commands + builder
        └── metrics.rs      # sysinfo collector + ring buffer + tests
```

`src/` (web) next to `src-tauri/` (Rust) is the default Tauri layout from
`create-tauri-app` and the official *Project Structure* docs. The directory
name is not a hard requirement — the CLI finds the Rust project by looking for
`tauri.conf.json` — but keeping it means every tutorial and plugin example
still applies, so it was left alone.

## Rust side

`metrics.rs` owns a long-lived `MetricsState` (stored via `.manage(...)`):

- `System` and `Disks` handles are reused so CPU usage is computed from the
  delta between two refreshes (`sysinfo` needs ≥ 200 ms between samples; the
  frontend polls every 2 s)
- Disk readings go through a `DiskCache` with a 10 s TTL
  (`DISK_REFRESH_INTERVAL_MS`), because re-statting every mount costs about as
  much as the rest of a snapshot put together
- A bounded `VecDeque<HistoryPoint>` (capacity 60) backs the line chart
- Pure helpers (`percent`, `push_history`, `should_record`,
  `should_refresh_disks`, `top_processes`) are unit tested without a Tauri
  runtime

Two commands are exposed:

| Command           | Returns                                              |
| ----------------- | ---------------------------------------------------- |
| `system_snapshot` | fresh `Snapshot`, and appends a point to the history |
| `system_history`  | the current history buffer                           |

Both return `Result<T, String>`; the frontend surfaces failures in an alert
banner. Serialization uses `#[serde(rename_all = "camelCase")]` so the TS
interfaces in `src/lib/ipc.ts` mirror the Rust structs field for field.

## Usage

```bash
pnpm install

pnpm dev            # browser only: uses the built-in mock, no Rust needed
pnpm tauri dev      # real desktop window with real metrics
pnpm build          # tsc (type check) + vite build
pnpm lint           # oxlint --type-aware
pnpm test           # vitest run (jsdom + Testing Library)
pnpm test:watch     # vitest in watch mode

cd src-tauri
cargo test
cargo clippy --all-targets
```

`pnpm dev` shows a “Browser mock” badge; inside Tauri it reads
“Tauri / Rust”. That is how the same UI can be developed and tested without
opening a window.

### Mock data outside the desktop app

Every read goes through `src/lib/ipc.ts`, which branches on `isDesktopApp()`
(a thin wrapper around Tauri's `isTauri()`):

| Runtime                                            | `fetchSnapshot` / `fetchHistory`                         | Data                                          |
| -------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------- |
| Tauri window (`pnpm tauri dev`, packaged app)      | `invoke("system_snapshot")` / `invoke("system_history")` | real `sysinfo` readings from Rust             |
| Plain browser (`pnpm dev`, `pnpm preview`, Vitest) | `mockHostSnapshot()` / `mockHostHistory`                 | synthetic values, no Rust and no IPC involved |

The mock generates a sine-wave CPU and memory trace, 8 cores, two disks and six
fixed processes, and keeps its own 60-point history buffer that mirrors the Rust
ring buffer. Consequences worth remembering:

- Anything that runs in a browser (browser dev server, the Vitest suite) never
  touches the Tauri bridge — the Rust side is only covered by `cargo test` and by
  running `pnpm tauri dev`.
- The numbers are fabricated, so a screenshot from `pnpm dev` says nothing about
  what the real machine reported; the badge is what tells the two apart.
- The mock exposes six processes while the real command returns up to
  `TOP_PROCESS_COUNT` (8), so the browser version draws fewer bars.

## Tests

The frontend is covered by Vitest (jsdom environment, Testing Library), because
this workflow cannot read screenshots — assertions go against the rendered DOM
instead. 63 tests over 12 files:

| File                                               | Covers                                                                                                                                          |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/format.test.ts`                           | `formatBytes` / `formatPercent` / `formatUptime` / `formatClock`, including sub-byte, `NaN` and negative input                                  |
| `src/lib/ipc.test.ts`                              | browser mock shape, defensive copies, one history point per snapshot, 60-point cap                                                              |
| `src/hooks/use-system-stats.test.tsx`              | initial fetch, 2 s polling with fake timers, in-flight ticks skipped, request timeout + late result ignored, error messages, cleanup on unmount |
| `src/components/stat-cards.test.tsx`               | loading skeletons, one card per metric, progress-bar clamping, `role="progressbar"` values                                                      |
| `src/components/cores-grid.test.tsx`               | one row + one labelled meter per core, empty core list                                                                                          |
| `src/components/theme-toggle.test.tsx`             | dark class flip, stored preference, no write before the user chooses                                                                            |
| `src/components/charts/cpu-memory-line.test.tsx`   | one surface, two line curves with real SVG path geometry, history-window caption, empty history                                                 |
| `src/components/charts/top-processes-bar.test.tsx` | one bar per process, truncation, collision disambiguation, lone-surrogate safety, empty state                                                   |
| `src/components/charts/disk-usage-pie.test.tsx`    | one sector per disk, volume name / mount point / free space, unnamed volume fallback, duplicate mount points                                    |
| `src/App.test.tsx`                                 | dashboard smoke test: header, badge, cards fill in, chart paints                                                                                |

`src/test/setup.ts` shims the two things jsdom lacks: `ResizeObserver` (without
it Recharts' `ResponsiveContainer` measures 0×0 and no chart renders) and
`window.matchMedia` (used to pick the initial theme). `src/test/recharts.ts`
centralises the Recharts DOM selectors the chart tests depend on, so a Recharts
bump only has one file to check. The Vitest config lives in `vite.config.ts` so
the `@` alias has a single definition.

The real Rust side is covered by `cargo test` (10 tests) and the real
IPC path by running `pnpm tauri dev` — the Vitest suite exercises the browser
mock, not the Tauri bridge.

## Notes and gotchas

- **TypeScript 7 drops the JS compiler API.** `require("typescript")` now only
  exposes `{ version, versionMajorMinor }`; the AST APIs live under
  `typescript/unstable/*`. Practical consequence: `typescript-eslint` (peer
  `<6.1.0`) cannot be installed, which is why linting uses oxlint +
  `oxlint-tsgolint` (type-aware rules powered by typescript-go). `tsc`,
  `tsc --noEmit` and `tsc -b` behave normally. To go back to the JS
  implementation, pin `typescript@~6.0.3` and add typescript-eslint.
- **`baseUrl` is deprecated** in TS 6/7 and errors out; the `@/*` alias uses
  `paths` only.
- **shadcn pulls `recharts` 3.8** itself, so the older “shadcn charts need
  Recharts 2.x” concern does not apply to this version.
- **Recharts needs a `ResizeObserver` to draw anything in jsdom.** Without the
  shim in `src/test/setup.ts`, `ResponsiveContainer` measures 0×0 and every
  chart renders zero SVGs — with it, tests see real path geometry
  (`M5,178.33L400,15.83…`). The alternatives (passing explicit `width`/`height`
  instead of `ResponsiveContainer`) would mean testing something other than
  what ships.
- **The Vitest config lives in `vite.config.ts`.** A separate `vitest.config.ts`
  would take precedence and force the `@` alias to be declared twice; keeping
  one file means one source of truth (and `src/test/**` stays inside `tsc`'s
  `include`, so the shims are type-checked by `pnpm build`).
- **A wedged request cannot freeze the dashboard.** Each poll is abandoned if it
  does not answer within the request timeout (`max(10s, 2 × poll interval)`, so a
  longer interval can never time out by construction); the late result is
  ignored and the next tick retries, with the error shown in the banner until
  the following successful poll.
- **Sampling is throttled on the Rust side.** `system_snapshot` is a read with a
  side effect (it appends to the ring buffer), so samples arriving within
  `MIN_SAMPLE_SPACING_MS` (500 ms) of the previous one are dropped. That
  absorbs React StrictMode's double-mounted effect and several windows polling
  at once.
- **The template's opener plugin was removed.** `tauri-plugin-opener`, its
  `@tauri-apps/plugin-opener` npm package and the `opener:default` capability
  were unused — the app opens no external URLs — so the dependency and the
  permission grant are gone.
- **Disk usage is cached for 10 s.** `Disks::refresh` re-stats every mount; it
  measured ~10.6 ms per call on this laptop, about half of a `snapshot()` (~19.1
  ms), and is far slower for network mounts while free space barely changes.
  `metrics.rs` now keeps the last reading (`DiskCache` + `should_refresh_disks`,
  TTL `DISK_REFRESH_INTERVAL_MS`) so the 2 s poll costs ~8.0 ms instead —
  measured 20 snapshots: 382 ms before, 161 ms after.
- **The chart palette is theme-specific and contrast-guarded.** The shadcn
  preset ships one grayscale ramp for both themes, which left the CPU line at
  1.48:1 on the white background and the process bars at 2.53:1 on the dark one.
  `src/index.css` now has separate ramps (light 0.55→0.31, dark 0.87→0.55
  lightness) and `src/index-css.test.ts` fails if any `--chart-N` drops below
  3:1 (WCAG 1.4.11 for meaningful graphics) on `--background` or `--card`, or if
  a chart component hard-codes a colour instead of using a token. The palette
  stays greyscale (the preset's neutral look), which is a deliberate trade-off:
  readable everywhere, but a five-slice donut is five shades of grey — a hued
  palette would be the next step if that bothers you.
- **The CSP is set, not `null`, and was verified against the production build.**
  `tauri.conf.json` ships a production policy (self-only scripts, inline styles
  for Recharts' injected `<style>`, IPC connect-src) plus a looser `devCsp` that
  also allows the Vite dev server and its HMR websocket. Serving `dist/` with the
  production policy and loading it in headless Chrome renders the full dashboard
  (cards, two line curves, fonts, stylesheets) with **zero
  `securitypolicyviolation` events**. The `ipc:` / `asset:` entries and `devCsp`
  can only be exercised inside a real Tauri window; if `pnpm tauri dev` shows a
  blank window or CSP console errors, that is the first thing to look at. The dev
  policy was checked the same way (Vite dev server + a probe that injects the
  `devCsp` as a meta tag) and renders with zero violations **without**
  `'unsafe-eval'` — it only needs `'unsafe-inline'` for the React Refresh
  preamble Vite inlines.
- **Radix Tabs activates on `mousedown`, not `click`**: a bare
  `element.click()` silently does nothing (relevant if you drive the tabs from
  a test; `user-event` dispatches the full pointer/mouse sequence).
- **Bundle size is ~675 kB** (205 kB gzipped); Recharts is most of it. No code
  splitting — fine for a prototype, would be the first thing to fix for real.
- **Packaging was skipped here.** `pnpm tauri build` produced a 4.2 MB `.app`
  successfully, but the `.dmg` step failed in a non-GUI shell
  (`bundle_dmg.sh` drives Finder). Run `pnpm tauri build --bundles app` for a
  reliable bundle, or `--bundles dmg` from a logged-in desktop session.
- **APFS caveat**: on macOS `/` and `/System/Volumes/Data` are the same
  container and report the same numbers, so the disk donut lists them twice.
  That is what the OS reports, not a bug.
- `src/components/ui/**` and `src/lib/utils.ts` are generated by the shadcn CLI
  and excluded from oxlint; re-generate them with
  `pnpm dlx shadcn@latest add <name>` instead of editing by hand. Our own
  components import `cn` straight from the `cn` package, so `utils.ts` is only
  there for components added later.
- **Icons**: only the five files referenced by `tauri.conf.json:bundle.icon`
  are kept, plus `icon.png` as the source for `pnpm tauri icon <file>`. The
  template's unused Microsoft-Store sizes (`Square*.png`, `StoreLogo.png`) were
  deleted.
- **`src-tauri/gen/schemas/` is generated, not tracked.** `tauri-build`
  regenerates it (ACL manifest + capability JSON schemas) on every
  `dev`/`build`, and `src-tauri/.gitignore` ignores it. A fresh clone has no
  schema file until the first build, so the `$schema` reference in
  `capabilities/default.json` may warn in the IDE until you run
  `pnpm tauri dev` once. Mobile targets would be the opposite case:
  `gen/android/` and `gen/apple/` are editable project sources and do belong in
  git (only `gen/schemas` is ignored).
- **IDE settings are shared, not per-prototype.** This directory has no
  `.vscode/`: `rust-analyzer.linkedProjects` (including
  `prototypes/tauri-demo/src-tauri/Cargo.toml`) and the Tauri / rust-analyzer
  extension recommendations live in the repo root
  [`.vscode/`](../../.vscode/). Add new Rust prototypes to that list.
