import { useState } from 'react'

/*
 * `subgrid` is the difference between "rows that happen to have three columns" and "rows that
 * align on the parent's tracks". The toggle renders the same data both ways so the misalignment is
 * visible instead of theoretical.
 */

const rows = [
  { id: '1', label: 'GET /api/notes', meta: 'ok', detail: '24 ms' },
  { id: '2', label: 'POST /api/notes (draft)', meta: 'warning', detail: 'needs a body' },
  { id: '3', label: 'DELETE /api/notes/7', meta: 'error', detail: '403 from the gateway' },
]

export default function Demo() {
  const [subgrid, setSubgrid] = useState(true)
  const [longLabel, setLongLabel] = useState(false)

  const rowClass = subgrid
    ? 'col-span-full grid grid-cols-subgrid items-center gap-2 border-b border-border px-2 py-2 text-sm last:border-b-0'
    : 'flex items-center gap-2 border-b border-border px-2 py-2 text-sm last:border-b-0'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setSubgrid((value) => !value)}
          aria-pressed={subgrid}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          {subgrid ? 'switch to flex rows' : 'switch to subgrid'}
        </button>
        <button
          type="button"
          onClick={() => setLongLabel((value) => !value)}
          aria-pressed={longLabel}
          className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        >
          {longLabel ? 'short labels' : 'long labels'}
        </button>
        <span className="font-mono text-[11px] text-muted-foreground">
          {subgrid ? 'grid-cols-subgrid' : 'flex per row'}
        </span>
      </div>

      <section className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Rows aligned on the parent's tracks
        </h3>
        <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] gap-2 rounded-lg border border-border">
          <div className="col-span-full grid grid-cols-subgrid border-b border-border bg-muted/60 px-2 py-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            <span>request</span>
            <span>status</span>
            <span className="text-right">detail</span>
          </div>
          {rows.map((row, index) => (
            <div key={row.id} className={rowClass}>
              <span className="truncate font-mono text-xs">
                {longLabel && index === 1 ? 'PATCH /api/notes/7/preview (draft)' : row.label}
              </span>
              <span
                className={
                  row.meta === 'error'
                    ? 'text-xs text-destructive'
                    : row.meta === 'warning'
                      ? 'text-xs text-foreground'
                      : 'text-xs text-muted-foreground'
                }
              >
                {row.meta}
              </span>
              <span className="text-right text-xs text-muted-foreground">{row.detail}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          With <code className="rounded bg-muted px-1">col-span-full grid grid-cols-subgrid</code>{' '}
          every row inherits the parent's three tracks, so a long label in one row cannot push the
          others out of alignment. The header is a subgrid row too, which is what keeps it on the
          same tracks without duplicating the column definition.
        </p>
      </section>

      <section className="space-y-2">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          auto-fit — the other half of intrinsic grids
        </h3>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(7rem,1fr))] gap-2">
          {[
            'notes',
            'tasks',
            'calendar',
            'health',
            'running',
            'film & tv',
            'reading',
            'english',
          ].map((item) => (
            <div
              key={item}
              className="rounded-md border border-border bg-card px-2 py-3 text-center text-xs"
            >
              {item}
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          <code className="rounded bg-muted px-1">
            grid-cols-[repeat(auto-fit,minmax(7rem,1fr))]
          </code>{' '}
          fits as many 7rem tracks as the width allows and then stretches them; no breakpoints, no
          container query, no JS. Subgrid and auto-fit answer different questions — aligning across
          rows versus filling a row.
        </p>
      </section>
    </div>
  )
}
