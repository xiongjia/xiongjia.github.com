import type { Demo } from '@/generated/demo-registry'
import {
  lazy,
  Suspense,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react'

import { useI18n } from '../i18n/use-i18n'
import { DemoPreview } from './demo-preview'
import { DemoSource } from './demo-source'

const TABS = ['preview', 'source', 'notes'] as const
type Tab = (typeof TABS)[number]

/**
 * DemoShell: the three views every demo gets for free —
 * Preview (the live component, wrapped in its own error boundary), Source (the raw `demo.tsx`, with
 * copy) and Notes (the current locale's write-up, English when the translation is missing).
 *
 * Panels stay mounted once visited, so a demo keeps its state while the reader looks at the source.
 */
export function DemoShell({
  demo,
  notes,
}: {
  demo: Demo
  /** Notes loader for the current locale; absent when neither the locale nor English has one. */
  notes?: Demo['locales']['en']['loadNotes']
}) {
  const { t } = useI18n()

  const tabs = useMemo(() => TABS.filter((tab) => tab !== 'notes' || notes !== undefined), [notes])

  const [active, setActive] = useState<Tab>('preview')
  const [visited, setVisited] = useState<readonly Tab[]>(['preview'])
  const buttons = useRef<Array<HTMLButtonElement | null>>([])

  // Switching to a locale without notes removes the tab; never leave the panel on a missing view.
  const current = tabs.includes(active) ? active : 'preview'

  const select = (tab: Tab) => {
    setActive(tab)
    setVisited((previous) => (previous.includes(tab) ? previous : [...previous, tab]))
  }

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const index = tabs.indexOf(current)
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

  const Notes = useMemo(() => (notes ? lazy(notes) : null), [notes])

  return (
    <div className="space-y-3">
      <div
        role="tablist"
        aria-label={t.demo.views}
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
            aria-selected={current === tab}
            tabIndex={current === tab ? 0 : -1}
            onClick={() => select(tab)}
            className={
              current === tab
                ? '-mb-px border-b-2 border-primary px-3 py-2 text-sm font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring'
                : '-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring'
            }
          >
            {t.demo[tab]}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="demo-panel-preview"
        aria-labelledby="demo-tab-preview"
        hidden={current !== 'preview'}
        className="rounded-lg border border-border bg-card p-5"
      >
        <DemoPreview demo={demo} />
      </div>

      {visited.includes('source') ? (
        <div
          role="tabpanel"
          id="demo-panel-source"
          aria-labelledby="demo-tab-source"
          hidden={current !== 'source'}
        >
          <DemoSource demo={demo} />
        </div>
      ) : null}

      {Notes && visited.includes('notes') ? (
        <div
          role="tabpanel"
          id="demo-panel-notes"
          aria-labelledby="demo-tab-notes"
          hidden={current !== 'notes'}
        >
          <div className="mdx">
            <Suspense
              fallback={<p className="text-sm text-muted-foreground">{t.demo.loadingNotes}</p>}
            >
              <Notes />
            </Suspense>
          </div>
        </div>
      ) : null}
    </div>
  )
}
