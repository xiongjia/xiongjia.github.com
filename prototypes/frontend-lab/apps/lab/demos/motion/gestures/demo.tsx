import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react'
import { useRef, useState } from 'react'

/*
 * Drag as a gesture, not a listener pile.
 *
 *   drag                 the element is draggable inside its own bounds by default
 *   dragConstraints      a ref to the box it may move in; `dragElastic` softens the edges
 *   whileHover / whileTap visual feedback the browser cannot give a `div` for free
 *   dragSnapToOrigin     release and it springs back — the cheap way to "pick up a card"
 *
 * The printed numbers come from motion values (`useMotionValue` + `useSpring`), i.e. from the same
 * source the animation reads, so the readout cannot drift from the visual.
 */

export default function Demo() {
  const bounds = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const springX = useSpring(x, { stiffness: 260, damping: 30 })
  const springY = useSpring(y, { stiffness: 260, damping: 30 })
  const [last, setLast] = useState({ x: 0, y: 0, released: true })
  const [snap, setSnap] = useState(true)
  const [elastic, setElastic] = useState(0.4)
  const reduced = useReducedMotion()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={snap}
            onChange={(event) => setSnap(event.target.checked)}
            className="size-4 accent-primary"
          />
          dragSnapToOrigin
        </label>
        <label className="flex items-center gap-2">
          <span className="text-muted-foreground">dragElastic</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={elastic}
            onChange={(event) => setElastic(Number(event.target.value))}
            className="w-28 accent-primary"
            aria-label="dragElastic"
          />
          <span className="font-mono">{elastic.toFixed(1)}</span>
        </label>
        <span className="font-mono text-[11px] text-muted-foreground">
          x: {last.x.toFixed(0)} · y: {last.y.toFixed(0)} ·{' '}
          {last.released ? 'released' : 'dragging'}
        </span>
      </div>

      <div
        ref={bounds}
        className="relative grid h-64 place-items-center overflow-hidden rounded-lg border border-dashed border-border bg-muted/40"
      >
        <p className="absolute top-2 left-3 font-mono text-[10px] text-muted-foreground">
          dragConstraints box
        </p>
        <motion.div
          drag={!reduced}
          dragConstraints={bounds}
          dragElastic={elastic}
          dragSnapToOrigin={snap}
          dragMomentum={!reduced}
          whileHover={{ scale: 1.06, rotate: -1 }}
          whileTap={{ scale: 0.94, cursor: 'grabbing' }}
          onDrag={(_, info) => setLast({ x: info.point.x, y: info.point.y, released: false })}
          onDragEnd={(_, info) => setLast({ x: info.point.x, y: info.point.y, released: true })}
          style={{ x: snap ? springX : x, y: snap ? springY : y }}
          className="cursor-grab touch-none rounded-xl border border-border bg-card px-5 py-4 text-center shadow-sm select-none"
        >
          <p className="text-sm font-medium">Drag me</p>
          <p className="text-[11px] text-muted-foreground">
            {reduced ? 'drag disabled: reduced motion' : 'spring on release'}
          </p>
        </motion.div>
      </div>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Constraints are a box, not a number</p>
          <p className="mt-1 text-muted-foreground">
            Passing a ref measures the element and its container; the drag area follows the layout
            without a resize listener. `dragElastic` is what happens past the edge — 0 is a hard
            stop, 1 lets the card follow the pointer and snap back.
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Motion values are the state</p>
          <p className="mt-1 text-muted-foreground">
            `x` and `y` are `MotionValue`s: they update outside React&apos;s render loop, so a drag
            does not re-render the tree 60 times a second. The readout updates on drag events only,
            which is a deliberate, cheap compromise for a demo.
          </p>
          <p className="mt-2 text-muted-foreground">
            Pointer, mouse and touch are one gesture in Motion; the browser gets the right events
            and `touch-none` keeps the page from scrolling while dragging on a phone.
          </p>
        </div>
      </div>
    </div>
  )
}
