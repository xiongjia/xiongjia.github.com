import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'

/*
 * Three things variants buy you, in one demo:
 *
 *   orchestration  the parent animates the children in sequence (`staggerChildren`), so the timing
 *                  lives in one place instead of in every child's `transition`
 *   layout         `layout` animates position changes caused by a reorder — no width/height math,
 *                  Motion measures before and after and interpolates with a transform
 *   presence       `AnimatePresence` keeps an element mounted until its exit animation finishes
 */

type Item = { id: number; label: string }

const initial: Item[] = [
  { id: 1, label: 'Design tokens' },
  { id: 2, label: 'Component API' },
  { id: 3, label: 'Interaction states' },
  { id: 4, label: 'Accessibility' },
]

const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 320, damping: 26 } },
  exit: { opacity: 0, x: 16, transition: { duration: 0.15 } },
}

let nextId = 10

export default function Demo() {
  const [items, setItems] = useState(initial)
  const [selected, setSelected] = useState<number | null>(null)
  const reduced = useReducedMotion()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setItems((current) => [...current].sort(() => Math.random() - 0.5))}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Shuffle (layout animation)
        </button>
        <button
          type="button"
          onClick={() =>
            setItems((current) => [...current, { id: nextId++, label: `Item ${nextId - 1}` }])
          }
          className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
        >
          Add
        </button>
        <button
          type="button"
          onClick={() =>
            setItems((current) =>
              selected === null ? current : current.filter((i) => i.id !== selected),
            )
          }
          disabled={selected === null}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-ring"
        >
          Remove selected (exit animation)
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          {reduced ? 'reduced motion: transitions shortened' : 'full motion'}
        </span>
      </div>

      <motion.ul
        variants={listVariants}
        initial="hidden"
        animate="show"
        className="space-y-2"
        // A reorder animates the *positions* of the existing nodes; `layout` on the parent keeps the
        // measurement pass to one place.
        layout
      >
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item) => (
            <motion.li
              key={item.id}
              layout
              variants={itemVariants}
              exit="exit"
              onClick={() => setSelected(item.id)}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              transition={reduced ? { duration: 0.01 } : undefined}
              className={[
                'flex cursor-pointer items-center justify-between rounded-lg border p-3 text-sm',
                selected === item.id
                  ? 'border-primary bg-secondary font-medium'
                  : 'border-border bg-card',
              ].join(' ')}
            >
              <span>{item.label}</span>
              <span className="font-mono text-[10px] text-muted-foreground">#{item.id}</span>
            </motion.li>
          ))}
        </AnimatePresence>
      </motion.ul>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Variants, not props on every child</p>
          <pre className="mt-1 overflow-x-auto font-mono text-[10px] leading-4 text-muted-foreground">
            {`list:  { show: { transition: { staggerChildren: 0.06 } } }
item:  { hidden: { opacity: 0, y: 8 },
         show:   { opacity: 1, y: 0 },
         exit:   { opacity: 0, x: 16 } }`}
          </pre>
          <p className="mt-1 text-muted-foreground">
            The child names a state, the parent decides the timing. A new item inherits both without
            repeating a `transition`.
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">What `layout` does</p>
          <p className="mt-1 text-muted-foreground">
            Shuffle: Motion measures each node before and after the DOM change and animates the
            difference with a transform. There is no height/width animation and no reflow per frame
            — which is why `layout` is cheap enough to use on a list.
          </p>
          <p className="mt-2 text-muted-foreground">
            Reduced motion comes from `useReducedMotion()`: the values are still applied, the
            duration collapses to zero, so the end state is identical without the movement.
          </p>
        </div>
      </div>
    </div>
  )
}
