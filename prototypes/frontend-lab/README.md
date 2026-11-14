# Frontend Lab

An experimental lab for frontend techniques, driven by real UI scenarios. Not a component
library, and not a lighter Storybook: every experiment must run, expose its source and carry an MDX
write-up.

Core principle: **MDX explains, React components interact, single-library experiments prove a
technique, composed demos prove a real scenario.**

- Created: 2026-11-02
- Status: `experimental` (roadmap complete at B17: shell, content loop, demo system, quality gates,
  theme, style presets, i18n, the single-library experiments B8–B12, the composed scenarios B13–B16
  and the verification stack B17)
- Plan of record: the roadmap below (batches B1–B17). The discussion draft lives outside the repo.

## Quick start

```bash
pnpm install        # uses the China npm mirror configured in .npmrc
pnpm dev            # http://localhost:5173
pnpm generate       # regenerate src/generated/* by hand (dev/build do it too)
pnpm test           # node:test unit tests for the checks
pnpm content:check  # frontmatter schema, content/demo rules, locale list
pnpm style:check    # palette / tokens / style presets / preset list agreement
pnpm check          # generate + typecheck + content/style checks + eslint + prettier + tests
pnpm build          # generate + checks + tsc --noEmit + vite build (dist in apps/lab/dist)
pnpm preview        # serve the production build
pnpm bundle:report  # gzip every built asset, attribute chunks, check the size budgets
pnpm e2e            # Playwright: critical paths + the axe matrix (needs a build)
pnpm verify         # build + bundle:report + e2e
```

Requires Node >= 22.12 (`.nvmrc` pins 24) and pnpm 11.

## What works today (B17)

- pnpm workspace with one app (`apps/lab`) and seven shared packages: `ui`, `editor`, `panels`,
  `state`, `workspace`, `charts` and `command-palette`
- React 19 + React Router 7 + Vite 8 + Tailwind v4, TypeScript strict
- App shell: sidebar navigation (content and demos merged into one topic tree), header with language
  / style / color-mode controls, routed content area, 404 route
- **Token layers**: primitive palette -> mode-aware semantic tokens -> style presets -> Tailwind
  utilities (`palette.css` / `tokens.css` / `styles.css` + `@theme inline`)
- **Theme**: light / dark / system, persisted in `localStorage`, applied by an inline bootstrap script
  before first paint (no flash); `color-scheme` keeps native controls in step
- **Style presets**: `default` / `sharp` / `warm` / `mono`, selected by `data-style` on `<html>` and
  scopable to any subtree
- **i18n**: typed English/Chinese dictionaries, bilingual MDX (`page.zh.mdx`, `notes.zh.mdx`),
  persisted locale, a missing-translation badge instead of a silent fallback
- `Button`, `SegmentedControl` and `cn()` in the shared package, consumed through a Vite alias
- **Content loop**: MDX pages under `apps/lab/content/`, Zod-validated frontmatter, a generated index,
  and a sidebar + home list derived from it — adding an `.mdx` file needs no code change
- **Demo system**: demo folders under `demos/`, a generated registry, a Preview / Source / Notes shell
  (source is the real file, copyable), and a per-demo error boundary so one crash cannot take the page
  down — 24 demos ship today
- **Quality gates**: `pnpm check` = generate + typecheck + `content:check` + `style:check` + eslint +
  prettier + `node:test`; `pnpm build` runs the same checks before `vite build`
- **Tailwind deep dive (B8)**: five experiments — container queries, `has-*` / `peer-*`, variant
  rules, keyframes vs Motion, grid + subgrid
- **CodeMirror (B9)**: `packages/editor`, a non-controlled editor wrapper with compartment-based
  theme and read-only, token-driven syntax colours, and three experiments (minimal editor, themes /
  keymaps, decorations); five themes (lab tokens, One Dark, Dracula, Nord, Solarized Light) are
  generated from palettes by one factory
- **Panels (B10)**: `packages/panels`, a dependency-free split with pointer capture, keyboard resize
  (`role="separator"`), clamping and `localStorage` persistence; panes are `@container`s
- **Zustand (B11)**: `packages/state`, a store factory (`createStoreContext`) with a vanilla store in
  a context, per-instance providers, and selector / `useShallow` guidance with render counts as
  evidence
- **Motion + dnd-kit (B12)**: variants with orchestration, `layout`, `AnimatePresence`, drag
  constraints and motion values; a sortable list whose keyboard sensor and live announcements are
  first-class
- **IDE workspace (B13)**: `packages/workspace` (pure model + zustand store + provider) behind a
  composed demo — file tree, tabs, editor, diagnostics and a status bar over one buffer, plus an
  editor-theme picker wired through a compartment; the contract is documented as a page and held by
  an integration test in `pnpm test`
- **Kanban (B14)**: cross-container drag, a per-instance store, debounced + validated
  `localStorage` persistence, enter/exit animation and an explicit keyboard path for both reordering
  and moving between columns
- **Dashboard builder (B15)**: a reorderable, resizable dashboard over `packages/charts`; the same
  dataset through hand-written SVG, Recharts and Chart.js, with load (bundle report) and render
  (measured in the demo) costs recorded on the page; a hand-written fund-flow Sankey (none of the
  renderers ships one) over a new `--chart-1..5` token set
- **Command palette (B16)**: `packages/command-palette` — combobox ARIA, a Tab trap, focus
  restoration on close, ranked fuzzy matching and recents; mounted in the shell with `Mod+K` over the
  generated indexes, and demoed with its own command set
- **Polish (B17)**: Playwright critical-path suite against a production build, an axe matrix over
  5 routes × colour mode × locale (plus the open palette dialog), and `pnpm bundle:report` with size
  budgets — recorded in `apps/lab/bundle-report.md`

## Adding a content page

Create a file anywhere under `apps/lab/content/` — the folder becomes the sidebar section and the
path becomes the URL:

```text
apps/lab/content/foundations/design-tokens.mdx   ->  /foundations/design-tokens
```

