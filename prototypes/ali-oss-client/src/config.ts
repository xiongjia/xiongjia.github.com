export interface OSSConfig {
  region: string;
  endpoint?: string;
  bucket: string;
  accessKeyId: string;
  accessKeySecret: string;
  demoPrefix: string;
  keepDemoObject: boolean;
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

/** Load OSS configuration from environment variables (see .env.example). */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): OSSConfig {
  return {
    region: env.ALIYUN_OSS_REGION ?? "",
    endpoint: env.ALIYUN_OSS_ENDPOINT || undefined,
    bucket: env.ALIYUN_OSS_BUCKET ?? "",
    accessKeyId: env.ALIYUN_OSS_ACCESS_KEY_ID ?? "",
    accessKeySecret: env.ALIYUN_OSS_ACCESS_KEY_SECRET ?? "",
    demoPrefix: normalizePrefix(env.ALIYUN_OSS_DEMO_PREFIX ?? "demo/ali-oss-client-prototype/"),
    keepDemoObject: parseBoolEnv(env.ALIYUN_OSS_KEEP_DEMO_OBJECT),
  };
}

/** True when all credentials needed to talk to OSS are present. */
export function isConfigured(cfg: OSSConfig): boolean {
  return Boolean(cfg.region && cfg.bucket && cfg.accessKeyId && cfg.accessKeySecret);
}
