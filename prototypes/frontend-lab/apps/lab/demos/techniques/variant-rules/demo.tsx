import { useState } from 'react'

/**
 * Tailwind's variant machinery is a selector generator: `*:` spans children, `**:` spans every
 * descendant, and state variants (`data-*`, `aria-*`, `open:`, `starting:`) key off attributes the
 * DOM already carries. The demos below print the attribute each rule reacts to, so the CSS and the
 * markup can be compared side by side.
 */
const rows = [
  { id: 'a', label: 'Alpha', state: 'idle' },
  { id: 'b', label: 'Beta', state: 'idle' },
  { id: 'c', label: 'Gamma', state: 'idle' },
]

export default function Demo() {
  const [sort, setSort] = useState<'ascending' | 'descending' | 'none'>('ascending')
  const [rowsState, setRowsState] = useState(rows)
  const [show, setShow] = useState(true)

  const cycleRow = (id: string) => {
    setRowsState((previous) =>
      previous.map((row) =>
        row.id === id
          ? {
              ...row,
              state: row.state === 'idle' ? 'active' : row.state === 'active' ? 'done' : 'idle',
            }
          : row,
      ),
    )
  }

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          *: children · nth-3: stripes · not-last: dividers
        </h3>
        <ul className="rounded-lg border border-border *:flex *:items-center *:justify-between *:px-3 *:py-2 *:text-sm nth-3:bg-muted/60">
          {['One', 'Two', 'Three', 'Four', 'Five', 'Six'].map((label, index) => (
            <li key={label} className="not-last:border-b not-last:border-border">
              <span>{label}</span>
              <span className="font-mono text-[11px] text-muted-foreground">nth-{index + 1}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          <code className="rounded bg-muted px-1">*:</code> styles direct children without a wrapper
          class; <code className="rounded bg-muted px-1">not-last:</code> draws the row divider;
          <code className="ml-1 rounded bg-muted px-1">nth-3:</code> stripes every third row — here
          3 and 6.
        </p>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          data-[state=…] — attribute-driven state
        </h3>
        <ul className="grid gap-2 sm:grid-cols-3">
          {rowsState.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                data-state={row.state}
                onClick={() => cycleRow(row.id)}
                className="w-full rounded-lg border border-border p-3 text-left text-sm outline-none transition-colors data-[state=active]:border-primary data-[state=active]:bg-primary/10 data-[state=done]:bg-muted data-[state=done]:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="block font-medium">{row.label}</span>
                <span className="block font-mono text-[11px]">data-state="{row.state}"</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          One class list, three looks — the variant reads the attribute instead of a conditional
          template string. This is the same contract a headless component library exposes.
        </p>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          aria-[sort=…] — styling the accessibility state
        </h3>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th
                scope="col"
                aria-sort={sort}
                className="border-b border-border px-3 py-2 text-left font-medium aria-[sort=ascending]:underline aria-[sort=descending]:italic"
              >
                <button
                  type="button"
                  onClick={() =>
                    setSort((previous) => (previous === 'ascending' ? 'descending' : 'ascending'))
                  }
                  className="outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Name
                  <span className="ml-1 font-mono text-[11px] text-muted-foreground">
                    {sort === 'ascending' ? '↑' : '↓'}
                  </span>
                </button>
              </th>
              <th scope="col" className="border-b border-border px-3 py-2 text-left font-medium">
                Effect
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">ascending</td>
              <td className="px-3 py-2 text-muted-foreground">underline</td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">descending</td>
              <td className="px-3 py-2 text-muted-foreground">italic</td>
            </tr>
          </tbody>
        </table>
        <p className="text-xs text-muted-foreground">
          The underline is not the state — <code className="rounded bg-muted px-1">aria-sort</code>{' '}
          is; screen readers announce it and the variant renders it. No visual-only sorting.
        </p>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          open: · starting: — states the DOM owns
        </h3>
        <details className="group rounded-lg border border-border p-3 open:border-primary">
          <summary className="cursor-pointer text-sm font-medium outline-none group-open:text-primary">
            A native details/summary
          </summary>
          <p className="mt-2 text-xs text-muted-foreground">
            <code className="rounded bg-muted px-1">open:</code> styles the expanded element, no
            state in React; <code className="rounded bg-muted px-1">group-open:</code> reaches the
            summary.
          </p>
        </details>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShow((value) => !value)}
            className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            {show ? 'Remove' : 'Insert'} the panel
          </button>
          <span className="font-mono text-[11px] text-muted-foreground">
            starting:opacity-0 + starting:-translate-y-2
          </span>
        </div>
        {show ? (
          <div className="rounded-lg border border-dashed border-border bg-card p-3 text-xs text-muted-foreground transition duration-300 starting:-translate-y-2 starting:opacity-0">
            Inserted nodes animate from their{' '}
            <code className="rounded bg-muted px-1">@starting-style</code> values. No mount effect,
            no first-frame flash of the final state.
          </div>
        ) : null}
      </section>
    </div>
  )
}
