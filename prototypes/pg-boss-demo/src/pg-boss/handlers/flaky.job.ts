import { Injectable } from "@nestjs/common";
import type { Job } from "pg-boss";
import { NotificationService } from "../notification.service";
import type { JobPayload } from "../pg-boss.types";
import { asNumber } from "../pg-boss.types";
import type { HandlerContext, DemoJobHandler } from "./registry";

/**
 * flaky — demonstrates retries. Fails randomly with the probability given in
 * the payload (`failProbability`, default 0.5). Throwing from a handler marks
 * the batch as failed: pg-boss retries the job up to the queue's `retryLimit`
 * (with `retryDelay`/`retryBackoff`), then marks it failed permanently.
 */
@Injectable()
export class FlakyJob implements DemoJobHandler {
  constructor(private readonly notifications: NotificationService) {}

  async run(jobs: Job<JobPayload>[], ctx: HandlerContext): Promise<void> {
    for (const job of jobs) {
      const failProbability = Math.min(
        1,
        Math.max(0, asNumber(job.data["failProbability"], 0.5)),
      );
      if (Math.random() < failProbability) {
        throw new Error(
          `flaky: deliberate random failure (p=${failProbability})`,
        );
      }
      await ctx.complete(job.id, {
        survived: true,
        processedAt: new Date().toISOString(),
      });
      this.notifications.notify(
        "flaky",
        `job ${job.id}: survived (p=${failProbability})`,
      );
    }
  }
}
