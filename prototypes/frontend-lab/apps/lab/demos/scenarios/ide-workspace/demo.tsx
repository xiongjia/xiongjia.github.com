import { Prec, RangeSetBuilder, StateField, type Extension, type Text } from '@codemirror/state'
import { Decoration, EditorView, keymap, type DecorationSet } from '@codemirror/view'
import { CodeEditor, editorThemeLabels, editorThemes, type EditorTheme } from '@frontend-lab/editor'
import { SplitPane, useSplitSize } from '@frontend-lab/panels'
import {
  activeDocument,
  documentText,
  isDirty,
  lineCount,
  treeOf,
  useWorkspace,
  useWorkspaceApi,
  WorkspaceProvider,
  type WorkspaceFile,
  type WorkspaceTreeNode,
} from '@frontend-lab/workspace'
import { useEffect, useId, useMemo, useRef, useState } from 'react'

/*
 * IDE workspace: four parts, one buffer.
 *
 *   file tree   navigates and shows which files are dirty
 *   tab strip   what is open; the active tab is what the editor shows
 *   editor      owns the text *between* mounts, the store owns it across mounts
 *   problems    derived from the draft on every keystroke
 *
 * Panels only decide geometry, the editor only decides text, and `@frontend-lab/workspace` decides
 * which text is where. That is the contract this demo — and its integration test — is about.
 */

const files: WorkspaceFile[] = [
  {
    path: 'README.md',
    language: 'plain',
    content: `# Workspace demo

This virtual project lives in \`demo.tsx\`, not on disk.
Open a file on the left, edit it, and watch the tree, the tabs,
the status bar and the problems panel follow.
`,
  },
  {
    path: 'src/main.tsx',
    language: 'javascript',
    content: `import { createRoot } from 'react-dom/client'

import { Button } from './components/button'
import './styles/tokens.css'

console.log('booting the lab')

export function App() {
  // TODO: replace the placeholder with the real layout
  return <Button onClick={() => console.log('clicked')}>Run</Button>
}

createRoot(document.getElementById('root')!).render(<App />)
`,
  },
  {
    path: 'src/components/button.tsx',
    language: 'javascript',
    content: `type ButtonProps = {
  children: string
  onClick: () => void
}

export function Button({ children, onClick }: ButtonProps) {
  return (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  )
}
`,
  },
  {
    path: 'src/styles/tokens.css',
    language: 'plain',
    content: `:root {
  --background: #ffffff;
  --foreground: #111111;
  --primary: #2563eb;
}
`,
  },
]

/* --- diagnostics ------------------------------------------------------------------------- */

type Severity = 'warning' | 'error'

type Diagnostic = {
  from: number
  to: number
  /** 1-based line number, for the panel and the jump target. */
  line: number
  severity: Severity
  message: string
  text: string
}

/** Two rules are enough to prove the slot: a real linter plugs into the same shape. */
const rules: { needle: string; severity: Severity; message: string }[] = [
  { needle: 'console.log(', severity: 'warning', message: 'debug statement left in source' },
  { needle: 'TODO', severity: 'error', message: 'unfinished work' },
]

function scan(doc: string): Diagnostic[] {
  const diagnostics: Diagnostic[] = []
  let offset = 0

  for (const [index, text] of doc.split('\n').entries()) {
    for (const rule of rules) {
      let at = text.indexOf(rule.needle)
      while (at !== -1) {
        diagnostics.push({
          from: offset + at,
          to: offset + at + rule.needle.length,
          line: index + 1,
          severity: rule.severity,
          message: rule.message,
          text: text.trim(),
        })
        at = text.indexOf(rule.needle, at + rule.needle.length)
      }
    }
    offset += text.length + 1
  }

  return diagnostics.sort((a, b) => a.from - b.from)
}

function classOf(problem: Diagnostic): string {
  return problem.severity === 'error' ? 'cm-diagnostic-error' : 'cm-diagnostic-warning'
}

/** One class per line, first problem wins — the colours come from the editor theme's tokens. */
function lineDecorations(doc: Text): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>()
  const seen = new Set<number>()

  for (const problem of scan(doc.toString())) {
    if (seen.has(problem.line)) continue
    seen.add(problem.line)
    const line = doc.line(problem.line)
    builder.add(line.from, line.from, Decoration.line({ class: classOf(problem) }))
  }

  return builder.finish()
}

