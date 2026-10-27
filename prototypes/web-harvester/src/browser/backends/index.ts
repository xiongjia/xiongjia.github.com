import type { BrowserBackend } from "./backend";
import { camoufoxBackend } from "./camoufox.backend";
import { patchrightBackend } from "./patchright.backend";

/**
 * DI token for the backend registry.
 *
 * Injecting the list (instead of hard-coding engines inside the service) is
 * what keeps `BrowserService` unit-testable: tests provide a fake backend.
 */
export const BROWSER_BACKENDS = Symbol("BROWSER_BACKENDS");

/** Camoufox first: it is the default engine (`HARVEST_BROWSER=camoufox`). */
export const DEFAULT_BACKENDS: BrowserBackend[] = [
  camoufoxBackend,
  patchrightBackend,
];
