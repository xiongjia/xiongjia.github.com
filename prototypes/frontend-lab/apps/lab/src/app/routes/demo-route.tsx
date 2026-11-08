import { findDemo, findDemoGroup } from '@/generated/demo-registry'
import { useParams } from 'react-router-dom'

import { DemoShell } from '../../components/demo-shell'
import { MissingTranslationBadge } from '../../components/missing-translation-badge'
import { useI18n } from '../../i18n/use-i18n'
import { useDocumentTitle } from '../use-document-title'
import { NotFoundRoute } from './not-found-route'

/** `/demos/<group>/<demo>` — one route for every generated demo. */
export function DemoRoute() {
  const params = useParams()
  const slug = [params['group'], params['name']].filter(Boolean).join('/')
  const demo = findDemo(slug)
  const { t, pick } = useI18n()

  const entry = demo ? pick(demo.locales) : undefined
  useDocumentTitle(
    entry ? `${entry.value.title} · ${t.app.name}` : `${t.notFound.title} · ${t.app.name}`,
  )

  if (!demo || !entry) {
    return <NotFoundRoute />
  }

  const groupTitle = t.groups[demo.group] ?? findDemoGroup(demo.group)?.title ?? demo.group

  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {groupTitle} · {t.nav.demoBadge}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{entry.value.title}</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{entry.value.summary}</p>
        {entry.missing ? <MissingTranslationBadge message={t.demo.notTranslated} /> : null}
      </header>

      {/* Keyed by slug: switching demos resets tabs, error state and the preview mount. */}
      <DemoShell key={demo.slug} demo={demo} notes={entry.value.loadNotes} />
    </article>
  )
}
