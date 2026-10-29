import type { ConfigService } from "@nestjs/config";
import { mkdir, mkdtemp, rm, utimes, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { FlowLoader } from "./loader";

function makeConfig(flowsDir: string): ConfigService {
  return {
    get: (key: string) => (key === "HARVEST_FLOWS_DIR" ? flowsDir : undefined),
  } as unknown as ConfigService;
}

/** A minimal valid flow, in JSONC with a comment and a trailing comma. */
function flowFile(name: string, description: string): string {
  return `{
  // written by the test
  "name": "${name}",
  "apiVersion": 1,
  "description": "${description}",
  "steps": [{ "action": "goto", "url": "https://example.test/" }],
}`;
}

describe("FlowLoader", () => {
  let dir: string;
  let loader: FlowLoader;

  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "harvester-flows-"));
    loader = new FlowLoader(makeConfig(dir));
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  async function write(name: string, description: string) {
    await writeFile(join(dir, name), flowFile(name.split(".")[0], description));
  }

  it("loads the shipped flows, comments and all", async () => {
    const flow = await loader.load("demo-visit");

    expect(flow.name).toBe("demo-visit");
    expect(flow.steps.some((step) => step.action === "include")).toBe(true);
  });

  it("lists names without extensions and never the generated schema", async () => {
    const names = await loader.list();
    expect(names).toEqual(
      expect.arrayContaining(["demo-read-page", "demo-visit"]),
    );
    expect(names).not.toContain("flow.schema");
  });

  it("accepts .json as well, and prefers .jsonc on a name clash", async () => {
    await write("plain.json", "from json");
    expect((await loader.load("plain")).description).toBe("from json");

    await write("clash.json", "from json");
    await write("clash.jsonc", "from jsonc");
    expect((await loader.load("clash")).description).toBe("from jsonc");
    expect(await loader.list()).toContain("clash");
  });

  it("shadows a built-in flow with a file of the same name", async () => {
    await write("demo-visit.jsonc", "local override");
    expect((await loader.load("demo-visit")).description).toBe(
      "local override",
    );
  });

  it("re-reads a flow that changed on disk", async () => {
    await write("live.jsonc", "first version");
    expect((await loader.load("live")).description).toBe("first version");

    // mtime resolution can be coarse: bump it explicitly.
    const path = join(dir, "live.jsonc");
    await writeFile(path, flowFile("live", "second version"));
    const later = new Date(Date.now() + 5_000);
    await utimes(path, later, later);

    expect((await loader.load("live")).description).toBe("second version");
  });

  it("refuses a name that is not a file name", async () => {
    await expect(loader.load("../etc/passwd")).rejects.toThrow(
      /not a flow name/,
    );
  });

  it("names the available flows when one is unknown", async () => {
    await expect(loader.load("nope")).rejects.toThrow(
      /unknown flow "nope" \(available: demo-read-page, demo-visit/,
    );
  });

  it("rejects a file whose name does not match its id", async () => {
    await writeFile(
      join(dir, "misnamed.jsonc"),
      flowFile("other-name", "mismatch"),
    );
    await expect(loader.load("misnamed")).rejects.toThrow(
      /declares name "other-name", expected "misnamed"/,
    );
  });

  it("skips a directory that does not exist", async () => {
    const missing = new FlowLoader(makeConfig(join(dir, "nope")));
    await mkdir(join(dir, "nope"), { recursive: true });

    expect(await missing.list()).toEqual(
      expect.arrayContaining(["demo-read-page", "demo-visit"]),
    );
  });

  it("catalogues the include graph", async () => {
    const catalogue = await loader.catalogue();

    const byName = new Map(catalogue.map((entry) => [entry.name, entry]));
    expect(byName.get("demo-read-page")).toMatchObject({
      kind: "fragment",
      includes: [],
    });
    expect(byName.get("demo-visit")).toMatchObject({
      kind: "flow",
      includes: ["demo-read-page"],
    });
    expect(byName.get("xhs-following")).toMatchObject({ kind: "flow" });
  });

  it("reports a broken flow in the catalogue instead of failing the listing", async () => {
    await writeFile(join(dir, "broken.jsonc"), '{ "name": "broken" }');

    const broken = (await loader.catalogue()).find(
      (flow) => flow.name === "broken",
    );
    expect(broken).toMatchObject({ name: "broken" });
    expect("error" in (broken ?? {})).toBe(true);
  });
});
