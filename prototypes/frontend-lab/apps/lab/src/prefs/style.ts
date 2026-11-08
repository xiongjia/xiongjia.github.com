import { useEffect } from 'react'

import { createPref, usePref } from './pref'

/*
 * Style presets: `default`, `sharp`, `warm`, `mono`.
 *
 * A preset is a set of semantic-token overrides (see `packages/ui/src/styles/styles.css`) selected
 * by `data-style` on `<html>`. Nothing in the component tree takes a `style` prop, so the whole
 * site — shell, MDX pages and every demo — follows the switch at once.
 *
 * This list is the source of truth for the header control; `pnpm style:check` compares it against
 * the CSS selectors and the palette, and refuses drift in either direction.
 */

export const styleValues = ['default', 'sharp', 'warm', 'mono'] as const

export type StylePreset = (typeof styleValues)[number]

export const stylePref = createPref({
  key: 'frontend-lab:style',
  values: styleValues,
  fallback: 'default',
})

/** Stamp the preset on `<html>`; a no-op when the bootstrap already set it. */
export function applyStyle(preset: StylePreset): void {
  if (document.documentElement.dataset.style === preset) return
  document.documentElement.dataset.style = preset
}

export function useStyle(): {
  preset: StylePreset
  setPreset: (preset: StylePreset) => void
} {
  const [preset, setPreset] = usePref(stylePref)

  useEffect(() => {
    applyStyle(preset)
  }, [preset])

  return { preset, setPreset }
}
