import { z } from "zod";

/**
 * The Flow DSL, as one zod schema.
 *
 * Single source of truth: the same definition validates a flow at load time and
 * generates `flows/flow.schema.json`, which is what the editor uses for validation
 * and hover. Every `.describe()` below is therefore documentation, not decoration
 * — keep each one a single short sentence.
 */

/** DSL version this host executes. A flow requiring another one is refused. */
export const FLOW_API_VERSION = 1;

/** One selector, or candidates tried in order (first hit wins). */
const selectorSpec = z
  .union([z.string().min(1), z.array(z.string().min(1)).min(1)])
  .describe(
    "A selector, or a list of candidates tried in order (first hit wins).",
  )
  // Named `$defs` entry: `"$ref": "#/$defs/selector"` instead of `__schema7`.
  .meta({ id: "selector" });
export type SelectorSpec = z.infer<typeof selectorSpec>;

const timeoutSpec = z
  .number()
  .int()
  .positive()
  .max(120_000)
  .describe("Milliseconds to wait for this step before failing (default 5000).")
  .meta({ id: "timeout" });

/** Flow names are file names and URL segments — nothing else. */
const flowNameSpec = z
  .string()
  .min(1)
  .max(64)
  .regex(/^[a-z0-9][a-z0-9._-]*$/, "use lower-case kebab/dot names")
  .describe("Flow id: lower-case kebab-case, also the file name.")
  .meta({ id: "flowName" });
export type FlowName = z.infer<typeof flowNameSpec>;

/** One column of an `extract`: an element's text, or one of its attributes. */
const extractField = z
  .union([
    selectorSpec,
    z
      .object({
        selector: selectorSpec,
        attr: z
          .string()
          .min(1)
          .describe(
            "Attribute to read instead of the text (e.g. `src`, `href`).",
          ),
      })
      .strict(),
  ])
  .describe("Text of the row's element, or one of its attributes.");
type ExtractField = z.infer<typeof extractField>;

/** A flow input: typed, optionally defaulted, described for the IDE. */
const paramSpec = z
  .object({
    type: z
      .enum(["string", "number", "boolean"])
      .describe("Value type; the caller's JSON is coerced to it."),
    default: z
      .union([z.string(), z.number(), z.boolean()])
      .optional()
      .describe("Used when the caller omits this input; may be a template."),
    required: z
      .boolean()
      .optional()
      .describe(
        "Fail the run when the caller omits it and there is no default.",
      ),
    description: z
      .string()
      .max(200)
      .optional()
      .describe("Shown here and in the editor."),
  })
  .strict()
  .meta({ id: "inputParam" });
type ParamSpec = z.infer<typeof paramSpec>;

/** Fields every step may carry. */
export interface StepDesc {
  /** One human sentence: it lands in logs and `meta.steps`. */
  desc?: string;
  /** Run the step again on failure: `{ attempts, delayMs }` (default 1 attempt). */
  retry?: { attempts: number; delayMs?: number };
  /**
   * Skip the step unless this template is truthy (`""`/`0`/`false` are falsy).
   * A leading `!` negates it, so `"!{{input.profileId}}"` means "only when unset".
   */
  when?: string;
}

/**
 * One step of a flow.
 *
 * Declared as a TypeScript union (instead of being inferred) because `if` nests
 * steps and the schema therefore has to reference itself.
 */
export type FlowStep = StepDesc &
  (
    | { action: "goto"; url: string }
    | {
        action: "wait";
        selector?: SelectorSpec;
        ms?: number;
        state?: "visible" | "attached";
        timeout?: number;
      }
    | {
        action: "click";
        selector: SelectorSpec;
        timeout?: number;
        optional?: boolean;
      }
    | {
        action: "fill";
        selector: SelectorSpec;
        value: string;
        timeout?: number;
      }
    | { action: "press"; selector?: SelectorSpec; key: string }
    | { action: "text"; selector: SelectorSpec; as: string; optional?: boolean }
    | {
        action: "extract";
        item: SelectorSpec;
        fields: Record<string, ExtractField>;
        as: string;
        limit?: number;
        uniqueBy?: string[];
      }
    | {
        action: "screenshot";
        selector?: SelectorSpec;
        name?: string;
        fullPage?: boolean;
      }
    | {
        action: "scroll";
        target: SelectorSpec;
        by?: number;
        until?: "end" | "grow";
        settleMs?: number;
        maxRounds?: number;
      }
    | {
        action: "attribute";
        selector: SelectorSpec;
        name: string;
        as: string;
        optional?: boolean;
      }
    | { action: "assertNotBlocked"; patterns: string[] }
    | { action: "include"; flow: FlowName }
    | {
        action: "if";
        selector: SelectorSpec;
        state?: "visible" | "attached";
        then?: FlowStep[];
        else?: FlowStep[];
      }
  );

