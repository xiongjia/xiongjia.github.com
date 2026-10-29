import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpException,
  NotFoundException,
  Param,
  Patch,
  Post,
  Query,
  Res,
} from "@nestjs/common";
import {
  ApiOkResponse,
  ApiOperation,
  ApiQuery,
  ApiTags,
} from "@nestjs/swagger";
import type { Response } from "express";
import { apiPath } from "../common/api";
import { QueueFullError } from "../run/queue";
import {
  isRunState,
  isTerminal,
  type RunRecord,
  type RunState,
} from "../run/run";
import type { FlowSummary } from "../flow/loader";
import type { ProfileSummary } from "../profile/profile";
import { flowJsonSchema } from "../flow/schema";
import { FlowService } from "./flow.service";

export interface StartRunBody {
  profile?: string;
  input?: Record<string, unknown>;
}

export interface RunResponse extends RunRecord {
  /** Where to poll for the final state. */
  pollUrl: string;
  /** True when `?wait=` covered the whole run — the result is in `output`. */
  settled: boolean;
}

const MAX_WAIT_MS = 60_000;
const DEFAULT_LIMIT = 20;

/**
 * Flow execution surface.
 *
 * Submit-then-poll on purpose: a browser flow takes tens of seconds, so the only
 * synchronous escape hatch is a bounded `?wait=` for interactive use (demo,
 * Swagger "Try it out").
 */
@ApiTags("flows")
@Controller()
export class FlowsController {
  constructor(private readonly flows: FlowService) {}

  @Get("flows")
  @ApiOperation({
    summary: "Flows this host can run, with kind and include edges",
    description:
      "`kind: fragment` is a file included by a flow and cannot be run on its own; `includes` lists the fragments a flow pulls in.",
  })
  async listFlows(): Promise<{ flows: FlowSummary[]; defaultProfile: string }> {
    return {
      flows: await this.flows.catalogue(),
      defaultProfile: this.flows.defaultProfile,
    };
  }

  @Get("flows/schema")
  @ApiOperation({
    summary: "JSON Schema of the flow DSL",
    description:
      "Generated from the same zod definition the host validates with — point an editor's `$schema` at it instead of keeping a file around.",
  })
  flowSchema(): Record<string, unknown> {
    return flowJsonSchema();
  }

  @Post("flows/:name/runs")
  @HttpCode(202)
  @ApiOperation({
    summary: "Submit a flow run; returns 202 with a pollUrl",
    description:
      "Pass ?wait=<ms> to block until the run finishes (200) or the wait expires (202).",
  })
  @ApiQuery({ name: "wait", required: false, type: Number, example: 5000 })
  @ApiQuery({ name: "profile", required: false, type: String })
  async startRun(
    @Param("name") name: string,
    @Body() body: unknown,
    @Res({ passthrough: true }) res: Response,
    @Query("wait") wait?: string,
    @Query("profile") profile?: string,
  ): Promise<RunResponse> {
    const request = parseStartRun(body, profile, this.flows.defaultProfile);
    const result = await this.guard(() =>
      this.flows.submit(name, {
        profile: request.profile,
        input: request.input,
        waitMs: parseWait(wait),
      }),
    );
    res.status(result.settled ? 200 : 202);
    return withPollUrl(result.record, result.settled);
  }

  @Post("flows/:name/run")
  @HttpCode(200)
  @ApiOperation({
    summary: "Run a `sync: true` flow and return its result in one call",
    description:
      "Answers `{ runId, output, meta }`; `?artifact=qr` streams that artifact (e.g. image/png) instead of JSON. Async flows are refused with 400.",
  })
  @ApiQuery({ name: "artifact", required: false, type: String, example: "qr" })
  @ApiQuery({ name: "wait", required: false, type: Number, example: 30000 })
  @ApiQuery({ name: "profile", required: false, type: String })
  async runSync(
    @Param("name") name: string,
    @Body() body: unknown,
    @Res({ passthrough: true }) res: Response,
    @Query("artifact") artifact?: string,
    @Query("wait") wait?: string,
    @Query("profile") profile?: string,
  ): Promise<unknown> {
    const request = parseStartRun(body, profile, this.flows.defaultProfile);
    const { record, output } = await this.guard(() =>
      this.flows.runSync(name, {
        profile: request.profile,
        input: request.input,
        waitMs: parseWait(wait) ?? 30_000,
      }),
    );

    if (!artifact) {
      res.status(200);
      return {
        runId: record.id,
        state: record.state,
        output,
        meta: record.meta,
        pollUrl: apiPath(`runs/${record.id}`),
      };
    }

    // One call for the whole point of these flows: ask for the QR, get the PNG.
    const { buffer, contentType } = await this.guard(() =>
      this.flows.artifact(record.id, `${artifact}.png`),
    );
    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Length", String(buffer.byteLength));
    res.setHeader("X-Run-Id", record.id);
    res.end(buffer);
    return undefined;
  }

