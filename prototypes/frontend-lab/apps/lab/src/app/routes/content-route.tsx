import { findContentGroup, findContentPage, type ContentPage } from '@/generated/content-index'
import { lazy, Suspense, useMemo, type ComponentType, type LazyExoticComponent } from 'react'
import { useParams } from 'react-router-dom'

import { useDocumentTitle } from '../use-document-title'
import { NotFoundRoute } from './not-found-route'

/**
 * `React.lazy` components are created once per slug and then cached: re-creating them on every
 * render would remount the MDX tree (and lose any component state inside it).
 */
const lazyCache = new Map<string, LazyExoticComponent<ComponentType>>()

function lazyPage(page: ContentPage): LazyExoticComponent<ComponentType> {
  const cached = lazyCache.get(page.slug)
  if (cached) return cached

  const component = lazy(page.load)
  lazyCache.set(page.slug, component)
  return component
}

function PageBody({ page }: { page: ContentPage }) {
  const Component = useMemo(() => lazyPage(page), [page])

  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading page…</p>}>
      <Component />
    </Suspense>
  )
}

/**
 * Renders any generated content page. The splat route (`*`) feeds the whole path in, so pages can
 * live at any depth inside `content/` without a matching route entry here.
 */
export function ContentRoute() {
  const params = useParams()
  const slug = params['*'] ?? ''
  const page = findContentPage(slug)

  useDocumentTitle(page ? `${page.title} · Frontend Lab` : 'Page not found · Frontend Lab')

  if (!page) {
    return <NotFoundRoute />
  }

  const groupTitle = findContentGroup(page.group)?.title ?? page.group

  return (
    <article>
      <header className="mb-6 space-y-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {groupTitle}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{page.title}</h1>
        {page.summary ? (
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{page.summary}</p>
        ) : null}
      </header>

      <div className="mdx">
        <PageBody page={page} />
      </div>
    </article>
  )
}
