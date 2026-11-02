import { findDemo, findDemoGroup } from '@/generated/demo-registry'
import { useParams } from 'react-router-dom'

import { DemoShell } from '../../components/demo-shell'
import { useDocumentTitle } from '../use-document-title'
import { NotFoundRoute } from './not-found-route'

/** `/demos/<group>/<demo>` — one route for every generated demo. */
export function DemoRoute() {
  const params = useParams()
  const slug = [params['group'], params['name']].filter(Boolean).join('/')
  const demo = findDemo(slug)

  useDocumentTitle(demo ? `${demo.title} · Frontend Lab` : 'Page not found · Frontend Lab')

  if (!demo) {
    return <NotFoundRoute />
  }

  const groupTitle = findDemoGroup(demo.group)?.title ?? demo.group

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {groupTitle} · demo
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{demo.title}</h1>
        {demo.summary ? (
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{demo.summary}</p>
        ) : null}
      </header>

      {/* Keyed by slug: switching demos resets tabs, error state and the preview mount. */}
      <DemoShell key={demo.slug} demo={demo} />
    </article>
  )
}
