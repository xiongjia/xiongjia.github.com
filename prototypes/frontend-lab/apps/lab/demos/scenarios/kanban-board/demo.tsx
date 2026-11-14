import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { createStoreContext } from '@frontend-lab/state'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useId, useState, type FormEvent } from 'react'

/*
 * Kanban: the B14 composed scenario.
 *
 * Three single-library lessons meet here, and the point of the demo is where each one stops:
 *
 *   dnd-kit   multi-container sorting — sensors, collision, sortable per column
 *   store     the board is a `createStoreContext` instance, not a module singleton (B11)
 *   motion    enter / exit only — never `layout` on a sortable card (see the notes)
 *   browser   the board is debounced into `localStorage`, validated on the way back in
 *
 * The keyboard path is first class twice over: the sortable handle supports Space + arrows, and
 * every card carries explicit "move to previous / next column" buttons, because arrows inside a
 * sortable context stop at the container edge.
 */

type ColumnId = 'backlog' | 'doing' | 'done'

type Card = { id: string; title: string; tag: string }
type Board = { cards: Record<string, Card>; columns: Record<ColumnId, string[]> }
type BoardState = Board & { actions: BoardActions }

type BoardActions = {
  move: (cardId: string, toColumn: ColumnId, toIndex: number) => void
  add: (title: string, column: ColumnId) => void
  remove: (cardId: string) => void
  reset: () => void
}

const STORAGE_KEY = 'frontend-lab:kanban'
const COLUMNS: { id: ColumnId; title: string; hint: string }[] = [
  { id: 'backlog', title: 'Backlog', hint: 'everything not started' },
  { id: 'doing', title: 'Doing', hint: 'work in flight' },
  { id: 'done', title: 'Done', hint: 'shipped' },
]

const defaultBoard: Board = {
  cards: {
    'card-tokens': { id: 'card-tokens', title: 'Design tokens', tag: 'foundations' },
    'card-panels': { id: 'card-panels', title: 'Split pane', tag: 'layout' },
    'card-motion': { id: 'card-motion', title: 'Motion variants', tag: 'motion' },
    'card-store': { id: 'card-store', title: 'Store factory', tag: 'state' },
    'card-dnd': { id: 'card-dnd', title: 'Sortable list', tag: 'motion' },
    'card-a11y': { id: 'card-a11y', title: 'Focus rings', tag: 'a11y' },
  },
  columns: {
    backlog: ['card-tokens', 'card-a11y', 'card-motion'],
    doing: ['card-panels', 'card-store'],
    done: ['card-dnd'],
  },
}

function isBoard(value: unknown): value is Board {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<Board>
  if (typeof candidate.cards !== 'object' || candidate.cards === null) return false
  if (typeof candidate.columns !== 'object' || candidate.columns === null) return false

  for (const column of COLUMNS) {
    const ids = candidate.columns[column.id]
    if (!Array.isArray(ids) || ids.some((id) => typeof id !== 'string')) return false
    if (ids.some((id) => candidate.cards?.[id] === undefined)) return false
  }

  return true
}

/** Read the stored board once per store; invalid or stale data falls back to the defaults. */
function loadBoard(): Board {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultBoard
    const parsed: unknown = JSON.parse(raw)
    return isBoard(parsed) ? parsed : defaultBoard
  } catch {
    return defaultBoard
  }
}

function columnOf(board: Board, id: string): ColumnId | undefined {
  return COLUMNS.find((column) => board.columns[column.id].includes(id))?.id
}

function moveCard(board: Board, cardId: string, toColumn: ColumnId, toIndex: number): Board {
  const from = columnOf(board, cardId)
  if (!from) return board
  if (!board.cards[cardId]) return board

  const columns = { ...board.columns }
  const source = [...board.columns[from]]
  const fromIndex = source.indexOf(cardId)
  source.splice(fromIndex, 1)

  const target = from === toColumn ? source : [...board.columns[toColumn]]
  target.splice(Math.max(0, Math.min(toIndex, target.length)), 0, cardId)

  columns[from] = source
  columns[toColumn] = target
  return { ...board, columns }
}

