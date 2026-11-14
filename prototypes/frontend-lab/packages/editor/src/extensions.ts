import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { javascript } from '@codemirror/lang-javascript'
import { bracketMatching, indentOnInput } from '@codemirror/language'
import { searchKeymap } from '@codemirror/search'
import type { Extension } from '@codemirror/state'
import {
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  placeholder as placeholderExtension,
} from '@codemirror/view'

/*
 * Extension sets, extracted from the component so the Fast Refresh boundary stays clean: a `.tsx`
 * file that exports both a component and helpers cannot hot-reload reliably.
 *
 * Theme extensions live in `theme.ts` (one palette-driven generator for every theme); this module
 * re-exports the API so callers keep importing `@frontend-lab/editor` and not its file layout.
 */

export { themeExtension } from './theme'
export type { EditorTheme } from './theme'

/** The default extension set: line numbers, history, search, brackets, indentation, wrapping. */
export function baseExtensions({
  language = 'javascript',
  placeholder,
}: {
  language?: 'javascript' | 'plain'
  placeholder?: string
} = {}): Extension[] {
  return [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    drawSelection(),
    dropCursor(),
    indentOnInput(),
    bracketMatching(),
    highlightActiveLine(),
    EditorView.lineWrapping,
    keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap, indentWithTab]),
    language === 'javascript' ? javascript({ jsx: true, typescript: true }) : [],
    placeholder ? placeholderExtension(placeholder) : [],
  ]
}
