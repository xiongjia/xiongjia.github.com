import { SplitPane, useSplitSize } from '@frontend-lab/panels'
import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'frontend-lab:split-demo'

/** Width readout per pane: the container queries inside depend on this, not on the window. */
function useWidth(ref: React.RefObject<HTMLDivElement | null>): number {
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

/** A card that follows its pane width — the B8 container query, now inside a resizable pane. */
function PaneCard({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="@container p-3">
      <div className="rounded-md border border-border bg-background p-2 @sm:p-3">
        <div className="flex flex-col gap-2 @sm:flex-row @sm:items-center @sm:justify-between">
          <p className="text-xs font-semibold">{title}</p>
          <span className="w-fit rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            @sm
          </span>
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>
      </div>
    </div>
  )
}

export default function Demo() {
  const split = useSplitSize({ storageKey: STORAGE_KEY, defaultSize: 55, min: 20, max: 80 })
  const [stored, setStored] = useState('')
  const first = useRef<HTMLDivElement>(null)
  const second = useRef<HTMLDivElement>(null)
  const firstWidth = useWidth(first)
  const secondWidth = useWidth(second)

  // The stored value is read back from `localStorage`, so the demo shows the real persistence.
  useEffect(() => {
    const read = () => setStored(window.localStorage.getItem(STORAGE_KEY) ?? '—')
    read()
    window.addEventListener('storage', read)
    return () => window.removeEventListener('storage', read)
  }, [split.size])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-mono text-[11px] text-muted-foreground">
          first pane: {split.size.toFixed(1)}% · stored: {stored}
        </span>
        <button
          type="button"
          onClick={split.reset}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Reset to 55% (double-click the handle too)
        </button>
      </div>

      <SplitPane
        size={split.size}
        onSizeChange={split.setSize}
        label="Resize the two panes"
        firstLabel="Outline pane"
        secondLabel="Preview pane"
        className="h-72"
        first={
          <div ref={first} className="h-full">
            <div className="border-b border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground">
              {firstWidth}px
            </div>
            <PaneCard title="Outline" hint="Drag the divider, or focus it and press arrow keys." />
            <PaneCard
              title="Same markup"
              hint="Both cards reflow on the pane width, not the page."
            />
          </div>
        }
        second={
          <div ref={second} className="h-full">
            <div className="border-b border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground">
              {secondWidth}px
            </div>
            <div className="p-3">
              <SplitPane
                direction="vertical"
                size={split.size}
                onSizeChange={(next) => split.setSize(100 - next)}
                label="Resize the nested preview panes"
                firstLabel="Canvas"
                secondLabel="Inspector"
                className="h-48"
                first={
                  <div className="p-3">
                    <PaneCard
                      title="Nested vertical split"
                      hint="The top pane is sized by the same percentage, inverted."
                    />
                  </div>
                }
                second={
                  <div className="p-3">
                    <PaneCard title="Inspector" hint="Small panes need small breakpoints." />
                  </div>
                }
              />
            </div>
          </div>
        }
      />

      <p className="text-xs text-muted-foreground">
        Reload the page: the split comes back. The size is a percentage in
        <code className="mx-1 rounded bg-muted px-1">localStorage</code>(
        <code className="rounded bg-muted px-1">{STORAGE_KEY}</code>), clamped to 20–80% on the way
        in and out, so a hand-edited value cannot collapse a pane. Panes are
        <code className="mx-1 rounded bg-muted px-1">@container</code>s — resize the split and the
        cards reflow while the page width never changes.
      </p>
    </div>
  )
}
