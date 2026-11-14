import { useMountCost, type ChartProps } from './measure'
import {
  describeFlow,
  layoutSankey,
  type SankeyLayoutOptions,
  type SankeyLink,
  type SankeyNode,
} from './sankey-layout'

/*
 * A fund-flow (Sankey) diagram, hand-written SVG.
 *
 * Why it is not a library renderer: Recharts has no Sankey, Chart.js needs a community plugin, and
 * the thing you would actually import (`d3-sankey`) is a layout library, not a renderer. The layout
 * lives in `sankey-layout.ts` as a pure function; this file only turns it into paths and labels.
 *
 * Colours come from the `--chart-*` tokens, so the diagram follows light/dark and the style presets
 * without a second palette — and it costs no chunk of its own.
 */

export type SankeyChartProps = {
  nodes: readonly SankeyNode[]
  links: readonly SankeyLink[]
  label: string
  /** Formats a value for the node labels and the accessible name, e.g. `38` -> `38k`. */
  format?: (value: number) => string
  layout?: SankeyLayoutOptions
  onMeasured?: (milliseconds: number) => void
}

export function SankeyChart({
  nodes,
  links,
  label,
  format = (value) => String(value),
  layout: layoutOptions,
  onMeasured,
}: SankeyChartProps) {
  useMountCost(onMeasured)
  const layout = layoutSankey(nodes, links, layoutOptions)
  const lastColumn = Math.max(0, ...layout.nodes.map((node) => node.column))

  return (
    <div
      role="img"
      aria-label={`${label}: ${describeFlow(nodes, links)}`}
      data-renderer="sankey"
      className="w-full"
    >
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-44 w-full"
        aria-hidden="true"
      >
        {layout.links.map((link) => (
          <path
            key={`${link.source}-${link.target}`}
            d={link.path}
            fill={link.color}
            fillOpacity={0.28}
          >
            <title>
              {link.source} → {link.target}: {format(link.value)}
            </title>
          </path>
        ))}

        {layout.nodes.map((node) => {
          const labelOnLeft = node.column === lastColumn
          const labelX = labelOnLeft ? node.x - 5 : node.x + layout.nodeWidth + 5
          const labelY = node.y + Math.min(node.height / 2 + 3, node.height + 8)

          return (
            <g key={node.id}>
              <rect
                x={node.x}
                y={node.y}
                width={layout.nodeWidth}
                height={Math.max(node.height, 1)}
                rx={2}
                fill={node.color}
              />
              <text
                x={labelX}
                y={labelY}
                textAnchor={labelOnLeft ? 'end' : 'start'}
                fontSize={9}
                fill="var(--foreground)"
              >
                {node.label}
                <tspan fill="var(--muted-foreground)"> {format(node.value)}</tspan>
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// The props type is shared with the other renderers, but a Sankey takes nodes and links instead of
// a series: re-export it so a caller can build a union without importing `measure` directly.
export type { ChartProps }