  @Get("runs")
  @ApiOperation({ summary: "Recent runs, newest first" })
  @ApiQuery({
    name: "state",
    required: false,
    type: String,
    example: "running,queued",
  })
  @ApiQuery({ name: "profile", required: false, type: String })
  @ApiQuery({ name: "flow", required: false, type: String })
  @ApiQuery({ name: "limit", required: false, type: Number })
  async listRuns(
    @Query("state") state?: string,
    @Query("profile") profile?: string,
    @Query("flow") flow?: string,
    @Query("limit") limit?: string,
  ): Promise<{ runs: RunRecord[] }> {
    const runs = await this.flows.list({
      state: parseStates(state),
      profile: profile?.trim() || undefined,
      flow: flow?.trim() || undefined,
      limit: parseLimit(limit),
    });
    return { runs };
  }

  @Get("runs/:runId/output")
  @ApiOperation({ summary: "The flow's output JSON" })
  async runOutput(
    @Param("runId") runId: string,
  ): Promise<Record<string, unknown>> {
    return this.guard(() => this.flows.output(runId));
  }

  @Get("runs/:runId")
  @ApiOperation({ summary: "One run: state, input, error, meta" })
  @ApiOkResponse({
    description: "RunRecord (poll this until state is terminal)",
  })
  async getRun(@Param("runId") runId: string): Promise<RunResponse> {
    const record = await this.guard(() => this.flows.get(runId));
    return withPollUrl(record, false);
  }

  @Post("runs/:runId/cancel")
  @ApiOperation({
    summary: "Cancel a run",
    description:
      "Queued runs become cancelled at once; a running run is aborted before its next step.",
  })
  async cancelRun(@Param("runId") runId: string): Promise<RunResponse> {
    const record = await this.guard(() => this.flows.cancel(runId));
    return withPollUrl(record, false);
  }

  @Get("runs/:runId/artifacts")
  @ApiOperation({ summary: "Names of a run's artifacts" })
  async runArtifacts(
    @Param("runId") runId: string,
  ): Promise<{ runId: string; artifacts: string[] }> {
    return this.guard(() => this.flows.artifacts(runId));
  }

  @Get("runs/:runId/events")
  @ApiOperation({
    summary: "Server-sent events: the run's state, until it is terminal",
    description:
      "Text/event-stream of `data: <RunRecord>` lines (250ms resolution).",
  })
  async runEvents(
    @Param("runId") runId: string,
    @Res() res: Response,
  ): Promise<void> {
    await this.guard(() => this.flows.get(runId));

    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache, no-transform");
    res.setHeader("Connection", "keep-alive");
    res.flushHeaders();

    let last = "";
    let finished = false;

    const tick = async () => {
      if (finished) {
        return;
      }
      try {
        const record = await this.flows.get(runId);
        const payload = JSON.stringify(record);
        if (payload !== last) {
          last = payload;
          res.write(`data: ${payload}\n\n`);
        }
        if (isTerminal(record.state)) {
          stop();
          res.end();
        }
      } catch {
        stop();
        res.end();
      }
    };

    // `stop` is only ever called from the interval or a close event, so `timer`
    // is always initialised by then.
    const stop = () => {
      finished = true;
      clearInterval(timer);
    };
    const timer = setInterval(() => void tick(), 250);

    res.on("close", stop);
    await tick();
  }

  @Get("runs/:runId/artifacts/:name")
  @ApiOperation({
    summary: "One artifact of a run (screenshot, QR, …)",
    description:
      "Path as reported in `meta.screenshots`, e.g. `visit.png` or `failure.png`.",
  })
  async runArtifact(
    @Param("runId") runId: string,
    @Param("name") name: string,
    @Res() res: Response,
  ): Promise<void> {
    const { buffer, contentType } = await this.guard(() =>
      this.flows.artifact(runId, name),
    );
    res.setHeader("Content-Type", contentType);
    res.setHeader("Content-Length", String(buffer.byteLength));
    res.end(buffer);
  }

