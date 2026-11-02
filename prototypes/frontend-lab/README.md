# Frontend Lab

An experimental lab for frontend techniques, driven by real UI scenarios. Not a component
library, and not a lighter Storybook: every experiment must run, expose its source and carry an MDX
write-up.

Core principle: **MDX explains, React components interact, single-library experiments prove a
technique, composed demos prove a real scenario.**

- Created: 2026-11-02
- Status: `experimental` (batch B1 done, MDX pipeline not built yet)
- Plan of record: the roadmap below (batches B1–B17). The discussion draft lives outside the repo.

## Quick start

```bash
pnpm install        # uses the China npm mirror configured in .npmrc
pnpm dev            # http://localhost:5173
pnpm check          # typecheck + eslint + prettier
pnpm build          # tsc --noEmit && vite build (dist in apps/lab/dist)
pnpm preview        # serve the production build
```

Requires Node >= 22.12 (`.nvmrc` pins 24) and pnpm 11.

## What works today (B1)

- pnpm workspace with one app (`apps/lab`) and one shared package (`packages/ui`)
- React 19 + React Router 7 + Vite 8 + Tailwind v4, TypeScript strict
- App shell: sidebar navigation, header, routed content area, 404 route
- Semantic design tokens in `packages/ui/src/styles/tokens.css` (light values only so far)
- `Button` + `cn()` in the shared package, consumed through a Vite alias (no package build step)
- One inline demo at `/demos/hello`: state, variants, sizes, keyboard focus rings
- Quality gate: `pnpm check` (typecheck, eslint, prettier) and `pnpm build`

Not built yet: MDX content, content index, demo registry, source view, error boundary, light/dark,
multiple styles, i18n, real experiments.

## Layout

```text
frontend-lab/
├── apps/lab/                 # the only web app
│   ├── src/app/              # router, layout, routes
│   ├── src/styles/app.css    # Tailwind entry + token import
│   └── vite.config.ts
├── packages/ui/              # shared components + token layer
│   └── src/{components,lib,styles}/
├── eslint.config.mjs
├── tsconfig.base.json
└── pnpm-workspace.yaml
```

Planned additions: `content/` (MDX), `packages/{mdx-runtime,editor,panels,charts,state}`,
`scripts/` (generators and content checks), `apps/lab/src/generated/` (generated registries).

## Roadmap

Status vocabulary: `done` / `doing` / `todo`. Only one batch may be `doing` at a time.

### Wave 1 · Shell and content loop

| #   | Batch        | Goal                                                                 | Exit criteria                                                                | Status |
| --- | ------------ | -------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------ |
| B1  | Shell        | workspace + Vite + Tailwind + router + layout                        | `pnpm dev` / `pnpm build` / `pnpm check` green, one interactive demo works   | done   |
| B2  | Content loop | MDX via `@mdx-js/rollup`, frontmatter, generated index               | adding an `.mdx` file makes it appear in the sidebar without code changes    | todo   |
| B3  | Demo system  | registry generator, DemoShell (Preview/Source/Notes), error boundary | 3 real demos, source visible and copyable, a failing demo breaks only itself | todo   |

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