```mdx
---
title: Design tokens
summary: One line shown in lists and as the page subtitle.
order: 10
---

Body starts at `##`. The page renders `title` / `summary` itself, so no `#` heading in the body.
```

| Frontmatter | Required | Meaning                                                          |
| ----------- | -------- | ---------------------------------------------------------------- |
| `title`     | yes      | Sidebar label and page heading (max 80 characters)               |
| `summary`   | yes      | One-liner on the home page and the page subtitle (max 180 chars) |
| `order`     | no       | Sort key inside the section (default `0`, ties break by title)   |

Unknown keys fail the build (`strictObject`), because a typo like `summery:` would otherwise fall
back silently. Section titles come from the folder name (`foundations` -> `Foundations`, translated
by the dictionary), sections sort alphabetically, and pages sort by `order` then title. `pnpm dev`
picks up add/edit/delete of `.mdx` files immediately (full reload); `pnpm build` and
`pnpm content:index` regenerate the same index on demand.

### Translations

A translated page is a sibling file with a locale suffix; it keeps the same slug and the English
file stays the base:

```text
apps/lab/content/foundations/design-tokens.mdx       # English (required, owns `order`)
apps/lab/content/foundations/design-tokens.zh.mdx    # Chinese (optional)
```

A `.zh.mdx` without its base file fails `pnpm content:check`. When the current locale has no file,
the page renders English and shows a "not translated yet" badge — and so does its sidebar entry.

## Adding a demo

A demo is a folder — no registration anywhere:

```text
apps/lab/demos/foundations/button-variants/
├── demo.tsx          # default export = the component that renders in Preview
├── notes.mdx         # frontmatter (title/summary/order) + the write-up in the Notes tab
└── notes.zh.mdx      # optional Chinese write-up and labels
```

- URL: `/demos/foundations/button-variants`; sidebar entry: under **Foundations**, with a `demo` badge
- `demo.tsx` may import from `@frontend-lab/ui` and plain React — never from the app shell; a
  lint zone enforces that, so every demo stays self-contained
- `notes.mdx` is required (`pnpm content:check` rejects a demo without it); the folder name is only
  a fallback label if frontmatter ever goes missing
- `notes.zh.mdx` is optional; without it the Chinese page shows the English write-up plus a badge
- The Source tab shows the _actual_ `demo.tsx` (imported with `?raw`), so it can never drift
- A crashing demo is contained by `DemoErrorBoundary`; tabs, source and other demos keep working

## Layout

```text
frontend-lab/
├── apps/lab/                 # the only web app
│   ├── content/              # MDX pages, grouped by folder (`.zh.mdx` = translation)
│   ├── demos/                # <group>/<demo>/{demo.tsx,notes.mdx,notes.zh.mdx}
│   ├── plugins/              # generators (content-index, demo-registry) + gates
│   │   │                     #   (content-check, style-check, bundle-report) + node:test files
│   ├── e2e/                  # Playwright: critical paths + the axe matrix
│   ├── src/app/              # router, layout, nav builder, routes
│   ├── src/components/       # DemoShell, DemoPreview, DemoSource, error boundary, header controls
│   │                         #   (incl. the shell command palette)
│   ├── src/generated/        # content-index.ts + demo-registry.ts (generated, git-ignored)
│   ├── src/i18n/             # locales, typed dictionaries, provider + hook, locale selector
│   ├── src/prefs/            # persisted preference store (theme, style, locale)
│   ├── src/styles/           # app.css (Tailwind entry) + mdx.css (content typography)
│   ├── tests/                # node:test integration suites (workspace contract, command matching)
│   ├── bundle-report.md      # generated baseline of every built asset (committed)
│   ├── playwright.config.ts
│   └── vite.config.ts
├── packages/ui/              # shared components + token layer
│   └── src/
│       ├── components/       # button, segmented-control
│       ├── lib/              # cn()
│       └── styles/           # palette.css, tokens.css, styles.css
├── packages/editor/          # CodeMirror wrapper: mount once, compartments, palette-driven themes
├── packages/panels/          # split pane + persisted split size (no dependencies)
├── packages/state/           # zustand store factory + useShallow re-export
├── packages/workspace/       # IDE session contract: model + vanilla store + provider
├── packages/charts/          # SVG baseline, fund-flow Sankey, lazy Recharts / Chart.js entries
├── packages/command-palette/ # dialog + combobox + focus trap + ranked matcher
├── eslint.config.mjs         # incl. boundary zones between app / demos / packages / plugins
├── tsconfig.base.json
└── pnpm-workspace.yaml
```

## Roadmap

Status vocabulary: `done` / `doing` / `todo`. Only one batch may be `doing` at a time.

### Wave 1 · Shell and content loop

| #   | Batch        | Goal                                                                 | Exit criteria                                                                | Status |
| --- | ------------ | -------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------ |
| B1  | Shell        | workspace + Vite + Tailwind + router + layout                        | `pnpm dev` / `pnpm build` / `pnpm check` green, one interactive demo works   | done   |
| B2  | Content loop | MDX via `@mdx-js/rollup`, frontmatter, generated index               | adding an `.mdx` file makes it appear in the sidebar without code changes    | done   |
| B3  | Demo system  | registry generator, DemoShell (Preview/Source/Notes), error boundary | 3 real demos, source visible and copyable, a failing demo breaks only itself | done   |

B3 completion is the vertical-slice MVP: worth pausing and re-evaluating scope there.

### Wave 2 · Cross-cutting capabilities

| #   | Batch           | Goal                                                             | Exit criteria                                                          | Status |
| --- | --------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------- | ------ |
| B4  | Quality gates   | Zod frontmatter schema, content/demo checks, boundary lint zones | four deliberate mistakes are all rejected by `pnpm check`              | done   |
| B5  | Theme           | tokens split, light/dark switch, persisted prefs, no FOUC        | reload keeps the choice, no flash, all demos follow the mode           | done   |
| B6  | Multiple styles | shadcn style presets, style token check, token playground        | switching a style updates the whole site and every demo                | done   |
| B7  | i18n            | typed dictionaries, bilingual MDX, missing-translation badge     | switching to `zh` translates UI and content, untranslated pages marked | done   |

### Wave 3 · Single-library experiments

| #   | Batch              | Goal                                                      | Exit criteria                                 | Status |
| --- | ------------------ | --------------------------------------------------------- | --------------------------------------------- | ------ |
| B8  | Tailwind deep dive | `@container`, `has-*`, variant rules, keyframes vs Motion | at least 5 experiments, each with conclusions | done   |
| B9  | CodeMirror         | minimal editor, theme/shortcuts, decorations/transactions | 3 MDX pages + 3 demos                         | done   |
| B10 | Panels             | resizable layout, keyboard resize, persisted sizes        | layout survives reload, keyboard path works   | done   |
| B11 | Zustand            | store factory, selectors, derived state, per-instance     | demos share the factory, no global singletons | done   |
| B12 | Motion + dnd-kit   | variants/layout/gestures, sensors/collision/sortable      | keyboard sensor verified for every drag demo  | done   |

### Wave 4 · Composed scenarios

| #   | Batch             | Goal                                            | Exit criteria                               | Status |
| --- | ----------------- | ----------------------------------------------- | ------------------------------------------- | ------ |
| B13 | IDE Workspace     | editor + panels + file tree + sync (splittable) | contract doc + integration test             | done   |
| B14 | Kanban            | drag + state + animation                        | drag, persistence and keyboard all work     | done   |
| B15 | Dashboard Builder | charts + drag layout, chart library comparison  | comparison experiment with recorded numbers | done   |
| B16 | Command Palette   | keyboard interaction, search, shortcuts         | focus management verified                   | done   |
| B17 | Polish            | Playwright suite, axe matrix, bundle report     | critical paths green, baseline recorded     | done   |

## Batch log

Completed batches keep their notes here; long findings go to the MDX page of that batch (from B2
on) and are only linked from here.

### B1 · Shell — done

- Goal: install the toolchain end to end and prove it with one interactive demo
- Built: workspace, app shell (sidebar + header + routed content), `packages/ui` with `Button` and
  `cn()`, token layer in CSS variables mapped into Tailwind v4 via `@theme inline`, one inline demo
- Exit check (verified through the DOM, not screenshots): `pnpm check` green; `pnpm build`
  produces `dist/`; headless Chrome `--dump-dom` on `/` renders the roadmap and on `/demos/hello`
  renders the demo with `aria-pressed` state and `bg-primary` on the button; generated CSS contains
  `.bg-primary{background-color:var(--primary)}`
- Pitfalls / decisions:
  - File names were converted from `PascalCase.tsx` to lowercase kebab-case after B1 (e.g.
    `App.tsx` → `index.tsx`, `Layout.tsx` → `layout.tsx`, `HelloDemoRoute.tsx` →
    `hello-demo-route.tsx`), aligning with shadcn's naming; see Conventions → File naming
  - `typescript` is pinned to `~5.9.3`: latest is 7.0.2 but `typescript-eslint@8` requires `<6.1.0`
  - `@frontend-lab/ui` is aliased to source in `vite.config.ts`, so the shared package needs no build
    step; the workspace dependency still covers types and is checked by `pnpm typecheck`
  - `pnpm-workspace.yaml` carries `onlyBuiltDependencies: [esbuild]` (pnpm 11 blocks build scripts by
    default) and pnpm's own `minimumReleaseAgeExclude` entry
  - `.npmrc` points at the China npm mirror; the default `registry.npmmirror.com` route was faster
    and more stable here than going through a proxy
  - `eslint-plugin-react-hooks` v7 and `react-refresh` are registered manually (rule by rule)
    instead of using their config presets, to stay independent of config-shape changes

### B2 · Content loop — done

- Goal: an `.mdx` file plus frontmatter is the only thing needed to add a page
- Built:
  - `content/` with three real pages (`foundations/design-tokens`, `foundations/focus-and-keyboard`,
    `interactions/controlled-vs-uncontrolled`), grouped by folder
  - `apps/lab/plugins/content-index.ts`: scans `content/**/*.mdx`, reads frontmatter, writes the typed
    module `apps/lab/src/generated/content-index.ts` (metadata) plus one `import()` per page (so MDX
    code-splits per page: 2–3 kB chunks in the build)
  - Vite plugin wrapper: regenerates on dev start and build, and watches `content/` for add / change /
    unlink, then triggers a full reload
  - `pnpm content:index` CLI path, used by `typecheck` / `build` so `tsc` always sees the file
  - Routing: one splat route (`*`) resolves the slug against the index; unknown slugs fall through to
    the 404 view, and static routes (`/demos/hello`) still win during ranking
  - Sidebar and home page are generated from the index (`nav.ts` is now a thin adapter); MDX
    typography lives in `src/styles/mdx.css` (tokens only, no `@tailwindcss/typography`)
- Exit check (DOM, not screenshots): with `pnpm dev` running, dropping a new
  `content/foundations/keyboard-checklist.mdx` made it appear in the sidebar and at its URL, and
  deleting it removed it again — no code change, no restart. Also asserted through `--dump-dom`: home
  lists 3 pages, `/foundations/design-tokens` renders title + summary + `##` body + a GFM table with
  inline `code`, `document.title` is set per page, `/foundations/does-not-exist` renders the 404 view,
  `/demos/hello` still works, and `vite preview` of the production build renders the same page
