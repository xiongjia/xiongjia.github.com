import { FlowError } from "./errors";

/** What `{{...}}` can resolve to while a flow runs. */
export interface TemplateScope {
  /** Validated flow input (`{{input.url}}`). */
  input: Record<string, unknown>;
  /** Variables captured so far (`{{vars.href}}`). */
  vars: Record<string, unknown>;
  /** Base URL of this host (`{{self}}/api/v1/demo`). */
  self: string;
}

const REF = /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g;

/** `{{input.url}}` → `{{self}}/api/v1/demo` → the URL: two passes is normal. */
const MAX_PASSES = 5;

/**
 * Substitute `{{input.x}}` / `{{self}}` in a string field.
 *
 * Repeated until nothing changes, so a default may itself be a template (the demo
 * flow's `input.url` default is `{{self}}/api/v1/demo`). Strict on unknown
 * references on purpose: failing here names the flow bug, instead of sending the
 * literal `{{inpt.x}}` to the browser and failing as "selector not found" three
 * steps later.
 */
export function interpolate(text: string, scope: TemplateScope): string {
  let current = text;
  for (let pass = 0; pass < MAX_PASSES; pass += 1) {
    const next = current.replace(REF, (_match, ref: string) => {
      const value = resolve(ref, scope);
      if (typeof value === "string") {
        return value;
      }
      if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
      }
      throw new FlowError(
        "bad-template",
        `{{${ref}}} did not resolve to a scalar value`,
      );
    });
    if (next === current) {
      return current;
    }
    current = next;
  }
  throw new FlowError(
    "bad-template",
    `"${text}" did not settle after ${MAX_PASSES} passes — templates refer to each other`,
  );
}

function resolve(ref: string, scope: TemplateScope): unknown {
  if (ref === "self") {
    return scope.self;
  }
  for (const bag of ["input", "vars"] as const) {
    if (ref.startsWith(`${bag}.`)) {
      const key = ref.slice(bag.length + 1);
      if (Object.hasOwn(scope[bag], key)) {
        return scope[bag][key];
      }
    }
  }
  throw new FlowError(
    "bad-template",
    `{{${ref}}} is not defined (available: self, input.<name>, vars.<name>)`,
  );
}
