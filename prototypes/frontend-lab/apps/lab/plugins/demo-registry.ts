import { mkdir, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import type { Plugin } from 'vite'

import {
  defaultLocale,
  importSpecifier,
  labRoot,
  locales,
  quote,
  requireFrontmatterFile,
  titleize,
  type Locale,
} from './frontmatter.ts'
import { createIndexPlugin } from './index-plugin.ts'

/*
 * Demo registry generator.
 *
 * A demo is a folder under `demos/` containing `demo.tsx` (default export = the component) and,
 * usually, `notes.mdx` (frontmatter + the write-up shown in the Notes tab):
 *
 *   demos/foundations/button-variants/
 *   ├── demo.tsx
 *   ├── notes.mdx        English write-up + labels
 *   └── notes.zh.mdx     Chinese write-up + labels (optional)
 *
 * The folder path becomes the slug (`foundations/button-variants` ->
 * `/demos/foundations/button-variants`), the top-level folder becomes the group, and each locale's
 * notes supply that locale's label. Everything is lazy: component, raw source and each locale's
 * notes are separate dynamic imports, so a page only pays for what it opens.
 */

export const defaultDemosDir = path.join(labRoot, 'demos')
export const defaultOutFile = path.join(labRoot, 'src/generated/demo-registry.ts')

/** Group id used for demos that sit directly in `demos/`. */
const ROOT_GROUP_ID = 'general'

const DEMO_FILE = 'demo.tsx'

/** Locale-independent file name of the write-up for a locale. */
export function notesFileName(locale: Locale): string {
  return locale === defaultLocale ? 'notes.mdx' : `notes.${locale}.mdx`
}

/** One locale of a demo, as the generator sees it. */
export type DemoLocaleSource = {
  title: string
  summary: string
  notesFile?: string
}

/** One demo folder, as the generator sees it. */
export type DemoSource = {
  slug: string
  order: number
  group: string
  demoFile: string
  locales: { en: DemoLocaleSource; zh?: DemoLocaleSource }
}

export type GenerateOptions = {
  demosDir?: string
  outFile?: string
}

function compareDemos(a: DemoSource, b: DemoSource): number {
  if (a.group !== b.group) return a.group.localeCompare(b.group)
  if (a.order !== b.order) return a.order - b.order
  return a.locales.en.title.localeCompare(b.locales.en.title)
}

/** Find every folder that contains a `demo.tsx`; nested folders are not descended into. */
async function findDemoDirs(
  dir: string,
): Promise<{ file: string; notes: Partial<Record<Locale, string>> }[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const names = new Set(entries.filter((entry) => entry.isFile()).map((entry) => entry.name))

  if (names.has(DEMO_FILE)) {
    const notes: Partial<Record<Locale, string>> = {}
    for (const locale of locales) {
      const name = notesFileName(locale)
      if (names.has(name)) notes[locale] = path.join(dir, name)
    }
    return [{ file: path.join(dir, DEMO_FILE), notes }]
  }

  const found: { file: string; notes: Partial<Record<Locale, string>> }[] = []
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue
    found.push(...(await findDemoDirs(path.join(dir, entry.name))))
  }
  return found
}

/** Read every demo folder under `demosDir` and return its metadata, sorted for the sidebar. */
export async function scanDemos(demosDir: string = defaultDemosDir): Promise<DemoSource[]> {
  const found = await findDemoDirs(demosDir)

  const demos = await Promise.all(
    found.map(async ({ file, notes }): Promise<DemoSource> => {
      const folder = path.dirname(file)
      const slug = path.relative(demosDir, folder).split(path.sep).join('/')
      const segments = slug.split('/')
      const folderName = segments.at(-1) ?? slug
      const group = segments.length > 1 ? String(segments[0]) : ROOT_GROUP_ID
      const fallbackTitle = titleize(folderName)

      const sources: { en: DemoLocaleSource; zh?: DemoLocaleSource } = {
        en: { title: fallbackTitle, summary: '' },
      }
      const orders: Partial<Record<Locale, number>> = {}

      for (const locale of locales) {
        const notesFile = notes[locale]
        if (!notesFile) continue
        // Notes carry the label; the English write-up is required by the content check.
        const { data } = await requireFrontmatterFile(notesFile)
        sources[locale] = { title: data.title, summary: data.summary, notesFile }
        orders[locale] = data.order
      }

      return {
        slug,
        // English owns the sort key, like content pages.
        order: orders.en ?? 0,
        group,
        demoFile: file,
        locales: sources,
      }
    }),
  )

  return demos.sort(compareDemos)
}

