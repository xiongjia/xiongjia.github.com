import { useEffect, useSyncExternalStore } from 'react'

import { createPref, usePref } from './pref'

/*
 * Theme mode: the user picks `light`, `dark` or `system`; `system` resolves through
 * `prefers-color-scheme` and keeps following OS changes.
 *
 * The resolved value lands on `<html data-theme="...">`, which is the single switch `tokens.css`
 * keys off. `index.html` sets the same attribute before first paint; this module keeps it correct
 * afterwards (switching, OS changes, other tabs).
 */

export const themeValues = ['light', 'dark', 'system'] as const

export type ThemeMode = (typeof themeValues)[number]
export type ResolvedTheme = 'light' | 'dark'

export const themePref = createPref({
  key: 'frontend-lab:theme',
  values: themeValues,
  fallback: 'system',
})

const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

/** Live OS preference; only `system` mode reads it, but subscribing unconditionally is cheaper. */
function useSystemDark(): boolean {
  return useSyncExternalStore(
    (listener) => {
      const query = darkQuery()
      query.addEventListener('change', listener)
      return () => query.removeEventListener('change', listener)
    },
    () => darkQuery().matches,
    () => false,
  )
}

/** Stamp the resolved mode on `<html>`; a no-op when the bootstrap already set it. */
export function applyTheme(theme: ResolvedTheme): void {
  if (document.documentElement.dataset.theme === theme) return
  document.documentElement.dataset.theme = theme
}

export function useTheme(): {
  mode: ThemeMode
  resolved: ResolvedTheme
  setMode: (mode: ThemeMode) => void
} {
  const [mode, setMode] = usePref(themePref)
  const systemDark = useSystemDark()
  const resolved: ResolvedTheme = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode

  useEffect(() => {
    applyTheme(resolved)
  }, [resolved])

  return { mode, resolved, setMode }
}
