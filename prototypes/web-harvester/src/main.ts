import "reflect-metadata";
import { Logger } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { NestFactory } from "@nestjs/core";
import { DocumentBuilder, SwaggerModule } from "@nestjs/swagger";
import { AppModule } from "./app.module";
import { API_PREFIX, SWAGGER_PATH } from "./common/api";

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  // Makes SIGINT/SIGTERM run onModuleDestroy, so the browser context closes.
  app.enableShutdownHooks();
  // Every feature route lives under /api/v1; Swagger keeps its own path.
  app.setGlobalPrefix(API_PREFIX);

  const config = app.get(ConfigService);
  const host = config.get<string>("HARVEST_HOST") ?? "127.0.0.1";
  const port = config.get<number>("HARVEST_PORT") ?? 8765;

  const document = SwaggerModule.createDocument(
    app,
    new DocumentBuilder()
      .setTitle("web-harvester API")
      .setDescription(
        "Demo self-check + Xiaohongshu operations (browser-driven).",
      )
      .setVersion("0.1.0")
      .build(),
  );
  SwaggerModule.setup(SWAGGER_PATH, app, document);

  await app.listen(port, host);

  const logger = new Logger("Bootstrap");
  const base = `http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${port}`;
  logger.log(`web-harvester listening on ${base}`);
  logger.log(`self-check page: ${base}/${API_PREFIX}/demo`);
  logger.log(`swagger:        ${base}/${SWAGGER_PATH}`);
}

void bootstrap();
