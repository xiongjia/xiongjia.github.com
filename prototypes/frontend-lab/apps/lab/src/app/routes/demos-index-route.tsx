import { demoGroups, demos } from '@/generated/demo-registry'
import { Link } from 'react-router-dom'

import { MissingTranslationBadge } from '../../components/missing-translation-badge'
import { useI18n } from '../../i18n/use-i18n'
import { format } from '../../i18n/dictionary'
import { useDocumentTitle } from '../use-document-title'

export function DemosIndexRoute() {
  const { t, pick } = useI18n()

  useDocumentTitle(`${t.demos.title} · ${t.app.name}`)

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t.demos.title}</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          {format(t.demos.intro, { count: demos.length })}
        </p>
      </section>

      <section className="space-y-4">
        {demoGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-sm font-semibold">{t.groups[group.id] ?? group.title}</h2>
            <ul className="mt-3 space-y-2">
              {group.demos.map((demo) => {
                const entry = pick(demo.locales)
                return (
                  <li key={demo.slug} className="flex flex-wrap items-baseline gap-2 text-sm">
                    <Link
                      to={`/demos/${demo.slug}`}
                      className="font-medium text-primary underline-offset-4 hover:underline"
                    >
                      {entry.value.title}
                    </Link>
                    {entry.missing ? (
                      <MissingTranslationBadge message={t.nav.missingTitle} compact />
                    ) : null}
                    <span className="text-muted-foreground">{entry.value.summary}</span>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </section>
    </div>
  )
}
