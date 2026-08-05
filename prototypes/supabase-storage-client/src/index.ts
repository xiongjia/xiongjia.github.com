import { execFile } from "node:child_process";
import { promisify } from "node:util";
import dotenv from "dotenv";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { isConfigured, loadConfig } from "./config.js";

const execFileAsync = promisify(execFile);

// Load env before anything reads process.env (module top-level, not inside
// main(), so future module-level code gets the variables too).
dotenv.config({ path: [".env.dev.local", ".env"] });

// Signed download URLs are short-lived by design; one constant keeps the
// printed section title and the actual expiry consistent. (Signed *upload*
// URLs have no client-side expiry — see signedUploadUrl.)
const SIGNED_URL_EXPIRES = 60; // seconds

/** Read the local project's anon key from `supabase status -o env`. */
async function fetchAnonKeyViaCli(): Promise<string> {
  try {
    const { stdout } = await execFileAsync("supabase", ["status", "-o", "env"], {
      timeout: 10000, // keep the dry-run fallback snappy when Docker is stalled
    });
    const match = stdout.match(/^ANON_KEY=(.*)$/m);
    const key = match ? match[1].trim() : "";
    return key.replace(/^"|"$/g, ""); // newer CLI versions quote the value
  } catch {
    return "";
  }
}

function section(title: string): void {
  console.log(`\n=== ${title} ===`);
}

async function listBuckets(client: SupabaseClient): Promise<void> {
  section("List buckets");
  const { data: buckets, error } = await client.storage.listBuckets();
  if (error) throw error;
  for (const b of buckets) {
    console.log(`  - ${b.name} (public: ${b.public})`);
  }
  if (buckets.length === 0) {
    console.log("  (no buckets)");
  }
}

/**
 * Make sure the bucket exists, creating it (private) when missing.
 * Returns true when this run created it — cleanup then deletes it; a
 * pre-existing bucket is only ever written under the demo prefix and is
 * left in place.
 */
/** True when the storage-api reports the bucket as missing. It signals this
 * as HTTP 404, or as HTTP 400 whose JSON body carries `statusCode: "404"`
 * — check both so the demo actually creates the bucket instead of
 * crashing on a "Bucket not found" error. */
function isBucketNotFound(error: unknown): boolean {
  if (!error) return false;
  const { status, statusCode } = error as { status?: number; statusCode?: string | number };
  return status === 404 || String(statusCode) === "404";
}

async function createBucketIfMissing(client: SupabaseClient, bucket: string): Promise<boolean> {
  section(`Ensure bucket: ${bucket}`);
  // storage-js reports a missing bucket as `{ data: null, error }` by
  // default, or as a thrown StorageApiError when `shouldThrowOnError` is
  // enabled — normalize both so a missing bucket always falls through to
  // createBucket below. Any other failure (network, auth, ...) is real and
  // must not be masked.
  let existing: Awaited<ReturnType<typeof client.storage.getBucket>>["data"] = null;
  try {
    const { data, error } = await client.storage.getBucket(bucket);
    if (error && !isBucketNotFound(error)) throw error;
    existing = data;
  } catch (err) {
    if (!isBucketNotFound(err)) throw err;
  }
  if (existing) {
    console.log("  (already exists — left in place after the run)");
    return false;
  }
  // Private by default — the demo never exposes objects to unauthenticated
  // GETs; access goes through signed URLs instead.
  const { data, error } = await client.storage.createBucket(bucket, { public: false });
  if (error) throw error;
  console.log(`  created (id: ${data?.name})`);
  return true;
}

async function listObjects(client: SupabaseClient, bucket: string, prefix: string): Promise<void> {
  section(`List objects (prefix: "${prefix}")`);
  const { data: files, error } = await client.storage.from(bucket).list(prefix, { limit: 20 });
  if (error) throw error;
  for (const f of files) {
    const size = f.metadata?.size;
    console.log(`  - ${f.name}${size != null ? ` (${size} bytes)` : ""}`);
  }
  if (files.length === 0) {
    console.log("  (no objects)");
  }
}

