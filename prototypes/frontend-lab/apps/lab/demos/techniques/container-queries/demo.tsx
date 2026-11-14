import { useEffect, useRef, useState } from 'react'

/**
 * `@container` variants answer a different question from `sm:` / `md:`: not "how wide is the
 * viewport" but "how wide is my container". The same card markup is rendered twice below — once
 * keyed to the viewport, once to its container — and the two disagree the moment the container is
 * narrower than the page.
 */
function useContainerWidth(ref: React.RefObject<HTMLDivElement | null>): number {
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries.at(0)
      if (entry) setWidth(Math.round(entry.contentRect.width))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])

  return width
}

/** A card whose internals reflow on container queries instead of viewport breakpoints. */
function ContainerCard() {
  return (
    <div className="@container">
      <div className="rounded-lg border border-border bg-background p-3 @md:p-4">
        <div className="flex flex-col gap-3 @sm:flex-row @sm:items-center">
          <div className="grid size-12 shrink-0 place-items-center rounded-md bg-primary font-mono text-xs text-primary-foreground">
            @sm
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">Container-aware card</p>
            <p className="text-xs text-muted-foreground @lg:text-sm">
              Padding and layout follow the container, not the window.
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">@sm</span>
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">@md</span>
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">@lg</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/** The same card, but keyed to the viewport: it cannot react to a narrow column. */
function ViewportCard() {
  return (
    <div className="rounded-lg border border-dashed border-border bg-background p-3 md:p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="grid size-12 shrink-0 place-items-center rounded-md bg-secondary font-mono text-xs text-secondary-foreground">
          sm:
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Viewport-aware card</p>
          <p className="text-xs text-muted-foreground lg:text-sm">
            Padding and layout follow the window; in a narrow column this overflows.
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">sm</span>
          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">md</span>
          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">lg</span>
        </div>
      </div>
    </div>
  )
}

export default function Demo() {
  const [width, setWidth] = useState(420)
  const containerRef = useRef<HTMLDivElement>(null)
  const measured = useContainerWidth(containerRef)

  return (
    <div className="space-y-5">
      <label className="block space-y-1">
        <span className="flex items-center justify-between text-xs font-medium tracking-wide text-muted-foreground uppercase">
          <span>container width</span>
          <span className="font-mono normal-case">
            {width}px · measured {measured}px
          </span>
        </span>
        <input
          type="range"
          min={220}
          max={720}
          step={10}
          value={width}
          onChange={(event) => setWidth(Number(event.target.value))}
          className="w-full accent-primary"
          aria-label="Container width in pixels"
        />
      </label>

      <div
        ref={containerRef}
        style={{ width: `${width}px`, maxWidth: '100%' }}
        className="space-y-3"
      >
        <ContainerCard />
        <ViewportCard />
      </div>

      <section className="space-y-2 text-xs text-muted-foreground">
        <p>
          Drag the slider: the solid card switches to a row at a 24rem container and grows its text
          at 28rem. The dashed one never moves — the browser reports the same viewport for both.
        </p>
        <p className="font-mono text-[11px]">
          container-type: inline-size · @container · @sm:flex-row · @md:p-4 · @lg:text-sm
        </p>
        <p>
          A named container (<code className="rounded bg-muted px-1">@container/card</code>) lets a
          nested card answer to its own width instead of the nearest ancestor; that is the only way
          to keep two levels of container queries from fighting each other.
        </p>
      </section>
    </div>
  )
}
