import { CodeEditor } from '@frontend-lab/editor'
import { redo, undo } from '@codemirror/commands'
import { EditorSelection } from '@codemirror/state'
import type { EditorView } from '@codemirror/view'
import { useRef, useState } from 'react'

const initialDoc = `// The document lives in a CodeMirror EditorState, not in React.
export function greet(name) {
  return \`Hello, \${name}\`
}

// Type here: React does not re-render on every keystroke.
`

export default function Demo() {
  const view = useRef<EditorView | undefined>(undefined)
  const [snapshot, setSnapshot] = useState({ text: initialDoc, size: initialDoc.length })
  const [reads, setReads] = useState(0)
  const [renders, setRenders] = useState(0)

  const read = () => {
    const current = view.current?.state.doc.toString() ?? ''
    setSnapshot({ text: current, size: current.length })
    setReads((value) => value + 1)
    setRenders((value) => value + 1)
  }

  return (
    <div className="space-y-4">
      <CodeEditor
        initialDoc={initialDoc}
        label="Minimal editor"
        // The wrapper hands out the view once; commands below are ordinary CodeMirror calls.
        onView={(created) => {
          view.current = created
        }}
        minHeight="11rem"
      />

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => view.current && undo(view.current)}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Undo
        </button>
        <button
          type="button"
          onClick={() => view.current && redo(view.current)}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Redo
        </button>
        <button
          type="button"
          onClick={() => {
            const target = view.current
            if (!target) return
            const end = target.state.doc.length
            // One transaction: insert text, put the cursor after it, scroll it into view. Three
            // effects, one undo step.
            target.dispatch({
              changes: { from: end, insert: '\nconsole.log(greet("lab"))\n' },
              selection: EditorSelection.cursor(end + 24),
              scrollIntoView: true,
            })
          }}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Dispatch a transaction
        </button>
        <button
          type="button"
          onClick={read}
          className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
        >
          Read the document
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3 text-xs">
          <p className="font-mono text-[11px] text-muted-foreground">
            reads from React: {reads} · keystrokes seen by React: 0
          </p>
          <p className="mt-1 text-muted-foreground">
            Typing never calls <code className="rounded bg-muted px-1">setState</code>: the editor
            owns the document. The snapshot below is a deliberate pull, not a subscription.
          </p>
          <p className="mt-2 font-mono text-[11px]">
            length: {snapshot.size} chars · renders of the readout: {renders}
          </p>
        </div>
        <pre className="max-h-40 overflow-auto rounded-lg border border-border bg-muted p-3 font-mono text-[11px] leading-5">
          <code>{snapshot.text.slice(-400)}</code>
        </pre>
      </div>

      <p className="text-xs text-muted-foreground">
        Undo/redo work because <code className="rounded bg-muted px-1">history()</code> is an
        extension: the undo stack lives in the editor state, next to the document it describes. A
        React-owned string would have lost it on the first parent re-render.
      </p>
    </div>
  )
}
