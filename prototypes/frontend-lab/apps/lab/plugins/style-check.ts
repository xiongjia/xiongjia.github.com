import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { prototypeRoot } from './frontmatter.ts'

/*
 * Style-token check.
 *
 * Style presets are CSS, so nothing in TypeScript would notice a preset that references a token
 * which does not exist, forgets its dark mode, or never made it into the picker. This module reads
 * the three CSS layers plus the preset list and proves they still agree:
 *
 *   palette.css   raw values          (`--blue-600`)
 *   tokens.css    mode semantics      (`--primary` light + dark) and the `@theme` utility mapping
 *   styles.css    preset overrides    (`[data-style='warm'][data-theme='dark']`)
 *   style.ts      the preset list the picker renders
 *
 * Every rule is one failure mode that a screenshot would not catch.
 */

export type StyleProblem = {
  file?: string
  message: string
}

export type StyleStats = {
  presets: number
  tokens: number
}

export type StyleCheckResult = {
  problems: StyleProblem[]
  stats: StyleStats
}

export type StyleCheckOptions = {
  paletteFile?: string
  tokensFile?: string
  presetsFile?: string
  presetListFile?: string
}

const defaultPaletteFile = path.join(prototypeRoot, 'packages/ui/src/styles/palette.css')
const defaultTokensFile = path.join(prototypeRoot, 'packages/ui/src/styles/tokens.css')
const defaultPresetsFile = path.join(prototypeRoot, 'packages/ui/src/styles/styles.css')
const defaultPresetListFile = path.join(prototypeRoot, 'apps/lab/src/prefs/style.ts')

type Declaration = { name: string; value: string }
type Block = { selector: string; declarations: Declaration[] }

