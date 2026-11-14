/*
 * Chart renderers for the B15 dashboard, in order of dependency weight:
 *
 *   @frontend-lab/charts           hand-written SVG, no dependencies
 *   @frontend-lab/charts/recharts  Recharts (SVG, declarative)
 *   @frontend-lab/charts/chartjs   Chart.js + adapter (canvas, imperative)
 *
 * The two library renderers live behind their own entry points so a caller can lazy-load them and
 * so the built chunks are attributable in `pnpm bundle:report`.
 */

export { SankeyChart } from './sankey'
export type { SankeyChartProps } from './sankey'
export { chartColor, describeFlow, layoutSankey } from './sankey-layout'
export type { SankeyLayout, SankeyLayoutOptions, SankeyLink, SankeyNode } from './sankey-layout'
export { SvgChart } from './svg-chart'
export { createSeries, describeSeries, summarize, tokenColor } from './series'
export type { ChartPoint, SeriesSummary } from './series'
export { useMountCost } from './measure'
export type { ChartProps } from './measure'