- Pitfalls / decisions:
  - `content/` sits outside the Vite root on purpose (content outlives the app shell). Two
    consequences: `server.fs.allow` must include the prototype folder, and MDX outside the root
    cannot resolve `react/jsx-runtime` from `frontend-lab/content/` — `resolve.dedupe: ['react',
'react-dom']` fixes it
  - `gray-matter` was dropped for `yaml`: it ships `export = matter`, which needs `esModuleInterop`
    (the repo has `verbatimModuleSyntax` and no interop flags), and `yaml` is ESM + typed
  - The generator is TypeScript run directly by Node 24 (type stripping, no build step); it is
    imported by `vite.config.ts` **with** the `.ts` extension because Vite 8's native config loader
    rejects extensionless relative imports (needs `allowImportingTsExtensions` in tsconfig)
  - The generated file is git-ignored and regenerated on demand, so content edits never produce noise
    in reviews; `eslint` and `prettier` skip it as well
  - Frontmatter is parsed twice by design — the generator reads it for metadata, `remark-frontmatter`
    strips it from the rendered page. B4 replaces the loose reads with a Zod schema
  - Frontmatter is intentionally optional for now (title falls back to the file name) so content can
    never break the sidebar; B4 turns that into hard failures

### B3 · Demo system — done

Vertical-slice MVP: shell + content loop + demo system. Worth a scope re-check before Wave 2.

- Goal: a demo folder is the only thing needed to add a runnable, source-visible, notes-carrying demo
- Built:
  - `apps/lab/demos/<group>/<name>/{demo.tsx,notes.mdx}` plus `plugins/demo-registry.ts`, which
    generates `src/generated/demo-registry.ts` (metadata + lazy `load` / `loadSource` / `loadNotes`)
  - Generators now share `plugins/frontmatter.ts` (frontmatter, walking, quoting) and
    `plugins/index-plugin.ts` (buildStart + watcher + full reload), so content and demos cannot drift
    apart; `pnpm generate` runs both
  - `DemoShell` with Preview / Source / Notes: ARIA tabs (roles, `aria-selected`, roving tabindex,
    Arrow/Home/End keys); panels stay mounted once visited so demo state survives a look at the source
  - Source tab loads the real `demo.tsx` via `?raw` (never a copy) with a Copy button; Clipboard API
    with a visible `Copied` / `Copy failed` state
  - `DemoErrorBoundary` (class component, `getDerivedStateFromError` + `componentDidCatch`) with a
    Recover button, keyed per demo
  - Three demos: `foundations/button-variants` (variant matrix + `cn()` merge read back from the DOM),
    `interactions/controlled-vs-uncontrolled` (commit counter), `foundations/focus-visible`
    (outline-none / focus / focus-visible + last input modality)
  - Sidebar merges content groups and demo groups into one topic tree; demo items get a `demo` badge;
    `/demos` lists everything; `routes/hello-demo-route.tsx` (B1) was replaced by demo 1
  - New `--destructive` token (+ `@theme` mapping) for the error card
  - `Button` accepts `ref` (React 19 passes it as a prop) so demos can read the rendered element
