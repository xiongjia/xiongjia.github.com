export interface SupabaseStorageConfig {
  url: string;
  anonKey: string;
  bucket: string;
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

/** Load Supabase Storage configuration from environment variables (see .env.example). */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): SupabaseStorageConfig {
  return {
    url: env.SUPABASE_URL ?? "http://127.0.0.1:64321",
    anonKey: env.SUPABASE_ANON_KEY ?? "",
    bucket: env.SUPABASE_BUCKET ?? "supabase-storage-demo",
    demoPrefix: normalizePrefix(env.SUPABASE_DEMO_PREFIX ?? "demo/supabase-storage-client/"),
    keepDemoObject: parseBoolEnv(env.SUPABASE_KEEP_DEMO_OBJECT),
  };
}

/** True when the demo can talk to Supabase Storage (URL + anon key + bucket). */
export function isConfigured(cfg: SupabaseStorageConfig): boolean {
  return Boolean(cfg.url && cfg.anonKey && cfg.bucket);
}
