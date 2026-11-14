/*
 * Sankey layout: the pure half of the fund-flow diagram.
 *
 * A Sankey is a *flow* chart, not a series chart: it answers "where did the money go", which is why
 * it is the right shape for a dashboard that already has trends and tables. None of the three
 * renderers compared in B15 ships one — Recharts has no Sankey, Chart.js needs a community plugin,
 * and the layout (node stacking, ribbon anchors, crossing order) is the actual work. So it is written
 * here, dependency-free, and kept as a pure function so `node:test` can assert it.
 *
 * Input: nodes with a column and links with a value. Oil: ribbons whose thickness is the value.
 */

export type SankeyNode = {
  id: string
  label: string
  /** 0-based stage; nodes in the same column are stacked. */
  column: number
}

export type SankeyLink = {
  source: string
  target: string
  value: number
}

export type SankeyNodeLayout = SankeyNode & {
  /** `max(incoming, outgoing)` — a middle node can lose a little to rounding or an unlisted flow. */
  value: number
  x: number
  y: number
  height: number
  /** CSS colour, from the `--chart-*` token cycle. */
  color: string
}

export type SankeyLinkLayout = SankeyLink & {
  /** SVG path data for the ribbon, already in viewBox units. */
  path: string
  thickness: number
  color: string
}

export type SankeyLayoutOptions = {
  width?: number
  height?: number
  nodeWidth?: number
  padding?: number
  /** Vertical space between nodes in one column. */
  gap?: number
}

export type SankeyLayout = {
  nodes: SankeyNodeLayout[]
  links: SankeyLinkLayout[]
  width: number
  height: number
  nodeWidth: number
  columns: number
}

/** The five categorical tokens, cycled. Declared in `tokens.css` for both modes. */
export function chartColor(index: number): string {
  return `var(--chart-${(index % 5) + 1})`
}

/** Round to two decimals: SVG path strings stay short and diff-stable. */
function round(value: number): number {
  return Math.round(value * 100) / 100
}

export function layoutSankey(
  nodes: readonly SankeyNode[],
  links: readonly SankeyLink[],
  options: SankeyLayoutOptions = {},
): SankeyLayout {
  const { width = 560, height = 200, nodeWidth = 9, padding = 8, gap = 10 } = options

  const incoming = new Map<string, number>()
  const outgoing = new Map<string, number>()
  for (const link of links) {
    incoming.set(link.target, (incoming.get(link.target) ?? 0) + link.value)
    outgoing.set(link.source, (outgoing.get(link.source) ?? 0) + link.value)
  }

  const valueOf = (id: string) => Math.max(incoming.get(id) ?? 0, outgoing.get(id) ?? 0)
  const columnCount = Math.max(0, ...nodes.map((node) => node.column)) + 1

  const columns: SankeyNode[][] = Array.from({ length: columnCount }, () => [])
  for (const node of nodes) columns[node.column]?.push(node)

  const columnTotals = columns.map((column) =>
    column.reduce((sum, node) => sum + valueOf(node.id), 0),
  )
  const maxTotal = Math.max(1, ...columnTotals)
  const maxNodes = Math.max(1, ...columns.map((column) => column.length))

  const usable = height - padding * 2
  // One shared scale for every column: equal values must be equally thick at any stage.
  const scale = Math.max(0.0001, (usable - gap * (maxNodes - 1)) / maxTotal)
  const xFor = (column: number) =>
    columnCount <= 1
      ? (width - nodeWidth) / 2
      : padding + (column / (columnCount - 1)) * (width - padding * 2 - nodeWidth)

  const placed = new Map<string, SankeyNodeLayout>()
  const laidOutNodes: SankeyNodeLayout[] = []

  columns.forEach((column, columnIndex) => {
    const total = columnTotals[columnIndex] ?? 0
    const columnHeight = total * scale + gap * Math.max(column.length - 1, 0)
    let cursor = padding + Math.max((usable - columnHeight) / 2, 0)

    for (const node of column) {
      const value = valueOf(node.id)
      const heightPx = value * scale
      const layout: SankeyNodeLayout = {
        ...node,
        value,
        x: xFor(columnIndex),
        y: cursor,
        height: heightPx,
        color: chartColor(nodes.indexOf(node)),
      }
      placed.set(node.id, layout)
      laidOutNodes.push(layout)
      cursor += heightPx + gap
    }
  })

  // Anchors: each node hands out vertical slices in its own band, in target order (less crossing).
  const outgoingCursor = new Map<string, number>()
  const incomingCursor = new Map<string, number>()
  for (const node of laidOutNodes) {
    outgoingCursor.set(node.id, node.y)
    incomingCursor.set(node.id, node.y)
  }

  const ordered = [...links].sort(
    (a, b) =>
      (placed.get(a.source)?.y ?? 0) - (placed.get(b.source)?.y ?? 0) ||
      (placed.get(a.target)?.y ?? 0) - (placed.get(b.target)?.y ?? 0),
  )

  const laidOutLinks: SankeyLinkLayout[] = []
  for (const link of ordered) {
    const source = placed.get(link.source)
    const target = placed.get(link.target)
    if (!source || !target) continue

    const thickness = link.value * scale
    const sourceY = outgoingCursor.get(link.source) ?? source.y
    const targetY = incomingCursor.get(link.target) ?? target.y
    outgoingCursor.set(link.source, sourceY + thickness)
    incomingCursor.set(link.target, targetY + thickness)

    const x0 = source.x + nodeWidth
    const x1 = target.x
    const mid = (x0 + x1) / 2
    const path = [
      `M ${round(x0)} ${round(sourceY)}`,
      `C ${round(mid)} ${round(sourceY)} ${round(mid)} ${round(targetY)} ${round(x1)} ${round(targetY)}`,
      `L ${round(x1)} ${round(targetY + thickness)}`,
      `C ${round(mid)} ${round(targetY + thickness)} ${round(mid)} ${round(sourceY + thickness)} ${round(x0)} ${round(sourceY + thickness)}`,
      'Z',
    ].join(' ')

    laidOutLinks.push({
      ...link,
      path,
      thickness,
      color: source.color,
    })
  }

  return {
    nodes: laidOutNodes,
    links: laidOutLinks,
    width,
    height,
    nodeWidth,
    columns: columnCount,
  }
}

/** One sentence for an accessible name; the SVG itself is decorative. */
export function describeFlow(nodes: readonly SankeyNode[], links: readonly SankeyLink[]): string {
  const columns = Math.max(0, ...nodes.map((node) => node.column)) + 1
  const total = links
    .filter((link) => nodes.find((node) => node.id === link.source)?.column === 0)
    .reduce((sum, link) => sum + link.value, 0)

  return `${total} across ${columns} stages, ${nodes.length} nodes and ${links.length} flows`
}
