import type { ConfigService } from "@nestjs/config";

/**
 * Base URL a flow should use to reach this host.
 *
 * The browser must reach the server over loopback: `0.0.0.0` / `::` are bind
 * addresses, not destinations.
 */
export function selfBaseUrl(config: ConfigService): string {
  const host = config.get<string>("HARVEST_HOST") ?? "127.0.0.1";
  const port = config.get<number>("HARVEST_PORT") ?? 8765;
  const reachableHost =
    host === "0.0.0.0" || host === "::" ? "127.0.0.1" : host;
  return `http://${reachableHost}:${port}`;
}
