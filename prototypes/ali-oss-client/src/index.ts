import "dotenv/config";
import OSS from "ali-oss";
import { isConfigured, loadConfig, type OSSConfig } from "./config.js";

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
  const buckets = await client.listBuckets(null);
  for (const b of buckets) {
    console.log(`  - ${b.name} (region: ${b.region}, created: ${b.creationDate})`);
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

async function signedUrl(client: OSS, key: string): Promise<void> {
  section(`Signed URL (GET, expires in 60s): ${key}`);
  const url = client.signatureUrl(key, { expires: 60, method: "GET" });
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
        "Copy .env.example to .env and fill in:",
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
    await signedUrl(client, key);
  } finally {
    // Clean up the demo object so repeated runs never accumulate files.
    await deleteObject(client, key).catch((err: unknown) => {
      const detail = describeError(err);
      console.error(`  (cleanup failed: ${detail})`);
    });
  }
}

main().catch((err) => {
  console.error("Demo failed:", err);
  process.exit(1);
});
