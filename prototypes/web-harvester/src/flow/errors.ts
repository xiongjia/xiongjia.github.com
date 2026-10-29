/** Why a flow run failed — carried into `run.json` so callers can react. */
export type FlowErrorCode =
  | "bad-template"
  | "selector-not-found"
  | "timeout"
  | "blocked"
  | "assert-failed"
  | "no-output-var"
  | "bad-fragment"
  | "cancelled";

/**
 * A flow-level failure.
 *
 * Distinct from a crash: every code here means "the flow said something the page
 * did not agree with", which is exactly the information a run record should keep.
 */
export class FlowError extends Error {
  constructor(
    readonly code: FlowErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "FlowError";
  }
}
