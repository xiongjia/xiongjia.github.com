import type { Type } from "@nestjs/common";
import type { Job, WorkOptions } from "pg-boss";
import type { QueueName } from "../pg-boss.constants";
import { QUEUES } from "../pg-boss.constants";
import type { JobPayload } from "../pg-boss.types";
import { EchoJob } from "./echo.job";
import { FlakyJob } from "./flaky.job";
import { SlowJob } from "./slow.job";

/**
 * Handler context injected by PgBossService: lets handlers settle jobs
 * individually without holding a reference to the boss instance.
 */
export interface HandlerContext {
  /** Complete a job and store `output` as its result. */
  complete(id: string, output: object | null): Promise<void>;
}

/**
 * A demo job handler. Handlers are @Injectable() classes resolved through the
 * Nest DI container (PgBossService instantiates them via ModuleRef), so they
 * can inject any other service in their constructor.
 */
export interface DemoJobHandler {
  run(jobs: Job<JobPayload>[], ctx: HandlerContext): Promise<void>;
}

export interface JobHandlerRegistration {
  queue: QueueName;
  workOptions: WorkOptions;
  handlerClass: Type<DemoJobHandler>;
}

/**
 * Registry of demo queues → handler classes. Adding a new demo job type only
 * means adding one entry here (PgBossService creates the queue, resolves the
 * handler from the DI container and registers the worker at startup).
 */
export function buildRegistry(concurrency: number): JobHandlerRegistration[] {
  const workOptions = {
    localConcurrency: concurrency,
    batchSize: 1,
  } satisfies WorkOptions;

  return [
    // Fresh workOptions per queue (each queue gets its own options object).
    {
      queue: QUEUES.ECHO,
      workOptions: { ...workOptions },
      handlerClass: EchoJob,
    },
    {
      queue: QUEUES.FLAKY,
      workOptions: { ...workOptions },
      handlerClass: FlakyJob,
    },
    {
      queue: QUEUES.SLOW,
      workOptions: { ...workOptions },
      handlerClass: SlowJob,
    },
  ];
}
