import type { Demo } from '@/generated/demo-registry'
import { lazy, Suspense, useMemo, type ComponentType, type LazyExoticComponent } from 'react'

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

  return (
    <DemoErrorBoundary demo={demo.slug}>
      <Suspense fallback={<p className="text-sm text-muted-foreground">Loading demo…</p>}>
        <Component />
      </Suspense>
    </DemoErrorBoundary>
  )
}