/** Shared fields. Objects are `.strict()` so a mistyped field is an error. */
const stepBase = {
  desc: z
    .string()
    .min(1)
    .max(200)
    .optional()
    .describe("One human sentence: the step's line in `meta.steps`."),
  retry: z
    .object({
      attempts: z.number().int().min(1).max(10),
      delayMs: z.number().int().min(0).max(60_000).optional(),
    })
    .strict()
    .optional()
    .describe("Retry this step on failure (attempts, delay between them)."),
  when: z
    .string()
    .min(1)
    .max(200)
    .optional()
    .describe(
      "Skip this step unless the template is truthy; a leading `!` negates it.",
    ),
};

const urlSpec = z
  .string()
  .min(1)
  .describe("URL to open; `{{input.x}}` and `{{self}}` are substituted.");

const optionalSpec = z
  .boolean()
  .optional()
  .describe(
    "Skip instead of failing when the selector is absent (the variable becomes an empty string).",
  );

const asSpec = z
  .string()
  .min(1)
  .describe("Variable name the value is stored under, read back by `output`.");

/**
 * `z.lazy` keeps the recursion without a second definition; the annotation is
 * what lets TypeScript accept the self-reference.
 */
const stepSchema: z.ZodType<FlowStep> = z
  .lazy(() =>
    z.union([
      z
        .object({
          ...stepBase,
          action: z.literal("goto").describe("Open a URL."),
          url: urlSpec,
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("wait")
            .describe(
              "Wait for a selector to reach a state, or wait `ms` when no selector is given.",
            ),
          selector: selectorSpec.optional(),
          ms: z
            .number()
            .int()
            .min(0)
            .max(120_000)
            .optional()
            .describe("Milliseconds to wait when no selector is given."),
          state: z
            .enum(["visible", "attached"])
            .optional()
            .describe(
              "What to wait for: drawn on screen, or merely in the DOM.",
            ),
          timeout: timeoutSpec.optional(),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("click")
            .describe("Click the first selector that matches."),
          selector: selectorSpec,
          timeout: timeoutSpec.optional(),
          optional: optionalSpec,
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("fill")
            .describe("Type a value into the first matching field."),
          selector: selectorSpec,
          value: z
            .string()
            .describe("Text to type; `{{input.x}}` is substituted."),
          timeout: timeoutSpec.optional(),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("press")
            .describe("Press a key, optionally on a selector."),
          selector: selectorSpec.optional(),
          key: z
            .string()
            .min(1)
            .describe("Key or chord, e.g. `Enter`, `Control+A`."),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("text")
            .describe("Read an element's text into a variable for `output`."),
          selector: selectorSpec,
          as: asSpec,
          optional: optionalSpec,
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("extract")
            .describe("Collect matching rows into an array of JSON objects."),
          item: selectorSpec.describe(
            "Selector for the rows themselves (the repeated element).",
          ),
          fields: z
            .record(z.string(), extractField)
            .describe(
              "Per-column selectors relative to the row (`:scope` = the row itself), or `{ selector, attr }` to read an attribute.",
            ),
          as: asSpec.describe(
            "Variable name the rows are stored under, read back by `output`.",
          ),
          limit: z
            .number()
            .int()
            .positive()
            .max(2_000)
            .optional()
            .describe("Maximum number of rows to keep (default 200)."),
          uniqueBy: z
            .array(z.string().min(1))
            .min(1)
            .optional()
            .describe(
              "Drop rows repeating the same value of these fields (first wins).",
            ),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("screenshot")
            .describe("Save a PNG under the run's `artifacts/` directory."),
          selector: selectorSpec
            .optional()
            .describe("When given, capture just this element."),
          name: z
            .string()
            .min(1)
            .optional()
            .describe(
              "Artifact name without extension (default `screenshot`).",
            ),
          fullPage: z
            .boolean()
            .optional()
            .describe("Capture the whole page instead of the viewport."),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("scroll")
            .describe(
              "Scroll a container until it stops moving or growing, e.g. before reading a long list.",
            ),
          target: selectorSpec.describe(
            "The scrollable container (not the window): its own scrollTop is moved.",
          ),
          by: z
            .number()
            .int()
            .positive()
            .max(20_000)
            .optional()
            .describe("Pixels per round (default 1000)."),
          until: z
            .enum(["end", "grow"])
            .optional()
            .describe(
              "Stop when the position stops moving (`end`, default) or when the content stops growing (`grow`, for lazy lists).",
            ),
          settleMs: z
            .number()
            .int()
            .min(0)
            .max(10_000)
            .optional()
            .describe("Wait after each round (default 400)."),
          maxRounds: z
            .number()
            .int()
            .positive()
            .max(500)
            .optional()
            .describe("Safety cap on scroll rounds (default 50)."),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("attribute")
            .describe("Read one attribute of an element into a variable."),
          selector: selectorSpec,
          name: z
            .string()
            .min(1)
            .describe("Attribute name, e.g. `href`, `src`, `data-id`."),
          as: asSpec.describe(
            "Variable name the value is stored under, read back by `output` / `{{vars.x}}`.",
          ),
          optional: optionalSpec,
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("assertNotBlocked")
            .describe(
              "Fail the run as `blocked` when the page matches a pattern.",
            ),
          patterns: z
            .array(z.string().min(1))
            .min(1)
            .describe(
              "Regexes (plain text also works) that mean the site blocked us.",
            ),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("include")
            .describe("Insert the steps of another flow file right here."),
          flow: flowNameSpec.describe(
            'Fragment to include (`kind: "fragment"`); it runs on this page and shares these variables.',
          ),
        })
        .strict(),
      z
        .object({
          ...stepBase,
          action: z
            .literal("if")
            .describe(
              "Run `then` when the selector matches (or is visible), otherwise `else`.",
            ),
          selector: selectorSpec,
          state: z
            .enum(["visible", "attached"])
            .optional()
            .describe(
              "Branch on visibility (`visible`, default) or mere presence (`attached`).",
            ),
          then: z
            .array(stepSchema)
            .min(1)
            .optional()
            .describe("Steps to run on a match."),
          else: z
            .array(stepSchema)
            .optional()
            .describe("Steps to run otherwise."),
        })
        .strict(),
    ]),
  )
  .meta({ id: "step" });

