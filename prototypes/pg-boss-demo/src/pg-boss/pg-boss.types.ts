/**
 * Shared types for the pg-boss demo.
 * Convention: no `any`, no non-null assertions (`!`) in this codebase.
 */

export type JobState =
  "created" | "retry" | "active" | "completed" | "cancelled" | "failed";

/** Arbitrary JSON payload carried by a job (pg-boss stores it as jsonb). */
export type JobPayload = Record<string, unknown>;

/** Typed configuration assembled from @nestjs/config (env vars). */
export interface PgBossConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
  schema: string;
  retryLimit: number;
  retryDelay: number;
  retryBackoff: boolean;
  expireInSeconds: number;
  deleteAfterSeconds: number;
  workerConcurrency: number;
}

/** Row shape of `pgboss.job` as read by the list/get endpoints (read-only SQL). */
export interface JobRow {
  id: string;
  name: string;
  state: JobState;
  data: unknown;
  output: unknown;
  retryCount: number;
  retryLimit: number;
  retryDelay: number;
  priority: number;
  createdOn: Date;
  startedOn: Date | null;
  completedOn: Date | null;
}

export interface JobListItem {
  id: string;
  queue: string;
  state: JobState;
  retryCount: number;
  retryLimit: number;
  createdAt: string;
}

export interface JobDetail extends JobListItem {
  data: unknown;
  output: unknown;
  priority: number;
  startedOn: string | null;
  completedOn: string | null;
}

/** Result of GET /health — DB reachability + pg-boss schema state. */
export interface HealthStatus {
  db: "up" | "down";
  installed: boolean;
  schemaVersion: number | null;
}

/** Cast helpers used to map DB rows and job payloads without `any`/`!`. */

export function asString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

export function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function toDateString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value);
}

/** Map one row of `pgboss.job` (snake_case columns) to a typed shape. */
export function toJobRow(row: Record<string, unknown>): JobRow {
  return {
    id: asString(row["id"], ""),
    name: asString(row["name"], ""),
    state: asString(row["state"], "created") as JobState,
    data: row["data"],
    output: row["output"],
    retryCount: asNumber(row["retry_count"], 0),
    retryLimit: asNumber(row["retry_limit"], 0),
    retryDelay: asNumber(row["retry_delay"], 0),
    priority: asNumber(row["priority"], 0),
    createdOn:
      row["created_on"] instanceof Date ? row["created_on"] : new Date(0),
    startedOn: row["started_on"] instanceof Date ? row["started_on"] : null,
    completedOn:
      row["completed_on"] instanceof Date ? row["completed_on"] : null,
  };
}

export function toJobListItem(row: JobRow): JobListItem {
  return {
    id: row.id,
    queue: row.name,
    state: row.state,
    retryCount: row.retryCount,
    retryLimit: row.retryLimit,
    createdAt: row.createdOn.toISOString(),
  };
}

export function toJobDetail(row: JobRow): JobDetail {
  return {
    ...toJobListItem(row),
    data: row.data,
    output: row.output,
    priority: row.priority,
    startedOn: toDateString(row.startedOn),
    completedOn: toDateString(row.completedOn),
  };
}