- Exit check (headless Chrome over CDP, real clicks — 23 assertions, all green): tabs render and
  Preview is selected; the counter increments; Source shows the whole 4 kB `demo.tsx`; Copy puts the
  exact source on the clipboard and the label flips to `Copied`; Notes renders MDX (real `h2`);
  demo state survives Source/Notes round trips; ArrowRight moves the tab; the other two demos render;
  the merged sidebar lists content + demos with badges; `/foundations/design-tokens` still works; an
  unknown demo slug falls through to the 404 view; and a deliberately throwing demo shows the error
  card while the shell, tabs (no Notes tab without `notes.mdx`) and neighbouring demos keep working.
  The production build was verified the same way (lazy `?raw` and notes chunks load under `vite
preview`), plus `pnpm check` / `pnpm build` green
- Pitfalls / decisions:
  - `?raw` import instead of a copied file: the Source tab cannot lie, and the demo is a normal
    module, so no build step or codegen for the source text
  - Everything is lazy per demo (`load`, `loadSource`, `loadNotes`), so the production build emits one
    ~2-3 kB chunk per demo plus one per source/notes — the registry chunk itself stays metadata-only
  - Panels are hidden, not unmounted: a demo that loses its state because you looked at the source
    would be a bad demo, and it is also what makes `DemoShell` testable
  - The CommitCounter in the controlled/uncontrolled demo mutates a ref during render on purpose;
    `useEffect` would count after paint and add a render per measurement
  - `React.lazy` instances are cached per slug (both for demos and content pages): recreating them on
    render remounts the subtree and throws state away
  - Clipboard reads in headless Chrome need `Emulation.setFocusEmulationEnabled`; without it the
    API rejects with "Document is not focused" — worth remembering for B17's axe/Playwright pass
  - `--destructive` was the first token added after B1; B5/B6 will need a dark variant of it

### B4 · Quality gates — done

- Goal: four deliberate mistakes are rejected by `pnpm check`, not by a reviewer
- Built:
  - `plugins/frontmatter.ts` now owns a Zod schema: `strictObject` with required `title` / `summary`,
    optional integer `order` and length caps. `readFrontmatterSource` never throws (it aggregates
    prettified issues) while `requireFrontmatterFile` is the generator path — invalid frontmatter
    ends the dev server or the build instead of falling back to a file name
  - `plugins/content-check.ts`: kebab-case names, no `index.mdx`, body must start at `##` and have a
    section, demo folders need `export default` + `notes.mdx` and no stray files, no nested demos,
    no orphan notes; output is grouped by file and exits non-zero
  - `plugins/{content-check,style-check}.test.ts` use `node:test` (no test framework dependency) with
    fixtures in temp directories; `pnpm test` runs them
  - ESLint boundary zones: app shell -> package entry point only, demos self-contained, `packages/ui`
    never depends on the app, build plugins never import app runtime
  - `pnpm check` = generate + typecheck + `content:check` + `style:check` + eslint + prettier + tests,
    and `pnpm build` runs the same checks before `vite build`
- Exit check, each mistake added, `pnpm check` run, mistake removed:
  1. unknown frontmatter key + `order: ten` -> schema failure (also via `pnpm generate`, i.e. in dev)
  2. `#` heading in the body -> content check
  3. demo folder without `export default` and without `notes.mdx` -> content check (and `tsc` refuses
     the generated registry import, which is a second gate for the same bug)
  4. app file importing `packages/ui/src/components/button` -> `no-restricted-imports`
     All four exited non-zero and the tree was restored afterwards; the 17 check tests stayed green
- Pitfalls / decisions:
  - Required `title`/`summary` deleted the file-name fallback on purpose: a missing field is an
    authoring bug, and a silent fallback hides it
  - Checks are exported functions plus a thin CLI wrapper, so tests call the same code path as CI
  - The lint zones use `no-restricted-imports` pattern groups (`../**` for demos); they encode a
    dependency direction, not a taste rule

### B5 · Theme — done

- Goal: one attribute switches the mode, the choice survives a reload, and nothing flashes
- Built:
  - `packages/ui/src/styles/palette.css` (primitive ramps) split from `tokens.css` (semantic light +
    `[data-theme='dark']` values, `color-scheme` per mode, `@theme inline` mapping unchanged)
  - `index.html` inline bootstrap reads `localStorage` and resolves `system` through
    `prefers-color-scheme` before the stylesheet applies; `prefs/pref.ts` is a small
    `useSyncExternalStore` store (cross-tab via `storage`), `prefs/theme.ts` owns `useTheme()`
  - `SegmentedControl` in the shared package, header Light / Dark / System control
  - `@custom-variant dark` so `dark:` utilities follow the attribute, not the OS
  - New demo `foundations/color-tokens` (reads every semantic token back from the cascade) and page
    `foundations/color-modes`
- Exit check: 23 CDP assertions over the dev server — default is `system` with nothing stored; Dark
  and Light write `data-theme`, `localStorage` and `color-scheme`, and change the computed
  `--background` (`oklch(0.99 …)` -> `oklch(0.13 …)`); a reload keeps `dark` with exactly **one**
  `data-theme` write, recorded while `document.readyState === 'loading'` (so React did not paint the
  wrong mode first); `system` follows an emulated OS change with no reload; demos and shared
  components repaint; a content page shares the mode
- Pitfalls / decisions:
  - Headless Chrome inherits the host appearance, so the verification script emulates
    `prefers-color-scheme` before navigating — otherwise "the default is light" is flaky
  - Dark is not inverted light: `--card` sits above `--background`, and the brand moves up the ramp
  - `color-scheme` is a separate switch from the tokens; without it scrollbars and form widgets stay
    light in dark mode

### B6 · Multiple styles — done

- Goal: a style preset re-themes the whole site (shell, MDX, every demo) from one control
- Built:
  - palette gains a warm ramp + amber brand; `packages/ui/src/styles/styles.css` holds the presets
  - `default` / `sharp` / `warm` / `mono` as `[data-style][data-theme]` token overrides; the compound
    selectors make the result independent of import order and let a preset apply to any subtree
  - `default` restates the base token values — a scoped `data-style="default"` has to reset a
    `warm` page, which only works if the default is spelled out
  - `prefs/style.ts` + a native `<select>`; `plugins/style-check.ts` (+ tests) proves the preset list
    and the CSS agree: both directions, no unknown token names, both modes present, `default` mirrors
    `tokens.css`, every `var(--x)` resolves
  - New demo `foundations/style-playground` (all four presets scoped on one page) and page
    `foundations/style-presets`
- Exit check: 28 CDP assertions — switching to `warm` re-points `--primary` and `--radius`, persists,
  and repaints a shared component in a demo; mode and style are independent layers; a reload applies
  `data-style` once before the app mounts; the playground resolves `0.625rem / 0 / 0.9rem / 0.375rem`
  per subtree with three distinct brands on one page; `mono` also applies to content pages
