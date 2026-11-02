import { demoGroups, demos } from '@/generated/demo-registry'
import { Link } from 'react-router-dom'

import { useDocumentTitle } from '../use-document-title'

export function DemosIndexRoute() {
  useDocumentTitle('Demos · Frontend Lab')

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Demos</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          {demos.length} runnable demos. Each one is a folder under <code>demos/</code> with a{' '}
          <code>demo.tsx</code> component and a <code>notes.mdx</code> write-up; the registry, the
          source view and the sidebar entry are generated from it.
        </p>
      </section>

      <section className="space-y-4">
        {demoGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold">{group.title}</h2>
            <ul className="mt-3 space-y-2">
              {group.demos.map((demo) => (
                <li key={demo.slug} className="text-sm">
                  <Link
                    to={`/demos/${demo.slug}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {demo.title}
                  </Link>
                  {demo.summary ? (
                    <span className="text-muted-foreground"> · {demo.summary}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  )
}