  @Get("profiles")
  @ApiOperation({ summary: "Profiles on disk (no secrets)" })
  async listProfiles(): Promise<Record<string, unknown>> {
    return {
      defaultProfile: this.flows.defaultProfile,
      profiles: await this.flows.profileSummaries(),
    };
  }

  @Patch("profiles/:name")
  @ApiOperation({
    summary: "Update a profile (locale, timezone, viewport, proxy, preset, …)",
    description:
      "The name and the existing preset stay unless you send a new one.",
  })
  async updateProfile(
    @Param("name") name: string,
    @Body() body: unknown,
  ): Promise<ProfileSummary> {
    const patch = body === undefined || body === null ? {} : body;
    if (typeof patch !== "object" || Array.isArray(patch)) {
      throw new BadRequestException("body must be a JSON object");
    }
    return this.flows.updateProfile(name, patch as Record<string, unknown>);
  }

  @Delete("profiles/:name")
  @ApiOperation({
    summary: "Delete a profile and its browser directory",
    description: "The default profile cannot be deleted.",
  })
  async deleteProfile(
    @Param("name") name: string,
  ): Promise<{ deleted: string }> {
    return this.flows.deleteProfile(name);
  }

  @Get("profiles/:name/queue")
  @ApiOperation({
    summary: "What a profile is running and what waits behind it",
  })
  queue(
    @Param("name") name: string,
  ): { profile: string } & ReturnType<FlowService["queueSnapshot"]> {
    return { profile: name, ...this.flows.queueSnapshot(name) };
  }

  /** Turn domain errors into the status code the caller can act on. */
  private async guard<T>(run: () => Promise<T>): Promise<T> {
    try {
      return await run();
    } catch (error) {
      if (error instanceof QueueFullError) {
        throw new HttpException({ message: error.message }, 429);
      }
      if (
        error instanceof BadRequestException ||
        error instanceof NotFoundException
      ) {
        throw error;
      }
      throw new BadRequestException(message(error));
    }
  }
}

/**
 * The body is optional on purpose: `POST .../runs` with no payload at all must
 * mean "run it with the flow's own defaults". Nest hands `undefined` to `@Body()`
 * when the request carries no body, hence the explicit shape checks — reading
 * `body.profile` off that would be a 500-shaped crash reported as a 400.
 */
function parseStartRun(
  body: unknown,
  profileQuery: string | undefined,
  fallbackProfile: string,
): { profile: string; input?: Record<string, unknown> } {
  const raw: Record<string, unknown> | null =
    body === null || body === undefined
      ? {}
      : (body as Record<string, unknown>);
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new BadRequestException("body must be a JSON object");
  }

  const unknownKeys = Object.keys(raw).filter(
    (key) => key !== "profile" && key !== "input",
  );
  if (unknownKeys.length > 0) {
    throw new BadRequestException(
      `unknown body field(s): ${unknownKeys.join(", ")} (accepted: profile, input)`,
    );
  }

  const profile = raw.profile ?? profileQuery ?? fallbackProfile;
  if (typeof profile !== "string") {
    throw new BadRequestException("profile must be a string");
  }

  const input = raw.input;
  if (input === undefined) {
    return { profile };
  }
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    throw new BadRequestException("input must be a JSON object");
  }
  return { profile, input: input as Record<string, unknown> };
}

function withPollUrl(record: RunRecord, settled: boolean): RunResponse {
  return { ...record, pollUrl: apiPath(`runs/${record.id}`), settled };
}

function parseWait(value: string | undefined): number | undefined {
  if (value === undefined || value.trim() === "") {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.min(Math.trunc(parsed), MAX_WAIT_MS);
}

function parseStates(value: string | undefined): RunState[] | undefined {
  if (value === undefined || value.trim() === "") {
    return undefined;
  }
  const states: RunState[] = [];
  for (const part of value.split(",")) {
    const state = part.trim();
    if (state === "") {
      continue;
    }
    if (!isRunState(state)) {
      throw new BadRequestException(`"${state}" is not a run state`);
    }
    states.push(state);
  }
  return states.length > 0 ? states : undefined;
}

function parseLimit(value: string | undefined): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_LIMIT;
  }
  return Math.min(Math.trunc(parsed), 200);
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
