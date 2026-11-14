import { useCallback, useState } from 'react'

/*
 * Persisted split size.
 *
 * The size is a percentage of the container, not a pixel value: a split that stored `320px` would
 * fight the layout at every other viewport width. `localStorage` is the storage because the reader
 * expects a window layout to survive a reload — the same reason the theme and style preferences
 * live there.
 *
 * Everything is clamped on the way in *and* on the way out: a hand-edited `localStorage` entry or a
 * future `min`/`max` change must not be able to produce a pane with zero width.
 */

export type SplitSizeOptions = {
  /** `localStorage` key; omit to keep the size in memory only. */
  storageKey?: string
  /** Starting percentage of the first pane. */
  defaultSize?: number
  /** Lower bound, in percent. */
  min?: number
  /** Upper bound, in percent. */
  max?: number
}

export type SplitSize = {
  /** Percentage of the container occupied by the first pane. */
  size: number
  setSize: (next: number) => void
  /** Back to `defaultSize`. */
  reset: () => void
  /** True while the stored value differs from the default. */
  changed: boolean
}

export function clampSize(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, value))
}

function readStored(key: string | undefined, fallback: number, min: number, max: number): number {
  if (!key) return fallback
  try {
    const stored = window.localStorage.getItem(key)
    if (stored === null) return fallback
    const parsed = Number.parseFloat(stored)
    // A corrupt value is not an error worth reporting: fall back and let the next write heal it.
    return Number.isFinite(parsed) ? clampSize(parsed, min, max) : fallback
  } catch {
    return fallback
  }
}

export function useSplitSize({
  storageKey,
  defaultSize = 50,
  min = 10,
  max = 90,
}: SplitSizeOptions = {}): SplitSize {
  const fallback = clampSize(defaultSize, min, max)
  const [size, setSizeState] = useState(() => readStored(storageKey, fallback, min, max))

  const setSize = useCallback(
    (next: number) => {
      const clamped = clampSize(next, min, max)
      setSizeState(clamped)
      if (!storageKey) return
      try {
        window.localStorage.setItem(storageKey, String(Math.round(clamped * 10) / 10))
      } catch {
        // Persisting is a nicety; the session keeps the chosen size.
      }
    },
    [max, min, storageKey],
  )

  const reset = useCallback(() => setSize(fallback), [fallback, setSize])

  return { size, setSize, reset, changed: Math.abs(size - fallback) > 0.05 }
}
