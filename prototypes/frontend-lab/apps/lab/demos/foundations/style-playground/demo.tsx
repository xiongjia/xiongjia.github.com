import { Button } from '@frontend-lab/ui'
import { useEffect, useRef, useState } from 'react'

const presets = [
  { id: 'default', label: 'Default', note: 'Blue brand, near-neutral surfaces.' },
  { id: 'sharp', label: 'Sharp', note: 'Same palette, no rounding at all.' },
  { id: 'warm', label: 'Warm', note: 'Warm neutrals, amber brand, softer corners.' },
  { id: 'mono', label: 'Mono', note: 'The foreground becomes the brand: greyscale.' },
] as const

type DisplayState = { theme: string; style: string }

/** The page contract a stylesheet sees: `data-theme` + `data-style` on `<html>`. */
function useDisplayState(): DisplayState {
  const read = (): DisplayState => ({
    theme: document.documentElement.dataset.theme ?? 'light',
    style: document.documentElement.dataset.style ?? 'default',
  })
  const [state, setState] = useState(read)

  useEffect(() => {
    const observer = new MutationObserver(() => setState(read()))
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'data-style'],
    })
    return () => observer.disconnect()
  }, [])

  return state
}

export default function Demo() {
  const { theme, style } = useDisplayState()
  const cards = useRef<Record<string, HTMLDivElement | null>>({})
  const [radii, setRadii] = useState<Record<string, string>>({})

  // Read the radius each scoped preset resolves to, so the difference is visible as a number too.
  useEffect(() => {
    const next: Record<string, string> = {}
    for (const [id, element] of Object.entries(cards.current)) {
      if (element) next[id] = getComputedStyle(element).getPropertyValue('--radius').trim()
    }
    setRadii(next)
  }, [theme, style])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium tracking-wide text-muted-foreground uppercase">global</span>
        <span className="rounded-full bg-primary px-2.5 py-1 font-medium text-primary-foreground">
          data-style="{style}"
        </span>
        <span className="rounded-full border border-border px-2.5 py-1 text-muted-foreground">
          data-theme="{theme}"
        </span>
        <span className="text-muted-foreground">
          the style select in the header changes the whole site
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {presets.map((preset) => (
          <div
            key={preset.id}
            ref={(element) => {
              cards.current[preset.id] = element
            }}
            data-style={preset.id}
            data-theme={theme}
            className="space-y-3 rounded-lg border border-border bg-background p-3 text-foreground"
          >
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-semibold">{preset.label}</p>
              <code className="font-mono text-[11px] text-muted-foreground">
                --radius: {radii[preset.id] ?? '…'}
              </code>
            </div>
            <p className="text-xs text-muted-foreground">{preset.note}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm">Primary</Button>
              <Button size="sm" variant="secondary">
                Secondary
              </Button>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                muted
              </span>
              <span className="rounded-md border border-border px-2 py-1 text-xs">border</span>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        Every card above is a plain <code>div</code> carrying its own <code>data-style</code> and{' '}
        <code>data-theme</code>: a preset is token overrides, so it scopes to any subtree instead of
        needing a provider.
      </p>
    </div>
  )
}
