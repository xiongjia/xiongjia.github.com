import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { BrowserModule } from "./browser/browser.module";
import { validateEnv } from "./config/env";
import { DemoModule } from "./demo/demo.module";
import { FlowsModule } from "./flows/flows.module";
import { XhsModule } from "./xhs/xhs.module";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: [".env.local", ".env"],
      validate: validateEnv,
      cache: true,
    }),
    BrowserModule,
    DemoModule,
    FlowsModule,
    XhsModule,
  ],
})
export class AppModule {}
