import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  rectSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  createSeries,
  SankeyChart,
  summarize,
  SvgChart,
  type ChartPoint,
  type SankeyLink,
  type SankeyNode,
} from '@frontend-lab/charts'
import { createStoreContext } from '@frontend-lab/state'
import { motion, useReducedMotion } from 'motion/react'
import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'

/*
 * Dashboard builder: the B15 composed scenario.
 *
 * A dashboard is a layout problem with charts inside it, and the two questions this demo answers are
 * both about cost:
 *
 *   layout   a grid of cards you can reorder and resize, persisted, with the keyboard path included
 *   charts   the same numbers through three renderers — hand-written SVG, Recharts, Chart.js — with
 *            the render cost measured and the load cost reported by `pnpm bundle:report`
 *   flow     a fund-flow Sankey, which none of those renderers ships: the branching diagram is the
 *            case where writing the layout yourself is the only option
 *
 * The two library renderers are `lazy()`: they only download when selected, which is what keeps the
 * comparison honest (the default dashboard does not pay for either of them).
 */

const RechartsChart = lazy(() =>
  import('@frontend-lab/charts/recharts').then((module) => ({ default: module.RechartsChart })),
)
const ChartjsChart = lazy(() =>
  import('@frontend-lab/charts/chartjs').then((module) => ({ default: module.ChartjsChart })),
)

type Renderer = 'svg' | 'recharts' | 'chartjs'
type CardKind = 'kpi' | 'chart' | 'table' | 'sankey'
type Span = 1 | 2 | 3

type DashboardCard = {
  id: string
  title: string
  kind: CardKind
  span: Span
  /** Chart cards only. Persisted with the layout, because it is part of the card's identity. */
  renderer?: Renderer
}

type DashboardState = {
  cards: DashboardCard[]
  actions: {
    move: (from: number, to: number) => void
    setSpan: (id: string, span: Span) => void
    setRenderer: (id: string, renderer: Renderer) => void
    reset: () => void
  }
}

const STORAGE_KEY = 'frontend-lab:dashboard:v2'

const defaultCards: DashboardCard[] = [
  { id: 'revenue', title: 'Revenue', kind: 'kpi', span: 1 },
  { id: 'users', title: 'Active users', kind: 'kpi', span: 1 },
  { id: 'conversion', title: 'Conversion', kind: 'kpi', span: 1 },
  { id: 'traffic', title: 'Weekly traffic', kind: 'chart', span: 2, renderer: 'svg' },
  { id: 'sessions', title: 'Sessions', kind: 'chart', span: 1, renderer: 'svg' },
  { id: 'flow', title: 'Fund flow', kind: 'sankey', span: 3 },
  { id: 'pages', title: 'Top pages', kind: 'table', span: 3 },
]

/*
 * Fund flow, in thousands per month. Three stages — income, buckets, funds — so the diagram actually
 * branches twice; a single split would not need a Sankey.
 */
const flowNodes: SankeyNode[] = [
  { id: 'salary', label: 'Salary', column: 0 },
  { id: 'bonus', label: 'Bonus', column: 0 },
  { id: 'returns', label: 'Returns', column: 0 },
  { id: 'housing', label: 'Housing', column: 1 },
  { id: 'living', label: 'Living', column: 1 },
  { id: 'savings', label: 'Savings', column: 1 },
  { id: 'investing', label: 'Investing', column: 1 },
  { id: 'emergency', label: 'Emergency fund', column: 2 },
  { id: 'travel', label: 'Travel fund', column: 2 },
  { id: 'index', label: 'Index funds', column: 2 },
  { id: 'single', label: 'Single stocks', column: 2 },
]

const flowLinks: SankeyLink[] = [
  { source: 'salary', target: 'housing', value: 12 },
  { source: 'salary', target: 'living', value: 11 },
  { source: 'salary', target: 'savings', value: 7 },
  { source: 'salary', target: 'investing', value: 2 },
  { source: 'bonus', target: 'savings', value: 2 },
  { source: 'bonus', target: 'investing', value: 2 },
  { source: 'returns', target: 'investing', value: 2 },
  { source: 'savings', target: 'emergency', value: 5 },
  { source: 'savings', target: 'travel', value: 4 },
  { source: 'investing', target: 'index', value: 4 },
  { source: 'investing', target: 'single', value: 2 },
]

