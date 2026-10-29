import {
  BadRequestException,
  HttpException,
  Injectable,
  Logger,
  NotFoundException,
  RequestTimeoutException,
  ServiceUnavailableException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { readFile } from "node:fs/promises";
import { extname, join } from "node:path";
import { BrowserService } from "../browser/browser.service";
import { ProfileRegistry } from "../profile/registry";
import type { ProfileSummary } from "../profile/profile";
import { selfBaseUrl } from "../common/self-url";
import { FlowError } from "../flow/errors";
import { FlowLoader, type FlowSummary } from "../flow/loader";
import { coerceInput, isSyncFlow, type FlowFile } from "../flow/schema";
import { runFlow, type RunMeta } from "../flow/step-runner";
import { interpolate } from "../flow/template";
import { isTerminal, newRunId, type RunRecord } from "../run/run";
import { RunQueue, type QueueSnapshot } from "../run/queue";
import { RunStore, type RunFilter } from "../run/store";

const PROFILE_PATTERN = /^[a-z0-9][a-z0-9._-]*$/;

export interface SubmitOptions {
  profile: string;
  input?: Record<string, unknown>;
  /** How long to let the caller wait for a finished result. */
  waitMs?: number;
}

export interface SubmitResult {
  record: RunRecord;
  /** True when the run finished inside `waitMs`. */
  settled: boolean;
}

/**
 * Submits flows, runs them through the browser, records everything.
 *
 * The HTTP surface never waits for a flow: `submit` returns as soon as the run is
 * queued, unless the caller asks for a bounded wait. Long-running flows are
 * normal (a scrape takes tens of seconds), so state lives on disk, not in a
 * request.
 */
@Injectable()
export class FlowService {
  private readonly logger = new Logger(FlowService.name);
  private readonly controllers = new Map<string, AbortController>();
  /** Last scheduled start per throttle key (`<profile>:<scope>`). */
  private readonly throttledUntil = new Map<string, number>();
  private readonly completions = new Map<string, Promise<RunRecord>>();

  constructor(
    private readonly flows: FlowLoader,
    private readonly store: RunStore,
    private readonly queue: RunQueue,
    private readonly browser: BrowserService,
    private readonly profiles: ProfileRegistry,
    private readonly config: ConfigService,
  ) {}

  /** Load a flow, mapping "unknown/broken flow" to the caller's 400. */
  private async loadFlow(name: string): Promise<FlowFile> {
    return this.flows.load(name).catch((error: unknown) => {
      throw new BadRequestException(
        error instanceof Error ? error.message : String(error),
      );
    });
  }

  /** Every flow file with its role and include edges. */
  async catalogue(): Promise<FlowSummary[]> {
    return this.flows.catalogue();
  }

  /** Profile used when the caller does not name one. */
  get defaultProfile(): string {
    return this.config.get<string>("HARVEST_PROFILE") ?? "main";
  }

  async submit(name: string, options: SubmitOptions): Promise<SubmitResult> {
    const profile = assertProfile(options.profile);
    // A bad flow name or a broken flow file is the caller's problem (400), not a
    // server fault — the message already says which flow and why.
    const flow = await this.flows.load(name).catch((error: unknown) => {
      throw new BadRequestException(
        error instanceof Error ? error.message : String(error),
      );
    });
    const coerced = coerceInput(flow, options.input);
    if (!coerced.ok) {
      throw new BadRequestException({
        message: "invalid flow input",
        errors: coerced.errors,
      });
    }

    // Record the effective input, not the declared default: `run.json` should
    // answer "which URL did this run open" without re-resolving templates.
    const input = resolveInput(coerced.value, selfBaseUrl(this.config));
    // Creates the profile on first use, so a typo is caught here (400) rather
    // than as a failed run.
    await this.profiles.get(profile).catch((error: unknown) => {
      throw new BadRequestException(
        error instanceof Error ? error.message : String(error),
      );
    });

    if (flow.kind === "fragment") {
      throw new BadRequestException(
        `"${name}" is a fragment — run the flow that includes it instead`,
      );
    }

    const controller = new AbortController();
    const record = await this.store.create({
      id: newRunId(),
      flow: flow.name,
      profile,
      state: "queued",
      input,
    });
    this.controllers.set(record.id, controller);

    const queued = this.queue.submit(profile, record.id, () =>
      this.execute(record, flow, controller),
    );
    this.completions.set(
      record.id,
      queued.then(async () => (await this.store.get(record.id)) ?? record),
    );
    // Nothing awaits this branch on the failure path; keep it quiet and rely on
    // `run.json` (which `execute` always writes).
    queued.catch(() => undefined);

    if (!options.waitMs) {
      return { record, settled: false };
    }
    const settled = await this.waitUntil(record.id, options.waitMs);
    return { record: settled ?? record, settled: settled !== null };
  }

  /**
   * Run a `sync: true` flow and hand back its result in the same call.
   *
   * Only short, interactive flows opt in (`xhs-login-qr`, `xhs-login-check`);
   * anything that scrapes stays on the submit/poll path, where a slow site cannot
   * turn into a held HTTP connection.
   */
  async runSync(
    name: string,
    options: SubmitOptions & { waitMs?: number },
  ): Promise<{ record: RunRecord; output: Record<string, unknown> }> {
    const flow = await this.loadFlow(name);
    if (!isSyncFlow(flow)) {
      throw new BadRequestException(
        `"${name}" is not a sync flow — add "sync": true to it, or submit it and poll the run`,
      );
    }

    const { record, settled } = await this.submit(name, {
      ...options,
      waitMs: options.waitMs ?? 30_000,
    });
    if (!settled) {
      throw new RequestTimeoutException({
        message: `run ${record.id} is still ${record.state}`,
        runId: record.id,
      });
    }
    if (record.state === "cancelled") {
      throw new HttpException(
        { message: `run ${record.id} was cancelled` },
        409,
      );
    }
    if (record.state !== "succeeded") {
      const message = `${flow.name} failed (${record.error?.code ?? record.state}): ${record.error?.message ?? "no detail"}`;
      if (record.error?.code === "blocked") {
        throw new ServiceUnavailableException(message);
      }
      throw new HttpException({ message, runId: record.id }, 502);
    }

    const output = (await this.store.readOutput(record.id)) ?? {};
    return { record, output };
  }

  async get(id: string): Promise<RunRecord> {
    const record = await this.store.get(id);
    if (!record) {
      throw new NotFoundException(`run ${id} does not exist`);
    }
    return record;
  }

  async output(id: string): Promise<Record<string, unknown>> {
    const record = await this.get(id);
    const output = await this.store.readOutput(record.id);
    if (!output) {
      throw new NotFoundException(
        `run ${id} has no output yet (state: ${record.state})`,
      );
    }
    return output;
  }

  async list(filter: RunFilter): Promise<RunRecord[]> {
    return this.store.list(filter);
  }

  /** Abort a run. Queued runs become `cancelled` immediately. */
  async cancel(id: string): Promise<RunRecord> {
    const record = await this.get(id);
    if (isTerminal(record.state)) {
      return record;
    }
    this.controllers.get(id)?.abort();
    if (record.state === "queued" && this.queue.drop(record.profile, id)) {
      return this.store.update(id, {
        state: "cancelled",
        finishedAt: new Date().toISOString(),
      });
    }
    return record;
  }

  /** Profiles on disk (never the preset — that stays local). */
  async profileSummaries(): Promise<ProfileSummary[]> {
    return this.profiles.list();
  }

  /** Names of this run's artifacts (screenshots, QR codes, …). */
  async artifacts(id: string): Promise<{ runId: string; artifacts: string[] }> {
    const record = await this.get(id);
    return {
      runId: record.id,
      artifacts: await this.store.listArtifacts(record.id),
    };
  }

  /** Change one profile's configuration (locale, proxy, preset, …). */
  async updateProfile(
    name: string,
    patch: Record<string, unknown>,
  ): Promise<ProfileSummary> {
    const profile = await this.profiles
      .update(name, patch)
      .catch((error: unknown) => {
        throw new BadRequestException(
          error instanceof Error ? error.message : String(error),
        );
      });
    return this.profiles.summary(profile);
  }

  /** Delete a profile and its browser directory. */
  async deleteProfile(name: string): Promise<{ deleted: string }> {
    await this.profiles.remove(name).catch((error: unknown) => {
      throw new BadRequestException(
        error instanceof Error ? error.message : String(error),
      );
    });
    return { deleted: name };
  }

  /** One artifact from a run, e.g. `visit.png` or `failure.png`. */
  async artifact(
    id: string,
    name: string,
  ): Promise<{ buffer: Buffer; contentType: string }> {
    const record = await this.get(id);
    const path = this.store.artifactPath(record.id, name);
    if (!path) {
      throw new NotFoundException(`"${name}" is not an artifact name`);
    }
    const buffer = await readFile(path).catch(() => null);
    if (!buffer) {
      throw new NotFoundException(`run ${id} has no artifact "${name}"`);
    }
    return { buffer, contentType: contentTypeOf(name) };
  }

  queueSnapshot(profile: string): QueueSnapshot {
    return this.queue.snapshot(assertProfile(profile));
  }

  /** Execute one run: browser page in, `output.json` + final state out. */
  private async execute(
    record: RunRecord,
    flow: FlowFile,
    controller: AbortController,
  ): Promise<void> {
    const current = await this.store.get(record.id);
    if (!current || current.state === "cancelled") {
      this.controllers.delete(record.id);
      return;
    }

    await this.store.update(record.id, {
      state: "running",
      startedAt: new Date().toISOString(),
    });

    // A flow may ask for a minimum gap between runs (the xhs flows share one
    // scope). Nothing else is affected: no field, no wait.
    const throttleMs = await this.throttle(flow, record.profile);

    // Shared with the runner so a failed run still records which step died.
    const meta: RunMeta = {
      url: "",
      userAgent: "",
      usedSelectors: {},
      screenshots: {},
      steps: [],
      ...(throttleMs > 0 ? { throttleMs } : {}),
    };

    try {
      const { output } = await this.browser.withPage(
        (page) =>
          runFlow(flow, {
            page,
            input: record.input,
            self: selfBaseUrl(this.config),
            vars: {},
            meta,
            artifactsDir: join(this.store.runDir(record.id), "artifacts"),
            signal: controller.signal,
            resolve: (fragment) => this.flows.load(fragment),
          }),
        record.profile,
      );
      await this.store.writeOutput(record.id, output);
      await this.store.update(record.id, {
        state: "succeeded",
        finishedAt: new Date().toISOString(),
        meta,
      });
    } catch (error) {
      const cancelled =
        controller.signal.aborted ||
        (error instanceof FlowError && error.code === "cancelled");
      await this.store.update(record.id, {
        state: cancelled ? "cancelled" : "failed",
        finishedAt: new Date().toISOString(),
        error: cancelled ? null : toRunError(error),
        meta,
      });
      if (!cancelled) {
        this.logger.warn(
          `flow ${flow.name} run ${record.id} failed: ${toRunError(error).message}`,
        );
      }
    } finally {
      this.controllers.delete(record.id);
      await this.store.prune().catch(() => undefined);
    }
  }

  /**
   * Enforce a flow's own pacing.
   *
   * The value comes from the flow file (`throttle.minIntervalMs`), so only the
   * flows that ask for it are slowed down — the demo, or any other site, keeps its
   * full speed. `scope` lets several flows share one budget (all xhs flows on one
   * account share `xhs`), which is what keeps a site from seeing a burst.
   */
  private async throttle(flow: FlowFile, profile: string): Promise<number> {
    const minIntervalMs = flow.throttle?.minIntervalMs ?? 0;
    if (minIntervalMs <= 0) {
      return 0;
    }
    const key = `${profile}:${flow.throttle?.scope ?? flow.name}`;
    const readyAt = this.throttledUntil.get(key) ?? 0;
    const now = Date.now();
    const waitMs = Math.min(Math.max(readyAt - now, 0), minIntervalMs);
    this.throttledUntil.set(key, now + waitMs + minIntervalMs);
    if (waitMs > 0) {
      this.logger.log(
        `throttle ${key}: waiting ${waitMs}ms before "${flow.name}" (min ${minIntervalMs}ms)`,
      );
      await new Promise((resolve) => setTimeout(resolve, waitMs));
    }
    return waitMs;
  }

  /** Resolve with the final record, or `null` when `waitMs` runs out first. */
  private async waitUntil(
    id: string,
    waitMs: number,
  ): Promise<RunRecord | null> {
    const done = this.completions.get(id);
    if (!done) {
      return this.store.get(id);
    }
    let timer: NodeJS.Timeout | undefined;
    const timeout = new Promise<null>((resolve) => {
      timer = setTimeout(() => resolve(null), waitMs);
      timer.unref();
    });
    try {
      return await Promise.race([done, timeout]);
    } finally {
      if (timer) {
        clearTimeout(timer);
      }
    }
  }
}

function resolveInput(
  input: Record<string, unknown>,
  self: string,
): Record<string, unknown> {
  const resolved: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(input)) {
    resolved[key] =
      typeof value === "string"
        ? interpolate(value, { input, vars: {}, self })
        : value;
  }
  return resolved;
}

function contentTypeOf(name: string): string {
  const extension = extname(name).toLowerCase();
  if (extension === ".png") {
    return "image/png";
  }
  if (extension === ".jpg" || extension === ".jpeg") {
    return "image/jpeg";
  }
  if (extension === ".webp") {
    return "image/webp";
  }
  if (extension === ".json") {
    return "application/json";
  }
  return "application/octet-stream";
}

function assertProfile(profile: string): string {
  const value = profile.trim();
  if (!PROFILE_PATTERN.test(value) || value.length > 64) {
    throw new BadRequestException(
      `"${profile}" is not a profile name (lower-case kebab-case, e.g. main)`,
    );
  }
  return value;
}

function toRunError(error: unknown): { code: string; message: string } {
  if (error instanceof FlowError) {
    return { code: error.code, message: error.message };
  }
  return {
    code: "error",
    message: error instanceof Error ? error.message : String(error),
  };
}
