import { randomBytes } from "node:crypto";
import type { RunMeta } from "../flow/step-runner";

/** Lifecycle of one flow run. Terminal states never change again. */
export type RunState =
  "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface RunError {
  code: string;
  message: string;
}

/** `run.json` — everything about a run except its output (that is `output.json`). */
export interface RunRecord {
  id: string;
  flow: string;
  profile: string;
  state: RunState;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  input: Record<string, unknown>;
  meta: RunMeta | null;
  error: RunError | null;
}

/**
 * `<ISO timestamp>-<6 hex>`: sorts chronologically as a string, so listing runs
 * never needs an index file.
 */
export function newRunId(now: number = Date.now()): string {
  const stamp = new Date(now).toISOString().replace(/[:.]/g, "-");
  return `${stamp}-${randomBytes(3).toString("hex")}`;
}

export function isTerminal(state: RunState): boolean {
  return state === "succeeded" || state === "failed" || state === "cancelled";
}

export function isRunState(value: string): value is RunState {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "cancelled"
  );
}
