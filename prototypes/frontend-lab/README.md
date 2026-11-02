# Frontend Lab

An experimental lab for frontend techniques, driven by real UI scenarios. Not a component
library, and not a lighter Storybook: every experiment must run, expose its source and carry an MDX
write-up.

Core principle: **MDX explains, React components interact, single-library experiments prove a
technique, composed demos prove a real scenario.**

- Created: 2026-11-02
- Status: `experimental` (vertical-slice MVP reached at B3: shell + content loop + demo system)
- Plan of record: the roadmap below (batches B1–B17). The discussion draft lives outside the repo.

## Quick start

```bash
pnpm install        # uses the China npm mirror configured in .npmrc
pnpm dev            # http://localhost:5173
pnpm generate       # regenerate src/generated/* by hand (dev/build do it too)
pnpm check          # typecheck + eslint + prettier
pnpm build          # content index + tsc --noEmit + vite build (dist in apps/lab/dist)
pnpm preview        # serve the production build
```

Requires Node >= 22.12 (`.nvmrc` pins 24) and pnpm 11.

## What works today (B3)

- pnpm workspace with one app (`apps/lab`) and one shared package (`packages/ui`)
- React 19 + React Router 7 + Vite 8 + Tailwind v4, TypeScript strict
- App shell: sidebar navigation (content and demos merged into one topic tree), header, routed
  content area, 404 route
- Semantic design tokens in `packages/ui/src/styles/tokens.css` (light values only so far)
- `Button` + `cn()` in the shared package, consumed through a Vite alias (no package build step)
- **Content loop**: MDX pages under `apps/lab/content/`, frontmatter-driven metadata, a generated
  index, and a sidebar + home list derived from it — adding an `.mdx` file needs no code change
- **Demo system**: demo folders under `demos/`, a generated registry, a Preview / Source / Notes shell
  (source is the real file, copyable), and a per-demo error boundary so one crash cannot take the page
  down — three real demos ship today
- Quality gate: `pnpm check` (typecheck, eslint, prettier) and `pnpm build`

Not built yet: frontmatter schema + content checks, light/dark, multiple styles, i18n, the single
library experiments (B8-B12) and the composed scenarios (B13-B17).

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

| Frontmatter | Required | Meaning                                                        |
| ----------- | -------- | -------------------------------------------------------------- |
| `title`     | no       | Sidebar label and page heading; falls back to the file name    |
| `summary`   | no       | One-liner used on the home page and as the page subtitle       |
| `order`     | no       | Sort key inside the section (default `0`, ties break by title) |

Section titles come from the folder name (`foundations` -> `Foundations`), sections sort
alphabetically, and pages sort by `order` then title. `pnpm dev` picks up add/edit/delete of `.mdx`
files immediately (full reload); `pnpm build` and `pnpm content:index` regenerate the same index on
demand.

## Adding a demo

A demo is a folder — no registration anywhere:

```text
apps/lab/demos/foundations/button-variants/
├── demo.tsx     # default export = the component that renders in Preview
└── notes.mdx    # frontmatter (title/summary/order) + the write-up in the Notes tab
```

- URL: `/demos/foundations/button-variants`; sidebar entry: under **Foundations**, with a `demo` badge
- `demo.tsx` may import from `@frontend-lab/ui`, `@/…` or plain React — it is just a component
- `notes.mdx` is optional; without it the Notes tab disappears (the folder name is then the label)
- The Source tab shows the _actual_ `demo.tsx` (imported with `?raw`), so it can never drift
- A crashing demo is contained by `DemoErrorBoundary`; tabs, source and other demos keep working

## Layout

```text
frontend-lab/
├── apps/lab/                 # the only web app
│   ├── content/              # MDX pages, grouped by folder
│   │   ├── foundations/
│   │   └── interactions/
│   ├── demos/                # <group>/<demo>/{demo.tsx,notes.mdx}
│   ├── plugins/              # generators: content-index.ts, demo-registry.ts (+ shared helpers)
│   ├── src/app/              # router, layout, nav adapter, routes
│   ├── src/components/       # DemoShell, DemoPreview, DemoSource, DemoErrorBoundary
│   ├── src/generated/        # content-index.ts + demo-registry.ts (generated, git-ignored)
│   ├── src/styles/           # app.css (Tailwind entry) + mdx.css (content typography)
│   └── vite.config.ts
├── packages/ui/              # shared components + token layer
│   └── src/{components,lib,styles}/
├── eslint.config.mjs
├── tsconfig.base.json
└── pnpm-workspace.yaml
```

Planned additions: `packages/{mdx-runtime,editor,panels,charts,state}`, `scripts/` (content checks
from B4 on).

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
| B4  | Quality gates   | Zod frontmatter schema, content/demo checks, boundary lint zones | four deliberate mistakes are all rejected by `pnpm check`              | todo   |
| B5  | Theme           | tokens split, light/dark switch, persisted prefs, no FOUC        | reload keeps the choice, no flash, all demos follow the mode           | todo   |
| B6  | Multiple styles | shadcn style presets, style token check, token playground        | switching a style updates the whole site and every demo                | todo   |
| B7  | i18n            | typed dictionaries, bilingual MDX, missing-translation badge     | switching to `zh` translates UI and content, untranslated pages marked | todo   |

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

### Workflow

- English everywhere in this folder (README, code, comments, MDX). Chinese learning notes belong in
  the site repo under `docs/notes/`, not here.
- Work batch by batch: only one `doing`, and a batch only flips to `done` once its exit criteria were
  actually verified (DOM assertions, build output, test runs — not eyeballing screenshots).
- Don't pre-specify implementation details for future batches; write the goal and exit criteria only.
- This prototype stays out of the main repo's MkDocs build, CI, and Python toolchain by design.