const renderers: Renderer[] = ['svg', 'recharts', 'chartjs']

function isCard(value: unknown): value is DashboardCard {
  if (typeof value !== 'object' || value === null) return false
  const card = value as Partial<DashboardCard>
  return (
    typeof card.id === 'string' &&
    typeof card.title === 'string' &&
    (card.kind === 'kpi' ||
      card.kind === 'chart' ||
      card.kind === 'table' ||
      card.kind === 'sankey') &&
    (card.span === 1 || card.span === 2 || card.span === 3) &&
    (card.renderer === undefined || renderers.includes(card.renderer))
  )
}

function loadCards(): DashboardCard[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultCards
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || parsed.length === 0 || !parsed.every(isCard)) return defaultCards
    return parsed
  } catch {
    return defaultCards
  }
}

/** One store per `<Dashboard.Provider>` — the layout is state, not a module constant. */
const Dashboard = createStoreContext<DashboardState>(
  (set) => ({
    cards: loadCards(),
    actions: {
      move: (from, to) =>
        set((state) => {
          if (from === to) return state
          return { ...state, cards: arrayMove(state.cards, from, to) }
        }),
      setSpan: (id, span) =>
        set((state) => ({
          ...state,
          cards: state.cards.map((card) => (card.id === id ? { ...card, span } : card)),
        })),
      setRenderer: (id, renderer) =>
        set((state) => ({
          ...state,
          cards: state.cards.map((card) => (card.id === id ? { ...card, renderer } : card)),
        })),
      reset: () => set({ cards: defaultCards }),
    },
  }),
  { name: 'dashboard' },
)

