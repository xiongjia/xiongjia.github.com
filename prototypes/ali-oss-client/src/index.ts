import dotenv from "dotenv";
import OSS from "ali-oss";
import { isConfigured, loadConfig, type OSSConfig } from "./config.js";

// Load env before anything reads process.env (module top-level, not inside
// main(), so future module-level code gets the variables too).
dotenv.config({ path: [".env.dev.local", ".env"] });

// Signed URLs are short-lived by design; one constant keeps the two printed
// section titles consistent (the README locates sections by title prefix).
const SIGNED_URL_EXPIRES = 60; // seconds

function createClient(cfg: OSSConfig): OSS {
  const options: OSS.Options = {
    region: cfg.region,
    accessKeyId: cfg.accessKeyId,
    accessKeySecret: cfg.accessKeySecret,
    bucket: cfg.bucket,
  };
  if (cfg.endpoint) {
    options.endpoint = cfg.endpoint;
  }
  return new OSS(options);
}

function section(title: string): void {
  console.log(`\n=== ${title} ===`);
}

async function listBuckets(client: OSS): Promise<void> {
  section("List buckets");
  // ali-oss 6.23 actually returns { buckets, owner, isTruncated, nextMarker, res },
  // not an array; buckets is null when the account has none. @types/ali-oss
  // declares the wrong return type, so cast to the real shape (see
  // node_modules/ali-oss/lib/bucket.js → listBuckets).
  const listResult = (await client.listBuckets({})) as unknown as {
    buckets: OSS.Bucket[] | null;
  };
  const buckets = listResult.buckets ?? [];
  for (const b of buckets) {
    console.log(`  - ${b.name} (region: ${b.region}, created: ${b.creationDate})`);
  }
  if (buckets.length === 0) {
    console.log("  (no buckets)");
  }
}

async function listObjects(client: OSS, prefix: string): Promise<void> {
  section(`List objects (prefix: "${prefix}")`);
  const result = await client.list({ prefix, "max-keys": 20 }, { timeout: 60000 });
  for (const obj of result.objects) {
    console.log(`  - ${obj.name} (${obj.size} bytes)`);
  }
  if (result.objects.length === 0) {
    console.log("  (no objects)");
  }
}

async function putObject(client: OSS, key: string): Promise<void> {
  section(`Put object: ${key}`);
  const content = `Hello from ali-oss-client prototype (${new Date().toISOString()})\n`;
  const result = await client.put(key, Buffer.from(content));
  console.log(`  status=${result.res.status}, name=${result.name}`);
}

async function getObject(client: OSS, key: string): Promise<void> {
  section(`Get object: ${key}`);
  const result = await client.get(key);
  console.log(`  status=${result.res.status}`);
  const content = result.content ? result.content.toString().trim() : "<empty>";
  console.log(`  content: ${content}`);
}

async function signedDownloadUrl(client: OSS, key: string): Promise<void> {
  section(`Signed download URL (GET, expires in ${SIGNED_URL_EXPIRES}s): ${key}`);
  const url = client.signatureUrl(key, { expires: SIGNED_URL_EXPIRES, method: "GET" });
  console.log(`  ${url}`);
}

async function signedUploadUrl(client: OSS, key: string): Promise<void> {
  // A signed PUT URL lets anyone with the link upload to this key until it
  // expires. The signature binds method + key + Content-Type: the uploader
  // must send the exact same Content-Type (text/plain for the demo object)
  // or OSS answers 403 SignatureDoesNotMatch.
  section(`Signed upload URL (PUT, expires in ${SIGNED_URL_EXPIRES}s): ${key}`);
  const url = client.signatureUrl(key, {
    expires: SIGNED_URL_EXPIRES,
    method: "PUT",
    "Content-Type": "text/plain",
  });
  console.log(`  ${url}`);
}

async function deleteObject(client: OSS, key: string): Promise<void> {
  section(`Delete object: ${key}`);
  const result = await client.delete(key);
  console.log(`  status=${result.res.status}`);
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

  if (!isConfigured(cfg)) {
    console.log(
      [
        "Aliyun OSS demo is not configured (dry-run, nothing to do).",
        "",
        "Copy .env.example to .env.dev.local and fill in:",
        "  ALIYUN_OSS_REGION             e.g. oss-cn-hangzhou",
        "  ALIYUN_OSS_BUCKET             your bucket name",
        "  ALIYUN_OSS_ACCESS_KEY_ID      RAM user AccessKey ID",
        "  ALIYUN_OSS_ACCESS_KEY_SECRET  RAM user AccessKey Secret",
        "",
        "See README.md for how to create the RAM user, bucket, and keys.",
      ].join("\n"),
    );
    return;
  }

  const client = createClient(cfg);
  const key = `${cfg.demoPrefix}hello.txt`;

  try {
    await listBuckets(client);
    await listObjects(client, cfg.demoPrefix);
    await putObject(client, key);
    await getObject(client, key);
    await signedDownloadUrl(client, key);
    await signedUploadUrl(client, key);
  } finally {
    // Clean up the demo object so repeated runs never accumulate files
    // (skip with ALIYUN_OSS_KEEP_DEMO_OBJECT=true, e.g. to curl-test the
    // signed upload URL after the demo exits — see README).
    if (cfg.keepDemoObject) {
      console.log("\n(keeping demo object — ALIYUN_OSS_KEEP_DEMO_OBJECT is set)");
    } else {
      await deleteObject(client, key).catch((err: unknown) => {
        const detail = describeError(err);
        console.error(`  (cleanup failed: ${detail})`);
      });
    }
  }
}

main().catch((err) => {
  console.error("Demo failed:", err);
  process.exit(1);
});