/** One store per `<Board.Provider>`; persisted into `localStorage` by the component below. */
const Board = createStoreContext<BoardState>(
  (set) => ({
    ...loadBoard(),
    actions: {
      move: (cardId, toColumn, toIndex) =>
        set((state) => {
          const next = moveCard(state, cardId, toColumn, toIndex)
          return next === state ? state : next
        }),
      add: (title, column) =>
        set((state) => {
          const id = `card-${crypto.randomUUID()}`
          return {
            cards: { ...state.cards, [id]: { id, title, tag: 'new' } },
            columns: { ...state.columns, [column]: [...state.columns[column], id] },
          }
        }),
      remove: (cardId) =>
        set((state) => {
          const from = columnOf(state, cardId)
          if (!from) return state
          const cards = { ...state.cards }
          delete cards[cardId]
          return {
            cards,
            columns: {
              ...state.columns,
              [from]: state.columns[from].filter((id) => id !== cardId),
            },
          }
        }),
      reset: () => set(defaultBoard),
    },
  }),
  { name: 'kanban' },
)

/** Debounced persistence: a drag emits many updates, a reload only needs the last one. */
function usePersistedBoard() {
  const api = Board.useStoreApi()
  const [writes, setWrites] = useState(0)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let latest: BoardState | undefined
    let mounted = true

    const flush = () => {
      if (!latest) return
      const payload = JSON.stringify({ cards: latest.cards, columns: latest.columns })
      latest = undefined
      try {
        window.localStorage.setItem(STORAGE_KEY, payload)
        if (mounted) setWrites((count) => count + 1)
      } catch {
        // Storage is a nicety; the board keeps working in memory.
      }
    }

    const schedule = (state: BoardState) => {
      latest = state
      clearTimeout(timer)
      timer = setTimeout(flush, 200)
    }

    schedule(api.getState())
    const unsubscribe = api.subscribe(schedule)

    return () => {
      mounted = false
      clearTimeout(timer)
      flush()
      unsubscribe()
    }
  }, [api])

  return writes
}

function SortableCard({
  card,
  column,
  columnTitle,
  onMove,
  onRemove,
  reducedMotion,
  position,
}: {
  card: Card
  column: ColumnId
  columnTitle: string
  onMove: (cardId: string, to: ColumnId) => void
  onRemove: (cardId: string) => void
  reducedMotion: boolean
  position: number
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id, data: { column } })

  const index = COLUMNS.findIndex((entry) => entry.id === column)
  const previous = COLUMNS[index - 1]
  const next = COLUMNS[index + 1]

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      data-card={card.id}
      className={isDragging ? 'opacity-40' : ''}
    >
      {/* Motion animates opacity only: a transform here would fight dnd-kit's drag transform. */}
      <motion.div
        initial={reducedMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: reducedMotion ? 0 : 0.18 }}
        className="rounded-lg border border-border bg-card p-2.5 shadow-sm"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium">{card.title}</p>
            <p className="mt-0.5 text-[10px] tracking-wide text-muted-foreground uppercase">
              {card.tag}
            </p>
          </div>
          <button
            ref={setActivatorNodeRef}
            type="button"
            {...attributes}
            {...listeners}
            aria-label={`Reorder ${card.title}`}
            className="cursor-grab touch-none rounded px-1 py-0.5 text-[11px] text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            ⠿
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between gap-1">
          <div className="flex gap-1">
            <button
              type="button"
              disabled={!previous}
              onClick={() => previous && onMove(card.id, previous.id)}
              aria-label={previous ? `Move ${card.title} to ${previous.title}` : undefined}
              className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground outline-none disabled:opacity-30 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
            >
              ←
            </button>
            <button
              type="button"
              disabled={!next}
              onClick={() => next && onMove(card.id, next.id)}
              aria-label={next ? `Move ${card.title} to ${next.title}` : undefined}
              className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground outline-none disabled:opacity-30 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
            >
              →
            </button>
          </div>
          <button
            type="button"
            onClick={() => onRemove(card.id)}
            aria-label={`Remove ${card.title}`}
            className="rounded px-1.5 py-0.5 text-[11px] text-muted-foreground outline-none hover:bg-muted hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring"
          >
            ×
          </button>
        </div>
        <p className="sr-only">
          In {columnTitle}, position {position}.
        </p>
      </motion.div>
    </li>
  )
}

