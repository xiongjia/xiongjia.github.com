import { Global, Module } from "@nestjs/common";
import { DEFAULT_BACKENDS, BROWSER_BACKENDS } from "./backends/index";
import { BrowserService } from "./browser.service";

/** Shared by DemoModule (self-check) and XhsModule (real scraping). */
@Global()
@Module({
  providers: [
    BrowserService,
    { provide: BROWSER_BACKENDS, useValue: DEFAULT_BACKENDS },
  ],
  exports: [BrowserService],
})
export class BrowserModule {}
