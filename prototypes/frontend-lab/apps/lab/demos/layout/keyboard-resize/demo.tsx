import { SplitPane, useSplitSize } from '@frontend-lab/panels'
import { useEffect, useRef, useState } from 'react'

/*
 * The keyboard path is the one that gets skipped and then breaks. This demo focuses the separator,
 * prints every key it handled and reads `aria-valuenow` back from the DOM, so "the keyboard works"
 * is something a test can assert instead of something a reviewer assumes.
 */

type LogEntry = { label: string; size: string }

export default function Demo() {
  const split = useSplitSize({ defaultSize: 50, min: 15, max: 85 })
  const container = useRef<HTMLDivElement>(null)
  const [keys, setKeys] = useState<string[]>([])
  const [log, setLog] = useState<LogEntry[]>([])
  const [aria, setAria] = useState({ now: 50, orientation: 'vertical' })
  const [focused, setFocused] = useState(false)

  // Read the separator's own attributes: the ARIA contract and the inline size must agree.
  useEffect(() => {
    const separator = container.current?.querySelector<HTMLElement>('[role="separator"]')
    if (!separator) return
    setAria({
      now: Number(separator.getAttribute('aria-valuenow')),
      orientation: separator.getAttribute('aria-orientation') ?? '?',
    })
    setLog((previous) =>
      [{ label: 'size changed', size: `${split.size.toFixed(1)}%` }, ...previous].slice(0, 5),
    )
  }, [split.size])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() =>
            container.current?.querySelector<HTMLElement>('[role="separator"]')?.focus()
          }
          className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
        >
          Focus the separator
        </button>
        <button
          type="button"
          onClick={split.reset}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Reset
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          aria-orientation=&quot;{aria.orientation}&quot; · aria-valuenow=&quot;{aria.now}&quot; ·{' '}
          {focused ? 'focused' : 'not focused'}
        </span>
      </div>

      <div
        ref={container}
        onKeyDownCapture={(event) => setKeys((previous) => [event.key, ...previous].slice(0, 8))}
        onFocusCapture={() => setFocused(true)}
        onBlurCapture={() => setFocused(false)}
      >
        <SplitPane
          size={split.size}
          onSizeChange={split.setSize}
          label="Keyboard-resizable split"
          firstLabel="Left pane"
          secondLabel="Right pane"
          className="h-40"
          first={
            <div className="p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Left</p>
              <p className="mt-1">
                Arrows move 4%, PageUp/PageDown 12%, Home/End jump to the limits, Enter resets to
                50%, double-click resets too.
              </p>
            </div>
          }
          second={
            <div className="p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Right</p>
              <p className="mt-1">{split.size.toFixed(1)}% — the separator owns the value.</p>
            </div>
          }
        />
      </div>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Keys seen</p>
          <p className="mt-1 font-mono text-[11px] break-words text-muted-foreground">
            {keys.length === 0 ? 'focus the separator and press a key…' : keys.join('  ')}
          </p>
          <p className="mt-2 font-medium">Size changes</p>
          <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-muted-foreground">
            {log.map((entry, index) => (
              <li key={index}>
                {entry.label} → {entry.size}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Why a separator</p>
          <p className="mt-1 text-muted-foreground">
            <code className="rounded bg-muted px-1">role=&quot;separator&quot;</code> with
            <code className="mx-1 rounded bg-muted px-1">aria-valuenow</code> is the contract a
            native splitter exposes: focusable, keyboard-adjustable, and announced with its current
            value. A div with a pointer handler implements a third of that.
          </p>
          <p className="mt-2 text-muted-foreground">
            The value is rounded before it reaches ARIA, so a 4% step cannot announce
            <code className="mx-1 rounded bg-muted px-1">54.00000000000001</code>.
          </p>
        </div>
      </div>
    </div>
  )
}
