import { EditorState, Compartment, type Extension } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { useEffect, useRef } from 'react'

import { baseExtensions, themeExtension, type EditorTheme } from './extensions'

/*
 * A React wrapper around CodeMirror 6.
 *
 * Three decisions carry the whole design:
 *
 * 1. **The document is owned by CodeMirror, not by React.** A controlled `value` prop would push
 *    every keystroke through `useState`, re-render the tree, and lose the selection and undo history
 *    on any parent update. The wrapper takes `initialDoc`, reports changes through `onChange`, and
 *    never writes back unless the caller dispatches.
 * 2. **Extensions are configured, not rebuilt.** Theme and read-only live in `Compartment`s, so
 *    switching them is an `EditorView.dispatch({ effects })` — the state (history, selections,
 *    scroll) survives. Recreating the view would throw all of that away.
 * 3. **The view is created once.** `EditorState.create` + `new EditorView` run inside a mount effect
 *    that depends on nothing, so a re-render is free; StrictMode's double mount is handled by
 *    destroying the first view.
 */

export type CodeEditorProps = {
  /** Starting document; the editor owns it afterwards. */
  initialDoc: string
  /** `javascript` also enables JS/TS parsing for syntax colours. */
  language?: 'javascript' | 'plain'
  /** Follows the lab's tokens by default; `one-dark` proves a packaged theme cannot. */
  theme?: EditorTheme
  readOnly?: boolean
  /** Called after every document change with the full text. */
  onChange?: (doc: string) => void
  /** Called once per mounted view — the handle for commands and custom transactions. */
  onView?: (view: EditorView) => void
  /** Extra extensions, appended after the defaults (keymaps in them take precedence last). */
  extensions?: Extension[]
  /** Accessible name; CodeMirror's contenteditable is otherwise announced as an empty text box. */
  label: string
  placeholder?: string
  /** Minimum height of the scroll area. */
  minHeight?: string
}

export function CodeEditor({
  initialDoc,
  language = 'javascript',
  theme = 'tokens',
  readOnly = false,
  onChange,
  onView,
  extensions,
  label,
  placeholder,
  minHeight = '8rem',
}: CodeEditorProps) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | undefined>(undefined)
  const themeCompartment = useRef(new Compartment())
  const readOnlyCompartment = useRef(new Compartment())

  // Latest callbacks in refs: the view is created once, so the listener must not capture the first
  // render's closure.
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const extra = useRef(extensions)
  extra.current = extensions

  useEffect(() => {
    const element = host.current
    if (!element) return

    const state = EditorState.create({
      doc: initialDoc,
      extensions: [
        ...baseExtensions({ language, placeholder }),
        themeCompartment.current.of(themeExtension(theme)),
        readOnlyCompartment.current.of([
          EditorState.readOnly.of(readOnly),
          EditorView.editable.of(!readOnly),
        ]),
        EditorView.contentAttributes.of({ 'aria-label': label, 'aria-multiline': 'true' }),
        EditorView.theme({ '.cm-scroller': { minHeight } }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current?.(update.state.doc.toString())
        }),
        ...(extra.current ?? []),
      ],
    })

    const created = new EditorView({ state, parent: element })
    view.current = created
    onView?.(created)

    return () => {
      created.destroy()
      view.current = undefined
    }
    // Deliberately mount-only: `initialDoc`, `language` and `label` are read once, and every runtime
    // change goes through a compartment or a dispatch instead of a rebuild.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    view.current?.dispatch({
      effects: themeCompartment.current.reconfigure(themeExtension(theme)),
    })
  }, [theme])

  useEffect(() => {
    view.current?.dispatch({
      effects: readOnlyCompartment.current.reconfigure([
        EditorState.readOnly.of(readOnly),
        EditorView.editable.of(!readOnly),
      ]),
    })
  }, [readOnly])

  return <div ref={host} className="overflow-hidden rounded-lg border border-border bg-muted/40" />
}