/** Same debounce contract as the kanban board: many updates during a drag, one write per pause. */
function usePersistedLayout(): number {
  const api = Dashboard.useStoreApi()
  const [writes, setWrites] = useState(0)

  useEffect(() => {
    // One subscription per provider: debounce the writes, flush the pending one on unmount.
    let timer: ReturnType<typeof setTimeout> | undefined
    let latest: DashboardCard[] | undefined
    let mounted = true

    const flush = () => {
      if (!latest) return
      const payload = JSON.stringify(latest)
      latest = undefined
      try {
        window.localStorage.setItem(STORAGE_KEY, payload)
        if (mounted) setWrites((count) => count + 1)
      } catch {
        // Storage is a nicety; the layout keeps working in memory.
      }
    }

    const schedule = (state: DashboardState) => {
      latest = state.cards
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

const spanClass: Record<Span, string> = {
  1: 'sm:col-span-1',
  2: 'sm:col-span-2',
  3: 'sm:col-span-3',
}

function kpiValue(series: ChartPoint[]) {
  const summary = summarize(series)
  return {
    total: String(summary.total),
    average: String(summary.average),
    delta: `${summary.deltaPct > 0 ? '+' : ''}${summary.deltaPct}%`,
  }
}

function ChartBody({
  renderer,
  series,
  label,
  onMeasured,
}: {
  renderer: Renderer
  series: ChartPoint[]
  label: string
  onMeasured: (milliseconds: number) => void
}) {
  if (renderer === 'svg') {
    return <SvgChart series={series} label={label} onMeasured={onMeasured} />
  }

  return (
    <Suspense
      fallback={
        <p className="h-24 animate-pulse rounded bg-muted/60 text-center text-[10px] leading-[6rem] text-muted-foreground">
          loading {renderer} chunk…
        </p>
      }
    >
      {renderer === 'recharts' ? (
        <RechartsChart series={series} label={label} onMeasured={onMeasured} />
      ) : (
        <ChartjsChart series={series} label={label} onMeasured={onMeasured} />
      )}
    </Suspense>
  )
}

function DashboardCardView({
  card,
  editing,
  children,
  onSpan,
  onRenderer,
}: {
  card: DashboardCard
  editing: boolean
  children: ReactNode
  onSpan: (span: Span) => void
  onRenderer: (renderer: Renderer) => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id, disabled: !editing })
  const reducedMotion = useReducedMotion() ?? false

  return (
    <motion.div
      layout={!editing}
      transition={{ duration: reducedMotion ? 0 : 0.2 }}
      ref={(node) => {
        setNodeRef(node)
      }}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      data-card={card.id}
      data-span={card.span}
      className={[
        'flex min-w-0 flex-col rounded-lg border bg-card p-3',
        isDragging ? 'border-primary opacity-60' : 'border-border',
        spanClass[card.span],
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            {card.title}
          </p>
        </div>
        {editing ? (
          <div className="flex items-center gap-1">
            {card.kind === 'chart' ? (
              <select
                aria-label={`Renderer for ${card.title}`}
                value={card.renderer ?? 'svg'}
                onChange={(event) => onRenderer(event.target.value as Renderer)}
                className="rounded border border-border bg-card px-1 py-0.5 text-[10px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {renderers.map((renderer) => (
                  <option key={renderer} value={renderer}>
                    {renderer}
                  </option>
                ))}
              </select>
            ) : null}
            <div role="group" aria-label={`Width of ${card.title}`} className="flex">
              {([1, 2, 3] as Span[]).map((span) => (
                <button
                  key={span}
                  type="button"
                  aria-pressed={card.span === span}
                  aria-label={`${span} column${span === 1 ? '' : 's'}`}
                  onClick={() => onSpan(span)}
                  className={[
                    'rounded px-1 py-0.5 text-[10px] outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    card.span === span
                      ? 'bg-secondary font-medium text-secondary-foreground'
                      : 'text-muted-foreground hover:bg-muted',
                  ].join(' ')}
                >
                  {span}
                </button>
              ))}
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
        ) : null}
      </div>

      <div className="mt-2 flex-1">{children}</div>
    </motion.div>
  )
}

function DashboardView() {
  const cards = Dashboard.useSelector((state) => state.cards)
  const actions = Dashboard.useSelector((state) => state.actions)
  const writes = usePersistedLayout()
  const [editing, setEditing] = useState(false)
  const [costs, setCosts] = useState<Record<Renderer, number>>({ svg: 0, recharts: 0, chartjs: 0 })
  const [flowCost, setFlowCost] = useState(0)
  const [measureRun, setMeasureRun] = useState(0)
  const [status, setStatus] = useState('layout ready')

  const traffic = useMemo(() => createSeries(12, 42), [])
  const sessions = useMemo(() => createSeries(12, 7), [])
  const kpis = useMemo(() => kpiValue(traffic), [traffic])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const record = (renderer: Renderer) => (milliseconds: number) =>
    setCosts((previous) => ({ ...previous, [renderer]: milliseconds }))

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const from = cards.findIndex((card) => card.id === active.id)
    const to = cards.findIndex((card) => card.id === over.id)
    if (from === -1 || to === -1) return
    actions.move(from, to)
    setStatus(`moved ${cards[from]?.title ?? String(active.id)} to position ${to + 1}`)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          aria-pressed={editing}
          onClick={() => setEditing((value) => !value)}
          className={[
            'rounded-md border px-2.5 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring',
            editing
              ? 'border-primary bg-secondary font-medium text-secondary-foreground'
              : 'border-border text-muted-foreground hover:bg-muted',
          ].join(' ')}
        >
          {editing ? 'Done editing' : 'Edit layout'}
        </button>
        <button
          type="button"
          onClick={() => {
            actions.reset()
            setStatus('reset the layout')
          }}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          Reset
        </button>
        <p className="text-[10px] text-muted-foreground" data-testid="dashboard-writes">
          {writes} layout writes
        </p>
        <p role="status" className="font-mono text-[10px] text-muted-foreground">
          {status}
        </p>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={cards.map((card) => card.id)} strategy={rectSortingStrategy}>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {cards.map((card) => (
              <DashboardCardView
                key={card.id}
                card={card}
                editing={editing}
                onSpan={(span) => actions.setSpan(card.id, span)}
                onRenderer={(renderer) => actions.setRenderer(card.id, renderer)}
              >
                {card.kind === 'kpi' ? (
                  <div>
                    <p className="text-2xl font-semibold tabular-nums" data-kpi={card.id}>
                      {card.id === 'revenue'
                        ? kpis.total
                        : card.id === 'users'
                          ? summarize(sessions).peak
                          : kpis.delta}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {card.id === 'conversion' ? 'vs last week' : 'last 12 weeks'}
                    </p>
                  </div>
                ) : null}

                {card.kind === 'chart' ? (
                  <ChartBody
                    // Remounting on demand is what makes the numbers comparable: a first mount on
                    // page load also pays for the page's own layout, which is not the chart's cost.
                    key={`${card.renderer ?? 'svg'}-${measureRun}`}
                    renderer={card.renderer ?? 'svg'}
                    series={card.id === 'traffic' ? traffic : sessions}
                    label={card.title}
                    onMeasured={record(card.renderer ?? 'svg')}
                  />
                ) : null}

                {card.kind === 'sankey' ? (
                  <div className="space-y-1">
                    <SankeyChart
                      key={`flow-${measureRun}`}
                      nodes={flowNodes}
                      links={flowLinks}
                      label="Monthly fund flow"
                      format={(value) => `¥${value}k`}
                      onMeasured={setFlowCost}
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Income → buckets → funds. Hand-written SVG: none of the compared renderers
                      ships a Sankey, and the layout is the actual work.
                    </p>
                  </div>
                ) : null}

                {card.kind === 'table' ? (
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="text-muted-foreground">
                        <th className="pb-1 font-medium">Page</th>
                        <th className="pb-1 text-right font-medium">Views</th>
                        <th className="pb-1 text-right font-medium">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['/demos', 4820, '31%'],
                        ['/foundations/design-tokens', 3110, '20%'],
                        ['/scenarios/ide-workspace', 2740, '18%'],
                        ['/motion/dnd-kit-sortable', 1980, '13%'],
                      ].map(([page, views, share]) => (
                        <tr key={String(page)} className="border-t border-border">
                          <td className="py-1">{page}</td>
                          <td className="py-1 text-right tabular-nums">{views}</td>
                          <td className="py-1 text-right tabular-nums">{share}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
              </DashboardCardView>
            ))}
          </div>
        </SortableContext>
      </DndContext>

      <div className="grid gap-2 text-[11px] sm:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium">Render cost, measured</p>
            <button
              type="button"
              onClick={() => {
                setCosts({ svg: 0, recharts: 0, chartjs: 0 })
                setFlowCost(0)
                setMeasureRun((run) => run + 1)
                setStatus('re-measured the charts')
              }}
              className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
            >
              Measure again
            </button>
          </div>
          <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-muted-foreground">
            <li data-cost="sankey">
              sankey {flowCost === 0 ? 'not rendered yet' : `${flowCost} ms`}
            </li>
            {renderers.map((renderer) => (
              <li key={renderer} data-cost={renderer}>
                {renderer.padEnd(8, ' ')}{' '}
                {costs[renderer] === 0 ? 'not rendered yet' : `${costs[renderer]} ms`}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-muted-foreground">
            Render to committed DOM, after the chunk has loaded. Measure again remounts the charts,
            so the number excludes the page&apos;s own first mount. Load cost is in the bundle
            report — the two numbers are not interchangeable.
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium">Layout</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
            <li>
              Edit layout: drag a ⠿ handle with the pointer, or focus it and use Space + arrows.
            </li>
            <li>Width buttons and the renderer select are per card and persist with the order.</li>
            <li>The fund-flow card has no renderer switch: a Sankey is not a series chart.</li>
            <li>Leaving edit mode turns Motion&apos;s layout animation back on.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default function Demo() {
  return (
    <Dashboard.Provider>
      <DashboardView />
    </Dashboard.Provider>
  )
}
