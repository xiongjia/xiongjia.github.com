import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/*
 * Boundary lint zones.
 *
 * The lab has three layers with one dependency direction each:
 *
 *   packages/ui  <-  apps/lab/src (app shell)  <-  apps/lab/demos
 *         ^                    ^
 *         └── apps/lab/plugins (build-time only; shares nothing at runtime)
 *
 * `no-restricted-imports` is what keeps that direction honest. A demo that imports the app shell
 * cannot be copy-pasted out of the lab; an app that reaches into `packages/ui/src/...` bypasses the
 * package entry point and its `exports` map. Both fail here, before a reviewer has to notice.
 */

/** Turn a list of `{ group, message }` entries into a flat `no-restricted-imports` config. */
const restrictImports = (patterns) => ['error', { patterns }]

export default tseslint.config(
  {
    ignores: [
      '**/dist/**',
      '**/node_modules/**',
      '**/coverage/**',
      '**/src/generated/**',
      '**/*.d.ts',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },

  // App shell: go through the package entry point, never through the registry's targets.
  {
    files: ['apps/lab/src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': restrictImports([
        {
          group: ['**/packages/ui/src/**'],
          message: "Import shared UI through '@frontend-lab/ui', not its source files.",
        },
        {
          group: ['**/demos/**'],
          message: 'Demos are reached through the generated registry, never imported directly.',
        },
      ]),
    },
  },

  // Demos: self-contained — React, the UI package, and files in the same folder.
  {
    files: ['apps/lab/demos/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': restrictImports([
        {
          group: ['@/app', '@/app/**', '@/components', '@/components/**'],
          message: 'A demo must not depend on the app shell; keep it self-contained.',
        },
        {
          group: ['@/generated', '@/generated/**'],
          message: 'A demo must not depend on the generated indexes.',
        },
        {
          group: ['../**'],
          message: 'A demo may only import from React, @frontend-lab/ui and its own folder.',
        },
      ]),
    },
  },

  // Shared package: no knowledge of the app that consumes it.
  {
    files: ['packages/ui/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': restrictImports([
        {
          group: ['@frontend-lab/lab*', '**/apps/**', '@/**'],
          message: 'packages/ui must not depend on the app or the lab alias.',
        },
      ]),
    },
  },

  // Build-time plugins: node only, no app runtime.
  {
    files: ['apps/lab/plugins/**/*.ts', '**/*.config.{ts,mjs,js}'],
    languageOptions: { globals: { ...globals.node } },
    rules: {
      'no-restricted-imports': restrictImports([
        {
          group: ['@/**', '../src/**', '../../packages/ui/src/**'],
          message: 'Build scripts must not import the app runtime or shared UI source.',
        },
      ]),
    },
  },
)
