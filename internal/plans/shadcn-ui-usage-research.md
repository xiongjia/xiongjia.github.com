---
title: shadcn/ui Usage Research (from environment to basic usage)
created: 2026-08-17
updated: 2026-08-26
status: in-progress
tags: [shadcn, research, frontend, usage]
---

# shadcn/ui Usage Research (from environment to basic usage)

## Goal

Refactor `docs/notes/research/topics/shadcn-ui/`: **stop studying source code**,
switch to a hands-on research path modeled on the DuckDB / Protomaps topics —
from environment setup to basic usage, producing 2–3 practical documents.
The old "source code reading guide" is replaced.

## Tasks

- [x] **Replace the old topic index**

  - Rewritten `docs/notes/research/topics/shadcn-ui/index.md` as a usage
    research index: version snapshot (2026-08-26 hand-on), Sub Topics table,
    recommended reading order, key findings summary
  - Removed the "clone the repo / read CLI & Registry source" content
  - Structure modeled on `duckdb/` and `protomaps/` topic layouts

- [x] **Doc 1: Environment & init** → `setup.md`

  - Stack finalized: TypeScript **7.0.2** (the main `typescript` compiler,
    per current major version)
  - Hand-on flow: `pnpm create vite` (react-ts) → upgrade TS to ^7.0.2 →
    `pnpm add tailwindcss @tailwindcss/vite tw-animate-css` → Tailwind v4 via
    vite plugin + CSS-first (`@import "tailwindcss"`, no tailwind.config.js) →
    relative `paths` (no `baseUrl`) → `pnpm dlx shadcn@latest init -d`
  - `components.json` field-by-field explanation (style=base-nova, rsc,
    tailwind/cssVariables, iconLibrary, aliases, menuColor/menuAccent,
    registries)
  - Generated files: `components/ui/*`, `lib/utils.ts` (cn()), index.css
    additions (@import shadcn/tailwind.css, Geist font, @custom-variant dark,
    oklch variables, --radius scale)

- [x] **Doc 2: Adding & using components** → `components.md`

  - `add` usage: multiple components in one call, flags (-y/-o/--all/-p/
    --dry-run/--diff)
  - Automatic dependency resolution: registryDependencies (field → label +
    separator; dialog → button) and npm deps (sonner, next-themes)
  - Common components checklist with minimal examples (button/card/dialog/
    field/input/tabs/table/badge/sonner)
  - **v4 / Base UI paradigm shift**: `render={<Button/>}` replaces Radix
    `asChild` (verified: passing it is a type error); `Field` is a composition of
    child components (FieldLabel/FieldContent/FieldError), not label/error
    props
  - Customization basics: edit source, CVA variants, cn()

- [x] **Doc 3: Advanced topics** → `advanced.md`

  - Updating components: `add --diff` (old `diff` command deprecated),
    `--overwrite`, `--dry-run`
  - Theming: oklch CSS variables, `--radius` scale, dark mode
    (@custom-variant dark + .dark class), Geist font, menuColor/menuAccent
  - Form integration: react-hook-form + zod + Field (hand-on, passes strict
    `tsc -b`)
  - Registry mechanics: registry.json structure (name/homepage/items, 216
    items measured), style URL, `search @shadcn` namespace, item types
    (ui/example/block)
  - Framework differences: Vite (rsc:false) vs Next.js (rsc:true) vs Astro
  - Compiler note: full-stack type check passed (`tsc -b`), `vite build`
    2.2–2.6s

- [ ] **Custom registry hands-on** (optional follow-up)

  - Not yet measured: publishing a local custom registry (CLI `build` /
    `registry` / `preset` / `apply` commands, components.json `registries`
    field). Keep the docs honest — currently referenced with official docs
    links only

- [x] **Maintain indexes & cross-references**

  - `docs/notes/research/index.md`: shadcn/ui moved from Drafts to the main
    table, status `polished`, description now "usage research"
  - `docs/projects/index.md`: seedling Pipeline description synced
  - `docs/notes/collection/frontend.md`: added shadcn/ui entry + backlink

## Notes

- Old doc `docs/notes/research/topics/shadcn-ui/index.md` (source-reading
  guide, 7.6K) was fully replaced; `external/shadcn-ui` clone is no longer a
  research target (the dir itself stays under `external/`, never committed,
  nothing to delete)
- Hands-on project lives at `external/shadcn-demo/` (git-ignored, not
  committed), accessible for development reference. Full stack: pnpm 11.4 /
  Vite 8.2.2 / React 19.2.8 / TypeScript 7.0.2 / Tailwind 4.3.3 / shadcn CLI
  4.19.0 (style=base-nova, @base-ui/react 1.7.0) / lucide-react 1.34.0
- Measured pitfalls recorded in the docs:
  1. `init` does not auto-install Tailwind — must pre-install Tailwind v4 +
     `@import "tailwindcss"` + valid `@/*` alias, else "No Tailwind CSS
     configuration found" / "Could not find valid path aliases"
  1. Path aliases: use relative `paths` (`"./src/*"`), no `baseUrl`
  1. v4.19 writes components to a literal root-level `@/components/ui/`
     directory under Vite 8 solution-style tsconfig (alias not resolved on
     disk) — manually `mv` to `src/components/ui/`; component code builds
     fine either way
  1. `add form` is a silent no-op: the `form` registry item has empty files
     (stub); the real form component is `field` (Base UI Field)
  1. `search` needs an explicit namespace (`shadcn search @shadcn -q ...`),
     default reports "No registries are configured"
- Doc format follows duckdb/protomaps: frontmatter (title/tags/categories) +
  measured version notes + tables + code blocks + cross-doc links; validated
  with `uv run mdformat --check`
- No visual verification needed (CLI/file-structure topic); if rendering
  checks are needed later, use DOM verification, not screenshots

## References

- [shadcn/ui docs](https://ui.shadcn.com/docs)
- [shadcn/ui installation](https://ui.shadcn.com/docs/installation)
- [shadcn/ui Topic](../../docs/notes/research/topics/shadcn-ui/)
- [DuckDB Topic (structure reference)](../../docs/notes/research/topics/duckdb/index.md)
- [Protomaps Topic (structure reference)](../../docs/notes/research/topics/protomaps/index.md)
