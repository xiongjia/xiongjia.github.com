import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import tseslint from "typescript-eslint";

/**
 * Flat config. Deliberately not type-aware (`projectService`): the prototype
 * gains little from it and `nest build` already fails on real type errors.
 * Prettier owns formatting — `eslint-config-prettier` turns off overlapping rules.
 *
 * Note: `@typescript-eslint/consistent-type-imports` is intentionally absent.
 * NestJS resolves DI from runtime metadata, and turning an injected provider
 * (ConfigService, BrowserService, ...) into `import type` erases the reference,
 * which breaks `design:paramtypes` at boot.
 */
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "data/**",
      ".cache/**",
      "coverage/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Node scripts: plain ESM with process/console available.
    files: ["scripts/**/*.mjs"],
    languageOptions: {
      globals: {
        process: "readonly",
        console: "readonly",
        fetch: "readonly",
        AbortSignal: "readonly",
        setTimeout: "readonly",
      },
    },
  },
  {
    files: ["**/*.ts"],
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "no-console": "error",
    },
  },
  prettier,
);
