import "reflect-metadata";
import { Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { NestFactory } from "@nestjs/core";
import { DocumentBuilder, SwaggerModule } from "@nestjs/swagger";
import { AppModule } from "./app.module";

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);

  // Without this, SIGTERM/SIGINT do not trigger onApplicationShutdown,
  // so PgBossService.stop() (graceful worker shutdown) never runs.
  app.enableShutdownHooks();

  const config = app.get(ConfigService);
  const swaggerEnabled =
    config.get<string>("SWAGGER_ENABLED", "true") !== "false";
  const swaggerPath = config.get<string>("SWAGGER_PATH", "api/docs");

  if (swaggerEnabled) {
    // Manual decorator mode — the CLI plugin needs the TypeScript programmatic
    // API (unavailable) and @nestjs/swagger 12 removed the cliPlugin option.
    const doc = new DocumentBuilder()
      .setTitle("pg-boss-demo API")
      .setDescription(
        "NestJS + pg-boss job queue prototype: enqueue, inspect, retry jobs.",
      )
      .setVersion("0.1.0")
      .build();
    const document = SwaggerModule.createDocument(app, doc);
    SwaggerModule.setup(swaggerPath, app, document);
  }

  const port = Number(config.get<string>("PORT", "3000"));
  await app.listen(Number.isFinite(port) ? port : 3000);

  const logger = new Logger("Bootstrap");
  logger.log(`pg-boss-demo listening on http://localhost:${port}`);
  if (swaggerEnabled) {
    logger.log(`Swagger UI: http://localhost:${port}/${swaggerPath}`);
  }
}

void bootstrap();
