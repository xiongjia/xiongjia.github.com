import { useId } from 'react'

import { useMountCost, type ChartProps } from './measure'
import { describeSeries } from './series'

/*
 * The baseline: a hand-written SVG line chart, zero dependencies.
 *
 * It is deliberately small — two polylines, one polygon, one gradient — because the point of the
 * comparison is to show what a chart library buys beyond this: axes, ticks, tooltips, legends,
 * responsiveness, brushing, and the maintenance of all of it.
 *
 * Colours are CSS variables, which is the other half of the comparison: an SVG renderer inherits the
 * token layer, so theme and style presets apply without a single prop.
 */

export function SvgChart({ series, label, onMeasured }: ChartProps) {
  useMountCost(onMeasured)
  const gradientId = useId()

  const width = 360
  const height = 120
  const padding = 10
  const max = Math.max(...series.flatMap((point) => [point.value, point.previous]), 1)
  const step = (width - padding * 2) / Math.max(series.length - 1, 1)

  const point = (value: number, index: number): [number, number] => [
    padding + index * step,
    height - padding - (value / max) * (height - padding * 2),
  ]

  const line = (key: 'value' | 'previous') =>
    series.map((entry, index) => point(entry[key], index).join(',')).join(' ')

  const area = `${padding},${height - padding} ${line('value')} ${width - padding},${height - padding}`

  return (
    <div
      role="img"
      aria-label={`${label}: ${describeSeries(series)}`}
      data-renderer="svg"
      className="w-full"
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-24 w-full"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill={`url(#${gradientId})`} />
        <polyline
          points={line('previous')}
          fill="none"
          stroke="var(--muted-foreground)"
          strokeWidth="1.5"
          strokeDasharray="3 3"
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          points={line('value')}
          fill="none"
          stroke="var(--primary)"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}
