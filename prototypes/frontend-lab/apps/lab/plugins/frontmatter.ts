import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { parse as parseYaml } from 'yaml'

/*
 * Shared helpers for the generated-index plugins (`content-index`, `demo-registry`).
 *
 * Both read frontmatter from Markdown/MDX files and write a typed module the app imports. B4 reuses
 * the same readers for the content checks, so parsing lives here once.
 */

const pluginDir = path.dirname(fileURLToPath(import.meta.url))

export const labRoot = path.resolve(pluginDir, '..') // apps/lab
export const prototypeRoot = path.resolve(labRoot, '../..') // frontend-lab

/** Frontmatter fields the generators understand (B4 replaces this with a Zod schema). */
export type Frontmatter = {
  title?: unknown
  summary?: unknown
  order?: unknown
}

const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/

/** `focus-and-keyboard` -> `Focus and keyboard`; used for titles and group names. */
export function titleize(segment: string): string {
  return segment
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function readFrontmatter(source: string, file: string): Frontmatter {
  const match = FRONTMATTER_PATTERN.exec(source)
  const yamlSource = match?.[1]
  if (!yamlSource) return {}

  let parsed: unknown
  try {
    parsed = parseYaml(yamlSource)
  } catch (error) {
    throw new Error(
      `Invalid frontmatter in ${path.relative(prototypeRoot, file)}: ${String(error)}`,
      { cause: error },
    )
  }

  return parsed !== null && typeof parsed === 'object' ? (parsed as Frontmatter) : {}
}

export async function readFrontmatterFile(file: string): Promise<Frontmatter> {
  return readFrontmatter(await readFile(file, 'utf8'), file)
}

export function readText(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined
}

export function readOrder(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
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

/** Quote a maybe-undefined summary as a TS property line, or nothing. */
export function renderSummary(value: string | undefined): string {
  return value ? `\n    summary: ${quote(value)},` : ''
}
