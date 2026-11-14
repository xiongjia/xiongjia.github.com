import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  chartColor,
  describeFlow,
  layoutSankey,
  type SankeyLink,
  type SankeyNode,
} from '@frontend-lab/charts/sankey-layout'

/*
 * The Sankey layout is the part of the fund-flow card that can be wrong without looking wrong: a
 * ribbon anchored outside its node band, a column that overflows the viewBox, or a scale that differs
 * between stages all still render "a diagram". These cases pin the geometry.
 */

const nodes: SankeyNode[] = [
  { id: 'salary', label: 'Salary', column: 0 },
  { id: 'bonus', label: 'Bonus', column: 0 },
  { id: 'housing', label: 'Housing', column: 1 },
  { id: 'savings', label: 'Savings', column: 1 },
  { id: 'emergency', label: 'Emergency', column: 2 },
]

const links: SankeyLink[] = [
  { source: 'salary', target: 'housing', value: 12 },
  { source: 'salary', target: 'savings', value: 8 },
  { source: 'bonus', target: 'savings', value: 2 },
  { source: 'savings', target: 'emergency', value: 10 },
]

test('a node carries the larger of its incoming and outgoing total', () => {
  const layout = layoutSankey(nodes, links)
  const byId = new Map(layout.nodes.map((node) => [node.id, node]))

  assert.equal(byId.get('salary')?.value, 20)
  assert.equal(byId.get('bonus')?.value, 2)
  assert.equal(byId.get('savings')?.value, 10)
  // A sink only has incoming flow.
  assert.equal(byId.get('housing')?.value, 12)
})

test('columns are counted from the node column values', () => {
  assert.equal(layoutSankey(nodes, links).columns, 3)
  assert.equal(layoutSankey([{ id: 'only', label: 'Only', column: 0 }], []).columns, 1)
})

test('every node band stays inside the viewBox and columns do not overlap', () => {
  const layout = layoutSankey(nodes, links, { height: 200, padding: 8, gap: 10 })

  for (const node of layout.nodes) {
    assert.ok(node.y >= 0, `${node.id} starts at ${node.y}`)
    assert.ok(node.y + node.height <= 200, `${node.id} ends at ${node.y + node.height}`)
  }

  for (const column of [0, 1, 2]) {
    const inColumn = layout.nodes.filter((node) => node.column === column).sort((a, b) => a.y - b.y)
    for (let index = 1; index < inColumn.length; index += 1) {
      const previous = inColumn[index - 1]
      const current = inColumn[index]
      if (!previous || !current) continue
      assert.ok(previous.y + previous.height <= current.y, 'stacked nodes overlap')
    }
  }
})

test('ribbon thickness is proportional to the value at every stage', () => {
  const layout = layoutSankey(nodes, links)
  const byLink = new Map(layout.links.map((link) => [`${link.source}->${link.target}`, link]))

  const housing = byLink.get('salary->housing')
  const savings = byLink.get('salary->savings')
  assert.ok(housing && savings)
  assert.ok(Math.abs(housing.thickness / savings.thickness - 12 / 8) < 0.001)

  // Equal values are equally thick across columns, because one scale is shared.
  const emergency = byLink.get('savings->emergency')
  assert.ok(emergency)
  assert.ok(Math.abs(emergency.thickness / savings.thickness - 10 / 8) < 0.001)
})

test('a node hands out its ribbons without leaving its own band', () => {
  const layout = layoutSankey(nodes, links)
  const salary = layout.nodes.find((node) => node.id === 'salary')
  assert.ok(salary)

  const outgoing = layout.links.filter((link) => link.source === 'salary')
  // Every ribbon's path starts at the node's right edge; the anchors are encoded in the path.
  for (const link of outgoing) {
    assert.ok(link.path.startsWith(`M ${Math.round((salary.x + 9) * 100) / 100}`))
    assert.equal(link.color, salary.color)
  }
})

test('empty input is a valid, empty layout', () => {
  const layout = layoutSankey([], [])
  assert.deepEqual(layout.links, [])
  assert.deepEqual(layout.nodes, [])
  // One column is still reported, so a caller can render the frame without a special case.
  assert.equal(layout.columns, 1)
})

test('links that point at unknown nodes are dropped instead of throwing', () => {
  const layout = layoutSankey(
    [{ id: 'a', label: 'A', column: 0 }],
    [{ source: 'a', target: 'ghost', value: 4 }],
  )
  assert.deepEqual(layout.links, [])
})

test('the categorical colours cycle through five tokens', () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5].map(chartColor), [
    'var(--chart-1)',
    'var(--chart-2)',
    'var(--chart-3)',
    'var(--chart-4)',
    'var(--chart-5)',
    'var(--chart-1)',
  ])
})

test('the accessible name summarises the first stage, not every ribbon', () => {
  assert.equal(describeFlow(nodes, links), '22 across 3 stages, 5 nodes and 4 flows')
})
