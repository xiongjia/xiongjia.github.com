import type { ReactNode } from 'react'

import { cn } from '../lib/cn'

export type SegmentedOption<T extends string> = {
  value: T
  label: ReactNode
  /** Accessible name when the visible label is short or symbolic (e.g. "EN"). */
  description?: string
}

export type SegmentedControlProps<T extends string> = {
  /** Accessible name for the group, e.g. "Color mode". */
  label: string
  value: T
  options: readonly SegmentedOption<T>[]
  onChange: (value: T) => void
}

/**
 * A small segmented control: one selected option out of a handful, kept visible at all times.
 *
 * `aria-pressed` (not `aria-selected`, not radios) because this is a group of toggle buttons, not
 * navigation: it stays focusable and clickable, and a screen reader announces the pressed state.
 */
export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex items-center gap-0.5 rounded-full border border-border bg-card p-0.5"
    >
      {options.map((option) => {
        const active = option.value === value

        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            title={option.description}
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-full px-2.5 py-1 text-xs font-medium transition-colors outline-none',
              'focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'bg-secondary text-secondary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