- Pitfalls / decisions:
  - The first version of the playground exposed a real gap: `data-style="default"` matched no rule and
    inherited the page's preset. Making `default` explicit (plus the mirror check) fixed the demo and
    the model at once
  - Presets may only override existing semantic tokens; a new concept belongs in `tokens.css`, where
    every style gets a value for it
  - `sharp` only declares `--radius`, which the check accepts as a mode-independent override

### B7 · i18n — done

- Goal: switching to `zh` translates the UI _and_ the content, and an untranslated page says so
- Built:
  - `src/i18n/`: `locales.ts` (list, labels, `<html lang>` tags), `dictionary.ts` (`en` defines the
    `Dictionary` type, so `zh` cannot miss a key; `format()` for `{count}` templates), `context.ts` /
    `provider.tsx` / `use-i18n.ts` (provider + hook split so Fast Refresh stays honest)
  - Bilingual MDX by file suffix: `page.mdx` + `page.zh.mdx`, `notes.mdx` + `notes.zh.mdx`. The
    generators emit per-locale metadata and per-locale lazy imports; the English file owns `order`
  - `pick()` returns `{ value, missing }`; a badge component marks an untranslated page, its sidebar
    entry and its list rows, instead of silently showing English
  - Locale is a persisted preference applied to `<html lang>` (bootstrap sets it before first paint),
    with an `EN / 中文` switch next to the style and mode controls
  - `pnpm content:check` grew two rules: a translation never stands alone, and `src/i18n/locales.ts`
    must match the plugins' locale list
  - Four content pages and four demo notes translated; `interactions/controlled-vs-uncontrolled` and
    the `foundations/focus-visible` notes are deliberately left untranslated to keep the badge path
    exercised
- Exit check: 33 CDP assertions — `EN -> 中文` flips `lang`, `document.title`, sidebar, control labels
  and the 404 page; `/foundations/design-tokens` renders the Chinese chunk (设计令牌 / 三层结构);
  a demo swaps to 预览 / 源码 / 说明 and loads the Chinese notes; the untranslated page keeps its
  English body and shows the badge, with `EN` tags in the sidebar; reload keeps the locale with
  `lang` set while the document is still loading; locale + mode + style coexist; the production
  preview (6 assertions) loads the `.zh` chunks and dark tokens from the built CSS
- Pitfalls / decisions:
  - The lazy cache must be keyed by `slug:locale`; keying by slug alone reuses the English module
  - `useMemo` after the early return broke `rules-of-hooks` in the content route; extracting
    `PageBody` fixed it and gave the locale swap its own Suspense boundary
  - `pages` in the check output counts slugs, not files, or every translation would inflate it
  - Chinese content is real content, not a token translation: the tables and code samples are
    rewritten, because a half-translated table reads worse than English

### B8 · Tailwind deep dive — done

- Goal: separate the utilities people memorise from the ones that change layout behaviour
- Built: five experiments under `demos/techniques/` with a page at `content/techniques/tailwind-deep-dive`
  - `container-queries`: one card markup rendered twice — `@container` vs `sm:` — with a slider for the
    container width and a `ResizeObserver` readout of the width the query actually saw
  - `has-and-peer`: `group-has-[input:invalid]` validation, `peer-checked` reveal, `has-[:checked]`
    radio rows, `has-[img]` card padding — no React state decides any colour
  - `variant-rules`: `*:` children, `nth-3:` stripes, `not-last:`, `data-[state=…]`, `aria-[sort=…]`,
    `open:`, and `starting:` for inserted nodes
  - `keyframes-vs-motion`: the same impulse through `@keyframes` (restarted by remounting) and
    Motion (`y: [null, -32, 0]`, continuing from the current value), with `getAnimations()` printed
  - `grid-subgrid`: `col-span-full grid grid-cols-subgrid` rows vs flex rows from the same data, plus
    `repeat(auto-fit, minmax(7rem, 1fr))`
- Exit check (CDP over `vite preview`, DOM only): the container-query card reports
  `flex-direction: column` at 220px and `row` at 700px while the viewport never changes; the
  `has-[input:invalid]` wrapper's `border-top-color` moves from the destructive token back to the
  border token when the value becomes valid; the built CSS contains `:has(:is(input:invalid)`,
  `container-type:inline-size`, `@starting-style`, `grid-template-columns:subgrid`,
  `nth-child(3)` and `@keyframes kick`
- Pitfalls / decisions:
  - A named keyframe animation cannot live in a demo folder (`demo.tsx` + notes only), so
    `--animate-kick` is registered under `@theme` in `src/styles/animations.css` and used as a
    normal utility
  - `nth-3:` compiles to `:nth-child(3)` — it selects the third sibling, not "every third"; striping
    rows 3 and 6 needs `nth-[3n]:` or a computed index, which the notes call out
  - Tailwind's automatic content detection scans MDX too, so a class name quoted in prose lands in
    the built CSS; harmless here, but it is why `grid-template-columns:…` appears in the bundle
  - React's value tracker defeats `input.value = x` in a CDP script; the verification harness has to
    use the native `HTMLInputElement.prototype.value` setter or the demo looks broken

### B9 · CodeMirror — done

- Goal: an editor wrapper that is a component, not a framework, plus three experiments
- Built:
  - `packages/editor`: `CodeEditor` (mount once, `initialDoc` not `value`, callbacks in refs,
    `Compartment`s for theme and read-only, `onView` handle), `baseExtensions`, `themeExtension`,
    `labEditorTheme` + `labHighlightStyle` written entirely in CSS variables
  - `demos/editing/minimal-editor`: undo/redo, a three-part transaction, and a deliberate "read the
    document" pull that keeps the "keystrokes seen by React: 0" claim honest
  - `demos/editing/theme-and-shortcuts`: `tokens` vs `one-dark` through a compartment (undo still
    works afterwards), read-only as two extensions, a `Prec.highest` keymap overriding `Tab`
  - `demos/editing/decorations`: a tag field recomputed on `docChanged` and a search field driven by a
    `StateEffect`, both providing decorations; counts read back from the state
  - Three pages: `editing/codemirror-basics`, `editing/codemirror-themes-and-shortcuts`,
    `editing/codemirror-decorations`
- Exit check (CDP): `.cm-content` paints 7 tag marks; typing in the search box raises the derived hit
  count; the theme switch keeps the view (undo still enabled); all three routes render in both locales
- Pitfalls / decisions:
  - `@codemirror/*` ends up in two manifests (the package and the app, for demos that need
    `StateField`/`Decoration` directly); pnpm resolves both to one instance, which is what matters
    for `instanceof`-based facets
  - Extensions passed by a caller are appended, so they have _lower_ precedence than the defaults —
    the right default for extension, the wrong one for override, hence `Prec.highest` in the demo
  - `EditorView.theme` keys are selectors and self-references (`&.cm-focused`); a plain CSS rule
    silently does nothing
  - Fast Refresh complains when a `.tsx` file exports both a component and helpers, so
    `extensions.ts` was split out of `code-editor.tsx`

