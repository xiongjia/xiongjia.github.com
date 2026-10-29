import { readFile } from "node:fs/promises";
import { join } from "node:path";
import prettier from "prettier";
import { describe, expect, it } from "vitest";
import { FlowError } from "./errors";
import { parseJsonc } from "./jsonc";
import {
  FLOW_API_VERSION,
  coerceInput,
  flowJsonSchema,
  parseFlow,
  type FlowFile,
} from "./schema";
import { interpolate } from "./template";

const FLOW_PATH = join(process.cwd(), "flows", "demo-visit.jsonc");

async function readDemoFlow(): Promise<unknown> {
  // Flow files are JSONC — comments are part of how they explain themselves.
  return parseJsonc(await readFile(FLOW_PATH, "utf8"), FLOW_PATH);
}

function minimal(overrides: Record<string, unknown> = {}): unknown {
  return {
    name: "demo",
    apiVersion: FLOW_API_VERSION,
    steps: [{ action: "goto", url: "https://example.test/" }],
    ...overrides,
  };
}

function flow(overrides: Record<string, unknown> = {}): FlowFile {
  return parseFlow(minimal(overrides));
}

describe("parseFlow", () => {
  it("accepts the flow shipped with the prototype", async () => {
    const parsed = parseFlow(await readDemoFlow(), FLOW_PATH);
    expect(parsed.name).toBe("demo-visit");
    expect(parsed.steps).toHaveLength(6);
    expect(parsed.steps[3]).toMatchObject({
      action: "include",
      flow: "demo-read-page",
    });
    expect(parsed.output).toMatchObject({ heading: "heading" });
  });

  it("keeps the shipped flow's explanatory comments", async () => {
    expect(await readFile(FLOW_PATH, "utf8")).toMatch(/\n\s*\/\/ /);
  });

  it("rejects an unknown action", () => {
    expect(() =>
      parseFlow(minimal({ steps: [{ action: "teleport" }] })),
    ).toThrow(/not a valid flow/);
  });

  it("rejects a name that would not be a file name", () => {
    expect(() => parseFlow(minimal({ name: "Demo Visit" }))).toThrow(
      /use lower-case kebab\/dot names/,
    );
  });

  it("rejects a flow written for another DSL version", () => {
    expect(() =>
      parseFlow(minimal({ apiVersion: FLOW_API_VERSION + 1 })),
    ).toThrow(/needs apiVersion 2, this host executes 1/);
  });

  it("requires nested steps inside if", () => {
    expect(() =>
      parseFlow(
        minimal({ steps: [{ action: "if", selector: "#a", then: [] }] }),
      ),
    ).toThrow(/then/);
  });

  it("accepts an include step and rejects a bad fragment name", () => {
    expect(
      parseFlow(
        minimal({ steps: [{ action: "include", flow: "demo-read-page" }] }),
      ).steps[0],
    ).toEqual({ action: "include", flow: "demo-read-page" });
    expect(() =>
      parseFlow(
        minimal({ steps: [{ action: "include", flow: "../etc/passwd" }] }),
      ),
    ).toThrow(/lower-case kebab/);
  });

  it("keeps fragments free of input and output", () => {
    expect(parseFlow(minimal({ kind: "fragment" })).kind).toBe("fragment");
    expect(() =>
      parseFlow(
        minimal({
          kind: "fragment",
          output: { heading: "heading" },
          steps: [{ action: "text", selector: "#a", as: "heading" }],
        }),
      ),
    ).toThrow(/fragment may not declare input or output/);
  });

  it("rejects a mistyped field instead of dropping it", () => {
    expect(() =>
      parseFlow(
        minimal({
          steps: [{ action: "click", selector: "#a", slector: "#b" }],
        }),
      ),
    ).toThrow(/Unrecognized key/);
    expect(() => parseFlow(minimal({ stepz: [] }))).toThrow(/Unrecognized key/);
  });

  it("rejects an empty selector list", () => {
    expect(() =>
      parseFlow(minimal({ steps: [{ action: "click", selector: [] }] })),
    ).toThrow(/not a valid flow/);
  });
});

