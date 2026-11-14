import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

/*
 * The axe matrix.
 *
 * Accessibility regressions are cross-cutting: a token change can break contrast in one mode, a
 * translation can break a label, and a demo can ship an unlabelled control. Scanning one page in one
 * mode would miss most of that, so the matrix is:
 *
 *   routes × colour mode × locale  (+ one open-dialog state, which axe cannot reach by navigation)
 *
 * `addInitScript` writes the two preferences before the app boots, which is the same path the
 * inline bootstrap reads — no waiting for a control to be clickable, and the scan sees the mode the
 * reader would actually get.
 */

const routes = [
  { name: 'home', path: '/' },
  { name: 'content page', path: '/foundations/design-tokens' },
  { name: 'demo with editor', path: '/demos/scenarios/ide-workspace' },
  { name: 'demo with kanban', path: '/demos/scenarios/kanban-board' },
  { name: 'demo with charts', path: '/demos/scenarios/dashboard-builder' },
]

const modes = ['light', 'dark'] as const
const locales = ['en', 'zh'] as const

for (const route of routes) {
  for (const mode of modes) {
    for (const locale of locales) {
      test(`axe: ${route.name} · ${mode} · ${locale}`, async ({ page }) => {
        await page.addInitScript(
          ({ mode, locale }) => {
            localStorage.setItem('frontend-lab:theme', mode)
            localStorage.setItem('frontend-lab:locale', locale)
          },
          { mode, locale },
        )

        await page.goto(route.path)
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

        const results = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze()

        expect(
          results.violations.map((violation) => ({
            id: violation.id,
            impact: violation.impact,
            help: violation.help,
            nodes: violation.nodes.map((node) => node.target.join(' ')),
          })),
        ).toEqual([])
      })
    }
  }
}

test('axe: the command palette dialog', async ({ page }) => {
  await page.goto('/demos/scenarios/command-palette')
  await page.locator('#palette-trigger').click()
  await expect(page.getByRole('dialog')).toBeVisible()

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()

  expect(
    results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => node.target.join(' ')),
    })),
  ).toEqual([])
})
