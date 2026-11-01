import { Link } from 'react-router-dom'

const waves = [
  {
    name: 'Wave 1 · Shell & content loop',
    batches: [
      { id: 'B1', label: 'Shell (workspace, Vite, Tailwind, router, layout)', status: 'done' },
      { id: 'B2', label: 'Content loop (MDX, frontmatter, generated index)', status: 'next' },
      { id: 'B3', label: 'Demo system (registry, DemoShell, source view)', status: 'todo' },
    ],
  },
  {
    name: 'Wave 2 · Cross-cutting',
    batches: [
      { id: 'B4', label: 'Quality gates (schema, content checks, e2e smoke)', status: 'todo' },
      { id: 'B5', label: 'Theme (tokens, light/dark, persisted prefs)', status: 'todo' },
      { id: 'B6', label: 'Multiple styles (presets, style playground)', status: 'todo' },
      { id: 'B7', label: 'i18n (dictionaries, bilingual content)', status: 'todo' },
    ],
  },
]

const statusStyles: Record<string, string> = {
  done: 'bg-primary text-primary-foreground',
  next: 'bg-secondary text-secondary-foreground',
  todo: 'bg-muted text-muted-foreground',
}

export function HomeRoute() {
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">Frontend Lab</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          An experiment lab for frontend techniques: every experiment runs, exposes its source and
          ships an MDX write-up. Built batch by batch — the roadmap lives in the prototype README.
        </p>
        <Link
          to="/demos/hello"
          className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          Open the first inline demo
        </Link>
      </section>

      <section className="space-y-4">
        {waves.map((wave) => (
          <div key={wave.name} className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold">{wave.name}</h2>
            <ul className="mt-3 space-y-2">
              {wave.batches.map((batch) => (
                <li key={batch.id} className="flex items-start gap-3 text-sm">
                  <span
                    className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase ${statusStyles[batch.status]}`}
                  >
                    {batch.status}
                  </span>
                  <span className="text-muted-foreground">
                    <span className="font-medium text-foreground">{batch.id}</span> · {batch.label}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        B1 has no MDX pipeline yet: this page is plain TSX and the demo is a hand-written component.
        B2 adds MDX + the generated content index, B3 adds the demo registry, source view and error
        boundary.
      </section>
    </div>
  )
}
