import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import type { Extension } from '@codemirror/state'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from '@codemirror/view'
import { tags as t } from '@lezer/highlight'

/*
 * Editor themes, generated from palettes rather than hand-written per theme.
 *
 * Two kinds of theme live here on purpose:
 *
 *   `tokens`     every colour is a CSS variable from the lab's token layer, so the editor follows
 *                `data-theme` and even `data-style` without a second theme, a mode prop or a
 *                re-mount. This is the one that belongs to the lab.
 *   fixed        Dracula / Nord / Solarized Light: a concrete palette. They exist because a reader
 *                expects theme choices, and because they make the trade-off visible — a fixed theme
 *                cannot follow the page's light/dark switch.
 *
 * On top of those, `one-dark` is the packaged `@codemirror/theme-one-dark`, kept as the control: it
 * shows what a theme you did not generate looks like (and that a `Compartment` can swap it live).
 *
 * A palette is a data structure and `createTheme` is the only renderer, so adding a sixth theme means
 * adding six hex values, not another 60-line `EditorView.theme` call.
 */

export type EditorTheme = 'tokens' | 'one-dark' | 'dracula' | 'nord' | 'solarized'

export const editorThemes: readonly EditorTheme[] = [
  'tokens',
  'one-dark',
  'dracula',
  'nord',
  'solarized',
]

export const editorThemeLabels: Record<EditorTheme, string> = {
  tokens: 'Lab tokens',
  'one-dark': 'One Dark',
  dracula: 'Dracula',
  nord: 'Nord',
  solarized: 'Solarized Light',
}

type EditorPalette = {
  background: string
  foreground: string
  /** Comments, operators and other quiet syntax. */
  muted: string
  keyword: string
  string: string
  number: string
  function: string
  type: string
  property: string
  /** Caret, selection and match highlight. */
  accent: string
  gutterBackground: string
  gutterForeground: string
  border: string
  panel: string
  panelForeground: string
  error: string
}

const tokensPalette: EditorPalette = {
  background: 'transparent',
  foreground: 'var(--foreground)',
  muted: 'var(--muted-foreground)',
  keyword: 'var(--primary)',
  string: 'var(--destructive)',
  number: 'var(--destructive)',
  function: 'var(--primary)',
  type: 'var(--foreground)',
  property: 'var(--foreground)',
  accent: 'var(--primary)',
  gutterBackground: 'var(--muted)',
  gutterForeground: 'var(--muted-foreground)',
  border: 'var(--border)',
  panel: 'var(--card)',
  panelForeground: 'var(--foreground)',
  error: 'var(--destructive)',
}

const draculaPalette: EditorPalette = {
  background: '#282a36',
  foreground: '#f8f8f2',
  muted: '#6272a4',
  keyword: '#ff79c6',
  string: '#f1fa8c',
  number: '#bd93f9',
  function: '#50fa7b',
  type: '#8be9fd',
  property: '#f8f8f2',
  accent: '#bd93f9',
  gutterBackground: '#21222c',
  gutterForeground: '#6272a4',
  border: '#44475a',
  panel: '#21222c',
  panelForeground: '#f8f8f2',
  error: '#ff5555',
}

const nordPalette: EditorPalette = {
  background: '#2e3440',
  foreground: '#d8dee9',
  muted: '#616e88',
  keyword: '#81a1c1',
  string: '#a3be8c',
  number: '#b48ead',
  function: '#88c0d0',
  type: '#8fbcbb',
  property: '#d8dee9',
  accent: '#88c0d0',
  gutterBackground: '#2e3440',
  gutterForeground: '#616e88',
  border: '#3b4252',
  panel: '#3b4252',
  panelForeground: '#eceff4',
  error: '#bf616a',
}

const solarizedPalette: EditorPalette = {
  background: '#fdf6e3',
  foreground: '#657b83',
  muted: '#93a1a1',
  keyword: '#859900',
  string: '#2aa198',
  number: '#d33682',
  function: '#268bd2',
  type: '#b58900',
  property: '#657b83',
  accent: '#268bd2',
  gutterBackground: '#eee8d5',
  gutterForeground: '#93a1a1',
  border: '#eee8d5',
  panel: '#eee8d5',
  panelForeground: '#586e75',
  error: '#dc322f',
}

const palettes: Record<Exclude<EditorTheme, 'one-dark'>, EditorPalette> = {
  tokens: tokensPalette,
  dracula: draculaPalette,
  nord: nordPalette,
  solarized: solarizedPalette,
}