/** Render one locale property of a demo (indented for the generated module). */
function renderLocale(key: Locale, entry: DemoLocaleSource, outFile: string): string {
  const notes = entry.notesFile
    ? `\n        loadNotes: () => import(${importSpecifier(outFile, entry.notesFile)}),`
    : ''

  return `      ${key}: {
        title: ${quote(entry.title)},
        summary: ${quote(entry.summary)},${notes}
      },`
}

/** Render the generated `demo-registry.ts` source for the given demos. */
export function renderRegistry(
  demos: DemoSource[],
  { outFile = defaultOutFile }: GenerateOptions = {},
): string {
  const groupIds = [...new Set(demos.map((demo) => demo.group))]

  const demoEntries = demos.map((demo) => {
    const zh = demo.locales.zh ? `\n${renderLocale('zh', demo.locales.zh, outFile)}` : ''
    return `  {
    slug: ${quote(demo.slug)},
    order: ${demo.order},
    group: ${quote(demo.group)},
    load: () => import(${importSpecifier(outFile, demo.demoFile)}),
    loadSource: () => import(${importSpecifier(outFile, demo.demoFile, '?raw')}),
    locales: {
${renderLocale('en', demo.locales.en, outFile)}${zh}
    },
  },`
  })

  const groupEntries = groupIds.map(
    (id) => `  {
    id: ${quote(id)},
    title: ${quote(titleize(id))},
    demos: demos.filter((demo) => demo.group === ${quote(id)}),
  },`,
  )

  return `/* eslint-disable */
// Generated by apps/lab/plugins/demo-registry.ts — do not edit by hand.
// Regenerated by \`vite\` (dev/build) and by \`pnpm demos:index\`.

import type { ComponentType } from 'react'

export type Locale = ${locales.map((locale) => quote(locale)).join(' | ')}

export const locales: Locale[] = [${locales.map((locale) => quote(locale)).join(', ')}]

export type DemoLocaleEntry = {
  title: string
  summary: string
  /** The write-up for this locale; absent until the translation exists. */
  loadNotes?: () => Promise<{ default: ComponentType }>
}

export type Demo = {
  /** Folder path inside \`demos/\`, e.g. \`foundations/button-variants\`. */
  slug: string
  /** Sort key inside the group; always taken from the English notes. */
  order: number
  /** Top-level folder inside \`demos/\`. */
  group: string
  /** The demo component (\`demo.tsx\` default export) — code is not localised. */
  load: () => Promise<{ default: ComponentType }>
  /** Raw \`demo.tsx\` text for the Source tab. */
  loadSource: () => Promise<{ default: string }>
  /** Per-locale labels and write-ups. */
  locales: { en: DemoLocaleEntry; zh?: DemoLocaleEntry }
}

export type DemoGroup = {
  id: string
  title: string
  demos: Demo[]
}

export const demos: Demo[] = [
${demoEntries.join('\n')}
]

export const demoGroups: DemoGroup[] = [
${groupEntries.join('\n')}
]

export function findDemo(slug: string): Demo | undefined {
  return demos.find((demo) => demo.slug === slug)
}

export function findDemoGroup(id: string): DemoGroup | undefined {
  return demoGroups.find((group) => group.id === id)
}
`
}

/** Scan `demos/` and write the generated registry module. */
export async function writeDemoRegistry(
  options: GenerateOptions = {},
): Promise<{ demos: DemoSource[]; outFile: string }> {
  const demosDir = options.demosDir ?? defaultDemosDir
  const outFile = options.outFile ?? defaultOutFile
  const demos = await scanDemos(demosDir)

  await mkdir(path.dirname(outFile), { recursive: true })
  await writeFile(outFile, renderRegistry(demos, { outFile }), 'utf8')

  return { demos, outFile }
}

/**
 * Vite plugin: regenerate the registry on start/build, and on every add / change / unlink inside
 * `demos/`, so a new demo appears without touching any code.
 */
export function demoRegistryPlugin(options: GenerateOptions = {}): Plugin {
  const demosDir = options.demosDir ?? defaultDemosDir
  const outFile = options.outFile ?? defaultOutFile

  return createIndexPlugin({
    name: 'frontend-lab:demo-registry',
    watchDir: demosDir,
    isRelevant: (file) => {
      const relative = path.relative(demosDir, file)
      return relative !== '' && !relative.startsWith('..')
    },
    generate: async () => {
      const { demos } = await writeDemoRegistry({ demosDir, outFile })
      return { label: 'demo registry', count: demos.length }
    },
  })
}

const invokedDirectly =
  process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  const { demos, outFile } = await writeDemoRegistry()
  console.log(
    `demo registry: ${demos.length} demo(s) from ${path.relative(process.cwd(), defaultDemosDir)} ` +
      `-> ${path.relative(process.cwd(), outFile)}`,
  )
}
