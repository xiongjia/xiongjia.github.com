import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { checkContent, formatProblems, type CheckResult } from './content-check.ts'

/*
 * The checks are the gate, so they are tested like code: every rule has a fixture that violates it
 * and an assertion that the rule fires. Temporary directories keep the real `content/` and `demos/`
 * folders untouched.
 */

function page(title = 'A page'): string {
  return `---\ntitle: ${title}\nsummary: One line of summary.\norder: 10\n---\n\n## Section\n\nBody.\n`
}

function demo(): string {
  return 'export default function Demo() {\n  return <div>demo</div>\n}\n'
}

async function writeTemp(source: string): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), 'frontend-lab-locales-'))
  const file = path.join(root, 'locales.ts')
  await writeFile(file, source, 'utf8')
  return file
}

async function runChecks(
  files: Record<string, string>,
  options: { appLocalesFile?: string } = {},
): Promise<CheckResult> {
  const root = await mkdtemp(path.join(os.tmpdir(), 'frontend-lab-check-'))

  try {
    for (const [relative, source] of Object.entries(files)) {
      const file = path.join(root, relative)
      await mkdir(path.dirname(file), { recursive: true })
      await writeFile(file, source, 'utf8')
    }

    const contentDir = path.join(root, 'content')
    const demosDir = path.join(root, 'demos')
    await mkdir(contentDir, { recursive: true })
    await mkdir(demosDir, { recursive: true })

    return await checkContent({ contentDir, demosDir, ...options })
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}

function messages(result: CheckResult): string {
  return formatProblems(result.problems)
}

test('a valid page and a valid demo pass', async () => {
  const result = await runChecks({
    'content/foundations/design-tokens.mdx': page('Design tokens'),
    'demos/foundations/button-variants/demo.tsx': demo(),
    'demos/foundations/button-variants/notes.mdx': page('Button variants'),
  })

  assert.deepEqual(result.problems, [])
  assert.deepEqual(result.stats, { pages: 1, demos: 1 })
})

test('frontmatter is validated by the schema, not by fallbacks', async () => {
  const result = await runChecks({
    'content/foundations/no-summary.mdx': '---\ntitle: No summary\n---\n\n## Section\n\nBody.\n',
    'content/foundations/bad-order.mdx':
      '---\ntitle: Bad order\nsummary: One line.\norder: ten\n---\n\n## Section\n\nBody.\n',
    'content/foundations/typo.mdx':
      '---\ntitle: Typo\nsummary: One line.\nsummery: duplicated\n---\n\n## Section\n\nBody.\n',
  })

  const output = messages(result)
  assert.match(output, /no-summary\.mdx[\s\S]*summary/)
  assert.match(output, /bad-order\.mdx[\s\S]*expected number[\s\S]*at order/)
  assert.match(output, /typo\.mdx[\s\S]*Unrecognized key: "summery"/)
})

test('the body must not introduce a second h1 and must have a section', async () => {
  const result = await runChecks({
    'content/foundations/h1.mdx': '---\ntitle: H1\nsummary: One line.\n---\n\n# Title\n\nBody.\n',
    'content/foundations/empty.mdx': '---\ntitle: Empty\nsummary: One line.\n---\n\nBody only.\n',
  })

  const output = messages(result)
  assert.match(output, /h1\.mdx[\s\S]*body must start at `##`/)
  assert.match(output, /empty\.mdx[\s\S]*at least one `##` section heading/)
})

test('file and folder names must be lowercase kebab-case', async () => {
  const result = await runChecks({
    'content/foundations/DesignTokens.mdx': page(),
    'demos/foundations/ButtonVariants/demo.tsx': demo(),
    'demos/foundations/ButtonVariants/notes.mdx': page(),
  })

  const output = messages(result)
  assert.match(output, /“DesignTokens” is not lowercase kebab-case/)
  assert.match(output, /“ButtonVariants” is not lowercase kebab-case/)
})

test('a demo folder needs a default export and a write-up', async () => {
  const result = await runChecks({
    'demos/foundations/no-default/demo.tsx': 'export function Demo() {\n  return null\n}\n',
    'demos/foundations/no-default/notes.mdx': page(),
    'demos/foundations/no-notes/demo.tsx': demo(),
  })

  const output = messages(result)
  assert.match(output, /no-default\/demo\.tsx[\s\S]*no default export/)
  assert.match(output, /no-notes[\s\S]*missing `notes\.mdx`/)
})

test('a translation never stands alone', async () => {
  const result = await runChecks({
    'content/foundations/orphan.zh.mdx': page(),
    'demos/foundations/no-base/demo.tsx': demo(),
    'demos/foundations/no-base/notes.zh.mdx': page(),
  })

  const output = messages(result)
  assert.match(output, /orphan\.zh\.mdx[\s\S]*translation without its English base/)
  assert.match(output, /no-base\/notes\.zh\.mdx[\s\S]*translation without `notes\.mdx`/)
  assert.match(output, /no-base[\s\S]*missing `notes\.mdx`/)
})

test('a translated notes file is allowed next to the English one', async () => {
  const result = await runChecks({
    'demos/foundations/translated/demo.tsx': demo(),
    'demos/foundations/translated/notes.mdx': page(),
    'demos/foundations/translated/notes.zh.mdx': page(),
    'content/foundations/bilingual.mdx': page(),
    'content/foundations/bilingual.zh.mdx': page(),
  })

  assert.deepEqual(result.problems, [])
  assert.deepEqual(result.stats, { pages: 1, demos: 1 })
})

test('the app locale list must match the plugins', async () => {
  const result = await runChecks(
    {},
    { appLocalesFile: await writeTemp("export const locales = ['en'] as const\n") },
  )

  assert.match(messages(result), /app locales \(en\) do not match the plugins \(en, zh\)/)
})

test('stray files, orphan notes and nested demos are rejected', async () => {
  const result = await runChecks({
    'demos/foundations/stray/demo.tsx': demo(),
    'demos/foundations/stray/notes.mdx': page(),
    'demos/foundations/stray/scratch.ts': 'export const x = 1\n',
    'demos/foundations/orphan/notes.mdx': page(),
    'demos/foundations/nested/demo.tsx': demo(),
    'demos/foundations/nested/notes.mdx': page(),
    'demos/foundations/nested/child/demo.tsx': demo(),
    'demos/foundations/nested/child/notes.mdx': page(),
    'demos/loose/demo.tsx': demo(),
    'demos/loose/notes.mdx': page(),
  })

  const output = messages(result)
  assert.match(output, /stray[\s\S]*unexpected file\(s\): scratch\.ts/)
  assert.match(output, /orphan[\s\S]*notes without `demo\.tsx`/)
  assert.match(output, /nested\/child[\s\S]*nested demo folder/)
  assert.match(output, /demos\/loose[\s\S]*demos\/<group>\/<name>/)
})
