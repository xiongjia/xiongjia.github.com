import { Injectable, Logger } from "@nestjs/common";

/**
 * Demo cross-service dependency: worker handlers are @Injectable() classes, so
 * they can inject any NestJS provider through their constructor (plain DI).
 * This service is called from the job handlers to show that pattern — see
 * echo.job.ts / flaky.job.ts / slow.job.ts.
 */
@Injectable()
export class NotificationService {
  private readonly logger = new Logger(NotificationService.name);

  notify(channel: string, message: string): void {
    this.logger.log(`[${channel}] ${message}`);
  }
}