/** The matched token, underlined — `Decoration.mark` needs a real range, not a line. */
function markDecorations(doc: Text): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>()

  for (const problem of scan(doc.toString())) {
    builder.add(
      problem.from,
      Math.min(problem.to, doc.length),
      Decoration.mark({ class: classOf(problem) }),
    )
  }

  return builder.finish()
}

/**
 * Two decoration fields rather than one: line decorations must be added at the line start and marks
 * at the match, and a single `RangeSetBuilder` would have to re-sort them against each other.
 */
const diagnosticFields: Extension[] = [
  StateField.define<DecorationSet>({
    create: (state) => lineDecorations(state.doc),
    update: (value, tr) => (tr.docChanged ? lineDecorations(tr.state.doc) : value),
    provide: (field) => EditorView.decorations.from(field),
  }),
  StateField.define<DecorationSet>({
    create: (state) => markDecorations(state.doc),
    update: (value, tr) => (tr.docChanged ? markDecorations(tr.state.doc) : value),
    provide: (field) => EditorView.decorations.from(field),
  }),
]

/* --- tree --------------------------------------------------------------------------------- */

function TreeBranch({
  node,
  depth,
  activePath,
  dirty,
  onOpen,
  collapsed,
  onToggle,
}: {
  node: WorkspaceTreeNode
  depth: number
  activePath?: string
  dirty: readonly string[]
  onOpen: (path: string) => void
  collapsed: readonly string[]
  onToggle: (path: string) => void
}) {
  const indent = { paddingLeft: `${depth * 0.75 + 0.5}rem` }

  if (node.kind === 'folder') {
    const open = !collapsed.includes(node.path)

    return (
      <li>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => onToggle(node.path)}
          style={indent}
          className="flex w-full items-center gap-1 rounded px-1 py-1 text-left text-xs text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span aria-hidden="true">{open ? '▾' : '▸'}</span>
          <span className="font-medium">{node.name}</span>
        </button>
        {open ? (
          <ul>
            {node.children.map((child) => (
              <TreeBranch
                key={child.path}
                node={child}
                depth={depth + 1}
                activePath={activePath}
                dirty={dirty}
                onOpen={onOpen}
                collapsed={collapsed}
                onToggle={onToggle}
              />
            ))}
          </ul>
        ) : null}
      </li>
    )
  }

  const active = node.path === activePath
  const unsaved = dirty.includes(node.path)

  return (
    <li>
      <button
        type="button"
        aria-current={active ? 'true' : undefined}
        data-dirty={unsaved ? 'true' : 'false'}
        onClick={() => onOpen(node.path)}
        style={indent}
        className={[
          'flex w-full items-center justify-between gap-1 rounded px-1 py-1 text-left text-xs outline-none',
          'focus-visible:ring-2 focus-visible:ring-ring',
          active
            ? 'bg-secondary font-medium text-secondary-foreground'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        ].join(' ')}
      >
        <span className="truncate">{node.name}</span>
        {unsaved ? (
          <span aria-label="unsaved changes" className="text-destructive">
            ●
          </span>
        ) : null}
      </button>
    </li>
  )
}

/* --- workspace ---------------------------------------------------------------------------- */

