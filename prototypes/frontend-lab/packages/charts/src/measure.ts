import { useLayoutEffect, useRef } from 'react'

import type { ChartPoint } from './series'

/*
 * The comparison's measuring stick.
 *
 * "How expensive is a chart library" has two costs and they are not interchangeable:
 *
 *   load    the chunk the library adds to the bundle — reported by `pnpm bundle:report`
 *   render  the work from the first render to the committed DOM — measured here
 *
 * Every renderer calls the same hook, so the render numbers in the dashboard are comparable. The
 * measurement starts at the first render of the component (after its chunk has loaded) and stops in
 * a layout effect, which is exactly "render + commit" and excludes network and parse time.
 */

export type ChartProps = {
  series: ChartPoint[]
  /** Accessible name; every renderer also describes the series, so a screen reader gets the gist. */
  label: string
  /** Render cost in milliseconds, reported once per mount. */
  onMeasured?: (milliseconds: number) => void
}

export function useMountCost(onMeasured?: (milliseconds: number) => void): void {
  const start = useRef(performance.now())
  const callback = useRef(onMeasured)
  callback.current = onMeasured

  useLayoutEffect(() => {
    const elapsed = performance.now() - start.current
    callback.current?.(Math.round(elapsed * 100) / 100)
  }, [])
}
