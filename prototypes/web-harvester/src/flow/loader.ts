import { Injectable } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { parseJsonc } from "./jsonc";
import { type FlowFile, type FlowStep, parseFlow } from "./schema";

/** Generated for editors; not a flow. */
const SCHEMA_FILE = "flow.schema.json";

/**
 * Flow files are `.jsonc` — comments are how a flow explains itself, and VS Code
 * rejects `//` in a file it thinks is plain JSON. `.json` stays accepted so a
 * hand-written flow without comments still loads; `.jsonc` wins on a name clash.
 */
const FLOW_EXTENSIONS = [".jsonc", ".json"] as const;

/** Reserved by the DSL: flow names become URLs and file names. */
const NAME_PATTERN = /^[a-z0-9][a-z0-9._-]*$/;

/** One row of `GET /api/v1/flows`: what a file is and what it pulls in. */
export type FlowSummary =
  | {
      name: string;
      kind: "flow" | "fragment";
      description?: string;
      /** Fragments this flow includes, in step order (repeats kept). */
      includes: string[];
    }
  | { name: string; error: string };

/**
 * Finds and validates flow files.
 *
 * Two directories, override first: `flows/` ships with the host (compiled-in
 * defaults, versioned with the code), `HARVEST_FLOWS_DIR` is writable and wins on
 * a name clash — that is how a scraping script is swapped without a rebuild.
 */
@Injectable()
export class FlowLoader {
  /** Parsed flows, keyed by name, with the mtime they were read at. */
  private readonly cache = new Map<
    string,
    { flow: FlowFile; mtimeMs: number }
  >();

  constructor(private readonly config: ConfigService) {}

  /** Flow files that ship with the host. */
  get builtinDir(): string {
    return join(process.cwd(), "flows");
  }

  /** Writable directory that may override a built-in flow of the same name. */
  get overrideDir(): string {
    return this.config.get<string>("HARVEST_FLOWS_DIR") ?? ".cache/flows";
  }

  /** Flow names, override shadowing built-in, sorted. */
  async list(): Promise<string[]> {
    const names = new Set<string>();
    for (const dir of [this.builtinDir, this.overrideDir]) {
      for (const entry of await readNames(dir)) {
        names.add(entry);
      }
    }
    return [...names].sort();
  }

  /**
   * Every flow with its role and its include edges.
   *
   * Flow names alone do not say how the files relate; this is the answer to
   * "which flow uses which file", without grepping the JSON.
   */
  async catalogue(): Promise<FlowSummary[]> {
    const names = await this.list();
    return Promise.all(
      names.map(async (name): Promise<FlowSummary> => {
        try {
          const flow = await this.load(name);
          return {
            name,
            kind: flow.kind ?? "flow",
            description: flow.description,
            includes: includes(flow.steps),
          };
        } catch (error) {
          return {
            name,
            error: error instanceof Error ? error.message : String(error),
          };
        }
      }),
    );
  }

  /** Load one flow by name; parsed, validated, API-version checked. */
  async load(name: string): Promise<FlowFile> {
    if (!NAME_PATTERN.test(name)) {
      throw new Error(
        `"${name}" is not a flow name (lower-case kebab-case only, e.g. demo-visit)`,
      );
    }

    for (const dir of [this.overrideDir, this.builtinDir]) {
      for (const extension of FLOW_EXTENSIONS) {
        const path = join(dir, `${name}${extension}`);
        const mtimeMs = await stat(path)
          .then((info) => info.mtimeMs)
          .catch(() => null);
        if (mtimeMs === null) {
          continue;
        }
        const cached = this.cache.get(name);
        if (cached && cached.mtimeMs === mtimeMs && cached.flow.name === name) {
          return cached.flow;
        }

        const raw = await readFile(path, "utf8");
        const flow = parseFlow(parseJsonc(raw, path), path);
        if (flow.name !== name) {
          throw new Error(
            `${path} declares name "${flow.name}", expected "${name}"`,
          );
        }
        // Re-read only when the file changed: editing a flow under
        // `HARVEST_FLOWS_DIR` takes effect without restarting the host.
        this.cache.set(name, { flow, mtimeMs });
        return flow;
      }
    }

    const available = await this.list();
    throw new Error(
      `unknown flow "${name}" (available: ${available.join(", ") || "none"})`,
    );
  }
}

/** Include edges, looking inside `if` branches too. */
function includes(steps: FlowStep[]): string[] {
  const found: string[] = [];
  for (const step of steps) {
    if (step.action === "include") {
      found.push(step.flow);
    }
    if (step.action === "if") {
      found.push(...includes(step.then ?? []), ...includes(step.else ?? []));
    }
  }
  return found;
}

async function readNames(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
  const names = new Set<string>();
  for (const extension of FLOW_EXTENSIONS) {
    for (const entry of entries) {
      if (
        entry.isFile() &&
        entry.name.endsWith(extension) &&
        entry.name !== SCHEMA_FILE
      ) {
        names.add(entry.name.slice(0, -extension.length));
      }
    }
  }
  return [...names];
}
