import type { Demo } from '@/generated/demo-registry'
import { Suspense, use, useEffect, useState } from 'react'

/** One promise per demo: re-rendering the panel must not re-fetch the raw file. */
const cache = new Map<string, Promise<string>>()

function loadSource(demo: Demo): Promise<string> {
  const cached = cache.get(demo.slug)
  if (cached) return cached

  const promise = demo.loadSource().then((module) => module.default)
  cache.set(demo.slug, promise)
  return promise
}

function CopyButton({ text }: { text: string }) {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (status === 'idle') return
    const timer = setTimeout(() => setStatus('idle'), 2000)
    return () => clearTimeout(timer)
  }, [status])

  const copy = () => {
    navigator.clipboard.writeText(text).then(
      () => setStatus('copied'),
      () => setStatus('failed'),
    )
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="rounded-md border border-border px-2.5 py-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
    >
      {status === 'copied' ? 'Copied' : status === 'failed' ? 'Copy failed' : 'Copy'}
      <span className="sr-only"> source of the demo</span>
    </button>
  )
}

function SourceCode({ demo }: { demo: Demo }) {
  const source = use(loadSource(demo))

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          demo.tsx
        </p>
        <CopyButton text={source} />
      </div>
      <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs leading-6">
        <code>{source}</code>
      </pre>
    </div>
  )
}

export function DemoSource({ demo }: { demo: Demo }) {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading source…</p>}>
      <SourceCode demo={demo} />
    </Suspense>
  )
}
