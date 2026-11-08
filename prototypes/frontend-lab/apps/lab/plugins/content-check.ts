import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  defaultLocale,
  isKebabCase,
  labRoot,
  locales,
  readFrontmatterSource,
  relToPrototype,
  splitLocalePath,
  walkDirs,
  walkFiles,
  type Locale,
} from './frontmatter.ts'
import { notesFileName } from './demo-registry.ts'

/*
 * Content and demo quality gates.
 *
 * The generators accept anything the filesystem gives them; this module is the part that refuses
 * the mistakes an author actually makes:
 *
 *   - frontmatter that does not satisfy the Zod schema (missing title, wrong type, unknown key)
 *   - a body that starts at `#` (the page renders its own title, so the body must start at `##`)
 *   - a demo folder without a default export, without a write-up, or with stray files
 *   - file and folder names that are not lowercase kebab-case
 *   - a translation without its English base file, or a locale list that drifted from the plugins
 *
 * Every problem is collected before failing, in one run, with a path relative to the prototype root.
 * `pnpm content:check` runs this from the CLI; `pnpm check` and `pnpm build` run that.
 */

export type Problem = {
  /** Path relative to the prototype root; absent for cross-cutting problems. */
  file?: string
  message: string
}

export type CheckStats = {
  pages: number
  demos: number
}

export type CheckResult = {
  problems: Problem[]
  stats: CheckStats
}

export type CheckOptions = {
  contentDir?: string
  demosDir?: string
  /** File that lists the app's locales; defaults to the lab's own list. */
  appLocalesFile?: string
}

const DEMO_FILE = 'demo.tsx'

/** Every file name a demo folder may contain. */
const allowedDemoFiles = new Set([DEMO_FILE, ...locales.map((locale) => notesFileName(locale))])

/** Every ATX heading in the body, with its level and text. */
function headings(body: string): { level: number; text: string }[] {
  return [...body.matchAll(/^(#{1,6})\s+(.+?)\s*$/gm)].map((match) => ({
    level: (match[1] ?? '').length,
    text: (match[2] ?? '').trim(),
  }))
}

function checkSegments(relativePath: string): Problem[] {
  const problems: Problem[] = []

  for (const segment of relativePath.split('/')) {
    // `.zh.mdx` is a locale suffix, not part of the name: check the slug itself.
    const name = splitLocalePath(segment.replace(/\.(mdx|tsx|ts)$/, '')).baseSlug
    if (!isKebabCase(name)) {
      problems.push({
        file: relativePath,
        message: `“${name}” is not lowercase kebab-case (use-this-style)`,
      })
    }
  }

  return problems
}

/** Frontmatter plus body rules shared by content pages and demo notes. */
async function checkDocument(file: string, relativePath: string): Promise<Problem[]> {
  const source = await readFile(file, 'utf8')
  const result = readFrontmatterSource(source)
  const problems: Problem[] = []

  if (!result.ok) {
    problems.push(...result.problems.map((message) => ({ file: relativePath, message })))
  }

  const found = headings(result.body)

  if (found.some((heading) => heading.level === 1)) {
    problems.push({
      file: relativePath,
      message: 'body must start at `##` — the page renders the frontmatter title as its `h1`',
    })
  }

  if (!found.some((heading) => heading.level >= 2)) {
    problems.push({
      file: relativePath,
      message: 'body needs at least one `##` section heading',
    })
  }

  return problems
}

async function checkContentDir(
  contentDir: string,
): Promise<{ problems: Problem[]; pages: number }> {
  const files = await walkFiles(contentDir, ['.mdx'])
  const problems: Problem[] = []

  /** `${slug}.${locale}` for every file, so a translation can look for its base. */
  const present = new Set<string>()
  const slugs = new Set<string>()

  const keyOf = (slugPath: string) => {
    const { baseSlug, locale } = splitLocalePath(slugPath.replace(/\.mdx$/, ''))
    slugs.add(baseSlug)
    return `${baseSlug}.${locale}`
  }

  for (const file of files) {
    present.add(keyOf(path.relative(contentDir, file).split(path.sep).join('/')))
  }

  for (const file of files) {
    const relativePath = relToPrototype(file)
    const slugPath = path.relative(contentDir, file).split(path.sep).join('/')
    const { baseSlug, locale } = splitLocalePath(slugPath.replace(/\.mdx$/, ''))

    problems.push(...checkSegments(slugPath))
    problems.push(...(await checkDocument(file, relativePath)))

    if (path.basename(file) === 'index.mdx') {
      problems.push({
        file: relativePath,
        message: 'name the page after its subject, not `index.mdx` (it becomes the URL slug)',
      })
    }

    // A translation is a sibling of the English page, never a page on its own.
    if (locale !== defaultLocale && !present.has(`${baseSlug}.${defaultLocale}`)) {
      problems.push({
        file: relativePath,
        message: `translation without its English base — add \`${baseSlug}.mdx\` next to it`,
      })
    }
  }

  return { problems, pages: slugs.size }
}

type DemoFolder = {
  dir: string
  relativePath: string
  entries: string[]
  notes: Partial<Record<Locale, string>>
  hasDemo: boolean
}

