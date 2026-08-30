import { Body, Controller, Get, Param, Post, Query } from "@nestjs/common";
import {
  ApiBadRequestResponse,
  ApiCreatedResponse,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiParam,
  ApiQuery,
  ApiTags,
} from "@nestjs/swagger";
import {
  CommandResultDto,
  CreateJobDto,
  EnqueueResultDto,
  JobDetailDto,
  JobListItemDto,
  JobQueryDto,
} from "./dto";
import { JobsService } from "./jobs.service";

@ApiTags("jobs")
@Controller("jobs")
export class JobsController {
  constructor(private readonly jobsService: JobsService) {}

  @Post()
  @ApiOperation({ summary: "Enqueue a job into one of the demo queues" })
  @ApiCreatedResponse({ description: "Job enqueued", type: EnqueueResultDto })
  @ApiBadRequestResponse({ description: "Unknown queue type" })
  create(@Body() dto: CreateJobDto): Promise<EnqueueResultDto> {
    return this.jobsService.create(dto);
  }

  @Get()
  @ApiOperation({
    summary: "List jobs of a queue, optionally filtered by state",
  })
  @ApiQuery({
    name: "queue",
    required: true,
    description: "Queue name (echo | flaky | slow)",
  })
  @ApiQuery({
    name: "state",
    required: false,
    description: "created | retry | active | completed | cancelled | failed",
  })
  @ApiQuery({
    name: "limit",
    required: false,
    description: "Max rows, 1..1000 (default 50)",
  })
  @ApiOkResponse({
    description: "Job list",
    type: JobListItemDto,
    isArray: true,
  })
  list(@Query() query: JobQueryDto): Promise<JobListItemDto[]> {
    return this.jobsService.list(query);
  }

  @Get(":id")
  @ApiOperation({ summary: "Get one job with its payload and result" })
  @ApiParam({ name: "id", description: "Job id (uuid)" })
  @ApiOkResponse({ description: "Job detail", type: JobDetailDto })
  @ApiNotFoundResponse({ description: "Job not found" })
  findOne(@Param("id") id: string): Promise<JobDetailDto> {
    return this.jobsService.findOne(id);
  }

  @Post(":id/cancel")
  @ApiOperation({
    summary: "Cancel an unfinished job (no-op for completed/failed)",
  })
  @ApiParam({ name: "id", description: "Job id (uuid)" })
  @ApiOkResponse({ description: "Command result", type: CommandResultDto })
  cancel(@Param("id") id: string): Promise<CommandResultDto> {
    return this.jobsService.cancel(id);
  }

  @Post(":id/retry")
  @ApiOperation({ summary: "Re-queue a failed/retry job for another attempt" })
  @ApiParam({ name: "id", description: "Job id (uuid)" })
  @ApiOkResponse({ description: "Command result", type: CommandResultDto })
  retry(@Param("id") id: string): Promise<CommandResultDto> {
    return this.jobsService.retry(id);
  }
}
