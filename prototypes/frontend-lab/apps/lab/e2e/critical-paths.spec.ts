import { expect, test } from '@playwright/test'

/*
 * Critical paths.
 *
 * These are the flows a reader actually performs, one per batch capability: navigate, read a demo's
 * source, keep a preference, edit and save in the IDE, move a kanban card with the keyboard, switch
 * a chart renderer, and drive the app from the command palette.
 *
 * The suite runs against a production build (`vite preview`), so these tests also prove the lazy
 * chunks, the generated registries and the pref bootstrap work outside `pnpm dev`.
 */

const modifier = process.platform === 'darwin' ? 'Meta' : 'Control'

test('the sidebar navigates from the home page to a content page', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1, name: 'Frontend Lab' })).toBeVisible()
  await page
    .getByRole('navigation', { name: 'Lab' })
    .getByRole('link', { name: 'Design tokens' })
    .click()

  await expect(page).toHaveURL(/\/foundations\/design-tokens$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Design tokens' })).toBeVisible()
  await expect(page.getByRole('table')).toContainText('Primitive')
})

test('a demo shell switches views and the source is the real file', async ({ page }) => {
  await page.goto('/demos/foundations/button-variants')

  await expect(page.getByRole('tab', { name: 'Preview' })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: 'Source' }).click()
  await expect(page.getByRole('tabpanel', { name: 'Source' })).toContainText('export default')

  await page.getByRole('tab', { name: 'Notes' }).click()
  await expect(
    page.getByRole('tabpanel', { name: 'Notes' }).getByRole('heading').first(),
  ).toBeVisible()
})

test('the colour mode control persists and repaints', async ({ page }) => {
  await page.goto('/')
  const background = () =>
    page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--background').trim(),
    )

  const light = await background()
  await page
    .getByRole('group', { name: 'Color mode' })
    .getByRole('button', { name: 'Dark' })
    .click()

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  const dark = await background()
  expect(dark).not.toBe(light)

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await background()).toBe(dark)
})

test('switching the language translates the UI and survives a reload', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('group', { name: 'Language' }).getByRole('button', { name: '中文' }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN')
  await expect(page.getByRole('group', { name: '配色模式' })).toBeVisible()

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-CN')
})

test('the IDE workspace opens a file, marks a draft dirty and saves it', async ({ page }) => {
  await page.goto('/demos/scenarios/ide-workspace')

  await expect(page.getByTestId('status-line')).toHaveText('src/main.tsx')
  await page
    .getByRole('navigation', { name: 'Project files' })
    .getByRole('button', { name: 'README.md' })
    .click()
  await expect(page.getByTestId('status-line')).toHaveText('README.md')

  await page.locator('.cm-content').click()
  await page.keyboard.type('\nplaywright edit')
  await expect(page.getByTestId('dirty-count')).toHaveText('1 dirty')

  await page.getByRole('button', { name: /Save/ }).click()
  await expect(page.getByTestId('dirty-count')).toHaveText('0 dirty')
  await expect(page.getByText('saved README.md')).toBeVisible()
})

test('the IDE workspace switches editor themes without losing the draft', async ({ page }) => {
  await page.goto('/demos/scenarios/ide-workspace')

  await page.locator('.cm-content').click()
  await page.keyboard.type('\n// keep this draft')
  await expect(page.getByTestId('dirty-count')).toHaveText('1 dirty')

  await page.getByTestId('editor-theme').selectOption('dracula')
  await expect(page.locator('.cm-editor')).toHaveCSS('background-color', 'rgb(40, 42, 54)')
  await expect(page.getByTestId('dirty-count')).toHaveText('1 dirty')
  await expect(page.locator('.cm-content')).toContainText('keep this draft')
})

test('the dashboard renders the fund-flow Sankey', async ({ page }) => {
  await page.goto('/demos/scenarios/dashboard-builder')

  const sankey = page.locator('[data-renderer=sankey]')
  await expect(sankey).toBeVisible()
  await expect(sankey.locator('path')).toHaveCount(11)
  await expect(sankey).toContainText('Salary')
})

test('a kanban card moves across columns from the keyboard', async ({ page }) => {
  await page.goto('/demos/scenarios/kanban-board')
  await page.evaluate(() => localStorage.removeItem('frontend-lab:kanban'))
  await page.reload()

  const move = page.getByRole('button', { name: 'Move Design tokens to Doing' })
  await move.focus()
  await page.keyboard.press('Enter')

  await expect(page.locator('[data-column=doing] [data-card=card-tokens]')).toBeVisible()
  await expect(page.getByText('moved Design tokens to doing')).toBeVisible()
})

test('the dashboard switches a chart renderer and loads it lazily', async ({ page }) => {
  await page.goto('/demos/scenarios/dashboard-builder')
  await page.evaluate(() => localStorage.removeItem('frontend-lab:dashboard:v2'))
  await page.reload()

  await page.getByRole('button', { name: 'Edit layout' }).click()
  await page.getByRole('combobox', { name: 'Renderer for Weekly traffic' }).selectOption('recharts')

  await expect(page.locator('[data-renderer=recharts]')).toBeVisible()
})

test('the command palette opens with Mod+K and navigates', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press(`${modifier}+k`)

  const dialog = page.getByRole('dialog', { name: 'Command palette' })
  await expect(dialog).toBeVisible()

  const input = dialog.getByRole('combobox')
  await expect(input).toBeFocused()
  await input.fill('command palette')
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL(/\/scenarios\/command-palette$/)
})

test('closing the palette returns focus to its trigger', async ({ page }) => {
  await page.goto('/demos/scenarios/command-palette')

  const trigger = page.locator('#palette-trigger')
  await trigger.focus()
  await trigger.click()

  const dialog = page.getByRole('dialog', { name: 'Demo command palette' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('combobox')).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('an unknown route renders the 404 view', async ({ page }) => {
  await page.goto('/foundations/does-not-exist')

  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
})
