import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import type { Extension } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { tags as t } from '@lezer/highlight'

/*
 * The lab's editor theme.
 *
 * Every value is a CSS variable from the lab's token layer, which is the whole trick: the editor
 * follows `data-theme` (and even a style preset) without a second theme, without a mode prop and
 * without a re-mount. The generated CSS is identical in light and dark; the variables resolve
 * differently.
 *
 * A packaged theme like `@codemirror/theme-one-dark` cannot do that — it is a fixed set of colours —
 * which is why the demo can switch between the two with a `Compartment` and compare.
 */

export const labEditorTheme: Extension = EditorView.theme({
  '&': {
    color: 'var(--foreground)',
    backgroundColor: 'transparent',
    fontSize: '13px',
  },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    lineHeight: '1.6',
  },
  '.cm-content': { caretColor: 'var(--primary)' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--primary)' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
    backgroundColor: 'color-mix(in oklab, var(--primary) 24%, transparent)',
  },
  '.cm-selectionMatch': { backgroundColor: 'color-mix(in oklab, var(--primary) 14%, transparent)' },
  '.cm-gutters': {
    backgroundColor: 'var(--muted)',
    color: 'var(--muted-foreground)',
    border: 'none',
    borderRight: '1px solid var(--border)',
  },
  '.cm-activeLine': { backgroundColor: 'color-mix(in oklab, var(--primary) 7%, transparent)' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--foreground)' },
  '.cm-searchMatch': {
    backgroundColor: 'color-mix(in oklab, var(--primary) 22%, transparent)',
    outline: '1px solid var(--primary)',
  },
  '.cm-panels': { backgroundColor: 'var(--card)', color: 'var(--foreground)' },
  '.cm-panels.cm-panels-top': { borderBottom: '1px solid var(--border)' },
  '.cm-tooltip': {
    backgroundColor: 'var(--card)',
    border: '1px solid var(--border)',
    color: 'var(--foreground)',
  },
  '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
    backgroundColor: 'var(--secondary)',
    color: 'var(--secondary-foreground)',
  },
})

/** Syntax colours as tokens: same CSS, different resolution per mode. */
export const labHighlightStyle: Extension = syntaxHighlighting(
  HighlightStyle.define([
    { tag: [t.keyword, t.modifier, t.operatorKeyword], color: 'var(--primary)' },
    { tag: [t.controlKeyword, t.moduleKeyword], color: 'var(--primary)', fontWeight: '600' },
    { tag: [t.string, t.special(t.string)], color: 'var(--destructive)' },
    { tag: [t.number, t.bool, t.null], color: 'var(--destructive)' },
    {
      tag: [t.comment, t.lineComment, t.blockComment],
      color: 'var(--muted-foreground)',
      fontStyle: 'italic',
    },
    { tag: [t.function(t.variableName), t.function(t.propertyName)], color: 'var(--primary)' },
    { tag: [t.className, t.typeName], color: 'var(--foreground)', fontWeight: '600' },
    { tag: [t.propertyName, t.attributeName], color: 'var(--foreground)' },
    { tag: [t.variableName, t.definition(t.variableName)], color: 'var(--foreground)' },
    { tag: [t.operator, t.punctuation, t.bracket, t.separator], color: 'var(--muted-foreground)' },
    { tag: t.invalid, color: 'var(--destructive)' },
  ]),
)