function Column({
  id,
  title,
  hint,
  cards,
  onMove,
  onRemove,
  reducedMotion,
}: {
  id: ColumnId
  title: string
  hint: string
  cards: Card[]
  onMove: (cardId: string, to: ColumnId) => void
  onRemove: (cardId: string) => void
  reducedMotion: boolean
}) {
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <section
      ref={setNodeRef}
      aria-label={`${title} column`}
      data-column={id}
      data-over={isOver ? 'true' : 'false'}
      className={[
        'flex min-w-0 flex-col rounded-lg border bg-muted/30 p-2 transition-colors',
        isOver ? 'border-primary' : 'border-border',
      ].join(' ')}
    >
      <header className="flex items-baseline justify-between px-1 pb-2">
        <p className="text-xs font-semibold">{title}</p>
        <p className="font-mono text-[10px] text-muted-foreground">{cards.length}</p>
      </header>

      <SortableContext items={cards.map((card) => card.id)} strategy={verticalListSortingStrategy}>
        <ul className="flex min-h-24 flex-1 flex-col gap-1.5">
          <AnimatePresence initial={false}>
            {cards.map((card, index) => (
              <SortableCard
                key={card.id}
                card={card}
                column={id}
                columnTitle={title}
                onMove={onMove}
                onRemove={onRemove}
                reducedMotion={reducedMotion}
                position={index + 1}
              />
            ))}
          </AnimatePresence>
        </ul>
      </SortableContext>

      <p className="px-1 pt-2 text-[10px] text-muted-foreground">{hint}</p>
    </section>
  )
}

