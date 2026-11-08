import { useEffect, useState } from 'react'

const tokens = [
  'background',
  'foreground',
  'card',
  'muted',
  'muted-foreground',
  'secondary',
  'secondary-foreground',
  'accent',
  'primary',
  'primary-foreground',
  'destructive',
  'destructive-foreground',
  'border',
  'ring',
] as const

/**
 * The resolved mode, read from the DOM rather than from the theme module: a demo is a standalone
 * folder, so it consumes the public contract (`data-theme` on `<html>`) the same way a stylesheet
 * does.
 */
function useResolvedTheme(): string {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? 'light')

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.dataset.theme ?? 'light')
    })
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  return theme
}

/** Read the semantic tokens back from the cascade — the values the browser actually uses. */
function readTokenValues(): Record<string, string> {
  const styles = getComputedStyle(document.documentElement)
  return Object.fromEntries(
    tokens.map((token) => [token, styles.getPropertyValue(`--${token}`).trim()]),
  )
}

export default function Demo() {
  const theme = useResolvedTheme()
  const [values, setValues] = useState(readTokenValues)

  // Re-read after the attribute changed, so the printed values match the swatches.
  useEffect(() => {
    setValues(readTokenValues())
  }, [theme])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          resolved mode
        </span>
        <span className="rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground">
          data-theme="{theme}"
        </span>
        <span className="text-xs text-muted-foreground">
          switch Light / Dark / System in the header — every value below is re-read from the cascade
        </span>
      </div>

      <ul className="grid gap-2 sm:grid-cols-2">
        {tokens.map((token) => (
          <li key={token} className="flex items-center gap-3 rounded-lg border border-border p-2">
            <span
              aria-hidden="true"
              className="size-9 shrink-0 rounded-md border border-border"
              style={{ background: `var(--${token})` }}
            />
            <span className="min-w-0 space-y-0.5">
              <span className="block font-mono text-xs">--{token}</span>
              <span className="block truncate font-mono text-[11px] text-muted-foreground">
                {values[token]}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <p className="text-xs text-muted-foreground">
        The swatches and the resolved values come from the same variables: if a value changes for
        the mode, the swatch changes with it, and so does every component built on these tokens.
      </p>
    </div>
  )
}
