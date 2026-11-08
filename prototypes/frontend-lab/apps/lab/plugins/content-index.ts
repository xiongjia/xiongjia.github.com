import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import type { Plugin } from 'vite'

import {
  importSpecifier,
  labRoot,
  locales,
  quote,
  requireFrontmatterFile,
  splitLocalePath,
  titleize,
  walkFiles,
  type Locale,
} from './frontmatter.ts'
import { createIndexPlugin } from './index-plugin.ts'

/*
 * Content index generator.
 *
 * The lab keeps its pages as MDX under `content/`. Nothing in the app hard-codes a page list: this
 * module scans the folder, reads each file's frontmatter and writes a typed module
 * (`src/generated/content-index.ts`) that the sidebar, the home page and the router consume.
 *
 * Localisation is file-based: `design-tokens.mdx` is English, `design-tokens.zh.mdx` is the
 * Chinese sibling of the same page. Both land on one slug with per-locale metadata and per-locale
 * lazy imports, so switching language swaps the MDX chunk without touching the registry.
 *
 * Runs in three places:
 *   - `vite` dev/build, through `contentIndexPlugin()`
 *   - `pnpm content:index`, as a CLI (so `tsc --noEmit` always sees the file)
 *   - `plugins/content-check.ts`, which reuses `scanContent()` to prove the frontmatter is valid
 */

export const defaultContentDir = path.join(labRoot, 'content')
export const defaultOutFile = path.join(labRoot, 'src/generated/content-index.ts')

/** Group id used for pages that sit directly in `content/`. */
const ROOT_GROUP_ID = 'general'

/** One locale of a page, as the generator sees it. */
export type LocaleSource = {
  title: string
  summary: string
  order: number
  file: string
}

/** One MDX page (all its locales), as the generator sees it. */
export type ContentPageSource = {
  /** Route path without extension or locale: `foundations/design-tokens`. */
  slug: string
  order: number
  group: string
  locales: { en: LocaleSource; zh?: LocaleSource }
}

export type GenerateOptions = {
  contentDir?: string
  outFile?: string
}

function comparePages(a: ContentPageSource, b: ContentPageSource): number {
  if (a.group !== b.group) return a.group.localeCompare(b.group)
  if (a.order !== b.order) return a.order - b.order
  return a.locales.en.title.localeCompare(b.locales.en.title)
}

/** Read every `.mdx` file under `contentDir` and group it by slug and locale. */
export async function scanContent(
  contentDir: string = defaultContentDir,
): Promise<ContentPageSource[]> {
  const files = await walkFiles(contentDir, ['.mdx'])

  type PageEntries = { group: string; locales: Partial<Record<Locale, LocaleSource>> }
  const entries = new Map<string, PageEntries>()

  for (const file of files) {
    const relativePath = path.relative(contentDir, file).split(path.sep).join('/')
    const { baseSlug, locale } = splitLocalePath(relativePath.replace(/\.mdx$/, ''))
    const segments = baseSlug.split('/')
    const group = segments.length > 1 ? String(segments[0]) : ROOT_GROUP_ID

    // Throws on invalid frontmatter: the schema is the contract, not a suggestion.
    const { data } = await requireFrontmatterFile(file)

    const entry = entries.get(baseSlug) ?? { group, locales: {} }
    entry.locales[locale] = {
      title: data.title,
      summary: data.summary,
      order: data.order,
      file,
    }
    entries.set(baseSlug, entry)
  }

  const pages: ContentPageSource[] = []
  for (const [slug, entry] of entries) {
    const en = entry.locales.en
    if (!en) {
      throw new Error(
        `Missing English page for '${slug}': every locale needs a base .mdx file (found: ${locales
          .filter((locale) => entry.locales[locale])
          .join(', ')})`,
      )
    }

    pages.push({
      slug,
      // English owns the sort key; a translated file never moves the sidebar on its own.
      order: en.order,
      group: entry.group,
      locales: { en, zh: entry.locales.zh },
    })
  }

  return pages.sort(comparePages)
}