describe("coerceInput", () => {
  const typed = flow({
    input: {
      url: { type: "string", default: "https://example.test/" },
      limit: { type: "number", default: 10 },
      dryRun: { type: "boolean", default: false },
      required: { type: "string", required: true },
    },
    steps: [
      { action: "goto", url: "{{input.url}}" },
      { action: "click", selector: "#a", timeout: 1 },
    ],
  });

  it("fills defaults and accepts caller values", () => {
    const result = coerceInput(typed, { required: "x", limit: 5 });
    expect(result).toEqual({
      ok: true,
      value: {
        url: "https://example.test/",
        limit: 5,
        dryRun: false,
        required: "x",
      },
    });
  });

  it("coerces query-string style values", () => {
    const result = coerceInput(typed, {
      required: "x",
      limit: "7",
      dryRun: "true",
    });
    expect(result).toMatchObject({ ok: true });
    if (result.ok) {
      expect(result.value.limit).toBe(7);
      expect(result.value.dryRun).toBe(true);
    }
  });

  it("reports unknown, missing and mistyped inputs in one pass", () => {
    const result = coerceInput(typed, { typo: 1, limit: "many" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain(
        "input.typo is not declared by this flow",
      );
      expect(result.errors).toContain("input.required is required");
      expect(result.errors).toContain("input.limit must be a number");
    }
  });

  it("treats an empty string as absent so a default applies", () => {
    const result = coerceInput(typed, { required: "x", url: "" });
    expect(result).toMatchObject({ ok: true });
    if (result.ok) {
      expect(result.value.url).toBe("https://example.test/");
    }
  });
});

describe("flowJsonSchema", () => {
  it("keeps flows/flow.schema.json in sync with the DSL", async () => {
    const onDisk = await readFile(
      join(process.cwd(), "flows", "flow.schema.json"),
      "utf8",
    );
    // Generated artifact, committed so a fresh clone gets editor support. Stale
    // file = the DSL changed without `pnpm flow:schema`.
    const expected = await prettier.format(JSON.stringify(flowJsonSchema()), {
      parser: "json",
    });
    expect(onDisk).toBe(expected);
  });

  it("describes every action and field for the editor", () => {
    // These sentences are the DSL's documentation: an undescribed field shows up
    // as a bare name in the editor's hover instead of an explanation.
    type Described = { description?: string; $ref?: string; const?: string };
    type Variant = { properties: Record<string, Described> };
    const schema = flowJsonSchema() as unknown as {
      properties: { steps: { items: { $ref: string } } };
      $defs: Record<string, { $ref?: string; anyOf?: Variant[] }>;
    };
    const nameOf = (ref: string) => ref.replace("#/$defs/", "");
    const steps = schema.$defs[nameOf(schema.properties.steps.items.$ref)];
    const union = steps.$ref ? schema.$defs[nameOf(steps.$ref)] : steps;
    const variants = union.anyOf ?? [];

    expect(variants).toHaveLength(13);
    for (const variant of variants) {
      const action = variant.properties.action;
      expect(
        action.description,
        `${action.const} has no description`,
      ).toBeTruthy();
      for (const [field, spec] of Object.entries(variant.properties)) {
        // A `$ref` points at a named `$defs` entry that carries the sentence.
        expect(
          spec.description ?? spec.$ref,
          `${action.const}.${field} is undocumented`,
        ).toBeTruthy();
      }
    }
  });

  it("describes the same DSL the host validates", () => {
    const schema = flowJsonSchema();
    expect(schema.$schema).toBe("https://json-schema.org/draft/2020-12/schema");
    expect(schema.title).toBe("web-harvester flow");
    expect(JSON.stringify(schema)).toContain('"const":"extract"');
  });
});

describe("interpolate", () => {
  const scope = {
    input: { url: "https://example.test/", slow: true },
    vars: { href: "/user/profile/abc" },
    self: "http://127.0.0.1:8765",
  };

  it("substitutes input values and the host URL", () => {
    expect(interpolate("{{input.url}}?fast={{input.slow}}", scope)).toBe(
      "https://example.test/?fast=true",
    );
    expect(interpolate("{{self}}/api/v1/demo", scope)).toBe(
      "http://127.0.0.1:8765/api/v1/demo",
    );
  });

  it("resolves a default that is itself a template", () => {
    expect(
      interpolate("{{input.selfRef}}", {
        input: { selfRef: "{{self}}/api/v1/demo" },
        vars: {},
        self: "http://h:1",
      }),
    ).toBe("http://h:1/api/v1/demo");
  });

  it("reads captured variables too", () => {
    expect(interpolate("{{vars.href}}", scope)).toBe("/user/profile/abc");
  });

  it("leaves plain strings alone", () => {
    expect(interpolate("#bump", scope)).toBe("#bump");
  });

  it("fails on an unknown reference instead of sending it to the page", () => {
    expect(() => interpolate("{{input.urll}}", scope)).toThrow(FlowError);
    expect(() => interpolate("{{vars.x}}", scope)).toThrow(/is not defined/);
  });
});

describe("FlowError", () => {
  it("carries a machine-readable code", () => {
    const error = new FlowError("blocked", "risk control");
    expect(error.code).toBe("blocked");
    expect(error.name).toBe("FlowError");
  });
});
