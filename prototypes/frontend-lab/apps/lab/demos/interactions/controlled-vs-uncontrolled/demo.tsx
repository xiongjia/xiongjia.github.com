import { useRef, useState } from 'react'

/**
 * Render counter used for measurement only. Mutating a ref during render is normally a smell; here it
 * is the cheapest honest way to show how many times this component committed.
 */
function useCommitCount(): number {
  const commits = useRef(0)
  commits.current += 1
  return commits.current
}

export default function Demo() {
  const commits = useCommitCount()

  const [controlled, setControlled] = useState('typed by React')
  const [uncontrolledReads, setUncontrolledReads] = useState<string[]>([])
  const uncontrolled = useRef<HTMLInputElement>(null)

  const readUncontrolled = () => {
    const value = uncontrolled.current?.value ?? ''
    setUncontrolledReads((reads) => [`"${value}"`, ...reads].slice(0, 3))
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <section className="space-y-2 rounded-lg border border-border p-4">
          <h3 className="text-sm font-semibold">Controlled</h3>
          <p className="text-xs text-muted-foreground">
            <code>value</code> + <code>onChange</code>; React owns the text.
          </p>
          <label className="block text-xs font-medium text-muted-foreground" htmlFor="controlled">
            Name
          </label>
          <input
            id="controlled"
            value={controlled}
            onChange={(event) => setControlled(event.target.value)}
            className="h-9 w-full rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <p className="text-xs text-muted-foreground">
            Live value: <span className="font-mono">{controlled || '∅'}</span>
          </p>
        </section>

        <section className="space-y-2 rounded-lg border border-border p-4">
          <h3 className="text-sm font-semibold">Uncontrolled</h3>
          <p className="text-xs text-muted-foreground">
            <code>defaultValue</code> + <code>ref</code>; the DOM owns the text.
          </p>
          <label className="block text-xs font-medium text-muted-foreground" htmlFor="uncontrolled">
            Name
          </label>
          <input
            id="uncontrolled"
            ref={uncontrolled}
            defaultValue="typed by the DOM"
            className="h-9 w-full rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="button"
            onClick={readUncontrolled}
            className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            Read value
          </button>
          <p className="text-xs text-muted-foreground">
            Last reads:{' '}
            <span className="font-mono">{uncontrolledReads.join(' · ') || 'none yet'}</span>
          </p>
        </section>
      </div>

      <p className="text-xs text-muted-foreground">
        Commits since load: <span className="font-mono">{commits}</span> — every keystroke in the
        controlled input adds one; typing in the uncontrolled input adds none, only "Read value"
        does.
      </p>
    </div>
  )
}
