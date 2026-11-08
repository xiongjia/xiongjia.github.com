import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { checkStyles, formatStyleProblems, type StyleCheckResult } from './style-check.ts'

/*
 * The style check protects a contract that spans four files, so it is tested with fixtures: each
 * rule gets a case that violates it and an assertion that it fires.
 */

const palette = `
:root {
  --gray-50: oklch(0.99 0.002 265);
  --blue-600: oklch(0.55 0.19 265);
}
`

const tokens = (darkPrimary = true) => `
:root {
  --radius: 0.5rem;
}

:root,
[data-theme='light'] {
  --background: var(--gray-50);
  --primary: var(--blue-600);
  color-scheme: light;
}

[data-theme='dark'] {
  --background: var(--gray-50);
  ${darkPrimary ? '--primary: var(--blue-600);' : ''}
  color-scheme: dark;
}

@theme inline {
  --color-background: var(--background);
  --color-primary: var(--primary);
}
`

const presetList = (ids = ['default', 'sharp', 'warm']) =>
  `export const styleValues = [${ids.map((id) => `'${id}'`).join(', ')}] as const\n`

const defaultPreset = `
[data-style='default'] {
  --radius: 0.5rem;
}

[data-style='default'][data-theme='light'] {
  --background: var(--gray-50);
  --primary: var(--blue-600);
}

[data-style='default'][data-theme='dark'] {
  --background: var(--gray-50);
  --primary: var(--blue-600);
}
`

const presets = (
  blocks = `
[data-style='sharp'] {
  --radius: 0;
}

[data-style='warm'][data-theme='light'] {
  --primary: var(--blue-600);
}

[data-style='warm'][data-theme='dark'] {
  --primary: var(--blue-600);
}
`,
) => defaultPreset + blocks

type Fixtures = {
  palette?: string
  tokens?: string
  presets?: string
  presetList?: string
}

async function runChecks(fixtures: Fixtures): Promise<StyleCheckResult> {
  const root = await mkdtemp(path.join(os.tmpdir(), 'frontend-lab-styles-'))

  try {
    const files = {
      palette: path.join(root, 'palette.css'),
      tokens: path.join(root, 'tokens.css'),
      presets: path.join(root, 'styles.css'),
      presetList: path.join(root, 'style.ts'),
    }

    const contents = {
      palette: fixtures.palette ?? palette,
      tokens: fixtures.tokens ?? tokens(),
      presets: fixtures.presets ?? presets(),
      presetList: fixtures.presetList ?? presetList(),
    }

    await mkdir(root, { recursive: true })
    for (const [key, file] of Object.entries(files)) {
      await writeFile(file, contents[key as keyof typeof contents], 'utf8')
    }

    return await checkStyles({
      paletteFile: files.palette,
      tokensFile: files.tokens,
      presetsFile: files.presets,
      presetListFile: files.presetList,
    })
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}

const output = (result: StyleCheckResult) => formatStyleProblems(result.problems)

test('consistent palette, tokens, presets and preset list pass', async () => {
  const result = await runChecks({})
  assert.deepEqual(result.problems, [])
  assert.deepEqual(result.stats, { presets: 3, tokens: 3 })
})

test('a preset may only override semantic tokens', async () => {
  const result = await runChecks({
    presets: presets(`
[data-style='warm'][data-theme='light'] {
  --primari: var(--blue-600);
}

[data-style='warm'][data-theme='dark'] {
  --primary: var(--blue-600);
}
`),
  })

  assert.match(output(result), /preset `warm` overrides --primari, which is not a semantic token/)
})

test('a preset without a dark block is rejected', async () => {
  const result = await runChecks({
    presets: presets(`
[data-style='warm'][data-theme='light'] {
  --primary: var(--blue-600);
}
`),
  })

  assert.match(output(result), /preset `warm` has no dark-mode block/)
})

test('the preset list and the CSS selectors must match in both directions', async () => {
  const missingCss = await runChecks({
    presetList: presetList(['default', 'sharp', 'warm', 'mono']),
  })
  assert.match(output(missingCss), /preset `mono` is listed in styleValues but has no CSS block/)

  const missingList = await runChecks({ presetList: presetList(['default']) })
  assert.match(output(missingList), /CSS preset `warm` is missing from styleValues/)
})

test('dark mode must define every mode-aware token', async () => {
  const result = await runChecks({ tokens: tokens(false) })
  assert.match(output(result), /token --primary has a light value but no dark value/)
})

test('unresolvable var() references are rejected', async () => {
  const result = await runChecks({
    tokens: traces(),
  })
  assert.match(output(result), /var\(--gray-950\) does not resolve to a palette or semantic token/)
})

test('the default preset must mirror the base token blocks', async () => {
  const result = await runChecks({
    presets: presets().replace(
      `[data-style='default'][data-theme='dark'] {
  --background: var(--gray-50);`,
      `[data-style='default'][data-theme='dark'] {`,
    ),
  })

  assert.match(
    output(result),
    /default preset is missing --background in dark mode, so a scoped default would inherit it/,
  )
})

test('a missing preset list is reported instead of skipped', async () => {
  const result = await runChecks({ presetList: 'export const styles = []\n' })
  assert.match(output(result), /could not read `styleValues`/)
})

function traces(): string {
  return `
:root {
  --radius: 0.5rem;
}

:root,
[data-theme='light'] {
  --background: var(--gray-950);
  --primary: var(--blue-600);
}

[data-theme='dark'] {
  --background: var(--gray-950);
  --primary: var(--blue-600);
}
`
}
