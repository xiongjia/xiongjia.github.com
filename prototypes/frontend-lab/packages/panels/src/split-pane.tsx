import {
  useId,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'

/*
 * A two-pane split with a real separator.
 *
 * Three input paths, one state:
 *
 *   pointer   `setPointerCapture` on the separator, so a fast drag outside the element keeps
 *             reporting (and cannot select page text on the way)
 *   keyboard  `role="separator"` + `aria-valuenow`, arrows / PageUp / PageDown / Home / End, the
 *             same contract a native scrollbar exposes
 *   reset     double-click or Enter, back to the default size
 *
 * Both panes are `@container`s, so a card inside a pane reflows on the pane width (B8) instead of
 * the window width — exactly what a resizable layout needs.
 */

export type SplitPaneProps = {
  /** `horizontal` = panes side by side (columns); `vertical` = stacked (rows). */
  direction?: 'horizontal' | 'vertical'
  first: ReactNode
  second: ReactNode
  /** Percentage of the container taken by `first`. */
  size: number
  onSizeChange: (size: number) => void
  /** Step for a single arrow key, in percent. */
  step?: number
  /** Label for the separator; a split without one is unreachable for a screen reader. */
  label: string
  /** Accessible name of the pane contents, announced instead of "group". */
  firstLabel?: string
  secondLabel?: string
  className?: string
}

export function SplitPane({
  direction = 'horizontal',
  first,
  second,
  size,
  onSizeChange,
  step = 4,
  label,
  firstLabel,
  secondLabel,
  className,
}: SplitPaneProps) {
  const horizontal = direction === 'horizontal'
  const containerRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<
    { pointerId: number; startPos: number; startSize: number; total: number } | undefined
  >(undefined)
  const [dragging, setDragging] = useState(false)
  const id = useId()
  const firstId = `${id}-first`
  const secondId = `${id}-second`

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const container = containerRef.current
    if (!container || event.button !== 0) return
    const rect = container.getBoundingClientRect()
    event.preventDefault()
    // Capture: the pointer may leave the 6px handle during a fast drag and still be ours.
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      pointerId: event.pointerId,
      startPos: horizontal ? event.clientX : event.clientY,
      startSize: size,
      total: Math.max(horizontal ? rect.width : rect.height, 1),
    }
    setDragging(true)
  }

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const delta = (horizontal ? event.clientX : event.clientY) - drag.startPos
    onSizeChange(drag.startSize + (delta / drag.total) * 100)
  }

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    dragRef.current = undefined
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const back = horizontal ? 'ArrowLeft' : 'ArrowUp'
    const forward = horizontal ? 'ArrowRight' : 'ArrowDown'

    const next =
      event.key === back
        ? size - step
        : event.key === forward
          ? size + step
          : event.key === 'PageDown'
            ? size + step * 3
            : event.key === 'PageUp'
              ? size - step * 3
              : event.key === 'Home'
                ? 0
                : event.key === 'End'
                  ? 100
                  : event.key === 'Enter'
                    ? 50
                    : undefined

    if (next === undefined) return
    event.preventDefault()
    onSizeChange(next)
  }

  return (
    <div
      ref={containerRef}
      data-split-direction={direction}
      data-split-dragging={dragging ? 'true' : 'false'}
      className={[
        'flex overflow-hidden rounded-lg border border-border bg-card',
        horizontal ? 'flex-row' : 'flex-col',
        className ?? '',
      ].join(' ')}
    >
      <div
        id={firstId}
        role="group"
        aria-label={firstLabel}
        style={{ flexBasis: `${size}%`, flexGrow: 0, flexShrink: 0 }}
        className="@container min-w-0 overflow-auto"
      >
        {first}
      </div>

      <div
        role="separator"
        tabIndex={0}
        aria-label={label}
        aria-orientation={horizontal ? 'vertical' : 'horizontal'}
        aria-controls={`${firstId} ${secondId}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(size)}
        aria-valuetext={`${Math.round(size)}% / ${Math.round(100 - size)}%`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        onDoubleClick={() => onSizeChange(50)}
        className={[
          'group relative shrink-0 touch-none outline-none select-none',
          horizontal ? 'w-1.5 cursor-col-resize' : 'h-1.5 cursor-row-resize',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
        ].join(' ')}
      >
        <span
          aria-hidden="true"
          className={[
            'absolute inset-0 transition-colors',
            dragging
              ? 'bg-primary'
              : 'bg-border group-hover:bg-primary group-focus-visible:bg-primary',
          ].join(' ')}
        />
      </div>

      <div
        id={secondId}
        role="group"
        aria-label={secondLabel}
        style={{ flexBasis: `${100 - size}%`, flexGrow: 0, flexShrink: 0 }}
        className="@container min-w-0 overflow-auto"
      >
        {second}
      </div>
    </div>
  )
}