/** Minimal CSS block reader: these files are flat (no nesting, no at-rule bodies with braces). */
function parseBlocks(source: string): Block[] {
  const withoutComments = source.replace(/\/\*[\s\S]*?\*\//g, '')
  const blocks: Block[] = []

  for (const match of withoutComments.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selector = (match[1] ?? '').trim().replace(/\s+/g, ' ')
    const body = match[2] ?? ''
    const declarations: Declaration[] = []

    for (const declaration of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
      declarations.push({ name: declaration[1] ?? '', value: (declaration[2] ?? '').trim() })
    }

    if (declarations.length > 0) blocks.push({ selector, declarations })
  }

  return blocks
}

function rel(file: string): string {
  const relative = path.relative(prototypeRoot, file)
  return relative.startsWith('..') || path.isAbsolute(relative)
    ? file.split(path.sep).join('/')
    : relative.split(path.sep).join('/')
}

function varReferences(source: string): string[] {
  return [...source.matchAll(/var\(\s*(--[\w-]+)/g)].map((match) => match[1] ?? '')
}

/** The preset ids listed in `styleValues`. */
function readPresetIds(source: string): string[] | undefined {
  const match = /styleValues\s*=\s*\[([\s\S]*?)\]/.exec(source)
  if (!match) return undefined
  return [...(match[1] ?? '').matchAll(/'([^']+)'/g)].map((entry) => entry[1] ?? '')
}

export async function checkStyles({
  paletteFile = defaultPaletteFile,
  tokensFile = defaultTokensFile,
  presetsFile = defaultPresetsFile,
  presetListFile = defaultPresetListFile,
}: StyleCheckOptions = {}): Promise<StyleCheckResult> {
  const [paletteSource, tokensSource, presetsSource, presetListSource] = await Promise.all([
    readFile(paletteFile, 'utf8'),
    readFile(tokensFile, 'utf8'),
    readFile(presetsFile, 'utf8'),
    readFile(presetListFile, 'utf8'),
  ])

  const problems: StyleProblem[] = []

  // --- palette and semantic layers ---------------------------------------------------------
  const paletteTokens = new Set(
    parseBlocks(paletteSource).flatMap((block) => block.declarations.map((item) => item.name)),
  )

  const tokenBlocks = parseBlocks(tokensSource)
  const themeBlocks = tokenBlocks.filter((block) => !block.selector.startsWith('@'))
  const lightTokens = new Set(
    themeBlocks
      .filter((block) => /\[data-theme='light'\]/.test(block.selector))
      .flatMap((block) => block.declarations.map((item) => item.name)),
  )
  const darkTokens = new Set(
    themeBlocks
      .filter((block) => /\[data-theme='dark'\]/.test(block.selector))
      .flatMap((block) => block.declarations.map((item) => item.name)),
  )
  // `:root` carries mode-independent tokens (`--radius`); presets may override those too.
  const neutralTokens = new Set(
    themeBlocks
      .filter((block) => block.selector === ':root')
      .flatMap((block) => block.declarations.map((item) => item.name)),
  )
  const semanticTokens = new Set([...lightTokens, ...darkTokens, ...neutralTokens])

  const lightValues = new Map(
    themeBlocks
      .filter((block) => /\[data-theme='light'\]/.test(block.selector))
      .flatMap((block) => block.declarations.map((item) => [item.name, item.value] as const)),
  )
  const darkValues = new Map(
    themeBlocks
      .filter((block) => /\[data-theme='dark'\]/.test(block.selector))
      .flatMap((block) => block.declarations.map((item) => [item.name, item.value] as const)),
  )
  const neutralValues = new Map(
    themeBlocks
      .filter((block) => block.selector === ':root')
      .flatMap((block) => block.declarations.map((item) => [item.name, item.value] as const)),
  )

  // Everything a `var(...)` may legally point at: palette + every declaration in `tokens.css`.
  const declaredTokens = new Set([
    ...paletteTokens,
    ...tokenBlocks.flatMap((block) => block.declarations.map((item) => item.name)),
  ])

  for (const source of [
    { file: tokensFile, text: tokensSource },
    { file: presetsFile, text: presetsSource },
  ]) {
    for (const name of new Set(varReferences(source.text))) {
      if (!declaredTokens.has(name)) {
        problems.push({
          file: rel(source.file),
          message: `var(${name}) does not resolve to a palette or semantic token`,
        })
      }
    }
  }

  if (semanticTokens.size === 0) {
    problems.push({ file: rel(tokensFile), message: 'no semantic tokens found' })
  }

  // Every mode-aware token needs both values, otherwise dark mode silently inherits light.
  for (const name of lightTokens) {
    if (!darkTokens.has(name)) {
      problems.push({
        file: rel(tokensFile),
        message: `token ${name} has a light value but no dark value`,
      })
    }
  }
  for (const name of darkTokens) {
    if (!lightTokens.has(name)) {
      problems.push({
        file: rel(tokensFile),
        message: `token ${name} has a dark value but no light value`,
      })
    }
  }

  // --- preset layer -----------------------------------------------------------------------
  const presetIds = readPresetIds(presetListSource)
  if (!presetIds) {
    problems.push({ file: rel(presetListFile), message: 'could not read `styleValues`' })
  }

  type PresetBlocks = { light: Map<string, string>; dark: Map<string, string>; modes: Set<string> }
  const presets = new Map<string, PresetBlocks>()

  for (const block of parseBlocks(presetsSource)) {
    const id = /\[data-style='([\w-]+)'\]/.exec(block.selector)?.[1]
    if (!id) continue

    const entry = presets.get(id) ?? {
      light: new Map<string, string>(),
      dark: new Map<string, string>(),
      modes: new Set<string>(),
    }
    const mode = /\[data-theme='dark'\]/.test(block.selector)
      ? 'dark'
      : /\[data-theme='light'\]/.test(block.selector)
        ? 'light'
        : 'any'

    entry.modes.add(mode)
    for (const declaration of block.declarations) {
      if (!semanticTokens.has(declaration.name)) {
        problems.push({
          file: rel(presetsFile),
          message: `preset \`${id}\` overrides ${declaration.name}, which is not a semantic token`,
        })
      }
      // A mode-independent declaration applies to both modes, so it counts for both.
      if (mode !== 'dark') entry.light.set(declaration.name, declaration.value)
      if (mode !== 'light') entry.dark.set(declaration.name, declaration.value)
    }

    presets.set(id, entry)
  }

  if (presetIds) {
    for (const id of presetIds) {
      if (id === 'default') continue // the base token blocks are the default preset
      const entry = presets.get(id)
      if (!entry) {
        problems.push({
          file: rel(presetsFile),
          message: `preset \`${id}\` is listed in styleValues but has no CSS block`,
        })
        continue
      }

      // Light and dark blocks may not be asymmetric: a preset that only handles one mode is a
      // colour bug in the other. A mode-independent block covers both.
      if (!entry.modes.has('light') && !entry.modes.has('any')) {
        problems.push({
          file: rel(presetsFile),
          message: `preset \`${id}\` has no light-mode block`,
        })
      }
      if (!entry.modes.has('dark') && !entry.modes.has('any')) {
        problems.push({
          file: rel(presetsFile),
          message: `preset \`${id}\` has no dark-mode block`,
        })
      }
    }

    for (const id of presets.keys()) {
      if (!presetIds.includes(id)) {
        problems.push({
          file: rel(presetsFile),
          message: `CSS preset \`${id}\` is missing from styleValues in ${rel(presetListFile)}`,
        })
      }
    }

    // `default` mirrors the base token blocks, which is what lets a scoped subtree reset to it.
    const defaultPreset = presets.get('default')
    if (defaultPreset) {
      for (const mode of ['light', 'dark'] as const) {
        const declared = mode === 'dark' ? defaultPreset.dark : defaultPreset.light
        // Mode values plus the mode-independent ones (`--radius`), minus what the theme blocks
        // themselves do not declare.
        const modeValues = mode === 'dark' ? darkValues : lightValues
        const base = new Map([...neutralValues, ...modeValues])
        if (declared.size === 0) continue // the block rules above already flag a missing mode

        for (const [name, value] of base) {
          const override = declared.get(name)
          if (override === undefined) {
            problems.push({
              file: rel(presetsFile),
              message: `default preset is missing ${name} in ${mode} mode, so a scoped default would inherit it`,
            })
          } else if (override !== value) {
            problems.push({
              file: rel(presetsFile),
              message: `default preset sets ${name} to \`${override}\` but tokens.css uses \`${value}\``,
            })
          }
        }

        for (const name of declared.keys()) {
          if (!base.has(name)) {
            problems.push({
              file: rel(presetsFile),
              message: `default preset declares ${name}, which tokens.css does not define in ${mode} mode`,
            })
          }
        }
      }
    }
  }

  return {
    problems,
    stats: { presets: presets.size, tokens: semanticTokens.size },
  }
}

export function formatStyleProblems(problems: readonly StyleProblem[]): string {
  return problems
    .map(({ file, message }) =>
      file ? `  ${file}\n    · ${message}` : `  (project)\n    · ${message}`,
    )
    .join('\n')
}

const invokedDirectly =
  process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  const { problems, stats } = await checkStyles()

  if (problems.length > 0) {
    console.error(`style check: ${problems.length} problem(s)\n`)
    console.error(formatStyleProblems(problems))
    process.exit(1)
  }

  console.log(`style check: ${stats.presets} preset(s), ${stats.tokens} token(s), no problems`)
}
