/**
 * Regenerate `flows/flow.schema.json` from `src/flow/schema.ts`.
 *
 * The schema is what gives editors validation + hover (via `"$schema"` in a flow
 * file), and it carries the same `.describe()` sentences the host documents
 * itself with. It is generated, never hand-edited; `src/flow/schema.spec.ts`
 * fails when it is stale.
 *
 * Requires `dist/` — `pnpm flow:schema` builds first.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { flowJsonSchema } = require("../dist/flow/schema.js");
const prettier = require("prettier");

const schema = flowJsonSchema();
const dir = join(process.cwd(), "flows");
await mkdir(dir, { recursive: true });

// Formatted with Prettier, not `JSON.stringify`: the file is checked in, so
// `pnpm format:check` has to agree with it byte for byte.
const text = await prettier.format(JSON.stringify(schema), { parser: "json" });
await writeFile(join(dir, "flow.schema.json"), text, "utf8");

console.log(
  `wrote flows/flow.schema.json (${text.split("\n").length - 1} lines, ${text.length} bytes)`,
);
