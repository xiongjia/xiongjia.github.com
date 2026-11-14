import { CodeEditor, type EditorTheme } from '@frontend-lab/editor'
import { undo } from '@codemirror/commands'
import { Prec } from '@codemirror/state'
import { keymap, type EditorView } from '@codemirror/view'
import { useMemo, useRef, useState } from 'react'

const initialDoc = `// Try: Cmd/Ctrl-Enter, Tab, Escape, and the theme switch.
const topics = ['theme', 'shortcuts']

function install() {
  return topics.map((topic) => topic.toUpperCase())
}
`

type LogEntry = { key: string; bindings: string }

export default function Demo() {
  const view = useRef<EditorView | undefined>(undefined)
  const [theme, setTheme] = useState<EditorTheme>('tokens')
  const [readOnly, setReadOnly] = useState(false)
  const [log, setLog] = useState<LogEntry[]>([])
  const [output, setOutput] = useState('')

  const push = (key: string, bindings: string) =>
    setLog((previous) => [{ key, bindings }, ...previous].slice(0, 5))

  /*
   * A keymap the demo owns. It is appended *after* the wrapper's defaults, so without `Prec.highest`
   * it would lose every conflict — CodeMirror resolves by precedence first, then by the order of the
   * bindings inside one keymap.
   */
  const demoKeymap = useMemo(
    () =>
      Prec.highest(
        keymap.of([
          {
            key: 'Mod-Enter',
            preventDefault: true,
            run: () => {
              const doc = view.current?.state.doc.toString() ?? ''
              const lines = doc.split('\n').length
              setOutput(`ran ${lines} line(s) · ${doc.length} chars`)
              push('Mod-Enter', 'demo keymap (Prec.highest)')
              return true
            },
          },
          {
            key: 'Tab',
            preventDefault: true,
            run: (target) => {
              // Two spaces, the lab's style, instead of the default indent command.
              target.dispatch(target.state.replaceSelection('  '))
              push('Tab', 'demo keymap (Prec.highest) beats indentWithTab')
              return true
            },
          },
          {
            key: 'Escape',
            run: (target) => {
              target.contentDOM.blur()
              push('Escape', 'demo keymap — blur')
              return false
            },
          },
        ]),
      ),
    [],
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-full border border-border">
          {(['tokens', 'one-dark'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setTheme(value)}
              aria-pressed={theme === value}
              className={
                theme === value
                  ? 'bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground'
                  : 'px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted'
              }
            >
              {value}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setReadOnly((value) => !value)}
          aria-pressed={readOnly}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          {readOnly ? 'editable' : 'read-only'}
        </button>
        <button
          type="button"
          onClick={() => view.current && undo(view.current)}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Undo (after either switch)
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          {output || 'no run yet'}
        </span>
      </div>

      <CodeEditor
        initialDoc={initialDoc}
        label="Editor with custom keymap and theme"
        theme={theme}
        readOnly={readOnly}
        onView={(created) => {
          view.current = created
        }}
        extensions={[demoKeymap]}
        minHeight="10rem"
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3 text-xs">
          <p className="mb-1 font-medium">Last bindings</p>
          <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
            {log.length === 0 ? <li>press a shortcut…</li> : null}
            {log.map((entry, index) => (
              <li key={`${entry.key}-${index}`}>
                {entry.key} → {entry.bindings}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-3 text-xs text-muted-foreground">
          <p className="mb-1 font-medium text-foreground">Why the state survives</p>
          <p>
            Both switches dispatch <code className="rounded bg-muted px-1">reconfigure</code>{' '}
            effects into the existing view. Undo still works afterwards — history and selection were
            never thrown away, because the view was never recreated.
          </p>
          <p className="mt-2">
            <code className="rounded bg-muted px-1">tokens</code> reads CSS variables, so it follows
            the header&apos;s light/dark switch;{' '}
            <code className="rounded bg-muted px-1">one-dark</code> is a fixed palette and visibly
            ignores it.
          </p>
        </div>
      </div>
    </div>
  )
}
