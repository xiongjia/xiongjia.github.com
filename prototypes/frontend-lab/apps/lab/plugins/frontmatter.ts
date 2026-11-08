import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { parse as parseYaml } from 'yaml'
import { z } from 'zod'

/*
 * Shared helpers for the generated-index plugins (`content-index`, `demo-registry`) and for the
 * quality gates (`content-check`).
 *
 * Frontmatter is the only metadata an author writes, so it is validated once, here, with a Zod
 * schema: the generators refuse to emit an index for an invalid file and the checks report every
 * violation in one pass instead of the first one they hit.
 */

const pluginDir = path.dirname(fileURLToPath(import.meta.url))

export const labRoot = path.resolve(pluginDir, '..') // apps/lab
export const prototypeRoot = path.resolve(labRoot, '../..') // frontend-lab

/**
 * The frontmatter contract: required `title` and `summary`, optional `order`.
 *
 * `strictObject` rejects unknown keys, so a typo (`summery:`) fails the build instead of silently
 * falling back to a generated label. Values are trimmed before the length checks, and every field
 * is rendered somewhere in the UI, which is why the limits are short.
 */
export const frontmatterSchema = z.strictObject({
  title: z.string().trim().min(1).max(80),
  summary: z.string().trim().min(1).max(180),
  order: z.number().int().default(0),
})

export type Frontmatter = z.infer<typeof frontmatterSchema>

/*
 * Locales. English is the canonical file (`design-tokens.mdx`); every other locale is a sibling
 * with a suffix (`design-tokens.zh.mdx`). Order matters: `en` is the fallback and the one the
 * generated indexes always require.
 */
export const locales = ['en', 'zh'] as const

export type Locale = (typeof locales)[number]

export const defaultLocale: Locale = 'en'

/** Split `foundations/design-tokens.zh` into its slug and locale. */
export function splitLocalePath(slug: string): { baseSlug: string; locale: Locale } {
  for (const locale of locales) {
    if (locale === defaultLocale) continue
    const suffix = `.${locale}`
    if (slug.endsWith(suffix)) return { baseSlug: slug.slice(0, -suffix.length), locale }
  }
  return { baseSlug: slug, locale: defaultLocale }
}

const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/

/** Path relative to the prototype root: short, stable and greppable in check output. */
export function relToPrototype(file: string): string {
  const relative = path.relative(prototypeRoot, file)
  if (relative.startsWith('..') || path.isAbsolute(relative)) return file.split(path.sep).join('/')
  return relative.split(path.sep).join('/')
}

/** `focus-and-keyboard` -> `Focus and keyboard`; used for group names. */
export function titleize(segment: string): string {
  return segment
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Kebab-case, matching the lab's file naming rule. */
export function isKebabCase(segment: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(segment)
}

export type FrontmatterResult =
  { ok: true; data: Frontmatter; body: string } | { ok: false; problems: string[]; body: string }

/** Split a document into frontmatter and body without interpreting either one. */
function splitFrontmatter(source: string): { yamlSource?: string; body: string } {
  const match = FRONTMATTER_PATTERN.exec(source)
  if (!match) return { body: source }
  return { yamlSource: match[1], body: source.slice(match[0].length) }
}

/**
 * Parse and validate frontmatter. Never throws: the caller decides whether to abort (generators) or
 * collect the problems (checks).
 */
export function readFrontmatterSource(source: string): FrontmatterResult {
  const { yamlSource, body } = splitFrontmatter(source)

  if (yamlSource === undefined) {
    return { ok: false, body, problems: ['missing frontmatter block (--- ... ---)'] }
  }

  let parsed: unknown
  try {
    parsed = parseYaml(yamlSource)
  } catch (error) {
    return { ok: false, body, problems: [`frontmatter is not valid YAML: ${String(error)}`] }
  }

  const result = frontmatterSchema.safeParse(parsed ?? {})
  if (!result.success) {
    // `prettifyError` emits one issue per line plus indented `→ at <path>` continuations; fold them
    // back together so each problem stays one entry in the check report.
    const problems: string[] = []
    for (const line of z.prettifyError(result.error).split('\n')) {
      const text = line.trim()
      if (text === '') continue
      if (text.startsWith('→') && problems.length > 0) {
        problems[problems.length - 1] = `${problems[problems.length - 1]} ${text}`
      } else {
        problems.push(text)
      }
    }
    return { ok: false, body, problems }
  }

  return { ok: true, data: result.data, body }
}

export async function readFrontmatterFile(file: string): Promise<FrontmatterResult> {
  return readFrontmatterSource(await readFile(file, 'utf8'))
}

/**
 * Generator path: read frontmatter and fail loudly on the first invalid file. Content editors hit
 * this on `pnpm dev` / `pnpm build`, so the message names the file and every problem in it.
 */
export async function requireFrontmatterFile(
  file: string,
): Promise<{ data: Frontmatter; body: string }> {
  const result = await readFrontmatterFile(file)
  if (!result.ok) {
    throw new Error(
      `Invalid frontmatter in ${relToPrototype(file)}:\n  ${result.problems.join('\n  ')}`,
    )
  }
  return { data: result.data, body: result.body }
}

/** Recursively list files with one of `extensions`, sorted for stable output. */
export async function walkFiles(dir: string, extensions: readonly string[]): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await walkFiles(fullPath, extensions)))
    } else if (entry.isFile() && extensions.some((extension) => entry.name.endsWith(extension))) {
      files.push(fullPath)
    }
  }

  return files
}

/** Every directory under `dir`, including `dir` itself. */
export async function walkDirs(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const dirs: string[] = [dir]

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.isDirectory()) dirs.push(...(await walkDirs(path.join(dir, entry.name))))
  }

  return dirs
}

/** Emit a single-quoted TS string literal. */
export function quote(value: string): string {
  return `'${value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

/** Path of `file` relative to the generated module's folder, as an import specifier. */
export function importSpecifier(fromFile: string, file: string, suffix = ''): string {
  const relative = path.relative(path.dirname(fromFile), file).split(path.sep).join('/')
  const specifier = `${relative.startsWith('.') ? relative : `./${relative}`}${suffix}`
  return quote(specifier)
}