### B10 · Panels — done

- Goal: a split that survives a reload and works without a pointer
- Built:
  - `packages/panels` (no dependencies): `useSplitSize` (percentage, `localStorage`, clamped on read
    and write) and `SplitPane` (pointer capture, `role="separator"` with `aria-valuenow` /
    `aria-orientation` / `aria-valuetext`, arrows ±4%, PageUp/PageDown ±12%, Home/End, Enter resets,
    double-click resets, both panes `@container`)
  - `demos/layout/split-pane`: persisted horizontal split with a nested vertical split, live pane
    width readouts and the stored value printed from `localStorage`
  - `demos/layout/keyboard-resize`: focus the separator, every key echoed, `aria-valuenow` and the
    size log read back from the DOM
  - Page: `layout/resizable-panels`
- Exit check (CDP): ArrowRight moves `aria-valuenow` 50 → 54, End jumps to 85, Enter resets to 50;
  three ArrowRight presses then a reload restore the stored 63% (and `localStorage` holds it)
- Pitfalls / decisions:
  - `aria-orientation` describes the separator, not the layout: a horizontal layout needs a _vertical_
    separator
  - `setPointerCapture` is what makes a fast drag survive leaving the 6px handle, and it removes the
    need for a global `user-select: none`
  - The separator is 6px wide, so its focus ring has to be drawn inset
  - Persisting on every `pointermove` writes ~60 times a second; fine for one key, a debounce the
    moment several splits are saved together

### B11 · Zustand — done

- Goal: per-instance state from one definition, and selectors that measurably narrow subscriptions
- Built:
  - `packages/state`: `createStoreContext` (vanilla `createStore` in a context, store created in a
    `useState` initialiser, `useSelector` + `useStoreApi`, named errors when the provider is missing)
    and a `useShallow` re-export
  - `demos/state/store-factory`: two providers of one factory next to two panels of a module-level
    `create()` store, with render counters
  - `demos/state/selectors-and-derived`: a todo store with per-row selectors, `useShallow`-wrapped
    derived selectors, render counters per component, a `store.subscribe` log outside React
  - Page: `state/zustand-store-factory`
- Exit check (CDP): clicking instance A's `+` twice leaves B at 0; the shared pair both read 1 after
  one click; render counts confirm the store-factory panels do not notify each other
- Pitfalls / decisions:
  - `useRef(createStore(...))` and `useState(createStore(...))` both recreate the store; only a lazy
    `useState` initialiser gives one store per mounted provider
  - zustand v5 compares with `Object.is` — a derived array/object needs `useShallow` or every update
    re-renders every consumer
  - Actions stay a stable nested object (`state.actions`); recreating them inside `set()` would
    re-render every dispatcher-only component
  - The module-level store is kept in the demo on purpose: it is a legitimate app-wide pattern, and
    seeing it share state is the fastest way to understand why the factory exists

### B12 · Motion + dnd-kit — done

- Goal: variants, layout animation and gestures from Motion; sensors, collision and sortable from
  dnd-kit — with the keyboard path verified rather than assumed
- Built:
  - `demos/motion/variants-and-layout`: staggered variants declared on the parent, `layout` on list and
    items with shuffle, `AnimatePresence mode="popLayout"` for removal, reduced motion collapsing the
    duration
  - `demos/motion/gestures`: `dragConstraints` from a ref, `dragElastic` and `dragSnapToOrigin` as
    controls, `whileHover`/`whileTap`, `MotionValue` + `useSpring` readout, drag disabled under reduced
    motion
  - `demos/motion/dnd-sortable`: `PointerSensor` (4px threshold) + `KeyboardSensor` with
    `sortableKeyboardCoordinates`, `closestCenter` vs `rectIntersection` toggle, `DragOverlay`,
    custom `announcements` echoed into a visible log
  - Pages: `motion/motion-variants-and-gestures`, `motion/dnd-kit-sortable`
- Exit check (CDP): focus the first row, `Space`, `ArrowDown`, `Space` reorders
  `Design tokens|Component API|…` to `Component API|Design tokens|…` and the log shows
  `Picked up tokens` → `tokens is over components` → `Dropped tokens at position components` — the
  same strings a screen reader receives
- Pitfalls / decisions:
  - `layout` and `drag` both own `transform`; a draggable inside an animated list needs the drag
    transform on an inner element
  - `AnimatePresence` needs stable keys — an index key animates whichever item landed in that slot
  - `announcements` / `screenReaderInstructions` are passed through `accessibility={{ … }}` on
    `DndContext` (v6), not as top-level props
  - `activationConstraint: { distance: 4 }` is what keeps a click a click
  - Reduced motion is handled per interaction: durations collapse for variants, the drag is disabled
    entirely, because an instant drag leaves pointer and element disagreeing

### B13 · IDE workspace — done

- Goal: the first composed scenario — file tree, tabs, editor and diagnostics over one buffer
- Built:
  - `packages/workspace`: `model.ts` (pure open/edit/save/revert/close/tree/line count),
    `store.ts` (the same model behind zustand, no React), `provider.tsx` / `use-workspace.ts` /
    `context.ts` (one store per provider, split so Fast Refresh stays honest) — the contract is
    documented on `scenarios/ide-workspace`
  - `demos/scenarios/ide-workspace`: split layout (tree | editor+problems) with persisted sizes and
    pixel bounds, a tab strip with dirty dots, `CodeEditor` keyed by path (draft survives a tab
    switch, undo history does not), `Mod-s` via `Prec.highest`, a diagnostics StateField pair driving
    line + mark decorations, a problems panel that jumps by dispatching a selection, and an activity
    log
  - `SplitPane` gained `minFirstPx` / `maxFirstPx`, converted against the live container so a
    percentage stays usable at every width
  - `apps/lab/tests/workspace-contract.test.ts`: 13 `node:test` cases driving the real store
    (buffer rule, dirty derivation, inert unknown paths, neighbour activation on close, two
    independent stores, tree projection, split clamping)
  - an editor-theme picker: `packages/editor` now generates Dracula, Nord and Solarized Light from
    palette objects (one `createTheme` factory, cached extensions) next to lab tokens and packaged
    One Dark; the demo switches all five live through the theme `Compartment`, so draft, cursor and
    undo history survive
- Exit check: `pnpm check` green (40 tests); 20 CDP assertions over the production preview — tree
  click switches the buffer, typing marks it dirty and paints the tree dot, `Mod-s` saves and logs,
  the tab strip survives, `tree 31%` survives a reload, the tree collapses, three diagnostics render
  as both line and mark decorations, and the contract page renders in both locales