async function uploadObject(client: SupabaseClient, bucket: string, key: string): Promise<void> {
  section(`Upload object: ${key}`);
  const content = `Hello from supabase-storage-client prototype (${new Date().toISOString()})\n`;
  // upsert: true keeps repeated runs from failing with "Duplicate" on the
  // existing demo object — re-running the demo simply overwrites it.
  const { data, error } = await client.storage
    .from(bucket)
    .upload(key, Buffer.from(content), { contentType: "text/plain", upsert: true });
  if (error) throw error;
  console.log(`  uploaded (path: ${data?.path})`);
}

async function downloadObject(client: SupabaseClient, bucket: string, key: string): Promise<void> {
  section(`Download object: ${key}`);
  const { data, error } = await client.storage.from(bucket).download(key);
  if (error) throw error;
  // Whole-object in-memory read via Blob.text() — fine for the tiny demo
  // object; large files should stream instead.
  const text = await data.text();
  console.log(`  content: ${text.trim()}`);
}

async function signedDownloadUrl(
  client: SupabaseClient,
  bucket: string,
  key: string,
): Promise<void> {
  section(`Signed download URL (GET, expires in ${SIGNED_URL_EXPIRES}s): ${key}`);
  const { data, error } = await client.storage
    .from(bucket)
    .createSignedUrl(key, SIGNED_URL_EXPIRES, { download: true });
  if (error) throw error;
  console.log(`  ${data.signedUrl}`);
}

async function signedUploadUrl(client: SupabaseClient, bucket: string, key: string): Promise<void> {
  // A signed upload URL lets anyone with the link upload to this key without
  // credentials. Its lifetime is decided server-side (the default varies by
  // Storage API version), not by SIGNED_URL_EXPIRES. upsert: true keeps the
  // curl test repeatable: the demo object already exists (kept by
  // SUPABASE_KEEP_DEMO_OBJECT) and a non-upsert token rejects overwrites
  // with "Duplicate".
  section(`Signed upload URL (PUT, server-side expiry): ${key}`);
  const { data, error } = await client.storage
    .from(bucket)
    .createSignedUploadUrl(key, { upsert: true });
  if (error) throw error;
  console.log(`  ${data.signedUrl}`);
  console.log(`  (path: ${data.path}, token: ${data.token})`);
}

async function publicUrl(client: SupabaseClient, bucket: string, key: string): Promise<void> {
  // getPublicUrl is purely local (no network call): it stamps the URL scheme.
  // The demo bucket is private, so this URL returns 404 until the bucket is
  // made public — kept here to show the API, not as a working link.
  section(`Public URL (bucket is private → 404 until made public): ${key}`);
  const { data } = client.storage.from(bucket).getPublicUrl(key);
  console.log(`  ${data.publicUrl}`);
}

async function removeObject(client: SupabaseClient, bucket: string, key: string): Promise<void> {
  section(`Delete object: ${key}`);
  const { data, error } = await client.storage.from(bucket).remove([key]);
  if (error) throw error;
  console.log(`  removed: ${data.map((f) => f.name).join(", ")}`);
}

/** Remove the demo object if present — best-effort cleanup, never throws. */
async function removeObjectBestEffort(
  client: SupabaseClient,
  bucket: string,
  key: string,
): Promise<void> {
  await removeObject(client, bucket, key).catch((err: unknown) => {
    console.error(`  (cleanup of object failed: ${describeError(err)})`);
  });
}

/** Human-readable detail for a caught unknown error (never throws). */
function describeError(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (err && typeof err === "object") {
    try {
      return JSON.stringify(err) ?? String(err);
    } catch {
      return String(err);
    }
  }
  return String(err);
}

