import { Injectable } from "@nestjs/common";
import type { Job } from "pg-boss";
import { NotificationService } from "../notification.service";
import type { JobPayload } from "../pg-boss.types";
import { asNumber } from "../pg-boss.types";
import type { HandlerContext, DemoJobHandler } from "./registry";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * slow — demonstrates concurrency control. Sleeps `delayMs` (default 2000) per
 * job before completing. Enqueue several at once and watch the queue's
 * `localConcurrency` limit them in flight (see GET /queues stats).
 */
@Injectable()
export class SlowJob implements DemoJobHandler {
  constructor(private readonly notifications: NotificationService) {}

  async run(jobs: Job<JobPayload>[], ctx: HandlerContext): Promise<void> {
    for (const job of jobs) {
      const delayMs = asNumber(job.data["delayMs"], 2000);
      await sleep(delayMs);
      await ctx.complete(job.id, {
        sleptMs: delayMs,
        finishedAt: new Date().toISOString(),
      });
      this.notifications.notify("slow", `job ${job.id}: slept ${delayMs}ms`);
    }
  }
}