- Pitfalls / decisions:
  - Dirty is `draft !== saved`, never a flag, so a save of identical text cannot leave a stale marker
  - The editor is mounted with `initialDoc` and remounted by path: a controlled editor would lose
    history on every parent render, an uncontrolled one cannot be kept in sync without a dispatch
  - Two decoration fields instead of one: `RangeSetBuilder` needs ascending, non-overlapping ranges,
    and line decorations sit at the line start while marks sit at the match
  - Closing a tab discards its draft — documented, and asserted by the integration test

### B14 · Kanban — done

- Goal: cross-container drag over a real store, with persistence and a keyboard path that is not an
  afterthought
- Built:
  - `demos/scenarios/kanban-board`: three columns, one `DndContext` with `closestCorners`, one
    `SortableContext` per column, `PointerSensor` (4 px) + `KeyboardSensor`, `DragOverlay`, custom
    announcements echoed into a log
  - `onDragOver` moves the card between columns live, `onDragEnd` reorders inside the column
  - per-instance store via `createStoreContext`; persistence is a debounced (200 ms) subscription
    with a flush on unmount and an `isBoard` revalidation on read
  - Motion for enter/exit opacity and the overlay only; `layout` is left to dnd-kit's transition
  - per-card ← / → buttons move between columns, because arrow keys inside a sortable context stop at
    the container edge
- Exit check: 26 CDP assertions — Enter on a → button moves a card and announces it; `Space` +
  `ArrowDown` + `Space` reorders and announces it; a reload restores order, span and column; a
  pointer drag lands a card in the third column; add / remove / reset work and are announced; a
  corrupt stored board falls back to the defaults
- Pitfalls / decisions:
  - The naive `persist` middleware writes once per drag frame; the demo's subscription debounces and
    flushes, which is the pattern B15 reuses
  - `activationConstraint: { distance: 4 }` keeps the card buttons clickable
  - A card that is also `role="button"` cannot contain buttons: the drag listeners live on a ⠿
    handle, and `setNodeRef` stays on the row
  - dnd-kit auto-scrolls when the pointer nears the viewport edge; the CDP verification had to use a
    desktop-sized viewport, otherwise the drop target moves out from under the pointer mid-drag

### B15 · Dashboard builder — done

- Goal: a drag-layout dashboard plus a chart-library comparison with recorded numbers
- Built:
  - `packages/charts`: deterministic seeded series, a zero-dependency SVG renderer, and two lazy
    entry points (`./recharts`, `./chartjs`); every renderer reports its own render cost through a
    shared `useMountCost` hook
  - `demos/scenarios/dashboard-builder`: a store-backed grid (order, span, renderer persisted),
    edit mode with drag handles + width buttons + per-card renderer select, Motion `layout` only
    while not editing, and a live render-cost panel with a "Measure again" remount
  - `apps/lab/plugins/bundle-report.ts` + `pnpm bundle:report`: gzips every built asset, attributes
    the chart chunks by name, writes `apps/lab/bundle-report.md`, and fails on the size budgets
  - a fund-flow Sankey (`packages/charts/src/sankey-layout.ts` + `sankey.tsx`): income → buckets →
    funds, one shared vertical scale, per-node ribbon anchor slices, `max(in, out)` node values, and
    nine `node:test` geometry cases. No compared renderer ships a Sankey, so it is hand-written SVG
  - `--chart-1..5` categorical tokens in `tokens.css` (both modes) and the `default` preset, so the
    diagram follows light/dark and the style presets without hard-coded hex values
  - page `scenarios/dashboard-builder` with the recorded comparison: SVG ≈ 0 kB extra / 0.7–0.9 ms,
    Recharts 102.8 kB gzip / 2.6–3.0 ms, Chart.js 56.3 kB gzip / 0.7–0.9 ms warm, Sankey 1.6–2.2 ms
- Exit check: 25 CDP assertions — six cards, edit mode controls, lazy chunk load per renderer,
  canvas present for Chart.js, recorded render costs, span change, keyboard reorder, persistence of
  order + span + renderers across a reload, corrupt layout fallback, and both locales of the page
- Pitfalls / decisions:
  - Dynamic Tailwind class names (`col-span-${span}`) produce no CSS; the span map is explicit
  - `layout={!editing}` is the whole fix for Motion vs dnd-kit fighting over `transform`
  - Chart.js needs concrete colours: a canvas cannot read CSS variables, and a theme switch does not
    repaint without a re-render — recorded as a finding rather than hidden
  - The first measurement after a page load includes the page's own mount, which is why the panel has
    a re-measure button and the recorded numbers come from warm remounts

### B16 · Command palette — done

- Goal: a palette that is a component, with the focus contract as the feature
- Built:
  - `packages/command-palette`: `match.ts` (pure, ranked, banded scoring with merged highlight
    ranges), `command-palette.tsx` (portal dialog, combobox + listbox ARIA, Tab trap, focus
    restoration, scroll lock, recents), `use-command-shortcut.ts` (`Mod+K`, configurable key)
  - shell integration `src/components/command-menu.tsx`: commands generated from the content and
    demo indexes plus theme/style/locale actions; page and demo commands carry a `page` / `demo`
    hint so identical titles stay distinguishable
  - `demos/scenarios/command-palette`: its own command set, `Mod+J` (the shell owns `Mod+K`),
    recents, a run log, and instructions that double as the verification checklist
  - `apps/lab/tests/command-match.test.ts`: 10 `node:test` cases on the ranking rules
  - page `scenarios/command-palette` (English + Chinese)
- Exit check: 29 CDP assertions — dialog role/name, focus on the input, Tab trapped, filtering,
  `<mark>` highlighting, `aria-activedescendant` following the arrows with `aria-selected` matching,
  Enter running + closing, focus restored to the trigger, recents on reopen, backdrop click, `Mod+J`,
  `Mod+K` in the shell navigating to a demo, and the Chinese palette labels
- Pitfalls / decisions:
  - `aria-activedescendant` must reference an existing id; the active index is clamped to the match
    count, and the id is derived from the flat index
  - Opening resets the query: a palette that reopens with the last search hides its own commands
  - A subsequence match must stay inside one word — otherwise "set" matches "Send a test message"
  - Two global `Mod+K` handlers on one window race; a demo picks an unused key instead
  - Tailwind had never scanned `packages/`; the palette's `fixed inset-0` was silently missing until
    `app.css` gained `@source '../../../../packages'`. Any class that only a package uses was
    affected

### B17 · Polish and verification — done

- Goal: turn the per-batch throwaway checks into artifacts anyone can run
- Built:
  - `apps/lab/e2e/critical-paths.spec.ts`: 12 Playwright tests against `vite preview` (sidebar
    navigation, demo tabs, colour mode persistence, locale switch, IDE save, IDE theme switch,
    kanban keyboard move, dashboard renderer, dashboard Sankey, `Mod+K` navigation, palette focus
    restoration, 404)
  - `apps/lab/e2e/a11y.spec.ts`: the axe matrix — 5 routes × 2 colour modes × 2 locales plus the open
    palette dialog (21 scans), preferences injected through the same `localStorage` keys the
    bootstrap reads
  - `playwright.config.ts` with `channel: 'chrome'` (no browser download) and `reuseExistingServer`
  - `pnpm e2e`, `pnpm bundle:report`, `pnpm verify` scripts; `apps/lab/bundle-report.md` committed as
    the baseline
