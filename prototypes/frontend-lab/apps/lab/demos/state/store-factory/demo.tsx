import { createStoreContext } from '@frontend-lab/state'
import { useRef } from 'react'
import { create } from 'zustand'

/*
 * Three counters, two architectures:
 *
 *   A and B  two `Provider`s from one factory — two stores, independent state, one implementation
 *   Shared   a module-level `create()` store — one store for the whole page, by construction
 *
 * The factory is the interesting half: it proves "per instance" is a property of the provider, not
 * something the component has to be written differently for.
 */

type CounterState = {
  count: number
  history: number[]
  actions: { increment: () => void; reset: () => void }
}

const counter = createStoreContext<CounterState>(
  (set) => ({
    count: 0,
    history: [],
    actions: {
      increment: () =>
        set((state) => ({
          count: state.count + 1,
          history: [...state.history, state.count + 1].slice(-5),
        })),
      reset: () => set({ count: 0, history: [] }),
    },
  }),
  { name: 'counter' },
)

/** Module-level store: the classic `zustand` shape, shared by every import of this module. */
const useSharedCounter = create<{ count: number; increment: () => void; reset: () => void }>(
  (set) => ({
    count: 0,
    increment: () => set((state) => ({ count: state.count + 1 })),
    reset: () => set({ count: 0 }),
  }),
)

function InstancePanel({ name }: { name: string }) {
  const count = counter.useSelector((state) => state.count)
  const actions = counter.useSelector((state) => state.actions)
  const history = counter.useSelector((state) => state.history)
  const renders = useRef(0)
  renders.current += 1

  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium">instance {name}</p>
        <span className="font-mono text-[10px] text-muted-foreground">
          renders: {renders.current}
        </span>
      </div>
      <p className="font-mono text-2xl">{count}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={actions.increment}
          className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
        >
          +
        </button>
        <button
          type="button"
          onClick={actions.reset}
          className="rounded-md border border-border px-2.5 py-1 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          reset
        </button>
      </div>
      <p className="font-mono text-[10px] break-all text-muted-foreground">
        history: [{history.join(', ')}]
      </p>
    </div>
  )
}

function SharedPanel({ name }: { name: string }) {
  const count = useSharedCounter((state) => state.count)
  const increment = useSharedCounter((state) => state.increment)
  const reset = useSharedCounter((state) => state.reset)
  const renders = useRef(0)
  renders.current += 1

  return (
    <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium">shared · {name}</p>
        <span className="font-mono text-[10px] text-muted-foreground">
          renders: {renders.current}
        </span>
      </div>
      <p className="font-mono text-2xl">{count}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={increment}
          className="rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
        >
          +
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-md border border-border px-2.5 py-1 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          reset
        </button>
      </div>
      <p className="text-[10px] text-muted-foreground">
        Both panels read the same module-level store.
      </p>
    </div>
  )
}

export default function Demo() {
  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          One factory, two independent instances
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <counter.Provider>
            <InstancePanel name="A" />
          </counter.Provider>
          <counter.Provider>
            <InstancePanel name="B" />
          </counter.Provider>
        </div>
        <p className="text-xs text-muted-foreground">
          Click A: B does not move, and only A&apos;s render counter increases. Nothing separates
          them except a different <code className="rounded bg-muted px-1">Provider</code> — the
          state shape, the actions and the components are the same code.
        </p>
      </section>

      <section className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          The same component with a module-level store
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <SharedPanel name="1" />
          <SharedPanel name="2" />
        </div>
        <p className="text-xs text-muted-foreground">
          Here one click moves both: <code className="rounded bg-muted px-1">create()</code> makes
          the store a module singleton. That is the right tool for a session-wide store and the
          wrong one for anything that can appear twice on a page.
        </p>
      </section>

      <section className="rounded-lg border border-border p-3 text-xs">
        <p className="font-medium">Why a factory and not a hook</p>
        <p className="mt-1 text-muted-foreground">
          <code className="rounded bg-muted px-1">createStoreContext</code> returns one
          <code className="mx-1 rounded bg-muted px-1">Provider</code> plus
          <code className="mx-1 rounded bg-muted px-1">useSelector</code> and
          <code className="mx-1 rounded bg-muted px-1">useStoreApi</code>. The store itself is
          created inside a <code className="rounded bg-muted px-1">useState</code> initialiser, so
          it is one store per mounted provider — not one per render, and not one per module.
        </p>
      </section>
    </div>
  )
}
