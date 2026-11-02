import type { Demo } from '@/generated/demo-registry'
import {
  lazy,
  Suspense,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react'

import { DemoPreview } from './demo-preview'
import { DemoSource } from './demo-source'

const TABS = ['preview', 'source', 'notes'] as const
type Tab = (typeof TABS)[number]

const tabLabel: Record<Tab, string> = {
  preview: 'Preview',
  source: 'Source',
  notes: 'Notes',
}

/**
 * DemoShell: the three views every demo gets for free —
 * Preview (the live component, wrapped in its own error boundary), Source (the raw `demo.tsx`, with
 * copy) and Notes (the `notes.mdx` write-up).
 *
 * Panels stay mounted once visited, so a demo keeps its state while the reader looks at the source.
 */
export function DemoShell({ demo }: { demo: Demo }) {
  const tabs = useMemo(
    () => TABS.filter((tab) => tab !== 'notes' || demo.loadNotes !== undefined),
    [demo],
  )

  const [active, setActive] = useState<Tab>('preview')
  const [visited, setVisited] = useState<readonly Tab[]>(['preview'])
  const buttons = useRef<Array<HTMLButtonElement | null>>([])

  const select = (tab: Tab) => {
    setActive(tab)
    setVisited((previous) => (previous.includes(tab) ? previous : [...previous, tab]))
  }

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const index = tabs.indexOf(active)
    const last = tabs.length - 1

    const next =
      event.key === 'ArrowRight'
        ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : -1

    if (next === -1) return
    event.preventDefault()
    const tab = tabs[next] as Tab
    select(tab)
    buttons.current[next]?.focus()
  }

  const Notes = useMemo(() => (demo.loadNotes ? lazy(demo.loadNotes) : null), [demo])

  return (
    <div className="space-y-3">
      <div
        role="tablist"
        aria-label="Demo views"
        onKeyDown={onKeyDown}
        className="flex gap-1 border-b border-border"
      >
        {tabs.map((tab, index) => (
          <button
            key={tab}
            ref={(element) => {
              buttons.current[index] = element
            }}
            type="button"
            role="tab"
            id={`demo-tab-${tab}`}
            aria-controls={`demo-panel-${tab}`}
            aria-selected={active === tab}
            tabIndex={active === tab ? 0 : -1}
            onClick={() => select(tab)}
            className={
              active === tab
                ? '-mb-px border-b-2 border-primary px-3 py-2 text-sm font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring'
                : '-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring'
            }
          >
            {tabLabel[tab]}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="demo-panel-preview"
        aria-labelledby="demo-tab-preview"
        hidden={active !== 'preview'}
        className="rounded-lg border border-border bg-card p-5"
      >
        <DemoPreview demo={demo} />
      </div>

      {visited.includes('source') ? (
        <div
          role="tabpanel"
          id="demo-panel-source"
          aria-labelledby="demo-tab-source"
          hidden={active !== 'source'}
        >
          <DemoSource demo={demo} />
        </div>
      ) : null}

      {Notes && visited.includes('notes') ? (
        <div
          role="tabpanel"
          id="demo-panel-notes"
          aria-labelledby="demo-tab-notes"
          hidden={active !== 'notes'}
        >
          <div className="mdx">
            <Suspense fallback={<p className="text-sm text-muted-foreground">Loading notes…</p>}>
              <Notes />
            </Suspense>
          </div>
        </div>
      ) : null}
    </div>
  )
}
