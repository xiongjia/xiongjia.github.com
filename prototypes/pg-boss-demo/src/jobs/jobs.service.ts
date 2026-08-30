import {
  BadRequestException,
  Injectable,
  Logger,
  NotFoundException,
} from "@nestjs/common";
import type { SendOptions } from "pg-boss";
import { PgBossService } from "../pg-boss/pg-boss.service";
import type { JobState } from "../pg-boss/pg-boss.types";
import type {
  CommandResultDto,
  CreateJobDto,
  EnqueueResultDto,
  JobDetailDto,
  JobListItemDto,
  JobQueryDto,
} from "./dto";

const JOB_STATES: readonly string[] = [
  "created",
  "retry",
  "active",
  "completed",
  "cancelled",
  "failed",
];

/**
 * pg-boss send options we accept from the API, with per-field type rules.
 * Anything unknown or mistyped is rejected, so a malformed `options` value
 * cannot reach pg-boss as a 500.
 */
const SEND_OPTION_RULES = [
  { key: "retryLimit", type: "number", validate: isNumber },
  { key: "retryDelay", type: "number", validate: isNumber },
  { key: "retryBackoff", type: "boolean", validate: isBoolean },
  { key: "retryDelayMax", type: "number", validate: isNumber },
  { key: "expireInSeconds", type: "number", validate: isNumber },
  { key: "deleteAfterSeconds", type: "number", validate: isNumber },
  { key: "priority", type: "number", validate: isNumber },
  { key: "startAfter", type: "number | string | Date", validate: isStartAfter },
  { key: "singletonKey", type: "string", validate: isString },
] as const;

type SendOptionValue = string | number | boolean | Date;

function isNumber(value: unknown): value is number {
  return typeof value === "number";
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isStartAfter(value: unknown): value is number | string | Date {
  return (
    typeof value === "number" ||
    typeof value === "string" ||
    value instanceof Date
  );
}

function isPlainObject(value: unknown): boolean {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function sanitizeSendOptions(
  raw: Record<string, unknown> | undefined,
): SendOptions {
  if (raw === undefined) {
    return {};
  }
  const out: Record<string, SendOptionValue> = {};
  for (const { key, type, validate } of SEND_OPTION_RULES) {
    const value = raw[key];
    if (value === undefined || value === null) {
      continue;
    }
    if (!validate(value)) {
      throw new BadRequestException(
        `Invalid send option '${key}' — expected ${type}`,
      );
    }
    out[key] = value;
  }
  return out as SendOptions;
}

function parseState(value: string | undefined): JobState | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (JOB_STATES.includes(value)) {
    return value as JobState;
  }
  throw new BadRequestException(
    `Invalid state '${value}' — expected one of: ${JOB_STATES.join(", ")}`,
  );
}

function parseLimit(value: string | undefined): number {
  if (value === undefined) {
    return 50;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > 1000) {
    throw new BadRequestException(
      `Invalid limit '${value}' — expected 1..1000`,
    );
  }
  return Math.floor(parsed);
}

/**
 * REST-layer service: thin mapping between HTTP DTOs and PgBossService.
 * All pg-boss calls go through PgBossService (never touches the boss directly).
 */
@Injectable()
export class JobsService {
  private readonly logger = new Logger(JobsService.name);

  constructor(private readonly pgBoss: PgBossService) {}

  async create(dto: CreateJobDto): Promise<EnqueueResultDto> {
    // `isRegisteredQueue` is a type guard: after this check `type` is QueueName.
    const type = dto.type;
    if (!this.pgBoss.isRegisteredQueue(type)) {
      throw new BadRequestException(
        `Unknown queue type '${type}' — registered queues: echo, flaky, slow`,
      );
    }
    if (dto.payload !== undefined && !isPlainObject(dto.payload)) {
      throw new BadRequestException(
        "payload must be a JSON object (or omitted)",
      );
    }
    const options = sanitizeSendOptions(dto.options);
    const id = await this.pgBoss.send(type, dto.payload ?? {}, options);
    if (id === null) {
      return { id: null, reason: "not enqueued (deduplicated)" };
    }
    this.logger.log(`enqueued job ${id} on '${type}'`);
    return { id };
  }

  async list(query: JobQueryDto): Promise<JobListItemDto[]> {
    if (query.queue === undefined || query.queue === "") {
      throw new BadRequestException('query parameter "queue" is required');
    }
    return this.pgBoss.listJobs(
      query.queue,
      parseState(query.state),
      parseLimit(query.limit),
    );
  }

  async findOne(id: string): Promise<JobDetailDto> {
    const job = await this.pgBoss.findJobById(id);
    if (job === null) {
      throw new NotFoundException(`Job '${id}' not found`);
    }
    return job;
  }

  async cancel(id: string): Promise<CommandResultDto> {
    const job = await this.requireJob(id);
    await this.pgBoss.cancel(job.queue, id);
    return this.commandResult(id);
  }

  async retry(id: string): Promise<CommandResultDto> {
    const job = await this.requireJob(id);
    await this.pgBoss.retry(job.queue, id);
    return this.commandResult(id);
  }

  private async requireJob(id: string): Promise<JobDetailDto> {
    const job = await this.pgBoss.findJobById(id);
    if (job === null) {
      throw new NotFoundException(`Job '${id}' not found`);
    }
    return job;
  }

  private async commandResult(id: string): Promise<CommandResultDto> {
    const after = await this.pgBoss.findJobById(id);
    return { ok: true, state: after?.state ?? null };
  }
}
