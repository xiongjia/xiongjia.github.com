export interface R2Config {
  /** Cloudflare account ID; used to build the S3 endpoint when R2_ENDPOINT is unset. */
  accountId: string;
  /** S3-compatible endpoint (account-derived for real R2, override for local MinIO). */
  endpoint: string;
  /** Region string sent to the S3 API (R2 ignores it; MinIO wants us-east-1). */
  region: string;
  bucket: string;
  accessKeyId: string;
  secretAccessKey: string;
  demoPrefix: string;
  keepDemoObject: boolean;
  /** Path-style addressing — required by local MinIO, unnecessary for R2. */
  forcePathStyle: boolean;
}

/** Parse a boolean-ish env value: true for "1", "true", "yes", "on". */
function parseBoolEnv(value: string | undefined): boolean {
  return value != null && ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

/** Ensure a non-empty demo prefix ends with "/" so keys stay under it. */
function normalizePrefix(prefix: string): string {
  if (!prefix) return prefix;
  return prefix.endsWith("/") ? prefix : `${prefix}/`;
}

/** Load R2 configuration from environment variables (see .env.example). */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): R2Config {
  const accountId = env.R2_ACCOUNT_ID ?? "";
  return {
    accountId,
    // Real R2's S3 endpoint is derived from the account ID:
    // https://<ACCOUNT_ID>.r2.cloudflarestorage.com. R2_ENDPOINT overrides it
    // entirely (e.g. a local MinIO for testing without a Cloudflare account —
    // then the account ID is not needed).
    endpoint: env.R2_ENDPOINT || (accountId ? `https://${accountId}.r2.cloudflarestorage.com` : ""),
    region: env.R2_REGION ?? "auto",
    bucket: env.R2_BUCKET ?? "",
    accessKeyId: env.R2_ACCESS_KEY_ID ?? "",
    secretAccessKey: env.R2_SECRET_ACCESS_KEY ?? "",
    demoPrefix: normalizePrefix(env.R2_DEMO_PREFIX ?? "demo/r2-client/"),
    keepDemoObject: parseBoolEnv(env.R2_KEEP_DEMO_OBJECT),
    forcePathStyle: parseBoolEnv(env.R2_FORCE_PATH_STYLE),
  };
}

/** True when the demo can talk to R2 (endpoint + credentials + bucket). */
export function isConfigured(cfg: R2Config): boolean {
  return Boolean(cfg.endpoint && cfg.bucket && cfg.accessKeyId && cfg.secretAccessKey);
}
