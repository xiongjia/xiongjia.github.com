import { ApiProperty, ApiPropertyOptional } from "@nestjs/swagger";
import type { JobPayload, JobState } from "../pg-boss/pg-boss.types";

/**
 * Request/response models. Deliberately simple: no class-validator — the
 * prototype keeps validation minimal (registered-queue check, state strings).
 * These classes double as the OpenAPI schemas for Swagger.
 */

export class CreateJobDto {
  @ApiProperty({
    description: "Demo queue / job type to enqueue into",
    example: "echo",
  })
  type: string;

  @ApiPropertyOptional({
    description: "Arbitrary JSON payload carried by the job",
    example: { message: "hello" },
  })
  payload?: JobPayload;

  @ApiPropertyOptional({
    description:
      "pg-boss send options, e.g. { startAfter: 10, priority: 5, retryLimit: 3 }",
  })
  options?: Record<string, unknown>;
}

export class JobQueryDto {
  @ApiProperty({
    description: "Queue to list jobs from (required)",
    example: "echo",
  })
  queue: string;

  @ApiPropertyOptional({
    description: "Filter by job state",
    example: "completed",
  })
  state?: string;

  @ApiPropertyOptional({
    description: "Max rows to return (default 50)",
    example: "50",
  })
  limit?: string;
}

export class EnqueueResultDto {
  @ApiPropertyOptional({
    description: "Job id, or null when the job was not enqueued",
  })
  id?: string | null;

  @ApiPropertyOptional({
    description: "Reason when id is null (e.g. deduplicated)",
  })
  reason?: string;
}

export class JobListItemDto {
  @ApiProperty() id: string;
  @ApiProperty() queue: string;
  @ApiProperty() state: JobState;
  @ApiProperty() retryCount: number;
  @ApiProperty() retryLimit: number;
  @ApiProperty() createdAt: string;
}

export class JobDetailDto extends JobListItemDto {
  @ApiPropertyOptional({ description: "Job payload as submitted" })
  data?: unknown;

  @ApiPropertyOptional({ description: "Job result stored via complete()" })
  output?: unknown;

  @ApiProperty() priority: number;

  @ApiPropertyOptional() startedOn?: string | null;

  @ApiPropertyOptional() completedOn?: string | null;
}

export class CommandResultDto {
  @ApiProperty({ description: "True when the command ran" })
  ok: boolean;

  @ApiPropertyOptional({ description: "Job state after the command" })
  state?: JobState | null;
}