function BoardView() {
  const api = Board.useStoreApi()
  const cards = Board.useSelector((state) => state.cards)
  const columns = Board.useSelector((state) => state.columns)
  const actions = Board.useSelector((state) => state.actions)
  const writes = usePersistedBoard()
  const reducedMotion = useReducedMotion() ?? false

  const [activeId, setActiveId] = useState<string | null>(null)
  const [log, setLog] = useState<string[]>([])
  const [title, setTitle] = useState('')
  const [target, setTarget] = useState<ColumnId>('backlog')
  const inputId = useId()

  const push = (entry: string) => setLog((previous) => [entry, ...previous].slice(0, 8))

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const announcements: Announcements = {
    onDragStart: ({ active }) => {
      const message = `Picked up ${labelOf(cards, active.id)}. Use the arrow keys to move, space to drop.`
      push(message)
      return message
    },
    onDragOver: ({ active, over }) => {
      const message = over
        ? `${labelOf(cards, active.id)} is over ${String(over.id)}.`
        : `${labelOf(cards, active.id)} is not over a column.`
      push(message)
      return message
    },
    onDragEnd: ({ active, over }) => {
      const message = over
        ? `Dropped ${labelOf(cards, active.id)} in ${String(over.id)}.`
        : `Dropped ${labelOf(cards, active.id)} where it started.`
      push(message)
      return message
    },
    onDragCancel: ({ active }) => {
      const message = `Cancelled dragging ${labelOf(cards, active.id)}.`
      push(message)
      return message
    },
  }

  const onDragStart = ({ active }: DragStartEvent) => setActiveId(String(active.id))

  const onDragOver = ({ active, over }: DragOverEvent) => {
    if (!over || active.id === over.id) return
    const board = api.getState()
    const cardId = String(active.id)
    const from = columnOf(board, cardId)
    const overId = String(over.id)
    const to = isColumnId(overId) ? overId : columnOf(board, overId)
    if (!from || !to || from === to) return

    const overIndex = board.columns[to].indexOf(overId)
    actions.move(cardId, to, overIndex === -1 ? board.columns[to].length : overIndex)
  }

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveId(null)
    if (!over) return
    const board = api.getState()
    const cardId = String(active.id)
    const from = columnOf(board, cardId)
    const to = columnOf(board, String(over.id))
    if (!from) return

    // Cross-column movement already happened in `onDragOver`; this is the within-column reorder.
    if (from === to) {
      const overIndex = board.columns[from].indexOf(String(over.id))
      if (overIndex !== -1) actions.move(cardId, from, overIndex)
    }
    push(`saved ${labelOf(cards, active.id)} in ${from}`)
  }

  const moveTo = (cardId: string, to: ColumnId) => {
    actions.move(cardId, to, columns[to].length)
    push(`moved ${labelOf(cards, cardId)} to ${to}`)
  }

  const addCard = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = title.trim()
    if (!value) return
    actions.add(value, target)
    push(`added “${value}” to ${target}`)
    setTitle('')
  }

  const total = Object.values(columns).reduce((sum, ids) => sum + ids.length, 0)
  const active = activeId ? cards[activeId] : undefined

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <form onSubmit={addCard} className="flex flex-1 flex-wrap items-end gap-1.5">
          <span className="flex flex-col gap-0.5">
            <label htmlFor={inputId} className="text-[10px] text-muted-foreground">
              New card
            </label>
            <input
              id={inputId}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Card title"
              className="h-8 w-40 rounded-md border border-border bg-card px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </span>
          <span className="flex flex-col gap-0.5">
            <label htmlFor={`${inputId}-column`} className="text-[10px] text-muted-foreground">
              Column
            </label>
            <select
              id={`${inputId}-column`}
              value={target}
              onChange={(event) => setTarget(event.target.value as ColumnId)}
              className="h-8 rounded-md border border-border bg-card px-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {COLUMNS.map((column) => (
                <option key={column.id} value={column.id}>
                  {column.title}
                </option>
              ))}
            </select>
          </span>
          <button
            type="submit"
            disabled={title.trim() === ''}
            className="h-8 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground outline-none disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-ring"
          >
            Add
          </button>
        </form>

        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span data-testid="kanban-total">
            {total} cards · {writes} writes
          </span>
          <button
            type="button"
            onClick={() => {
              actions.reset()
              push('reset the board')
            }}
            className="rounded-md border border-border px-2 py-1 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            Reset
          </button>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        accessibility={{
          announcements,
          screenReaderInstructions: {
            draggable:
              'To pick up a card, press space or enter on its reorder handle. Use the arrow keys to move it, space or enter to drop, escape to cancel.',
          },
        }}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          setActiveId(null)
          push('drag cancelled')
        }}
      >
        <div className="grid gap-2 sm:grid-cols-3">
          {COLUMNS.map((column) => (
            <Column
              key={column.id}
              id={column.id}
              title={column.title}
              hint={column.hint}
              cards={columns[column.id]
                .map((id) => cards[id])
                .filter((card): card is Card => !!card)}
              onMove={moveTo}
              onRemove={(cardId) => {
                actions.remove(cardId)
                push(`removed ${labelOf(cards, cardId)}`)
              }}
              reducedMotion={reducedMotion}
            />
          ))}
        </div>

        <DragOverlay dropAnimation={{ duration: reducedMotion ? 0 : 160, easing: 'ease' }}>
          {active ? (
            <div className="rotate-1 rounded-lg border border-primary bg-card p-2.5 text-xs shadow-lg">
              {active.title}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <div className="grid gap-2 text-[11px] sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Keyboard</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
            <li>
              Tab to a card&apos;s ⠿ handle, Space to pick it up, arrows to reorder, Space to drop.
            </li>
            <li>
              ← / → move a card to the previous or next column — the one job the arrow keys inside a
              sortable context cannot do reliably.
            </li>
          </ul>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Announcements</p>
          <ul
            aria-live="polite"
            className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground"
          >
            {log.length === 0 ? <li>drag, move or add a card to see them…</li> : null}
            {log.map((entry, index) => (
              <li key={`${entry}-${index}`} className="truncate">
                {entry}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

function isColumnId(id: string): id is ColumnId {
  return COLUMNS.some((column) => column.id === id)
}

function labelOf(cards: Record<string, Card>, id: string | number): string {
  return cards[String(id)]?.title ?? String(id)
}

export default function Demo() {
  return (
    <Board.Provider>
      <BoardView />
    </Board.Provider>
  )
}
