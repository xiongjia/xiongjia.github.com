import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

import { matchCommands, type PaletteCommand } from './match.ts'

/*
 * A command palette: one input, one list, and the keyboard contract that makes it feel like an OS.
 *
 * The ARIA shape is the combobox pattern, not a search box next to a list:
 *
 *   input[role=combobox]   aria-expanded, aria-controls, aria-activedescendant, aria-autocomplete
 *   div[role=listbox]      the options, grouped with role=group + aria-label
 *   div[role=option]       aria-selected — the active one is *not* focused
 *
 * Focus stays in the input the whole time. That is what makes typing while arrowing possible, and it
 * is also why the palette needs a focus trap of its own: the dialog is modal, so Tab must not walk
 * out into the page behind it.
 *
 * Closing restores focus to whatever had it before opening — usually the button that opened the
 * palette. Losing that is the single most common command-palette bug: the user closes the palette and
 * lands back at the top of the document.
 */

export type CommandPaletteProps = {
  open: boolean
  onClose: () => void
  commands: readonly PaletteCommand[]
  /** Accessible name of the dialog and the listbox. */
  label: string
  placeholder?: string
  /** Shown instead of the list when nothing matches. */
  emptyLabel?: string
  /** Heading for the recent block; recents are only tracked when this and `storageKey` are set. */
  recentLabel?: string
  /** `localStorage` key for recent command ids. */
  storageKey?: string
  maxRecent?: number
  /** Small print under the list, e.g. "↑↓ move · Enter run · Esc close". */
  hint?: string
}

const RECENT_GROUP = '__recent'

function readRecent(storageKey: string | undefined, maxRecent: number): string[] {
  if (!storageKey) return []
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((id): id is string => typeof id === 'string').slice(0, maxRecent)
  } catch {
    return []
  }
}

/** Render matched characters as `<mark>`s; plain text when the match came from keywords. */
function highlight(text: string, ranges: Array<[number, number]>): ReactNode {
  if (ranges.length === 0) return text

  const parts: ReactNode[] = []
  let cursor = 0

  ranges.forEach(([from, to], index) => {
    if (from > cursor) parts.push(text.slice(cursor, from))
    parts.push(
      <mark key={index} className="bg-transparent font-semibold text-primary">
        {text.slice(from, to)}
      </mark>,
    )
    cursor = to
  })

  if (cursor < text.length) parts.push(text.slice(cursor))
  return parts
}

