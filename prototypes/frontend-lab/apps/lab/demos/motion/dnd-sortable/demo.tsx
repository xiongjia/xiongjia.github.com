import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  rectIntersection,
  useSensor,
  useSensors,
  type Announcements,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useState } from 'react'

/*
 * dnd-kit separates three concerns that hand-rolled drag code always merges:
 *
 *   sensors      how a drag starts — pointer, touch, or keyboard
 *   collision    which droppable is "under" the drag (`closestCenter` vs `rectIntersection`)
 *   sortable     the strategy layer that turns a reorder into indexes
 *
 * The keyboard sensor is the one that gets skipped. Here it is the primary path: focus an item,
 * press Space, move with the arrows, press Space again. Every announcement the library makes is
 * echoed into the log panel, so the accessibility output is visible, not assumed.
 */

type Item = { id: string; label: string }

const initial: Item[] = [
  { id: 'tokens', label: 'Design tokens' },
  { id: 'components', label: 'Component API' },
  { id: 'states', label: 'Interaction states' },
  { id: 'a11y', label: 'Accessibility' },
]

function SortableItem({ item, dragging }: { item: Item; dragging: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
  })

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      className={[
        'flex cursor-grab touch-none items-center justify-between rounded-lg border p-3 text-sm outline-none select-none',
        'focus-visible:ring-2 focus-visible:ring-ring',
        isDragging ? 'opacity-40' : 'border-border bg-card',
        dragging && !isDragging ? '' : '',
      ].join(' ')}
    >
      <span>{item.label}</span>
      <span className="font-mono text-[10px] text-muted-foreground">⠿</span>
    </li>
  )
}

export default function Demo() {
  const [items, setItems] = useState(initial)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [strategy, setStrategy] = useState<'closest' | 'intersection'>('closest')
  const [log, setLog] = useState<string[]>([])

  const push = (entry: string) => setLog((previous) => [entry, ...previous].slice(0, 6))

  const sensors = useSensors(
    // A few pixels of movement before a drag starts, so a click is still a click.
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const announcements: Announcements = {
    onDragStart: ({ active }) => {
      const message = `Picked up ${String(active.id)}. Use arrow keys to move, space to drop.`
      push(message)
      return message
    },
    onDragOver: ({ active, over }) => {
      const message = over
        ? `${String(active.id)} is over ${String(over.id)}.`
        : `${String(active.id)} is not over a drop target.`
      push(message)
      return message
    },
    onDragEnd: ({ active, over }) => {
      const message = over
        ? `Dropped ${String(active.id)} at position ${String(over.id)}.`
        : `Dropped ${String(active.id)} in the original position.`
      push(message)
      return message
    },
    onDragCancel: ({ active }) => {
      const message = `Cancelled dragging ${String(active.id)}.`
      push(message)
      return message
    },
  }

  const collisionDetection: CollisionDetection =
    strategy === 'closest' ? closestCenter : rectIntersection

  const onDragStart = (event: DragStartEvent) => {
    setActiveId(String(event.active.id))
    push(`dragstart: ${String(event.active.id)}`)
  }

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveId(null)
    if (!over || active.id === over.id) {
      push(`dragend: no reorder (${String(active.id)})`)
      return
    }
    setItems((current) => {
      const from = current.findIndex((item) => item.id === active.id)
      const to = current.findIndex((item) => item.id === over.id)
      push(`reorder: ${from} → ${to}`)
      return arrayMove(current, from, to)
    })
  }

  const active = items.find((item) => item.id === activeId)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span className="flex items-center gap-1.5">
          <span className="font-medium">collision:</span>
          {(['closest', 'intersection'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setStrategy(value)}
              aria-pressed={strategy === value}
              className={
                strategy === value
                  ? 'rounded-md bg-secondary px-2 py-1 font-medium text-secondary-foreground'
                  : 'rounded-md border border-border px-2 py-1 text-muted-foreground hover:bg-muted'
              }
            >
              {value}
            </button>
          ))}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">
          order: {items.map((item) => item.id).join(' · ')}
        </span>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        accessibility={{
          announcements,
          screenReaderInstructions: {
            draggable:
              'To pick up an item, press space or enter. Use the arrow keys to move it, space or enter to drop it, and escape to cancel.',
          },
        }}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          setActiveId(null)
          push('dragcancel')
        }}
      >
        <SortableContext
          items={items.map((item) => item.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul className="space-y-2">
            {items.map((item) => (
              <SortableItem key={item.id} item={item} dragging={activeId !== null} />
            ))}
          </ul>
        </SortableContext>

        {/* The overlay renders the lifted copy, so the list item itself can stay in place. */}
        <DragOverlay>
          {active ? (
            <div className="rounded-lg border border-primary bg-card p-3 text-sm shadow-md">
              {active.label}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Keyboard path</p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-4 text-muted-foreground">
            <li>Tab to a row — it is the drag handle itself.</li>
            <li>
              <kbd className="rounded border border-border px-1">Space</kbd> picks it up.
            </li>
            <li>
              <kbd className="rounded border border-border px-1">↑</kbd>/
              <kbd className="rounded border border-border px-1">↓</kbd> moves it.
            </li>
            <li>
              <kbd className="rounded border border-border px-1">Space</kbd> drops,
              <kbd className="ml-1 rounded border border-border px-1">Esc</kbd> cancels.
            </li>
          </ol>
          <p className="mt-2 text-muted-foreground">
            <code className="rounded bg-muted px-1">sortableKeyboardCoordinates</code> is what makes
            the arrows sort instead of nudging the overlay by a few pixels.
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Announcements</p>
          <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground">
            {log.length === 0 ? <li>drag or keyboard-sort to see them…</li> : null}
            {log.map((entry, index) => (
              <li key={index}>{entry}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
