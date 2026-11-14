import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { useMountCost, type ChartProps } from './measure'
import { describeSeries } from './series'

/*
 * Recharts: the declarative React option.
 *
 * The library renders SVG, so — like the hand-written baseline — it accepts `var(--token)` colours
 * and follows the theme without any wiring. What it adds is the rest of a chart: scales, ticks,
 * tooltips, responsive sizing, and composition (an `Area` is a child element, not an option object).
 */
export function RechartsChart({ series, label, onMeasured }: ChartProps) {
  useMountCost(onMeasured)

  return (
    <div
      role="img"
      aria-label={`${label}: ${describeSeries(series)}`}
      data-renderer="recharts"
      className="h-24 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
          <XAxis dataKey="label" hide />
          <YAxis hide domain={[0, 'dataMax + 8']} />
          <Tooltip
            cursor={{ stroke: 'var(--border)' }}
            contentStyle={{
              background: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 11,
              color: 'var(--foreground)',
            }}
          />
          <Area
            type="monotone"
            dataKey="previous"
            stroke="var(--muted-foreground)"
            strokeDasharray="3 3"
            fill="none"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.18}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
