import { Button, type ButtonSize, type ButtonVariant, cn } from '@frontend-lab/ui'
import { useState } from 'react'

const variants: ButtonVariant[] = ['primary', 'secondary', 'ghost']
const sizes: ButtonSize[] = ['sm', 'md']

export function HelloDemoRoute() {
  const [count, setCount] = useState(0)
  const [variant, setVariant] = useState<ButtonVariant>('primary')
  const [size, setSize] = useState<ButtonSize>('md')

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Foundations / B1
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">Inline demo</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          A hand-written demo proving the shell works: React state, shared UI package, Tailwind
          tokens, keyboard focus rings.
        </p>
      </header>

      <section
        className="rounded-lg border border-border bg-card p-5"
        aria-label="Inline demo playground"
      >
        <div className="flex flex-wrap items-center gap-3">
          <Button variant={variant} size={size} onClick={() => setCount((value) => value + 1)}>
            Clicked {count} {count === 1 ? 'time' : 'times'}
          </Button>
          <Button variant="ghost" size={size} onClick={() => setCount(0)} disabled={count === 0}>
            Reset
          </Button>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <fieldset className="space-y-2">
            <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Variant
            </legend>
            <div className="flex gap-2">
              {variants.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setVariant(item)}
                  aria-pressed={variant === item}
                  className={cn(
                    'rounded-md border px-2.5 py-1.5 text-xs outline-none',
                    'focus-visible:ring-2 focus-visible:ring-ring',
                    variant === item
                      ? 'border-primary bg-secondary font-medium'
                      : 'border-border text-muted-foreground hover:bg-muted',
                  )}
                >
                  {item}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className="space-y-2">
            <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Size
            </legend>
            <div className="flex gap-2">
              {sizes.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setSize(item)}
                  aria-pressed={size === item}
                  className={cn(
                    'rounded-md border px-2.5 py-1.5 text-xs outline-none',
                    'focus-visible:ring-2 focus-visible:ring-ring',
                    size === item
                      ? 'border-primary bg-secondary font-medium'
                      : 'border-border text-muted-foreground hover:bg-muted',
                  )}
                >
                  {item}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
      </section>

      <section className="space-y-2 text-sm text-muted-foreground">
        <h2 className="text-sm font-semibold text-foreground">What this checks</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <code className="rounded bg-muted px-1 py-0.5 text-xs">workspace:*</code> dependency
            resolves from <code className="rounded bg-muted px-1 py-0.5 text-xs">packages/ui</code>{' '}
            through a Vite alias, so no package build step is needed.
          </li>
          <li>
            Semantic tokens (
            <code className="rounded bg-muted px-1 py-0.5 text-xs">bg-primary</code>,{' '}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">border-border</code>) come from
            the shared token layer; B5 adds light/dark and B6 adds multiple style presets.
          </li>
          <li>
            <code className="rounded bg-muted px-1 py-0.5 text-xs">cn()</code> merges Tailwind
            classes, so caller overrides win over component defaults.
          </li>
          <li>
            Tab through the controls: focus rings must be visible on every interactive element.
          </li>
        </ul>
      </section>

      <section className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Preview / Source / Notes tabs, the demo registry and the error boundary arrive in B3.
      </section>
    </div>
  )
}
