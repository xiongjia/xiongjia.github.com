import swc from "unplugin-swc";
import { defineConfig } from "vitest/config";

/**
 * E2E config: same swc transform as unit tests, but includes only
 * test/**\/*.e2e-spec.ts and uses longer timeouts (jobs are polled until done).
 * Requires a running Postgres: `pnpm db:start`, then `pnpm test:e2e`.
 */
export default defineConfig({
  plugins: [
    swc.vite({
      module: { type: "es6" },
      jsc: {
        target: "es2023",
        parser: { syntax: "typescript", decorators: true },
        transform: { legacyDecorator: true, decoratorMetadata: true },
      },
    }),
  ],
  test: {
    include: ["test/**/*.e2e-spec.ts"],
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
