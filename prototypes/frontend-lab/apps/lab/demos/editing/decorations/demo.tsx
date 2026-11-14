import { CodeEditor } from '@frontend-lab/editor'
import {
  EditorSelection,
  StateEffect,
  StateField,
  type Extension,
  type Range,
} from '@codemirror/state'
import { Decoration, EditorView, type DecorationSet } from '@codemirror/view'
import { useMemo, useRef, useState } from 'react'

/*
 * Decorations are ranges attached to the document, and a `StateField` is how they stay correct:
 *
 *   create   compute once from the initial doc
 *   update   recompute on `docChanged`, otherwise keep the value (a mapped range set)
 *
 * Two fields below — tags and search hits — prove that several decorations providers compose: the
 * editor paints both without either field knowing about the other.
 */

const TAG_PATTERN = /\b(TODO|FIXME|NOTE)\b/g
const tagMark = Decoration.mark({ class: 'rounded-sm bg-primary/20 px-0.5 font-semibold' })
const hitMark = Decoration.mark({
  class: 'rounded-sm bg-destructive/20 outline outline-1 outline-destructive/40',
})

function tagDecorations(doc: string): DecorationSet {
  const ranges: Range<Decoration>[] = []
  for (const match of doc.matchAll(TAG_PATTERN)) {
    if (match.index === undefined) continue
    ranges.push(tagMark.range(match.index, match.index + match[0].length))
  }
  // `true` = already sorted by `from`, which the regex guarantees.
  return Decoration.set(ranges, true)
}

function hitDecorations(doc: string, query: string): DecorationSet {
  if (query.length < 2) return Decoration.none
  const ranges: Range<Decoration>[] = []
  let index = doc.indexOf(query)
  while (index !== -1) {
    ranges.push(hitMark.range(index, index + query.length))
    index = doc.indexOf(query, index + query.length)
  }
  return Decoration.set(ranges, true)
}

const tagField = StateField.define<DecorationSet>({
  create: (state) => tagDecorations(state.doc.toString()),
  update: (decorations, transaction) =>
    transaction.docChanged ? tagDecorations(transaction.state.doc.toString()) : decorations,
  provide: (field) => EditorView.decorations.from(field),
})

/** The search query is state too: the effect carries it, the field owns the derived ranges. */
const setSearch = StateEffect.define<string>()

type SearchState = { query: string; hits: DecorationSet }

const searchField = StateField.define<SearchState>({
  create: () => ({ query: '', hits: Decoration.none }),
  update: (value, transaction) => {
    let query = value.query
    for (const effect of transaction.effects) {
      if (effect.is(setSearch)) query = effect.value
    }
    if (query === value.query && !transaction.docChanged) return value
    return { query, hits: hitDecorations(transaction.state.doc.toString(), query) }
  },
  provide: (field) => EditorView.decorations.from(field, (value) => value.hits),
})

const initialDoc = `// Decorations, not DOM surgery.
const cache = new Map() // TODO: bound the size

export function load(key) {
  // FIXME: no error handling yet
  if (cache.has(key)) return cache.get(key)

  const value = key.toUpperCase()
  // NOTE: the example is deliberately short
  cache.set(key, value)
  return value
}
`

export default function Demo() {
  const view = useRef<EditorView | undefined>(undefined)
  const [query, setQuery] = useState('cache')
  const [counts, setCounts] = useState({ tags: 3, hits: 0 })

  const extensions = useMemo<Extension[]>(() => [tagField, searchField], [])

  const refresh = (nextQuery = query) => {
    const target = view.current
    if (!target) return
    const state = target.state
    setCounts({
      tags: state.field(tagField).size,
      hits: state.field(searchField).hits.size,
    })
    setQuery(nextQuery)
  }

  const search = (nextQuery: string) => {
    setQuery(nextQuery)
    const target = view.current
    if (!target) return
    // One transaction carries the effect; the field derives the decorations from it.
    target.dispatch({ effects: setSearch.of(nextQuery) })
    refresh(nextQuery)
  }

  const jumpToNext = () => {
    const target = view.current
    if (!target || query.length < 2) return
    const doc = target.state.doc.toString()
    const from = target.state.selection.main.head
    const next = doc.indexOf(query, from + 1)
    const position = next === -1 ? doc.indexOf(query) : next
    if (position === -1) return
    target.dispatch({
      selection: EditorSelection.range(position, position + query.length),
      scrollIntoView: true,
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => search(event.target.value)}
          placeholder="search in the document"
          aria-label="Search in the document"
          className="h-8 w-48 rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="button"
          onClick={jumpToNext}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Jump to next hit
        </button>
        <button
          type="button"
          onClick={() => {
            const target = view.current
            if (!target) return
            const end = target.state.doc.length
            target.dispatch({
              changes: { from: end, insert: '\n// TODO: added from a transaction\n' },
              scrollIntoView: true,
            })
            // The tag field recomputed itself on `docChanged`; read it back.
            refresh()
          }}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Insert a TODO
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          tags: {counts.tags} · hits: {counts.hits}
        </span>
      </div>

      <CodeEditor
        initialDoc={initialDoc}
        label="Editor with decorations"
        extensions={extensions}
        onView={(created) => {
          view.current = created
          created.dispatch({ effects: setSearch.of(query) })
          refresh(query)
        }}
        minHeight="12rem"
      />

      <div className="grid gap-3 sm:grid-cols-2 text-xs">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Tag field</p>
          <p className="mt-1 text-muted-foreground">
            Recomputes only when the document changes:{' '}
            <code className="rounded bg-muted px-1">TODO</code>,{' '}
            <code className="rounded bg-muted px-1">FIXME</code>,{' '}
            <code className="rounded bg-muted px-1">NOTE</code> are marked from a regex, so typing
            one highlights it immediately.
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Search field</p>
          <p className="mt-1 text-muted-foreground">
            Query arrives as an <code className="rounded bg-muted px-1">Effect</code>, hits are
            derived ranges. Type in the box: the editor re-renders, the React tree does not touch
            the document.
          </p>
        </div>
      </div>
    </div>
  )
}
