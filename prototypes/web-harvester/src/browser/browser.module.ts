import { Global, Module } from "@nestjs/common";
import { ProfileRegistry } from "../profile/registry";
import { DEFAULT_BACKENDS, BROWSER_BACKENDS } from "./backends/index";
import { BrowserService } from "./browser.service";

/** Shared by DemoModule (self-check) and XhsModule (real scraping). */
@Global()
@Module({
  providers: [
    ProfileRegistry,
    BrowserService,
    { provide: BROWSER_BACKENDS, useValue: DEFAULT_BACKENDS },
  ],
  exports: [ProfileRegistry, BrowserService],
})
export class BrowserModule {}
