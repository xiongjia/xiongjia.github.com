import {
  findContentGroup,
  findContentPage,
  type ContentLocaleEntry,
  type ContentPage,
} from '@/generated/content-index'
import { lazy, Suspense, useMemo, type ComponentType, type LazyExoticComponent } from 'react'
import { useParams } from 'react-router-dom'

import { MissingTranslationBadge } from '../../components/missing-translation-badge'
import type { Locale } from '../../i18n/locales'
import { useI18n } from '../../i18n/use-i18n'
import { useDocumentTitle } from '../use-document-title'
import { NotFoundRoute } from './not-found-route'

/**
 * `React.lazy` components are created once per slug *and locale* and then cached: re-creating them on
 * every render would remount the MDX tree (and lose any component state inside it).
 */
const lazyCache = new Map<string, LazyExoticComponent<ComponentType>>()

function lazyPage(
  slug: string,
  locale: Locale,
  load: () => Promise<{ default: ComponentType }>,
): LazyExoticComponent<ComponentType> {
  const key = `${slug}:${locale}`
  const cached = lazyCache.get(key)
  if (cached) return cached

  const component = lazy(load)
  lazyCache.set(key, component)
  return component
}

function PageBody({
  page,
  locale,
  entry,
  loading,
}: {
  page: ContentPage
  locale: Locale
  entry: ContentLocaleEntry
  loading: string
}) {
  const Component = useMemo(
    () => lazyPage(page.slug, locale, entry.load),
    [page.slug, locale, entry.load],
  )

  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">{loading}</p>}>
      <Component />
    </Suspense>
  )
}

/**
 * Renders any generated content page. The splat route (`*`) feeds the whole path in, so pages can
 * live at any depth inside `content/` without a matching route entry here. The body is the locale's
 * own MDX file; a page without a translation keeps its English body and says so.
 */
export function ContentRoute() {
  const params = useParams()
  const slug = params['*'] ?? ''
  const page = findContentPage(slug)
  const { locale, t, pick } = useI18n()

  const entry = page ? pick(page.locales) : undefined
  useDocumentTitle(
    entry ? `${entry.value.title} · ${t.app.name}` : `${t.notFound.title} · ${t.app.name}`,
  )

  if (!page || !entry) {
    return <NotFoundRoute />
  }

  const groupTitle = t.groups[page.group] ?? findContentGroup(page.group)?.title ?? page.group

  return (
    <article>
      <header className="mb-6 space-y-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {groupTitle}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{entry.value.title}</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{entry.value.summary}</p>
        {entry.missing ? <MissingTranslationBadge message={t.content.notTranslated} /> : null}
      </header>

      <div className="mdx">
        <PageBody page={page} locale={locale} entry={entry.value} loading={t.content.loading} />
      </div>
    </article>
  )
}
