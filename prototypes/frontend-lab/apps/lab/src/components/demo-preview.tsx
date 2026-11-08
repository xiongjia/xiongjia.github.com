import type { Demo } from '@/generated/demo-registry'
import { lazy, Suspense, useMemo, type ComponentType, type LazyExoticComponent } from 'react'

import { format } from '../i18n/dictionary'
import { useI18n } from '../i18n/use-i18n'
import { DemoErrorBoundary } from './demo-error-boundary'

/** Lazy components are cached per demo so switching tabs does not remount (and lose) demo state. */
const cache = new Map<string, LazyExoticComponent<ComponentType>>()

function lazyDemo(demo: Demo): LazyExoticComponent<ComponentType> {
  const cached = cache.get(demo.slug)
  if (cached) return cached

  const component = lazy(demo.load)
  cache.set(demo.slug, component)
  return component
}

export function DemoPreview({ demo }: { demo: Demo }) {
  const Component = useMemo(() => lazyDemo(demo), [demo])
  const { t } = useI18n()

  return (
    <DemoErrorBoundary
      demo={demo.slug}
      labels={{
        title: t.demo.crashed,
        hint: format(t.demo.crashedHint, { slug: demo.slug }),
        recover: t.demo.recover,
      }}
    >
      <Suspense fallback={<p className="text-sm text-muted-foreground">{t.demo.loading}</p>}>
        <Component />
      </Suspense>
    </DemoErrorBoundary>
  )
}
