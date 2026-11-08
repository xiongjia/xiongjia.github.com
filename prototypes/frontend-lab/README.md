# Frontend Lab

An experimental lab for frontend techniques, driven by real UI scenarios. Not a component
library, and not a lighter Storybook: every experiment must run, expose its source and carry an MDX
write-up.

Core principle: **MDX explains, React components interact, single-library experiments prove a
technique, composed demos prove a real scenario.**

- Created: 2026-11-02
- Status: `experimental` (Wave 2 reached at B7: shell, content loop, demo system, quality gates,
  theme, style presets, i18n)
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
```

Requires Node >= 22.12 (`.nvmrc` pins 24) and pnpm 11.

## What works today (B7)

- pnpm workspace with one app (`apps/lab`) and one shared package (`packages/ui`)
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
  down — five demos ship today
- **Quality gates**: `pnpm check` = generate + typecheck + `content:check` + `style:check` + eslint +
  prettier + `node:test`; `pnpm build` runs the same checks before `vite build`

Not built yet: the single-library experiments (B8-B12) and the composed scenarios (B13-B17).

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
│   │   │                     #   (content-check, style-check) + their node:test files
│   ├── src/app/              # router, layout, nav builder, routes
│   ├── src/components/       # DemoShell, DemoPreview, DemoSource, error boundary, header controls
│   ├── src/generated/        # content-index.ts + demo-registry.ts (generated, git-ignored)
│   ├── src/i18n/             # locales, typed dictionaries, provider + hook, locale selector
│   ├── src/prefs/            # persisted preference store (theme, style, locale)
│   ├── src/styles/           # app.css (Tailwind entry) + mdx.css (content typography)
│   └── vite.config.ts
├── packages/ui/              # shared components + token layer
│   └── src/
│       ├── components/       # button, segmented-control
│       ├── lib/              # cn()
│       └── styles/           # palette.css, tokens.css, styles.css
├── eslint.config.mjs         # incl. boundary zones between app / demos / ui / plugins
├── tsconfig.base.json
└── pnpm-workspace.yaml
```

Planned additions: `packages/{mdx-runtime,editor,panels,charts,state}`.

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
| B8  | Tailwind deep dive | `@container`, `has-*`, variant rules, keyframes vs Motion | at least 5 experiments, each with conclusions | todo   |
| B9  | CodeMirror         | minimal editor, theme/shortcuts, decorations/transactions | 3 MDX pages + 3 demos                         | todo   |
| B10 | Panels             | resizable layout, keyboard resize, persisted sizes        | layout survives reload, keyboard path works   | todo   |
| B11 | Zustand            | store factory, selectors, derived state, per-instance     | demos share the factory, no global singletons | todo   |
| B12 | Motion + dnd-kit   | variants/layout/gestures, sensors/collision/sortable      | keyboard sensor verified for every drag demo  | todo   |

### Wave 4 · Composed scenarios

| #   | Batch             | Goal                                            | Exit criteria                               | Status |
| --- | ----------------- | ----------------------------------------------- | ------------------------------------------- | ------ |
| B13 | IDE Workspace     | editor + panels + file tree + sync (splittable) | contract doc + integration test             | todo   |
| B14 | Kanban            | drag + state + animation                        | drag, persistence and keyboard all work     | todo   |
| B15 | Dashboard Builder | charts + drag layout, chart library comparison  | comparison experiment with recorded numbers | todo   |
| B16 | Command Palette   | keyboard interaction, search, shortcuts         | focus management verified                   | todo   |
| B17 | Polish            | Playwright suite, axe matrix, bundle report     | critical paths green, baseline recorded     | todo   |

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

| Step            | Owns                                                                         |
| --------------- | ---------------------------------------------------------------------------- |
| `typecheck`     | types, and the generated index shape after `pnpm generate`                   |
| `content:check` | frontmatter schema, naming, body rules, demo folder rules, translation pairs |
| `style:check`   | palette / tokens / preset blocks / preset list agreement                     |
| `lint`          | boundary zones (app / demos / ui / plugins) + React rules                    |
| `format:check`  | Prettier                                                                     |
| `test`          | `node:test` unit tests for both check modules, on temp fixtures              |

A check is a module that exports a function returning problems plus a thin CLI wrapper; that is what
lets the tests call the same code path as `pnpm check`. Every rule in the table exists because a real
mistake got past the previous gate — add a rule only with a fixture that fails without it.

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

### Workflow

- English everywhere in the code (README, comments, identifiers, console output). MDX content is
  bilingual: the base file is English, `.zh.mdx` is the Chinese translation. Chinese learning notes
  still belong in the site repo under `docs/notes/`, not here.
- Work batch by batch: only one `doing`, and a batch only flips to `done` once its exit criteria were
  actually verified (DOM assertions, build output, test runs — not eyeballing screenshots).
- Don't pre-specify implementation details for future batches; write the goal and exit criteria only.
- This prototype stays out of the main repo's MkDocs build, CI, and Python toolchain by design.
