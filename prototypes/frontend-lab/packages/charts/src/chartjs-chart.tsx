import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartOptions,
} from 'chart.js'
import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'

import { useMountCost, type ChartProps } from './measure'
import { describeSeries, tokenColor } from './series'

/*
 * Chart.js: the canvas option, behind the `react-chartjs-2` adapter.
 *
 * Two differences from the other two renderers, both visible in the comparison:
 *
 * 1. **Registration is manual.** Chart.js 3+ is tree-shakeable, and nothing renders until the
 *    scales/elements you use are registered. It is the only renderer here where bundle size depends
 *    on what you draw.
 * 2. **Canvas needs real colours.** A CSS variable never reaches `fillStyle`; tokens have to be
 *    resolved with `getComputedStyle` at render time, which also means a theme switch does not
 *    repaint the chart unless something re-renders it.
 */
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

export function ChartjsChart({ series, label, onMeasured }: ChartProps) {
  useMountCost(onMeasured)

  const data = useMemo(
    () => ({
      labels: series.map((point) => point.label),
      datasets: [
        {
          data: series.map((point) => point.value),
          borderColor: tokenColor('--primary', '#2563eb'),
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.35,
          fill: false,
        },
        {
          data: series.map((point) => point.previous),
          borderColor: tokenColor('--muted-foreground', '#8b8b8b'),
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 0,
          tension: 0.35,
          fill: false,
        },
      ],
    }),
    [series],
  )

  const options = useMemo<ChartOptions<'line'>>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      // Animation off: comparable render numbers, and no motion under reduced motion.
      animation: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
      elements: { line: { capBezierPoints: true } },
    }),
    [],
  )

  return (
    <div
      role="img"
      aria-label={`${label}: ${describeSeries(series)}`}
      data-renderer="chartjs"
      className="h-24 w-full"
    >
      <Line data={data} options={options} />
    </div>
  )
}