type GeneratedTheme = { view: Extension; highlight: Extension }

/** One theme renderer: chrome, selection, gutters, panels and syntax colours from a palette. */
function createTheme(palette: EditorPalette): GeneratedTheme {
  const view = EditorView.theme({
    '&': {
      color: palette.foreground,
      backgroundColor: palette.background,
      fontSize: '13px',
    },
    '&.cm-focused': { outline: 'none' },
    '.cm-scroller': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      lineHeight: '1.6',
    },
    '.cm-content': { caretColor: palette.accent },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: palette.accent },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: `color-mix(in oklab, ${palette.accent} 24%, transparent)`,
    },
    '.cm-selectionMatch': {
      backgroundColor: `color-mix(in oklab, ${palette.accent} 14%, transparent)`,
    },
    '.cm-gutters': {
      backgroundColor: palette.gutterBackground,
      color: palette.gutterForeground,
      border: 'none',
      borderRight: `1px solid ${palette.border}`,
    },
    '.cm-activeLine': { backgroundColor: `color-mix(in oklab, ${palette.accent} 8%, transparent)` },
    '.cm-activeLineGutter': { backgroundColor: 'transparent', color: palette.foreground },
    '.cm-searchMatch': {
      backgroundColor: `color-mix(in oklab, ${palette.accent} 22%, transparent)`,
      outline: `1px solid ${palette.accent}`,
    },
    '.cm-panels': { backgroundColor: palette.panel, color: palette.panelForeground },
    '.cm-panels.cm-panels-top': { borderBottom: `1px solid ${palette.border}` },
    '.cm-tooltip': {
      backgroundColor: palette.panel,
      border: `1px solid ${palette.border}`,
      color: palette.panelForeground,
    },
    '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
      backgroundColor: `color-mix(in oklab, ${palette.accent} 20%, ${palette.background})`,
      color: palette.foreground,
    },
    /*
     * Decoration classes, part of every theme: a caller marks a range or a line with one of these
     * class names (see `demos/scenarios/ide-workspace`), and the palette decides the colour.
     */
    '.cm-diagnostic-warning': {
      backgroundColor: `color-mix(in oklab, ${palette.accent} 12%, transparent)`,
      textDecoration: `underline wavy color-mix(in oklab, ${palette.accent} 70%, transparent)`,
    },
    '.cm-diagnostic-error': {
      backgroundColor: `color-mix(in oklab, ${palette.error} 14%, transparent)`,
      textDecoration: `underline wavy ${palette.error}`,
    },
  })

  const highlight = syntaxHighlighting(
    HighlightStyle.define([
      { tag: [t.keyword, t.modifier, t.operatorKeyword], color: palette.keyword },
      { tag: [t.controlKeyword, t.moduleKeyword], color: palette.keyword, fontWeight: '600' },
      { tag: [t.string, t.special(t.string)], color: palette.string },
      { tag: [t.number, t.bool, t.null], color: palette.number },
      {
        tag: [t.comment, t.lineComment, t.blockComment],
        color: palette.muted,
        fontStyle: 'italic',
      },
      { tag: [t.function(t.variableName), t.function(t.propertyName)], color: palette.function },
      { tag: [t.className, t.typeName], color: palette.type, fontWeight: '600' },
      { tag: [t.propertyName, t.attributeName], color: palette.property },
      { tag: [t.variableName, t.definition(t.variableName)], color: palette.foreground },
      { tag: [t.operator, t.punctuation, t.bracket, t.separator], color: palette.muted },
      { tag: t.invalid, color: palette.error },
    ]),
  )

  return { view, highlight }
}

const generated = new Map<EditorTheme, GeneratedTheme>()

function themeOf(theme: Exclude<EditorTheme, 'one-dark'>): GeneratedTheme {
  const cached = generated.get(theme)
  if (cached) return cached

  const created = createTheme(palettes[theme])
  generated.set(theme, created)
  return created
}

/** The token-driven theme's two halves, kept exported because they are the lab's default. */
export const labEditorTheme: Extension = themeOf('tokens').view
export const labHighlightStyle: Extension = themeOf('tokens').highlight

/**
 * The theme as one extension, ready for a `Compartment`. Generated themes are cached: switching back
 * and forth must not rebuild the extension (which would reconfigure the view for no reason).
 */
export function themeExtension(theme: EditorTheme): Extension {
  if (theme === 'one-dark') return oneDark
  const { view, highlight } = themeOf(theme)
  return [view, highlight]
}
