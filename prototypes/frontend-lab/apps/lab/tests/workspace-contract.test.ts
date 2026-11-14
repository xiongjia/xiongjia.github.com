import assert from 'node:assert/strict'
import { test } from 'node:test'

import { clampSize } from '@frontend-lab/panels/split-size'
import { documentText, lineCount, treeOf, type WorkspaceFile } from '@frontend-lab/workspace/model'
import { createWorkspaceStore } from '@frontend-lab/workspace/store'

/*
 * Integration test for the B13 workspace contract.
 *
 * It drives the real store (the same object the React provider holds) instead of rendering a demo,
 * because the contract is about data flow between the pieces: the tree asks for saved content, the
 * editor asks for `documentText`, the tab strip asks for the dirty list, and the panels persist a
 * number that must stay inside their own bounds. No DOM is needed to prove any of that — and a test
 * that needs no browser keeps running in `pnpm test`.
 */

const files: WorkspaceFile[] = [
  { path: 'README.md', content: '# demo', language: 'plain' },
  {
    path: 'src/main.tsx',
    content: "console.log('hi')\n",
    language: 'javascript',
  },
  { path: 'src/components/button.tsx', content: 'export const Button = 1\n' },
]

function store(initialPath?: string) {
  return createWorkspaceStore(files, initialPath)
}

test('opening a file creates a buffer from the saved content', () => {
  const workspace = store()
  assert.deepEqual(workspace.getState().snapshot.open, [])

  workspace.getState().actions.open('src/main.tsx')
  const snapshot = workspace.getState().snapshot

  assert.equal(snapshot.active, 'src/main.tsx')
  assert.deepEqual(snapshot.open, [
    { path: 'src/main.tsx', draft: "console.log('hi')\n", saved: "console.log('hi')\n" },
  ])
  // An open, unedited file is not dirty — that is the whole definition.
  assert.equal(snapshot.open[0]?.draft, snapshot.open[0]?.saved)
})

test('opening the active file again is a no-op, opening another activates it', () => {
  const workspace = store('src/main.tsx')
  const first = workspace.getState().snapshot

  workspace.getState().actions.open('src/main.tsx')
  assert.equal(workspace.getState().snapshot, first)

  workspace.getState().actions.open('README.md')
  const snapshot = workspace.getState().snapshot
  assert.equal(snapshot.active, 'README.md')
  // Tabs keep their open order; activating never reorders them.
  assert.deepEqual(
    snapshot.open.map((document) => document.path),
    ['src/main.tsx', 'README.md'],
  )
})

test('an unknown path never becomes a buffer', () => {
  const workspace = store()
  const before = workspace.getState().snapshot

  workspace.getState().actions.open('src/nope.ts')
  assert.equal(workspace.getState().snapshot, before)
  assert.deepEqual(workspace.getState().snapshot.open, [])
})

test('a draft lives in the tab until it is saved', () => {
  const workspace = store('src/main.tsx')
  const actions = workspace.getState().actions

  actions.edit('src/main.tsx', "console.log('hi')\nconsole.log('again')\n")
  let snapshot = workspace.getState().snapshot

  // The tree keeps the saved text; only the tab has the draft.
  assert.equal(snapshot.files['src/main.tsx']?.content, "console.log('hi')\n")
  assert.equal(snapshot.open[0]?.draft, "console.log('hi')\nconsole.log('again')\n")
  assert.notEqual(snapshot.open[0]?.draft, snapshot.open[0]?.saved)

  actions.save()
  snapshot = workspace.getState().snapshot

  assert.equal(snapshot.files['src/main.tsx']?.content, "console.log('hi')\nconsole.log('again')\n")
  assert.equal(snapshot.open[0]?.draft, snapshot.open[0]?.saved)
})

test('reverting throws the draft away, and a clean revert does nothing', () => {
  const workspace = store('src/main.tsx')
  const actions = workspace.getState().actions

  actions.edit('src/main.tsx', 'changed\n')
  assert.equal(workspace.getState().snapshot.open[0]?.draft, 'changed\n')

  actions.revert()
  assert.equal(workspace.getState().snapshot.open[0]?.draft, "console.log('hi')\n")

  // Same object: a no-op update must not notify subscribers.
  const clean = workspace.getState().snapshot
  actions.revert()
  assert.equal(workspace.getState().snapshot, clean)
})

