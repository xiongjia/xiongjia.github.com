import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { javascript } from '@codemirror/lang-javascript'
import { bracketMatching, indentOnInput } from '@codemirror/language'
import { searchKeymap } from '@codemirror/search'
import type { Extension } from '@codemirror/state'
import { oneDark } from '@codemirror/theme-one-dark'
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

import { labEditorTheme, labHighlightStyle } from './theme'

/*
 * Extension sets, extracted from the component so the Fast Refresh boundary stays clean: a `.tsx`
 * file that exports both a component and helpers cannot hot-reload reliably.
 */

export type EditorTheme = 'tokens' | 'one-dark'

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

/** The theme pair as one extension; a `Compartment` swaps it without touching the document. */
export function themeExtension(theme: EditorTheme): Extension {
  return theme === 'one-dark' ? [oneDark] : [labEditorTheme, labHighlightStyle]
}