- Exit check: `pnpm e2e` green (33 tests: 12 critical paths + 21 axe scans); `pnpm bundle:report`
  reports ≈730 kB total JS gzip and stays inside the 800 kB / 200 kB budgets; `pnpm check` green
  (49 `node:test` cases)
- Pitfalls / decisions:
  - The matrix earned its keep immediately: `--muted-foreground` (`gray-500`) on `--muted`
    (`gray-100`) is just under 4.5:1 for 10px text, so badges and palette hints failed in light mode.
    The token moved to `gray-600` (tokens + the `default` preset), which fixed every page at once
  - `channel: 'chrome'` avoids a Playwright browser download and runs on the same engine the lab is
    developed against; the trade-off is that the suite is Chrome-only by design
  - No visual regression snapshots: the workflow cannot read images, and DOM assertions are the
    actual contract (see the notes on vision verification in `AGENTS.md`)
  - The axe matrix runs the dark-mode scans too: a light-only matrix would have missed nothing here,
    but the reverse case (a dark-only contrast bug) is the common one

## Conventions

### File naming

Lowercase **kebab-case**, matching shadcn's file naming (`dropdown-menu.tsx`, `use-mobile.ts`,
blocks such as `login-01/`). This is a hard rule, not a preference:

- Every `.ts` / `.tsx` file under `apps/` and `packages/` is lowercase kebab-case
  (`hello-demo-route.tsx`) — never `PascalCase.tsx` and never `snake_case.tsx`
- Directories follow the same rule (`components/command-palette/`, `blocks/kanban-01/`)
- Exported symbols keep their natural casing, so the file → symbol mapping stays predictable:
  `routes/home-route.tsx` → `HomeRoute`, `hooks/use-media-query.ts` → `useMediaQuery`,
  `lib/format-date.ts` → `formatDate`
- A folder's own entry files use `index.tsx` (barrel/entry) and `layout.tsx` (shell), mirroring
  shadcn / Next's `app/` layout
- Tool-mandated file names keep their spelling: `vite.config.ts`, `eslint.config.mjs`,
  `tsconfig.base.json`, `pnpm-lock.yaml`, `.prettierrc.json`
- Why: case-insensitive filesystems (macOS/Windows) turn `App.tsx` vs `app.tsx` into a real
  collision, and the shadcn CLI writes kebab-case files, so mixing styles guarantees churn
  (see the B1 batch log entry for the rename that established this)
- Translation suffixes are part of the name, not the extension: `design-tokens.zh.mdx` next to
  `design-tokens.mdx`. The slug is the part before the suffix, so the URL never changes with the
  language

### Quality gates

`pnpm check` is the gate, and it is composed of small checks that each own one failure mode:

| Step            | Owns                                                                                               |
| --------------- | -------------------------------------------------------------------------------------------------- |
| `typecheck`     | types, and the generated index shape after `pnpm generate`                                         |
| `content:check` | frontmatter schema, naming, body rules, demo folder rules, translation pairs                       |
| `style:check`   | palette / tokens / preset blocks / preset list agreement                                           |
| `lint`          | boundary zones (app / demos / ui / plugins) + React rules                                          |
| `format:check`  | Prettier                                                                                           |
| `test`          | `node:test` unit tests for both check modules, plus the B13/B16 suites and the B15 Sankey geometry |

A check is a module that exports a function returning problems plus a thin CLI wrapper; that is what
lets the tests call the same code path as `pnpm check`. Every rule in the table exists because a real
mistake got past the previous gate — add a rule only with a fixture that fails without it.

`pnpm check` cannot see a rendered page or a built chunk, so B17 adds three gates that need a browser
or a build:

| Step            | Owns                                                                                     |
| --------------- | ---------------------------------------------------------------------------------------- |
| `e2e`           | ten critical paths in a real Chrome against `vite preview`                               |
| axe matrix      | 4 routes × 2 colour modes × 2 locales + the open palette dialog, zero serious violations |
| `bundle:report` | gzip sizes of every asset, per-chunk attribution, total + per-chunk budgets              |

`pnpm verify` = `build && bundle:report && e2e`. It is the local equivalent of CI; the prototype stays
out of the repo's CI on purpose.

### Display state

Three persisted preferences, all in `localStorage`, all applied to `<html>` and all read by CSS:

| Preference | Key                   | Attribute    | Values                                |
| ---------- | --------------------- | ------------ | ------------------------------------- |
| Color mode | `frontend-lab:theme`  | `data-theme` | `light` / `dark` (+ `system`)         |
| Style      | `frontend-lab:style`  | `data-style` | `default` / `sharp` / `warm` / `mono` |
| Language   | `frontend-lab:locale` | `lang`       | `en` / `zh`                           |

`index.html` carries one inline bootstrap that resolves `theme`, `style` and `lang` before the
stylesheet applies — that is the only duplicate read of these keys, and it exists so the first paint
is never wrong. Adding a preference means: `prefs/*` store, bootstrap line, control in the header,
and a DOM assertion that it survives a reload.

### i18n

- UI strings live in `src/i18n/dictionary.ts`: `en` defines the `Dictionary` type, `zh` is annotated
  with it, so a missing key is a compile error. Values stay plain strings; counts use
  `format(template, { count })`.
- Content and demo labels are **not** in the dictionary — they are frontmatter in each locale's own
  MDX file, which is why a translation can be added without touching code.
- Never fall back silently: `pick(localized)` returns `missing`, and the badge is what the reader
  sees. A new UI surface that shows titles must handle `missing`.
- `src/i18n/locales.ts` and `apps/lab/plugins/frontmatter.ts` both list the locales; `content:check`
  fails when they drift, because the generators and the app would otherwise disagree about which
  languages exist.
- Translation coverage after B17: every content page has a `.zh.mdx`. The demo write-ups added in
  B8-B16 are English-only on purpose — the sidebar's `EN` badge is the designed path for that, and
  keeping a visible set of untranslated demos is what stops the badge from rotting.

### Workflow

- English everywhere in the code (README, comments, identifiers, console output). MDX content is
  bilingual: the base file is English, `.zh.mdx` is the Chinese translation. Chinese learning notes
  still belong in the site repo under `docs/notes/`, not here.
- Work batch by batch: only one `doing`, and a batch only flips to `done` once its exit criteria were
  actually verified (DOM assertions, build output, test runs — not eyeballing screenshots).
- Don't pre-specify implementation details for future batches; write the goal and exit criteria only.
- This prototype stays out of the main repo's MkDocs build, CI, and Python toolchain by design.