/** Render one locale property of a page (indented for the generated module). */
function renderLocale(key: Locale, entry: LocaleSource, outFile: string): string {
  return `      ${key}: {
        title: ${quote(entry.title)},
        summary: ${quote(entry.summary)},
        load: () => import(${importSpecifier(outFile, entry.file)}),
      },`
}

/** Render the generated `content-index.ts` source for the given pages. */
export function renderIndex(
  pages: ContentPageSource[],
  { outFile = defaultOutFile }: GenerateOptions = {},
): string {
  const groupIds = [...new Set(pages.map((page) => page.group))]

  const pageEntries = pages.map((page) => {
    const zh = page.locales.zh ? `\n${renderLocale('zh', page.locales.zh, outFile)}` : ''
    return `  {
    slug: ${quote(page.slug)},
    order: ${page.order},
    group: ${quote(page.group)},
    locales: {
${renderLocale('en', page.locales.en, outFile)}${zh}
    },
  },`
  })

  const groupEntries = groupIds.map(
    (id) => `  {
    id: ${quote(id)},
    title: ${quote(titleize(id))},
    pages: contentPages.filter((page) => page.group === ${quote(id)}),
  },`,
  )

  return `/* eslint-disable */
// Generated by apps/lab/plugins/content-index.ts — do not edit by hand.
// Regenerated by \`vite\` (dev/build) and by \`pnpm content:index\`.

import type { ComponentType } from 'react'

export type Locale = ${locales.map((locale) => quote(locale)).join(' | ')}

export const locales: Locale[] = [${locales.map((locale) => quote(locale)).join(', ')}]

export type ContentLocaleEntry = {
  title: string
  summary: string
  /** The MDX module for this locale. */
  load: () => Promise<{ default: ComponentType }>
}

export type ContentPage = {
  /** Route path without extension, e.g. \`foundations/design-tokens\`. */
  slug: string
  /** Sort key inside the group; always taken from the English file. */
  order: number
  /** Top-level folder inside \`content/\`. */
  group: string
  /** English is always present; a translation is only present once its file exists. */
  locales: { en: ContentLocaleEntry; zh?: ContentLocaleEntry }
}

export type ContentGroup = {
  id: string
  title: string
  pages: ContentPage[]
}

export const contentPages: ContentPage[] = [
${pageEntries.join('\n')}
]

export const contentGroups: ContentGroup[] = [
${groupEntries.join('\n')}
]

export function findContentPage(slug: string): ContentPage | undefined {
  return contentPages.find((page) => page.slug === slug)
}

export function findContentGroup(id: string): ContentGroup | undefined {
  return contentGroups.find((group) => group.id === id)
}
`
}

/** Scan `content/` and write the generated index module. */
export async function writeContentIndex(
  options: GenerateOptions = {},
): Promise<{ pages: ContentPageSource[]; outFile: string }> {
  const contentDir = options.contentDir ?? defaultContentDir
  const outFile = options.outFile ?? defaultOutFile
  const pages = await scanContent(contentDir)

  await mkdir(path.dirname(outFile), { recursive: true })
  await writeFile(outFile, renderIndex(pages, { outFile }), 'utf8')

  return { pages, outFile }
}

/**
 * Vite plugin: regenerate the index before each dev/build, and again whenever an `.mdx` file under
 * `content/` is added, edited or deleted. Editing content therefore needs no code change at all.
 */
export function contentIndexPlugin(options: GenerateOptions = {}): Plugin {
  const contentDir = options.contentDir ?? defaultContentDir
  const outFile = options.outFile ?? defaultOutFile

  return createIndexPlugin({
    name: 'frontend-lab:content-index',
    watchDir: contentDir,
    isRelevant: (file) => {
      const relative = path.relative(contentDir, file)
      return relative !== '' && !relative.startsWith('..') && file.endsWith('.mdx')
    },
    generate: async () => {
      const { pages } = await writeContentIndex({ contentDir, outFile })
      return { label: 'content index', count: pages.length }
    },
  })
}

const invokedDirectly =
  process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  const { pages, outFile } = await writeContentIndex()
  console.log(
    `content index: ${pages.length} page(s) from ${path.relative(process.cwd(), defaultContentDir)} ` +
      `-> ${path.relative(process.cwd(), outFile)}`,
  )
}