function Workspace() {
  const api = useWorkspaceApi()
  const snapshot = useWorkspace((state) => state.snapshot)
  const actions = useWorkspace((state) => state.actions)

  const tree = useMemo(() => treeOf(snapshot.files), [snapshot.files])
  const dirty = useMemo(() => snapshot.open.filter(isDirty).map((doc) => doc.path), [snapshot])
  const problems = useMemo(() => scan(documentText(snapshot, snapshot.active ?? '')), [snapshot])

  const [collapsed, setCollapsed] = useState<readonly string[]>([])
  const [log, setLog] = useState<string[]>(['workspace ready'])
  const [readOnly, setReadOnly] = useState(false)
  const [treeVisible, setTreeVisible] = useState(true)
  const [jumpTo, setJumpTo] = useState<number>()
  const [theme, setTheme] = useState<EditorTheme>('tokens')
  const themeSelectId = useId()

  const treeSplit = useSplitSize({
    storageKey: 'frontend-lab:ide-tree',
    defaultSize: 26,
    min: 15,
    max: 45,
  })
  const bottomSplit = useSplitSize({
    storageKey: 'frontend-lab:ide-bottom',
    defaultSize: 70,
    min: 40,
    max: 88,
  })

  const push = (entry: string) => setLog((previous) => [entry, ...previous].slice(0, 8))

  const doc = activeDocument(snapshot)

  // Jumping to a problem is a dispatch on a live view, not a prop: the editor is not controlled.
  const viewRef = useRef<EditorView | undefined>(undefined)
  useEffect(() => {
    if (jumpTo === undefined || !viewRef.current) return
    viewRef.current.dispatch({ selection: { anchor: jumpTo }, scrollIntoView: true })
    setJumpTo(undefined)
  }, [jumpTo])

  const save = () => {
    const current = activeDocument(api.getState().snapshot)
    if (!current || !isDirty(current)) return
    actions.save()
    push(`saved ${current.path} · ${lineCount(current.draft)} lines`)
  }

  // The keymap is installed once per mounted editor, so the handler must survive re-renders.
  const saveRef = useRef(save)
  saveRef.current = save

  const extensions = useMemo(
    () => [
      Prec.highest(
        keymap.of([
          {
            key: 'Mod-s',
            run: () => {
              saveRef.current()
              return true
            },
          },
        ]),
      ),
      ...diagnosticFields,
    ],
    [],
  )

  const toggleCollapsed = (path: string) =>
    setCollapsed((previous) =>
      previous.includes(path) ? previous.filter((entry) => entry !== path) : [...previous, path],
    )

  const editor = (
    <div className="flex h-full flex-col">
      <div
        role="tablist"
        aria-label="Open files"
        className="flex flex-wrap items-center gap-1 border-b border-border bg-muted/40 px-1.5 py-1"
      >
        {snapshot.open.map((entry) => {
          const active = entry.path === snapshot.active
          const unsaved = entry.draft !== entry.saved

          return (
            <span
              key={entry.path}
              className={[
                'flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]',
                active
                  ? 'border-border bg-card font-medium'
                  : 'border-transparent text-muted-foreground',
              ].join(' ')}
            >
              <button
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => actions.open(entry.path)}
                className="outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {entry.path.split('/').at(-1)}
                {unsaved ? <span className="ml-1 text-destructive">●</span> : null}
              </button>
              <button
                type="button"
                aria-label={`Close ${entry.path}`}
                onClick={() => actions.close(entry.path)}
                className="rounded px-1 text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                ×
              </button>
            </span>
          )
        })}
        {snapshot.open.length === 0 ? (
          <span className="px-1 text-[11px] text-muted-foreground">no open files</span>
        ) : null}
      </div>

      {doc ? (
        <>
          <CodeEditor
            // Keyed by path: switching tabs remounts the view with *this* buffer's text.
            key={doc.path}
            initialDoc={doc.draft}
            language={snapshot.files[doc.path]?.language ?? 'plain'}
            theme={theme}
            readOnly={readOnly}
            onChange={(next) => actions.edit(doc.path, next)}
            onView={(view) => {
              viewRef.current = view
            }}
            extensions={extensions}
            label={`Source of ${doc.path}`}
            minHeight="12rem"
          />
          <p className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground">
            <span data-testid="status-line">{doc.path}</span>
            <span>·</span>
            <span>{lineCount(doc.draft)} lines</span>
            <span>·</span>
            <span data-testid="dirty-count">{dirty.length} dirty</span>
            <span>·</span>
            <span>{readOnly ? 'read-only' : 'editing'}</span>
            <span>·</span>
            <span>theme: {editorThemeLabels[theme]}</span>
            <span>·</span>
            <span>problems: {problems.length}</span>
          </p>
        </>
      ) : (
        <p className="p-4 text-xs text-muted-foreground">
          Pick a file on the left. The editor is not mounted until there is a buffer to own.
        </p>
      )}
    </div>
  )

  const problemsPane = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <p className="text-[11px] font-medium">Problems</p>
        <p className="font-mono text-[10px] text-muted-foreground">{problems.length} found</p>
      </div>
      <ul className="flex-1 overflow-auto p-1.5 text-[11px]">
        {problems.length === 0 ? (
          <li className="px-1.5 py-1 text-muted-foreground">No problems in the open buffer.</li>
        ) : null}
        {problems.map((problem) => (
          <li key={`${problem.line}:${problem.from}`}>
            <button
              type="button"
              onClick={() => setJumpTo(problem.from)}
              className="flex w-full items-start gap-1.5 rounded px-1.5 py-1 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span
                aria-hidden="true"
                className={problem.severity === 'error' ? 'text-destructive' : 'text-primary'}
              >
                {problem.severity === 'error' ? '✕' : '!'}
              </span>
              <span className="min-w-0">
                <span className="block truncate">
                  <span className="sr-only">{problem.severity}: </span>
                  {problem.message}
                </span>
                <span className="block truncate font-mono text-[10px] text-muted-foreground">
                  line {problem.line} · {problem.text}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="border-t border-border px-3 py-1.5">
        <p className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
          Activity
        </p>
        <ul aria-live="polite" className="mt-0.5 space-y-0.5 font-mono text-[10px]">
          {log.map((entry, index) => (
            <li key={`${entry}-${index}`} className="truncate text-muted-foreground">
              {entry}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )

  const editorPane = (
    <SplitPane
      direction="vertical"
      size={bottomSplit.size}
      onSizeChange={bottomSplit.setSize}
      label="Resize the editor and the problems panel"
      firstLabel="Editor"
      secondLabel="Problems and activity"
      minFirstPx={140}
      first={editor}
      second={problemsPane}
      className="h-full rounded-none border-0"
    />
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          onClick={save}
          disabled={dirty.length === 0}
          className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground outline-none disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-ring"
        >
          Save <kbd className="ml-1 font-mono text-[10px]">⌘S</kbd>
        </button>
        <button
          type="button"
          onClick={() => {
            actions.revert()
            push('reverted the active buffer')
          }}
          disabled={!doc || dirty.length === 0}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none disabled:opacity-50 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Revert
        </button>
        <label className="flex items-center gap-1.5 text-muted-foreground">
          <input
            type="checkbox"
            checked={readOnly}
            onChange={(event) => setReadOnly(event.target.checked)}
            className="accent-[var(--primary)]"
          />
          read-only
        </label>
        <span className="flex items-center gap-1.5">
          <label htmlFor={themeSelectId} className="text-[10px] text-muted-foreground">
            Editor theme
          </label>
          <select
            id={themeSelectId}
            data-testid="editor-theme"
            value={theme}
            onChange={(event) => setTheme(event.target.value as EditorTheme)}
            className="h-8 rounded-md border border-border bg-card px-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {editorThemes.map((entry) => (
              <option key={entry} value={entry}>
                {editorThemeLabels[entry]}
              </option>
            ))}
          </select>
        </span>
        <button
          type="button"
          aria-pressed={treeVisible}
          onClick={() => setTreeVisible((visible) => !visible)}
          className={[
            'rounded-md border px-2.5 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring',
            treeVisible
              ? 'border-border text-muted-foreground hover:bg-muted'
              : 'border-primary bg-secondary font-medium text-secondary-foreground',
          ].join(' ')}
        >
          {treeVisible ? 'Hide tree' : 'Show tree'}
        </button>
        <span className="font-mono text-[10px] text-muted-foreground">
          tree {Math.round(treeSplit.size)}% · editor {Math.round(bottomSplit.size)}%
        </span>
      </div>

      {treeVisible ? (
        <SplitPane
          size={treeSplit.size}
          onSizeChange={treeSplit.setSize}
          label="Resize the file tree"
          firstLabel="Files"
          secondLabel="Editor workspace"
          minFirstPx={132}
          maxFirstPx={260}
          className="h-[30rem]"
          first={
            <div className="flex h-full flex-col">
              <p className="border-b border-border px-3 py-1.5 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
                Files · {Object.keys(snapshot.files).length}
              </p>
              <nav aria-label="Project files" className="flex-1 overflow-auto p-1">
                <ul>
                  {tree.map((node) => (
                    <TreeBranch
                      key={node.path}
                      node={node}
                      depth={0}
                      activePath={snapshot.active}
                      dirty={dirty}
                      onOpen={(path) => actions.open(path)}
                      collapsed={collapsed}
                      onToggle={toggleCollapsed}
                    />
                  ))}
                </ul>
              </nav>
            </div>
          }
          second={editorPane}
        />
      ) : (
        <div className="h-[30rem] overflow-hidden rounded-lg border border-border">
          {editorPane}
        </div>
      )}
    </div>
  )
}

export default function Demo() {
  return (
    <WorkspaceProvider files={files} initialPath="src/main.tsx">
      <Workspace />
    </WorkspaceProvider>
  )
}
