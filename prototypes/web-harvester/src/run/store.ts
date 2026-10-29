import { Injectable } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { join } from "node:path";
import { isTerminal, type RunRecord, type RunState } from "./run";

/** Output and artifacts live next to `run.json`; the ids are file names. */
const RUN_FILE = "run.json";
const OUTPUT_FILE = "output.json";
const ARTIFACTS_DIR = "artifacts";
/** Only these characters end up in a path; `..` therefore cannot escape. */
const SAFE_ID = /^[A-Za-z0-9._-]+$/;

export interface RunFilter {
  state?: RunState[];
  profile?: string;
  flow?: string;
  limit?: number;
}

/**
 * The truth about runs on disk.
 *
 * One directory per run (`data/runs/<id>/`), replaced atomically on every state
 * change, plus a small in-memory cache so polling does not re-read the disk.
 * A restart rebuilds the cache from the directories it finds.
 */
@Injectable()
export class RunStore {
  private readonly cache = new Map<string, RunRecord>();

  constructor(private readonly config: ConfigService) {}

  get rootDir(): string {
    return this.config.get<string>("HARVEST_RUNS_DIR") ?? "data/runs";
  }

  /** How many finished runs of each kind are kept before pruning. */
  get keep(): number {
    return this.config.get<number>("HARVEST_RUN_KEEP") ?? 50;
  }

  runDir(id: string): string {
    return join(this.rootDir, assertId(id));
  }

  async create(
    record: Omit<
      RunRecord,
      "createdAt" | "startedAt" | "finishedAt" | "meta" | "error"
    >,
  ): Promise<RunRecord> {
    const full: RunRecord = {
      ...record,
      createdAt: new Date().toISOString(),
      startedAt: null,
      finishedAt: null,
      meta: null,
      error: null,
    };
    await mkdir(this.runDir(full.id), { recursive: true });
    return this.save(full);
  }

  /** Atomic write: a reader never sees a half-written `run.json`. */
  async save(record: RunRecord): Promise<RunRecord> {
    const dir = this.runDir(record.id);
    await mkdir(dir, { recursive: true });
    const path = join(dir, RUN_FILE);
    const tmp = `${path}.tmp`;
    await writeFile(tmp, `${JSON.stringify(record, null, 2)}\n`, "utf8");
    await rename(tmp, path);
    this.cache.set(record.id, record);
    return record;
  }

  async update(id: string, patch: Partial<RunRecord>): Promise<RunRecord> {
    const current = await this.get(id);
    if (!current) {
      throw new Error(`run ${id} does not exist`);
    }
    return this.save({ ...current, ...patch, id: current.id });
  }

  async get(id: string): Promise<RunRecord | null> {
    const cached = this.cache.get(id);
    if (cached) {
      return cached;
    }
    // An id from a URL is untrusted: an unsafe one is simply "no such run".
    let dir: string;
    try {
      dir = this.runDir(id);
    } catch {
      return null;
    }
    const raw = await readFile(join(dir, RUN_FILE), "utf8").catch(() => null);
    if (raw === null) {
      return null;
    }
    try {
      const record = JSON.parse(raw) as RunRecord;
      this.cache.set(record.id, record);
      return record;
    } catch {
      return null;
    }
  }

  /** Newest first; the directory name is the sort key. */
  async list(filter: RunFilter = {}): Promise<RunRecord[]> {
    const entries = await readdir(this.rootDir, { withFileTypes: true }).catch(
      () => [],
    );
    const ids = entries
      .filter((entry) => entry.isDirectory() && SAFE_ID.test(entry.name))
      .map((entry) => entry.name)
      .sort()
      .reverse();

    const runs: RunRecord[] = [];
    for (const id of ids) {
      const record = await this.get(id);
      if (!record) {
        continue;
      }
      if (filter.state && !filter.state.includes(record.state)) {
        continue;
      }
      if (filter.profile && record.profile !== filter.profile) {
        continue;
      }
      if (filter.flow && record.flow !== filter.flow) {
        continue;
      }
      runs.push(record);
      if (runs.length >= (filter.limit ?? 50)) {
        break;
      }
    }
    return runs;
  }

  async writeOutput(
    id: string,
    output: Record<string, unknown>,
  ): Promise<string> {
    const dir = this.runDir(id);
    await mkdir(dir, { recursive: true });
    await writeFile(
      join(dir, OUTPUT_FILE),
      `${JSON.stringify(output, null, 2)}\n`,
      "utf8",
    );
    return OUTPUT_FILE;
  }

  /**
   * Absolute path of one artifact, or `null` when the name is not a plain file
   * name — artifacts come from URLs, so `../` must never leave the run directory.
   */
  artifactPath(id: string, name: string): string | null {
    if (!SAFE_ID.test(name) || name.startsWith(".")) {
      return null;
    }
    return join(this.runDir(id), ARTIFACTS_DIR, name);
  }

  /** File names under the run's `artifacts/`, or `[]` when there are none. */
  async listArtifacts(id: string): Promise<string[]> {
    const dir = join(this.runDir(id), ARTIFACTS_DIR);
    const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
    return entries
      .filter((entry) => entry.isFile() && SAFE_ID.test(entry.name))
      .map((entry) => entry.name)
      .sort();
  }

  async readOutput(id: string): Promise<Record<string, unknown> | null> {
    const raw = await readFile(
      join(this.runDir(id), OUTPUT_FILE),
      "utf8",
    ).catch(() => null);
    if (raw === null) {
      return null;
    }
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return null;
    }
  }

  /**
   * Delete old finished runs: `keep` succeeded, twice that many failed or
   * cancelled. Queued/running ones are never touched — they are still needed.
   */
  async prune(): Promise<string[]> {
    const runs = await this.list({ limit: Number.MAX_SAFE_INTEGER });
    const buckets = new Map<string, number>();
    const removed: string[] = [];
    for (const run of runs) {
      if (!isTerminal(run.state)) {
        continue;
      }
      const seen = (buckets.get(run.state) ?? 0) + 1;
      buckets.set(run.state, seen);
      const limit =
        run.state === "succeeded" ? this.keep : Math.max(this.keep * 2, 10);
      if (seen > limit) {
        await rm(this.runDir(run.id), { recursive: true, force: true });
        this.cache.delete(run.id);
        removed.push(run.id);
      }
    }
    return removed;
  }
}

function assertId(id: string): string {
  if (!SAFE_ID.test(id) || id.startsWith(".")) {
    throw new Error(`"${id}" is not a run id`);
  }
  return id;
}
