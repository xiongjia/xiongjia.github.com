import { Button, cn, type ButtonSize, type ButtonVariant } from '@frontend-lab/ui'
import { useEffect, useRef, useState } from 'react'

const variants: ButtonVariant[] = ['primary', 'secondary', 'ghost']
const sizes: ButtonSize[] = ['sm', 'md']

export default function Demo() {
  const [count, setCount] = useState(0)
  const [variant, setVariant] = useState<ButtonVariant>('primary')
  const [size, setSize] = useState<ButtonSize>('md')
  const [classes, setClasses] = useState('')

  const button = useRef<HTMLButtonElement>(null)

  // Read the classes back from the DOM: the merge result should be visible, not assumed.
  useEffect(() => {
    setClasses(button.current?.className ?? '')
  }, [variant, size])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          ref={button}
          variant={variant}
          size={size}
          onClick={() => setCount((value) => value + 1)}
        >
          Clicked {count} {count === 1 ? 'time' : 'times'}
        </Button>
        <Button variant="ghost" size={size} onClick={() => setCount(0)} disabled={count === 0}>
          Reset
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <fieldset className="space-y-2">
          <legend className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            variant
          </legend>
          <div className="flex flex-wrap gap-2">
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
            size
          </legend>
          <div className="flex flex-wrap gap-2">
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

      <section className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Caller override
        </h3>
        <p className="text-sm text-muted-foreground">
          The next button passes <code className="rounded bg-muted px-1">bg-accent</code> to the
          shared <code className="rounded bg-muted px-1">Button</code>. <code>cn()</code> (clsx +
          tailwind-merge) drops the conflicting <code>bg-primary</code> instead of shipping both.
        </p>
        <Button variant="primary" className="bg-accent text-secondary-foreground">
          Override wins
        </Button>
      </section>

      <section className="space-y-1">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Classes on the live button
        </h3>
        <p className="font-mono text-xs break-words text-muted-foreground">{classes || '—'}</p>
      </section>
    </div>
  )
}
