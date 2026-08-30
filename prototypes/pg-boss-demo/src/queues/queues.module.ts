import { Module } from "@nestjs/common";
import { QueuesController } from "./queues.controller";

@Module({
  controllers: [QueuesController],
})
export class QueuesModule {}
