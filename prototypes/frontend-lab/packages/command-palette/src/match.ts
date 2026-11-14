/*
 * Command matching.
 *
 * A command palette is a search box first: the ranking decides whether the palette feels useful or
 * arbitrary. The rules here are deliberately boring and predictable, in this order:
 *
 *   1. the title is exactly the query
 *   2. the title starts with the query
 *   3. the query starts a word in the title ("set" -> "Open settings")
 *   4. the query appears inside the title
 *   5. the query is a subsequence of the title ("stg" -> "Settings")
 *   6. the same five checks against `keywords`
 *
 * The two fields live in separate score bands: *every* title match outranks *every* keyword match.
 * Otherwise a keyword that happens to start with the query would beat the command whose visible
 * title the user is typing, which is the one thing a palette must never do.
 *
 * Ties keep the caller's order, so a palette can present "recent" commands first and rely on the
 * sort being stable. Pure functions, no React — `apps/lab/tests/command-match.test.ts` covers them.
 */

export type PaletteCommand = {
  id: string
  title: string
  /** Group heading; commands with the same group render together, in first-seen order. */
  group?: string
  /** Extra searchable words that are not rendered ("preferences settings theme"). */
  keywords?: string
  /** Right-aligned hint, e.g. a keyboard shortcut. */
  hint?: string
  run: () => void
}

export type CommandMatch = {
  command: PaletteCommand
  score: number
  /** Character ranges of `title` to highlight; empty when the match came from `keywords`. */
  ranges: Array<[number, number]>
}

type FieldMatch = { score: number; ranges: Array<[number, number]> }

const WORD_BOUNDARY = /[^a-z0-9]/

/** Merge adjacent highlight ranges so the UI renders one `<mark>` instead of five. */
export function mergeRanges(ranges: Array<[number, number]>): Array<[number, number]> {
  const merged: Array<[number, number]> = []

  for (const [from, to] of [...ranges].sort((a, b) => a[0] - b[0])) {
    const last = merged.at(-1)
    if (last && from <= last[1]) {
      last[1] = Math.max(last[1], to)
    } else {
      merged.push([from, to])
    }
  }

  return merged
}

type Band = 'title' | 'keyword'

/** Every title score is >= 1000, every keyword score < 200. The bands never overlap. */
const bands: Record<Band, number> = { title: 1000, keyword: 100 }

function scoreField(text: string, query: string, band: Band): FieldMatch | undefined {
  const base = bands[band]
  const lower = text.toLowerCase()

  if (lower === query) return { score: base + 60, ranges: [[0, text.length]] }

  const index = lower.indexOf(query)
  if (index === 0) return { score: base + 50, ranges: [[0, query.length]] }
  if (index > 0) {
    const boundary = WORD_BOUNDARY.test(lower.charAt(index - 1))
    return {
      score: base + (boundary ? 40 : 30) - Math.min(index, 30),
      ranges: [[index, index + query.length]],
    }
  }

  // Subsequence: every character of the query appears, in order.
  const ranges: Array<[number, number]> = []
  let from = 0
  for (const character of query) {
    const at = lower.indexOf(character, from)
    if (at === -1) return undefined
    ranges.push([at, at + 1])
    from = at + 1
  }

  const first = ranges[0]?.[0] ?? 0
  const last = ranges.at(-1)?.[1] ?? first
  // A subsequence spread across the whole string matches almost everything ("set" would find
  // "share people team"); capping the span is what keeps it a fuzzy match instead of noise.
  const span = last - first
  if (span > Math.max(query.length * 3, 6)) return undefined
  // Matching initials across words is a different feature: a subsequence has to stay inside one
  // word, or "set" starts matching "Send a test message".
  if (/\s/.test(lower.slice(first, last))) return undefined

  return { score: base + 20 - Math.min(span, 20), ranges }
}

/** Rank commands against a query. An empty query keeps the caller's order untouched. */
export function matchCommands(commands: readonly PaletteCommand[], query: string): CommandMatch[] {
  const normalized = query.trim().toLowerCase()
  if (normalized === '') {
    return commands.map((command) => ({ command, score: 0, ranges: [] }))
  }

  const scored: Array<CommandMatch & { order: number }> = []

  commands.forEach((command, order) => {
    const title = scoreField(command.title, normalized, 'title')
    const keywords = command.keywords
      ? scoreField(command.keywords, normalized, 'keyword')
      : undefined
    const best = title ?? keywords
    if (!best) return

    scored.push({
      command,
      score: best.score,
      // Only the title is rendered, so keyword matches highlight nothing.
      ranges: title ? mergeRanges(title.ranges) : [],
      order,
    })
  })

  return scored
    .sort((a, b) => b.score - a.score || a.order - b.order)
    .map((match) => ({ command: match.command, score: match.score, ranges: match.ranges }))
}