test('editing a file that is not open is ignored', () => {
  const workspace = store()
  const actions = workspace.getState().actions

  actions.edit('README.md', 'changed')
  actions.save('README.md')

  assert.deepEqual(workspace.getState().snapshot.open, [])
  assert.equal(workspace.getState().snapshot.files['README.md']?.content, '# demo')
})

test('closing a tab activates the neighbour and discards its draft', () => {
  const workspace = store('README.md')
  const actions = workspace.getState().actions
  actions.open('src/main.tsx')
  actions.open('src/components/button.tsx')
  actions.edit('src/main.tsx', 'unsaved!')

  // Close the active tab: the one that took its place becomes active.
  actions.close('src/components/button.tsx')
  assert.equal(workspace.getState().snapshot.active, 'src/main.tsx')

  actions.close('src/main.tsx')
  assert.equal(workspace.getState().snapshot.active, 'README.md')
  assert.deepEqual(
    workspace.getState().snapshot.open.map((document) => document.path),
    ['README.md'],
  )
  // The contract says closing discards the draft; the saved text is untouched.
  assert.equal(workspace.getState().snapshot.files['src/main.tsx']?.content, "console.log('hi')\n")
})

test('closing the last tab leaves no active document', () => {
  const workspace = store('README.md')
  workspace.getState().actions.close('README.md')

  assert.equal(workspace.getState().snapshot.active, undefined)
  assert.deepEqual(workspace.getState().snapshot.open, [])
})

test('two stores built from one file list are independent', () => {
  const a = store('src/main.tsx')
  const b = store('src/main.tsx')

  a.getState().actions.edit('src/main.tsx', 'only in a\n')
  a.getState().actions.save()

  assert.equal(b.getState().snapshot.files['src/main.tsx']?.content, "console.log('hi')\n")
  assert.equal(a.getState().snapshot.files['src/main.tsx']?.content, 'only in a\n')
})

test('documentText is what an editor mounts with: draft in a tab, saved text outside one', () => {
  const workspace = store('src/main.tsx')
  const actions = workspace.getState().actions
  actions.edit('src/main.tsx', 'draft\n')

  // The open file gets the draft; a file that was never opened gets its saved text.
  assert.equal(documentText(workspace.getState().snapshot, 'src/main.tsx'), 'draft\n')
  assert.equal(
    documentText(workspace.getState().snapshot, 'src/components/button.tsx'),
    'export const Button = 1\n',
  )
})

test('the tree groups by folder, folders before files, both alphabetical', () => {
  const workspace = store()
  const tree = treeOf(workspace.getState().snapshot.files)

  assert.deepEqual(
    tree.map((node) => `${node.kind}:${node.name}`),
    ['folder:src', 'file:README.md'],
  )

  const src = tree[0]
  assert.equal(src?.kind, 'folder')
  if (src?.kind !== 'folder') return

  assert.deepEqual(
    src.children.map((node) => `${node.kind}:${node.name}`),
    ['folder:components', 'file:main.tsx'],
  )

  const components = src.children[0]
  assert.equal(components?.kind, 'folder')
  if (components?.kind !== 'folder') return

  assert.deepEqual(
    components.children.map((node) => `${node.kind}:${node.path}`),
    ['file:src/components/button.tsx'],
  )
})

test('the panel persisted size stays usable for every value storage can hold', () => {
  // The IDE persists two splits as percentages; a corrupt or hand-edited value must not produce an
  // invisible pane when the layout is restored.
  assert.equal(clampSize(0, 15, 45), 15)
  assert.equal(clampSize(100, 15, 45), 45)
  assert.equal(clampSize(Number.NaN, 15, 45), 15)
  assert.equal(clampSize(26.84, 15, 45), 26.84)
})

test('line counts survive empty documents and trailing newlines', () => {
  assert.equal(lineCount(''), 1)
  assert.equal(lineCount('one'), 1)
  assert.equal(lineCount('one\n'), 2)
})
