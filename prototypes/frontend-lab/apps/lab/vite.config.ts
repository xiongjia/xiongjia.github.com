import { fileURLToPath } from 'node:url'

import mdx from '@mdx-js/rollup'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import remarkFrontmatter from 'remark-frontmatter'
import remarkGfm from 'remark-gfm'
import { defineConfig } from 'vite'

import { contentIndexPlugin } from './plugins/content-index.ts'
import { demoRegistryPlugin } from './plugins/demo-registry.ts'

export default defineConfig({
  plugins: [
    // Regenerate `src/generated/*` on start/build and on every content or demo edit.
    contentIndexPlugin(),
    demoRegistryPlugin(),
    // MDX: frontmatter is stripped from the output (the generator reads it separately), GFM adds
    // tables, task lists and friends.
    mdx({ remarkPlugins: [remarkFrontmatter, remarkGfm] }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@frontend-lab/ui': fileURLToPath(new URL('../../packages/ui/src/index.ts', import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
})