/** A whole flow file. */
export const flowSchema = z
  .object({
    $schema: z
      .string()
      .optional()
      .describe("Editor hint, e.g. `./flow.schema.json`; ignored at runtime."),
    name: flowNameSpec.describe("Flow id; must match the file name."),
    version: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Author's own version number (informational)."),
    apiVersion: z
      .number()
      .int()
      .positive()
      .describe("DSL version; must match the host's `FLOW_API_VERSION`."),
    throttle: z
      .object({
        minIntervalMs: z.number().int().min(0).max(600_000),
        scope: z.string().min(1).max(64).optional(),
      })
      .strict()
      .optional()
      .describe(
        "Minimum gap between runs of this flow (`scope` shares the gap with other flows — e.g. every xhs flow on one account). Nothing else is affected.",
      ),
    sync: z
      .boolean()
      .optional()
      .describe(
        "Short flows that may be run synchronously (`POST /flows/:name/run`): the response carries the result instead of a run id.",
      ),
    kind: z
      .enum(["flow", "fragment"])
      .optional()
      .describe(
        "`fragment` = only meant to be included (cannot be run directly, has no input/output); default `flow`.",
      ),
    description: z
      .string()
      .max(500)
      .optional()
      .describe("What this flow does."),
    input: z
      .record(z.string(), paramSpec)
      .optional()
      .describe("Typed inputs, addressable as `{{input.<name>}}`."),
    steps: z
      .array(stepSchema)
      .min(1)
      .max(200)
      .describe(
        "Ordered steps; `use` pulls in another flow file instead of copying its steps.",
      ),
    output: z
      .record(z.string(), z.string().min(1))
      .optional()
      .describe("Result key → variable a step captured with `as`."),
  })
  .strict();