async function inspectDemoDirs(demosDir: string): Promise<DemoFolder[]> {
  const folders: DemoFolder[] = []

  for (const dir of await walkDirs(demosDir)) {
    const names = (await readdir(dir, { withFileTypes: true }))
      .filter((entry) => entry.isFile())
      .map((entry) => entry.name)

    const notes: Partial<Record<Locale, string>> = {}
    for (const locale of locales) {
      const name = notesFileName(locale)
      if (names.includes(name)) notes[locale] = name
    }

    folders.push({
      dir,
      relativePath: path.relative(demosDir, dir).split(path.sep).join('/'),
      entries: names,
      notes,
      hasDemo: names.includes(DEMO_FILE),
    })
  }

  return folders
}

async function checkDemoDir(folder: DemoFolder, demoDirs: ReadonlySet<string>): Promise<Problem[]> {
  const problems: Problem[] = []
  const { dir, relativePath, entries, notes, hasDemo } = folder

  if (!hasDemo && Object.keys(notes).length === 0) return problems

  if (!hasDemo) {
    problems.push({
      file: relToPrototype(dir),
      message: `notes without \`${DEMO_FILE}\` — a demo folder needs both`,
    })
    return problems
  }

  problems.push(...checkSegments(relativePath))

  if (relativePath.split('/').length < 2) {
    problems.push({
      file: relToPrototype(dir),
      message: 'demo folders live at demos/<group>/<name>/ so they land in a sidebar section',
    })
  }

  // A demo inside a demo is never scanned by the registry, so it would silently disappear.
  const parent = path.dirname(dir)
  if (parent !== dir && demoDirs.has(parent)) {
    problems.push({
      file: relToPrototype(dir),
      message: `nested demo folder — \`${DEMO_FILE}\` inside another demo is not discovered`,
    })
  }

  const stray = entries.filter((entry) => !allowedDemoFiles.has(entry))
  if (stray.length > 0) {
    problems.push({
      file: relToPrototype(dir),
      message: `unexpected file(s): ${stray.join(', ')} — a demo folder holds ${DEMO_FILE} and its notes`,
    })
  }

  if (!notes[defaultLocale]) {
    problems.push({
      file: relToPrototype(dir),
      message: `missing \`${notesFileName(defaultLocale)}\` — every experiment carries its write-up`,
    })
  }

  for (const locale of locales) {
    const name = notes[locale]
    if (!name) continue
    if (locale !== defaultLocale && !notes[defaultLocale]) {
      problems.push({
        file: relToPrototype(path.join(dir, name)),
        message: `translation without \`${notesFileName(defaultLocale)}\``,
      })
    }
    problems.push(
      ...(await checkDocument(path.join(dir, name), relToPrototype(path.join(dir, name)))),
    )
  }

  const demoSource = await readFile(path.join(dir, DEMO_FILE), 'utf8')
  if (!/export\s+default\s/.test(demoSource)) {
    problems.push({
      file: relToPrototype(path.join(dir, DEMO_FILE)),
      message: `no default export — \`${DEMO_FILE}\` must \`export default\` the demo component`,
    })
  }

  return problems
}

async function checkDemosDir(demosDir: string): Promise<{ problems: Problem[]; demos: number }> {
  const folders = await inspectDemoDirs(demosDir)
  const demoDirs = new Set(
    folders.filter((folder) => folder.hasDemo).map((folder) => path.resolve(folder.dir)),
  )

  const problems: Problem[] = []
  for (const folder of folders) {
    problems.push(...(await checkDemoDir(folder, demoDirs)))
  }

  return { problems, demos: demoDirs.size }
}

/**
 * The generated registries use the plugin's locale list, the app uses `src/i18n/locales.ts`. They
 * must agree, or a translated file would silently never be reachable.
 */
async function checkLocaleList(appLocalesFile: string): Promise<Problem[]> {
  const source = await readFile(appLocalesFile, 'utf8')
  const match = /export const locales = \[([^\]]*)\]/.exec(source)

  if (!match) {
    return [{ file: relToPrototype(appLocalesFile), message: 'could not read the `locales` list' }]
  }

  const appLocales = [...(match[1] ?? '').matchAll(/'([^']+)'/g)].map((entry) => entry[1])
  const pluginLocales: string[] = [...locales]

  if (appLocales.join(',') !== pluginLocales.join(',')) {
    return [
      {
        file: relToPrototype(appLocalesFile),
        message: `app locales (${appLocales.join(', ')}) do not match the plugins (${pluginLocales.join(', ')})`,
      },
    ]
  }

  return []
}

/** Run every content and demo check and return the aggregated problems. */
export async function checkContent({
  contentDir = path.join(labRoot, 'content'),
  demosDir = path.join(labRoot, 'demos'),
  appLocalesFile = path.join(labRoot, 'src/i18n/locales.ts'),
}: CheckOptions = {}): Promise<CheckResult> {
  const content = await checkContentDir(contentDir)
  const demos = await checkDemosDir(demosDir)
  const localeProblems = await checkLocaleList(appLocalesFile)

  return {
    problems: [...localeProblems, ...content.problems, ...demos.problems],
    stats: { pages: content.pages, demos: demos.demos },
  }
}

/** Render problems grouped by file, so one broken file is one block of output. */
export function formatProblems(problems: readonly Problem[]): string {
  const lines: string[] = []

  for (const { file, message } of problems) {
    lines.push(file ? `  ${file}` : '  (project)')
    lines.push(`    · ${message}`)
  }

  return lines.join('\n')
}

const invokedDirectly =
  process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  const { problems, stats } = await checkContent()

  if (problems.length > 0) {
    console.error(`content check: ${problems.length} problem(s)\n`)
    console.error(formatProblems(problems))
    process.exit(1)
  }

  console.log(`content check: ${stats.pages} page(s), ${stats.demos} demo(s), no problems`)
}
