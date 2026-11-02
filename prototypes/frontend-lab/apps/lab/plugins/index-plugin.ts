import type { Plugin, ViteDevServer } from 'vite'

export type GeneratedIndex = {
  /** Human label for the dev log, e.g. `content index`. */
  label: string
  /** How many items the regenerated module contains. */
  count: number
}

export type IndexPluginOptions = {
  /** Vite plugin name, e.g. `frontend-lab:demo-registry`. */
  name: string
  /** Folder to watch; may live outside the Vite root, so it is added to the watcher explicitly. */
  watchDir: string
  /** Only files that matter to this index should trigger a rebuild. */
  isRelevant: (file: string) => boolean
  /** Scan the source folders and (re)write the generated module. */
  generate: () => Promise<GeneratedIndex>
}

/**
 * Boilerplate shared by the generated-index plugins: run once before dev/build, then again on every
 * add / change / unlink in the source folder, and reload the page so the app picks up the new module.
 */
export function createIndexPlugin({
  name,
  watchDir,
  isRelevant,
  generate,
}: IndexPluginOptions): Plugin {
  const run = async (server?: ViteDevServer) => {
    const { label, count } = await generate()
    server?.config.logger.info(`${label}: ${count} item(s)`)
    server?.ws.send({ type: 'full-reload' })
    return { label, count }
  }

  return {
    name,

    async buildStart() {
      const { label, count } = await generate()
      this.info(`${label}: ${count} item(s)`)
    },

    configureServer(server) {
      server.watcher.add(watchDir)

      const onChange = (file: string) => {
        if (!isRelevant(file)) return
        run(server).catch((error: unknown) => {
          server.config.logger.error(`${name} failed: ${String(error)}`)
        })
      }

      server.watcher.on('add', onChange)
      server.watcher.on('change', onChange)
      server.watcher.on('unlink', onChange)
    },
  }
}