export function CommandPalette({
  open,
  onClose,
  commands,
  label,
  placeholder = 'Type a command…',
  emptyLabel = 'No matching command',
  recentLabel,
  storageKey,
  maxRecent = 5,
  hint,
}: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [recent, setRecent] = useState<string[]>(() => readRecent(storageKey, maxRecent))

  const inputRef = useRef<HTMLInputElement>(null)
  const restoreRef = useRef<HTMLElement | null>(null)
  const optionRefs = useRef<Array<HTMLDivElement | null>>([])
  const listId = useId()

  const recentEnabled = recentLabel !== undefined && storageKey !== undefined
  const recentIds = useMemo(() => new Set(recentEnabled ? recent : []), [recent, recentEnabled])

  /**
   * With an empty query the recent commands come first (they are what a palette is for); with a
   * query, ranking is the user's intent, so the order is the matcher's.
   */
  const ordered = useMemo(() => {
    if (!recentEnabled || query.trim() !== '' || recent.length === 0) return commands
    const byId = new Map(commands.map((command) => [command.id, command]))
    const recentCommands = recent
      .map((id) => byId.get(id))
      .filter((command): command is PaletteCommand => command !== undefined)
    return [...recentCommands, ...commands.filter((command) => !recentIds.has(command.id))]
  }, [commands, query, recent, recentEnabled, recentIds])

  const matches = useMemo(() => matchCommands(ordered, query), [ordered, query])

  // Clamp instead of resetting: deleting a character must not move the selection back to the top.
  const active = Math.min(activeIndex, Math.max(matches.length - 1, 0))

  const groups = useMemo(() => {
    const emptyQuery = query.trim() === ''
    const seen: string[] = []
    const items = new Map<string, { label?: string; entries: typeof matches }>()

    for (const match of matches) {
      const groupId =
        emptyQuery && recentEnabled && recentIds.has(match.command.id)
          ? RECENT_GROUP
          : (match.command.group ?? '')
      if (!items.has(groupId)) {
        items.set(groupId, {
          label: groupId === RECENT_GROUP ? recentLabel : match.command.group,
          entries: [],
        })
        seen.push(groupId)
      }
      items.get(groupId)?.entries.push(match)
    }

    return seen.map((id) => ({ id, ...(items.get(id) ?? { entries: [] }) }))
  }, [matches, query, recentEnabled, recentIds, recentLabel])

  // Open: remember the trigger, focus the input, close the page behind the dialog.
  useEffect(() => {
    if (!open) return

    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    // Every open starts from an empty query: a palette that reopens with the last search is a
    // palette that hides its own commands.
    setQuery('')
    setActiveIndex(0)
    inputRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
      const target = restoreRef.current
      if (target && document.contains(target)) target.focus()
    }
  }, [open])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  useEffect(() => {
    if (!open) return
    optionRefs.current[active]?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  if (!open) return null

  const run = (command: PaletteCommand) => {
    if (recentEnabled) {
      const next = [command.id, ...recent.filter((id) => id !== command.id)].slice(0, maxRecent)
      setRecent(next)
      try {
        window.localStorage.setItem(storageKey ?? '', JSON.stringify(next))
      } catch {
        // Recents are a convenience; the palette works without storage.
      }
    }
    command.run()
    onClose()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }

    if (event.key === 'Tab') {
      // The dialog is modal and has exactly one focusable control; Tab must not escape it.
      event.preventDefault()
      inputRef.current?.focus()
      return
    }

    const last = Math.max(matches.length - 1, 0)
    const next =
      event.key === 'ArrowDown'
        ? (active + 1) % (last + 1)
        : event.key === 'ArrowUp'
          ? (active - 1 + last + 1) % (last + 1)
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : undefined

    if (next !== undefined) {
      event.preventDefault()
      setActiveIndex(next)
      return
    }

    if (event.key === 'Enter') {
      event.preventDefault()
      const command = matches[active]?.command
      if (command) run(command)
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-24"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onKeyDown={onKeyDown}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <input
          ref={inputRef}
          role="combobox"
          aria-expanded={matches.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={matches.length > 0 ? `${listId}-option-${active}` : undefined}
          aria-label={label}
          value={query}
          placeholder={placeholder}
          onChange={(event) => setQuery(event.target.value)}
          className="w-full border-b border-border bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
        />

        {matches.length === 0 ? (
          <p role="status" className="px-3 py-6 text-center text-xs text-muted-foreground">
            {emptyLabel}
          </p>
        ) : (
          <div
            role="listbox"
            id={listId}
            aria-label={label}
            className="max-h-72 overflow-y-auto p-1"
          >
            {groups.map((group) => (
              <div key={group.id} role="group" aria-label={group.label ?? label} className="py-0.5">
                {group.label ? (
                  <p className="px-2 py-1 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                    {group.label}
                  </p>
                ) : null}
                {group.entries.map((match) => {
                  // Flat index, because `aria-activedescendant` addresses the option, not the group.
                  const index = matches.indexOf(match)
                  const selected = index === active

                  return (
                    <div
                      key={match.command.id}
                      ref={(element) => {
                        optionRefs.current[index] = element
                      }}
                      role="option"
                      id={`${listId}-option-${index}`}
                      aria-selected={selected}
                      data-command-id={match.command.id}
                      onClick={() => run(match.command)}
                      onMouseMove={() => setActiveIndex(index)}
                      className={[
                        'flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1.5 text-xs',
                        selected
                          ? 'bg-secondary text-secondary-foreground'
                          : 'text-foreground hover:bg-muted',
                      ].join(' ')}
                    >
                      <span className="truncate">
                        {highlight(match.command.title, match.ranges)}
                      </span>
                      {match.command.hint ? (
                        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                          {match.command.hint}
                        </span>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        )}

        {hint ? (
          <p className="border-t border-border px-3 py-1.5 text-[10px] text-muted-foreground">
            {hint}
          </p>
        ) : null}
      </div>
    </div>,
    document.body,
  )
}
