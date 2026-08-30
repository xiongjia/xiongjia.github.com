import { Injectable } from "@nestjs/common";
import type { Job } from "pg-boss";
import { NotificationService } from "../notification.service";
import type { JobPayload } from "../pg-boss.types";
import { asString } from "../pg-boss.types";
import type { HandlerContext, DemoJobHandler } from "./registry";

/**
 * echo — the simplest demo handler. Completes every job immediately and
 * stores the received message as the job result (`output`), which is what the
 * "query job result" API returns.
 *
 * Demonstrates the DI pattern: like any @Injectable() class it can inject
 * other services (here NotificationService) through its constructor.
 */
@Injectable()
export class EchoJob implements DemoJobHandler {
  constructor(private readonly notifications: NotificationService) {}

  async run(jobs: Job<JobPayload>[], ctx: HandlerContext): Promise<void> {
    for (const job of jobs) {
      const message = asString(job.data["message"], "no message");
      await ctx.complete(job.id, {
        received: message,
        processedAt: new Date().toISOString(),
      });
      this.notifications.notify(
        "echo",
        `job ${job.id}: processed "${message}"`,
      );
    }
  }
}