export type FlowFile = z.infer<typeof flowSchema>;

/** Flows are async unless they say otherwise. */
export function isSyncFlow(flow: FlowFile): boolean {
  return flow.sync === true;
}

/** Structural parse + API-version gate. Throws `Error` with a readable list. */
export function parseFlow(raw: unknown, source = "flow"): FlowFile {
  const parsed = flowSchema.safeParse(raw);
  if (!parsed.success) {
    const details = parsed.error.issues
      .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
      .join("; ");
    throw new Error(`${source} is not a valid flow: ${details}`);
  }
  const flow = parsed.data;
  if (flow.kind === "fragment" && (flow.input || flow.output)) {
    throw new Error(
      `${source}: a fragment may not declare input or output — the flow that includes it owns them`,
    );
  }
  for (const step of walkSteps(flow.steps)) {
    if (
      step.action === "if" &&
      step.then === undefined &&
      step.else === undefined
    ) {
      throw new Error(
        `${source}: an \`if\` step needs a \`then\` or an \`else\` branch`,
      );
    }
  }
  if (flow.apiVersion !== FLOW_API_VERSION) {
    throw new Error(
      `${source} needs apiVersion ${flow.apiVersion}, this host executes ${FLOW_API_VERSION} — update the host or the flow`,
    );
  }
  return flow;
}

/** Every step, including the ones nested inside `if` branches. */
export function* walkSteps(steps: FlowStep[]): Generator<FlowStep> {
  for (const step of steps) {
    yield step;
    if (step.action === "if") {
      yield* walkSteps(step.then ?? []);
      yield* walkSteps(step.else ?? []);
    }
  }
}

export type InputResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; errors: string[] };

/**
 * Apply the flow's own `input` block to what the caller sent.
 *
 * Unknown keys are rejected on purpose: a typo in an option name would otherwise
 * silently fall back to the default and look like "the flow ignores my setting".
 */
export function coerceInput(
  flow: FlowFile,
  raw: Record<string, unknown> | undefined,
): InputResult {
  const declared = flow.input ?? {};
  const errors: string[] = [];
  const value: Record<string, unknown> = {};

  for (const key of Object.keys(raw ?? {})) {
    if (!(key in declared)) {
      errors.push(`input.${key} is not declared by this flow`);
    }
  }

  for (const [key, spec] of Object.entries(declared)) {
    const provided = raw?.[key];
    if (provided === undefined || provided === null || provided === "") {
      if (spec.default !== undefined) {
        value[key] = spec.default;
      } else if (spec.required) {
        errors.push(`input.${key} is required`);
      }
      continue;
    }
    const coerced = coerceValue(key, spec, provided);
    if (coerced.ok) {
      value[key] = coerced.value;
    } else {
      errors.push(coerced.error);
    }
  }

  return errors.length > 0 ? { ok: false, errors } : { ok: true, value };
}

function coerceValue(
  key: string,
  spec: ParamSpec,
  provided: unknown,
): { ok: true; value: unknown } | { ok: false; error: string } {
  if (spec.type === "string") {
    if (typeof provided === "string") {
      return { ok: true, value: provided };
    }
    return { ok: false, error: `input.${key} must be a string` };
  }
  if (spec.type === "number") {
    const parsed = typeof provided === "number" ? provided : Number(provided);
    if (Number.isFinite(parsed)) {
      return { ok: true, value: parsed };
    }
    return { ok: false, error: `input.${key} must be a number` };
  }
  if (provided === true || provided === false) {
    return { ok: true, value: provided };
  }
  if (provided === "true" || provided === "1") {
    return { ok: true, value: true };
  }
  if (provided === "false" || provided === "0") {
    return { ok: true, value: false };
  }
  return { ok: false, error: `input.${key} must be a boolean` };
}

/** JSON Schema for editors (`flows/flow.schema.json` via `pnpm flow:schema`). */
export function flowJsonSchema(): Record<string, unknown> {
  const schema = z.toJSONSchema(flowSchema, {
    io: "input",
    target: "draft-2020-12",
    // Share repeated subschemas via `$defs` instead of inlining them: fewer
    // bytes, and one selector change no longer rewrites every step.
    reused: "ref",
  });
  return {
    $id: "https://web-harvester.local/flow.schema.json",
    title: "web-harvester flow",
    ...schema,
  };
}
