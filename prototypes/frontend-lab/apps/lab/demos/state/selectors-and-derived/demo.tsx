import { createStoreContext, useShallow } from '@frontend-lab/state'
import { useEffect, useRef, useState } from 'react'

/*
 * Selectors are the whole performance story of a store.
 *
 *   - A component re-renders when its selected value changes, not when the store changes.
 *   - A selector that builds a new object/array must be wrapped in `useShallow`, or the new identity
 *     re-renders on every store update.
 *   - A selector created per render (`useSelector((s) => s.todos.find(...))`) is fine when it returns
 *     a stable reference (the todo object itself) and wrong when it returns a derived array.
 *
 * The render counters below make the difference visible instead of theoretical.
 */

type Todo = { id: number; text: string; done: boolean }
type Filter = 'all' | 'open' | 'done'

type TodoState = {
  todos: Todo[]
  filter: Filter
  actions: {
    toggle: (id: number) => void
    add: () => void
    setFilter: (filter: Filter) => void
  }
}

let nextId = 4

const todosStore = createStoreContext<TodoState>(
  (set) => ({
    todos: [
      { id: 1, text: 'Read the store factory demo', done: true },
      { id: 2, text: 'Subscribe with a selector', done: false },
      { id: 3, text: 'Wrap derived selectors in useShallow', done: false },
    ],
    filter: 'all',
    actions: {
      toggle: (id) =>
        set((state) => ({
          todos: state.todos.map((todo) => (todo.id === id ? { ...todo, done: !todo.done } : todo)),
        })),
      add: () =>
        set((state) => ({
          todos: [...state.todos, { id: nextId++, text: 'New item', done: false }],
        })),
      setFilter: (filter) => set({ filter }),
    },
  }),
  { name: 'todos' },
)

/** Derived list: a new array every call, so it needs `useShallow` at the call site. */
const selectVisibleIds = (state: TodoState): number[] =>
  state.todos
    .filter((todo) =>
      state.filter === 'all' ? true : state.filter === 'open' ? !todo.done : todo.done,
    )
    .map((todo) => todo.id)

/** Derived object: same problem, same fix. */
const selectStats = (state: TodoState) => ({
  total: state.todos.length,
  done: state.todos.filter((todo) => todo.done).length,
})

const selectActions = (state: TodoState) => state.actions
const selectFilter = (state: TodoState) => state.filter
const selectTodo = (id: number) => (state: TodoState) => state.todos.find((todo) => todo.id === id)

function useRenders(): number {
  const renders = useRef(0)
  renders.current += 1
  return renders.current
}

function Stats() {
  const stats = todosStore.useSelector(useShallow(selectStats))
  const filter = todosStore.useSelector(selectFilter)
  const renders = useRenders()

  return (
    <div className="rounded-lg border border-border p-3 text-xs">
      <p className="font-medium">Derived state</p>
      <p className="mt-1 font-mono text-[11px] text-muted-foreground">
        {stats.done}/{stats.total} done · filter: {filter} · renders: {renders}
      </p>
      <p className="mt-1 text-muted-foreground">
        Two selectors, one component. `useShallow` compares the derived object field by field;
        without it this would re-render on every action.
      </p>
    </div>
  )
}

function FilterBar() {
  const filter = todosStore.useSelector(selectFilter)
  const actions = todosStore.useSelector(selectActions)
  const renders = useRenders()

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {(['all', 'open', 'done'] as const).map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => actions.setFilter(value)}
          aria-pressed={filter === value}
          className={
            filter === value
              ? 'rounded-md bg-secondary px-2.5 py-1 font-medium text-secondary-foreground'
              : 'rounded-md border border-border px-2.5 py-1 text-muted-foreground hover:bg-muted'
          }
        >
          {value}
        </button>
      ))}
      <span className="font-mono text-[10px] text-muted-foreground">renders: {renders}</span>
      <span className="ml-auto font-mono text-[10px] text-muted-foreground">
        actions are stable, so this component never updates on a todo change
      </span>
    </div>
  )
}

function Row({ id }: { id: number }) {
  // Selects one todo object: identity is stable unless that todo changed.
  const todo = todosStore.useSelector(selectTodo(id))
  const actions = todosStore.useSelector(selectActions)
  const renders = useRenders()
  if (!todo) return null

  return (
    <li className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm">
      <input
        type="checkbox"
        checked={todo.done}
        onChange={() => actions.toggle(id)}
        className="size-4 accent-primary"
        aria-label={`Toggle ${todo.text}`}
      />
      <span className={todo.done ? 'flex-1 text-muted-foreground line-through' : 'flex-1'}>
        {todo.text}
      </span>
      <span className="font-mono text-[10px] text-muted-foreground">renders: {renders}</span>
    </li>
  )
}

function RowList() {
  const ids = todosStore.useSelector(useShallow(selectVisibleIds))
  const renders = useRenders()

  return (
    <div className="space-y-1">
      <p className="font-mono text-[10px] text-muted-foreground">
        list renders: {renders} · visible: {ids.length}
      </p>
      <ul className="space-y-1">
        {ids.map((id) => (
          <Row key={id} id={id} />
        ))}
      </ul>
    </div>
  )
}

function SubscriptionLog() {
  const store = todosStore.useStoreApi()
  const [events, setEvents] = useState<string[]>([])

  useEffect(() => {
    // `useStoreApi()` is the escape hatch: plain `subscribe`, no React involved.
    return store.subscribe((state) => {
      setEvents((previous) =>
        [`${state.todos.length} todos · filter ${state.filter}`, ...previous].slice(0, 3),
      )
    })
  }, [store])

  return (
    <div className="rounded-lg border border-border p-3 text-xs">
      <p className="font-medium">Outside React</p>
      <p className="mt-1 text-muted-foreground">
        <code className="rounded bg-muted px-1">store.subscribe</code> sees every state, without
        re-rendering anything:
      </p>
      <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground">
        {events.length === 0 ? <li>waiting for a change…</li> : null}
        {events.map((event, index) => (
          <li key={index}>{event}</li>
        ))}
      </ul>
    </div>
  )
}

function AddButton() {
  const actions = todosStore.useSelector(selectActions)
  const renders = useRenders()

  return (
    <button
      type="button"
      onClick={actions.add}
      className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring"
    >
      Add an item <span className="font-mono opacity-70">(renders: {renders})</span>
    </button>
  )
}

export default function Demo() {
  return (
    <todosStore.Provider>
      <div className="space-y-4">
        <FilterBar />
        <div className="grid gap-3 sm:grid-cols-2">
          <RowList />
          <div className="space-y-3">
            <Stats />
            <AddButton />
            <SubscriptionLog />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Toggle a checkbox: the list and the other rows keep their render counts — only the row
          whose todo changed, plus the two components that derive from all todos, update. That is
          the whole value of selectors, and it is measurable in the DOM.
        </p>
      </div>
    </todosStore.Provider>
  )
}
