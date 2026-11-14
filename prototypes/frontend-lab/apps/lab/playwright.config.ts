import { defineConfig, devices } from '@playwright/test'

/*
 * The B17 verification layer.
 *
 * Two decisions keep it practical:
 *
 *   - `channel: 'chrome'` uses the Chrome that is already installed instead of downloading a
 *     Playwright browser. The suite then works on the same engine the lab is developed against, and
 *     `pnpm install` stays the only setup step.
 *   - the suite runs against `vite preview` of a real build, not the dev server, so a broken
 *     production chunk fails here rather than on the next deploy.
 *
 * `reuseExistingServer` means a preview server you left running is reused; the bundle report is what
 * guards chunk sizes, the tests are what guard behaviour.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 6_000 },
  // Each test gets a fresh browser context, but they all share one preview server.
  fullyParallel: false,
  workers: 2,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
  webServer: {
    command: 'pnpm preview --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
