import swc from "unplugin-swc";
import { defineConfig } from "vitest/config";

/**
 * NestJS unit tests need `emitDecoratorMetadata` (DI resolves constructor
 * params through `design:paramtypes`), which Vitest's default esbuild
 * transform does not emit — hence the SWC plugin.
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
    include: ["src/**/*.spec.ts"],
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
    clearMocks: true,
  },
});
