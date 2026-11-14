import { createContext, useContext, useState, type ReactNode } from 'react'
import { useStore } from 'zustand'
import { createStore, type StateCreator, type StoreApi } from 'zustand/vanilla'

/*
 * A store *factory*, not a global store.
 *
 * `zustand`'s default export (`create`) gives you one module-level store: every component that
 * imports it shares one instance, forever. That is the right default for an app-wide session, and
 * the wrong one for a reusable component — two editors, two kanban boards or two demos on one page
 * would silently share their state.
 *
 * This factory puts a vanilla store in a React context instead:
 *
 *   const counter = createStoreContext<CounterState>((set) => ({ … }))
 *   <counter.Provider>…</counter.Provider>
 *   const count = counter.useSelector(selectCount)
 *
 * Each `Provider` mounts one store, its children subscribe to it, and a second `Provider` is a
 * second, independent instance.
 */

export type StoreContext<T> = {
  /** One store per mount; nesting providers gives independent instances. */
  Provider: (props: { children: ReactNode }) => ReactNode
  /** The raw store: `getState`, `setState`, `subscribe` — usable outside React too. */
  useStoreApi: () => StoreApi<T>
  /** Subscribe to a slice. The selector must return a stable value (see `useShallow`). */
  useSelector: <U>(selector: (state: T) => U) => U
}

export function createStoreContext<T>(
  createState: StateCreator<T, [], []>,
  options: { name?: string } = {},
): StoreContext<T> {
  const Context = createContext<StoreApi<T> | null>(null)
  const name = options.name ?? 'store'

  function Provider({ children }: { children: ReactNode }) {
    // `useState` with a factory, not `useRef`/module scope: StrictMode may render twice, and the
    // store must be created once per mounted instance, not once per render.
    const [store] = useState(() => createStore<T>()(createState))
    return <Context.Provider value={store}>{children}</Context.Provider>
  }

  function useStoreApi(): StoreApi<T> {
    const store = useContext(Context)
    if (!store) {
      throw new Error(`[${name}] no provider found — wrap the tree in <Provider> from this factory`)
    }
    return store
  }

  function useSelector<U>(selector: (state: T) => U): U {
    return useStore(useStoreApi(), selector)
  }

  return { Provider, useStoreApi, useSelector }
}
