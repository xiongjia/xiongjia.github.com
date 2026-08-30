import swc from "unplugin-swc";
import { defineConfig } from "vitest/config";

/**
 * Vitest config for NestJS-style unit tests (Test.createTestingModule).
 *
 * The default esbuild transform does NOT support `emitDecoratorMetadata`,
 * which NestJS DI needs to resolve constructor parameters (design:paramtypes).
 * unplugin-swc transforms with @swc/core instead, with decorators enabled.
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
  },
});