async function main(): Promise<void> {
  const cfg = loadConfig();

  // Zero-config local run: when the anon key is not set explicitly, pull it
  // from the running local project (`supabase status -o env`). Fails soft so
  // a missing key falls through to the dry-run instructions below.
  if (!cfg.anonKey) {
    const auto = await fetchAnonKeyViaCli();
    if (auto) {
      console.log("(SUPABASE_ANON_KEY not set — auto-read from `supabase status -o env`)");
      cfg.anonKey = auto;
    }
  }

  if (!isConfigured(cfg)) {
    console.log(
      [
        "Supabase Storage demo is not configured (dry-run, nothing to do).",
        "",
        "1. Start a local Supabase instance (Docker required):",
        "     supabase start",
        "",
        "2. Then run the demo — the anon key is auto-read from the CLI:",
        "     pnpm dev",
        "",
        "The URL (SUPABASE_URL) defaults to http://127.0.0.1:64321 and the",
        "bucket (SUPABASE_BUCKET) to supabase-storage-demo, so no .env file",
        "is needed for a plain local test. Copy .env.example to .env.dev.local",
        "only when you must override these (e.g. a non-local project).",
        "",
        "See README.md for the full local setup.",
      ].join("\n"),
    );
    return;
  }

  const client = createClient(cfg.url, cfg.anonKey);
  const bucket = cfg.bucket;
  const key = `${cfg.demoPrefix}hello.txt`;
  // Tracks whether this run created the bucket. Cleanup always removes the
  // demo object, but deletes the bucket only when this run created it — a
  // pre-existing bucket may hold unrelated data and must not be deleted.
  let bucketCreated = false;
  // Whether this run reached the bucket check: an early failure (e.g. Docker
  // down) never touched the bucket, so cleanup messages must not claim
  // anything about it.
  let bucketChecked = false;
  // Whether this run uploaded the demo object (drives the keep message).
  let objectUploaded = false;

  try {
    await listBuckets(client);
    bucketCreated = await createBucketIfMissing(client, bucket);
    bucketChecked = true;
    await listObjects(client, bucket, cfg.demoPrefix);
    await uploadObject(client, bucket, key);
    objectUploaded = true;
    await downloadObject(client, bucket, key);
    await signedDownloadUrl(client, bucket, key);
    await signedUploadUrl(client, bucket, key);
    await publicUrl(client, bucket, key);
  } finally {
    // Clean up so repeated runs never accumulate files or buckets (skip with
    // SUPABASE_KEEP_DEMO_OBJECT=true, e.g. to curl-test the signed upload URL
    // after the demo exits — see README). Messages stay honest on early
    // failures: a run that aborted before the bucket check has nothing to
    // clean up and must not claim the bucket pre-existed.
    if (cfg.keepDemoObject) {
      if (objectUploaded) {
        console.log("\n(keeping demo object and bucket — SUPABASE_KEEP_DEMO_OBJECT is set)");
      } else {
        console.log("\n(SUPABASE_KEEP_DEMO_OBJECT is set — nothing was uploaded this run)");
      }
    } else if (bucketCreated) {
      // Deleting a non-empty bucket fails; the object removal above runs
      // first. If the object cleanup failed the bucket deletion will too —
      // both are best-effort.
      await removeObjectBestEffort(client, bucket, key);
      const { error } = await client.storage.deleteBucket(bucket);
      if (error) {
        console.error(`  (cleanup of bucket failed: ${describeError(error)})`);
      } else {
        console.log("  (demo bucket deleted)");
      }
    } else if (bucketChecked) {
      // Bucket pre-existed: this run only touched keys under the demo prefix,
      // so remove the demo object and leave the bucket in place.
      await removeObjectBestEffort(client, bucket, key);
      console.log("  (bucket pre-existed — left in place)");
    } else {
      console.log("  (run failed before bucket setup — nothing to clean up)");
    }
  }
}

main().catch((err) => {
  console.error("Demo failed:", err);
  process.exit(1);
});
