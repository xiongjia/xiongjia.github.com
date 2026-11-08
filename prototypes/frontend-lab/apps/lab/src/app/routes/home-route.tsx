import { contentGroups, contentPages } from '@/generated/content-index'
import { demoGroups, demos } from '@/generated/demo-registry'
import { Link } from 'react-router-dom'

import { MissingTranslationBadge } from '../../components/missing-translation-badge'
import { useI18n } from '../../i18n/use-i18n'
import { format } from '../../i18n/dictionary'
import { useDocumentTitle } from '../use-document-title'

const ctaClass =
  'inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'

const secondaryCtaClass =
  'inline-flex h-10 items-center rounded-md border border-border px-4 text-sm font-medium text-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2'

export function HomeRoute() {
  const { t, pick } = useI18n()
  const firstPage = contentPages.at(0)
  const firstDemo = demos.at(0)

  const firstDemoEntry = firstDemo ? pick(firstDemo.locales).value : undefined
  const firstPageEntry = firstPage ? pick(firstPage.locales).value : undefined

  useDocumentTitle(t.app.name)

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t.app.name}</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{t.home.intro}</p>
        <div className="flex flex-wrap gap-3">
          {firstDemo && firstDemoEntry ? (
            <Link to={`/demos/${firstDemo.slug}`} className={ctaClass}>
              {t.home.openFirstDemo}
            </Link>
          ) : null}
          {firstPage && firstPageEntry ? (
            <Link to={`/${firstPage.slug}`} className={secondaryCtaClass}>
              {format(t.home.startWith, { title: firstPageEntry.title })}
            </Link>
          ) : null}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold">
          {format(t.home.demosHeading, { count: demos.length })}
        </h2>
        {demoGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold">{t.groups[group.id] ?? group.title}</h3>
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

      <section className="space-y-4">
        <h2 className="text-sm font-semibold">
          {format(t.home.contentHeading, { count: contentPages.length })}
        </h2>
        {contentGroups.map((group) => (
          <div key={group.id} className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold">{t.groups[group.id] ?? group.title}</h3>
            <ul className="mt-3 space-y-2">
              {group.pages.map((page) => {
                const entry = pick(page.locales)
                return (
                  <li key={page.slug} className="flex flex-wrap items-baseline gap-2 text-sm">
                    <Link
                      to={`/${page.slug}`}
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

      <section className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        {t.home.footnote}
      </section>
    </div>
  )
}
