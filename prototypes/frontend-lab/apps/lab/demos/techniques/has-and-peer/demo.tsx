import { useState } from 'react'

/**
 * `has-*` turns a descendant's state into a parent's style, and `peer-*` does the same for a
 * following sibling. Every state below is a native form state — no `useState` decides any colour,
 * which is the point: the styles cannot drift from the DOM, because they *are* the DOM.
 */
export default function Demo() {
  const [email, setEmail] = useState('not-an-email')
  const [agree, setAgree] = useState(false)
  const [plan, setPlan] = useState<'basic' | 'pro'>('pro')

  const emailInvalid = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          group-has — a parent styled by its own invalid input
        </h3>
        <div
          data-probe=""
          className="group flex flex-col gap-2 rounded-lg border-2 border-border p-3 transition-colors has-[input:invalid]:border-destructive has-[input:invalid]:bg-destructive/5"
        >
          <label className="flex flex-col gap-1 text-xs font-medium">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={emailInvalid}
              className="h-9 rounded-md border border-border bg-background px-2 text-sm outline-none invalid:border-destructive focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
          <p className="text-xs text-muted-foreground group-has-[input:invalid]:text-destructive">
            {emailInvalid
              ? 'The wrapper turned red because it has [input:invalid] — the message is a `has-` variant too.'
              : 'Valid: the wrapper is back to the border token, with no state in React deciding it.'}
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          peer-checked — a sibling revealed by a checkbox
        </h3>
        <div className="rounded-lg border border-border p-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={agree}
              onChange={(event) => setAgree(event.target.checked)}
              className="peer size-4 accent-primary"
            />
            <span className="peer-checked:font-semibold">Show the details</span>
          </label>
          <div className="mt-2 hidden rounded-md bg-muted p-2 text-xs peer-checked:block">
            Revealed by <code>peer-checked:block</code>. The checkbox state is the only input; no
            conditional class name was computed.
          </div>
          <p className="mt-2 font-mono text-[11px] text-muted-foreground">
            checked={String(agree)} · panel visible via peer-checked only
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          has-[:checked] — a row that styles itself when selected
        </h3>
        <div role="radiogroup" aria-label="Plan" className="grid gap-2 sm:grid-cols-2">
          {(['basic', 'pro'] as const).map((value) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-border p-3 text-sm transition-colors has-[:checked]:border-primary has-[:checked]:bg-secondary"
            >
              <input
                type="radio"
                name="plan"
                value={value}
                checked={plan === value}
                onChange={() => setPlan(value)}
                className="size-4 accent-primary"
              />
              <span className="has-[:checked]:font-medium">{value}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          has-[img] — card padding that depends on content
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {[true, false].map((withImage) => (
            <div
              key={String(withImage)}
              className="rounded-lg border border-border p-3 pt-0 has-[img]:pt-0 has-[img]:pb-3 [&:not(:has(img))]:pt-3"
            >
              {withImage ? (
                <div
                  aria-hidden="true"
                  className="-mx-3 mb-2 h-16 rounded-t-lg bg-gradient-to-br from-primary/30 to-accent"
                />
              ) : null}
              <p className="text-sm font-medium">{withImage ? 'With image' : 'Without image'}</p>
              <p className="text-xs text-muted-foreground">
                {withImage ? 'Image bleeds to the card edge; no top padding.' : 'Normal padding.'}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
