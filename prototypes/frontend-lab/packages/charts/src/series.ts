/*
 * Deterministic sample data.
 *
 * Every renderer in the B15 comparison draws the *same* numbers, so a difference in the output is a
 * difference in the renderer, not in the data. A seeded LCG instead of `Math.random()` is what makes
 * that reproducible across renders and reloads.
 */

export type ChartPoint = {
  /** Category label, e.g. `W1`. */
  label: string
  value: number
  /** Previous period, drawn as a dashed reference line. */
  previous: number
}

/** A tiny linear congruential generator: deterministic, dependency-free, good enough for demo data. */
function seeded(seed: number): () => number {
  let state = seed
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648
    return state / 2147483648
  }
}

export function createSeries(count = 12, seed = 42): ChartPoint[] {
  const random = seeded(seed)

  return Array.from({ length: count }, (_, index) => ({
    label: `W${index + 1}`,
    value: 40 + Math.round(random() * 60),
    previous: 40 + Math.round(random() * 60),
  }))
}

export type SeriesSummary = {
  total: number
  average: number
  latest: number
  /** Percentage change between the last two periods, rounded. */
  deltaPct: number
  peak: number
}

export function summarize(series: ChartPoint[]): SeriesSummary {
  const values = series.map((point) => point.value)
  const total = values.reduce((sum, value) => sum + value, 0)
  const latest = values.at(-1) ?? 0
  const before = values.at(-2) ?? latest
  const average = values.length === 0 ? 0 : total / values.length

  return {
    total,
    average: Math.round(average * 10) / 10,
    latest,
    deltaPct: before === 0 ? 0 : Math.round(((latest - before) / before) * 1000) / 10,
    peak: values.length === 0 ? 0 : Math.max(...values),
  }
}

/** One-line description reused as the accessible name of every renderer. */
export function describeSeries(series: ChartPoint[]): string {
  const summary = summarize(series)
  return `${series.length} weeks, peak ${summary.peak}, latest ${summary.latest} (${summary.deltaPct > 0 ? '+' : ''}${summary.deltaPct}%)`
}

/** Resolve a semantic token to a colour a canvas can use. */
export function tokenColor(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value === '' ? fallback : value
}
