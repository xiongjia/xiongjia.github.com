import { useSyncExternalStore } from 'react'

/*
 * A tiny persisted-preference store.
 *
 * Preferences (theme mode, style preset, language) are read from `localStorage`, applied to
 * `<html>` by effects, and read by components. A plain module-level store keeps that readable:
 * `useSyncExternalStore` gives React a stable snapshot, and the `storage` event keeps tabs in sync.
 *
 * The bootstrap script in `index.html` duplicates the *initial* read for the theme, on purpose: it
 * has to run before React exists, or the first paint would show the wrong mode.
 */

export type Pref<T extends string> = {
  /** `localStorage` key, e.g. `frontend-lab:theme`. */
  key: string
  /** Accepted values; anything else in storage is treated as corrupt and ignored. */
  values: readonly T[]
  fallback: T
  read: () => T
  write: (value: T) => void
  subscribe: (listener: () => void) => () => void
}

export type PrefOptions<T extends string> = {
  key: string
  values: readonly T[]
  fallback: T
}

function readStored<T extends string>({ key, values, fallback }: PrefOptions<T>): T {
  try {
    const stored = window.localStorage.getItem(key)
    return values.includes(stored as T) ? (stored as T) : fallback
  } catch {
    // Storage can be unavailable (private mode, disabled cookies); the lab then runs unpersisted.
    return fallback
  }
}

export function createPref<T extends string>(options: PrefOptions<T>): Pref<T> {
  const listeners = new Set<() => void>()
  let current = readStored(options)

  const emit = () => {
    for (const listener of listeners) listener()
  }

  window.addEventListener('storage', (event) => {
    if (event.key !== options.key) return
    const next = readStored(options)
    if (next === current) return
    current = next
    emit()
  })

  return {
    key: options.key,
    values: options.values,
    fallback: options.fallback,
    read: () => current,
    write: (value) => {
      if (value === current) return
      current = value
      try {
        window.localStorage.setItem(options.key, value)
      } catch {
        // Persisting is a nicety; the session still follows the chosen value.
      }
      emit()
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
}

/** Read a preference reactively. The setter persists and notifies every subscriber. */
export function usePref<T extends string>(pref: Pref<T>): readonly [T, (value: T) => void] {
  const value = useSyncExternalStore(pref.subscribe, pref.read, () => pref.fallback)
  return [value, pref.write] as const
}
