/**
 * Single place for the HTTP surface layout.
 *
 * Feature routes are versioned (`/api/v1/...`); the Swagger UI deliberately is
 * not, so bookmarks to the docs survive a version bump.
 */
export const API_PREFIX = "api/v1";

/** Swagger UI + OpenAPI document routes (registered outside the versioned prefix). */
export const SWAGGER_PATH = "api/docs";

/** Absolute path for a feature route, e.g. `apiPath("demo")` → `/api/v1/demo`. */
export function apiPath(route = ""): string {
  const trimmed = route.replace(/^\/+/, "");
  return `/${API_PREFIX}${trimmed ? `/${trimmed}` : ""}`;
}
