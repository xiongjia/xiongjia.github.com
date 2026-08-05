import dotenv from "dotenv";
import {
  CreateBucketCommand,
  DeleteBucketCommand,
  DeleteObjectCommand,
  GetObjectCommand,
  HeadBucketCommand,
  ListBucketsCommand,
  ListObjectsV2Command,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { isConfigured, loadConfig, type R2Config } from "./config.js";

// Load env before anything reads process.env (module top-level, not inside
// main(), so future module-level code gets the variables too).
dotenv.config({ path: [".env.dev.local", ".env"] });

// Presigned URLs are short-lived by design; one constant keeps the printed
// section titles consistent (the README locates sections by title prefix).
const SIGNED_URL_EXPIRES = 60; // seconds

function createClient(cfg: R2Config): S3Client {
  return new S3Client({
    region: cfg.region,
    endpoint: cfg.endpoint,
    forcePathStyle: cfg.forcePathStyle,
    // Newer SDK versions default to requestChecksumCalculation:
    // "WHEN_SUPPORTED", which stamps a CRC32 header onto every PutObject.
    // "WHEN_REQUIRED" keeps uploads plain — accepted by every S3-compatible
    // endpoint (R2, MinIO, ...) and the demo has no use for checksum
    // verification.
    requestChecksumCalculation: "WHEN_REQUIRED",
    credentials: {
      accessKeyId: cfg.accessKeyId,
      secretAccessKey: cfg.secretAccessKey,
    },
  });
}

function section(title: string): void {
  console.log(`\n=== ${title} ===`);
}

/** True when the AWS error is a 404 (missing bucket/object, HEAD probe). */
function isNotFound(err: unknown): boolean {
  const status = (err as { $metadata?: { httpStatusCode?: number } })?.$metadata?.httpStatusCode;
  return status === 404;
}

async function listBuckets(client: S3Client): Promise<void> {
  section("List buckets");
  // Needs the ListAllMyBuckets permission — R2 API tokens with "Admin Read &
  // Write" carry it; object-only tokens ("Object Read & Write") do not.
  const { Buckets } = await client.send(new ListBucketsCommand({}));
  for (const b of Buckets ?? []) {
    const created = b.CreationDate ? `, created: ${b.CreationDate.toISOString()}` : "";
    console.log(`  - ${b.Name}${created}`);
  }
  if ((Buckets ?? []).length === 0) {
    console.log("  (no buckets)");
  }
}

/**
 * Make sure the bucket exists, creating it when missing. Returns true when
 * this run created it — cleanup then deletes it; a pre-existing bucket is
 * only ever written under the demo prefix and is left in place.
 */
async function ensureBucket(client: S3Client, bucket: string): Promise<boolean> {
  section(`Ensure bucket: ${bucket}`);
  try {
    await client.send(new HeadBucketCommand({ Bucket: bucket }));
    console.log("  (already exists — left in place after the run)");
    return false;
  } catch (err) {
    // Only a 404 means "missing"; anything else (network, auth) is real and
    // must not be masked.
    if (!isNotFound(err)) throw err;
  }
  // R2 buckets are private by default, so no extra config is needed for a
  // private demo bucket.
  await client.send(new CreateBucketCommand({ Bucket: bucket }));
  console.log("  created");
  return true;
}

async function listObjects(client: S3Client, bucket: string, prefix: string): Promise<void> {
  section(`List objects (prefix: "${prefix}")`);
  const { Contents } = await client.send(
    new ListObjectsV2Command({ Bucket: bucket, Prefix: prefix, MaxKeys: 20 }),
  );
  for (const obj of Contents ?? []) {
    console.log(`  - ${obj.Key} (${obj.Size} bytes)`);
  }
  if ((Contents ?? []).length === 0) {
    console.log("  (no objects)");
  }
}

async function putObject(client: S3Client, bucket: string, key: string): Promise<void> {
  section(`Put object: ${key}`);
  const content = `Hello from r2-client prototype (${new Date().toISOString()})\n`;
  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: Buffer.from(content),
      ContentType: "text/plain",
    }),
  );
  console.log("  uploaded");
}

async function getObject(client: S3Client, bucket: string, key: string): Promise<void> {
  section(`Get object: ${key}`);
  const { Body, ContentType } = await client.send(
    new GetObjectCommand({ Bucket: bucket, Key: key }),
  );
  // Whole-object in-memory read via transformToString() — fine for the tiny
  // demo object; large files should stream instead.
  const text = await Body?.transformToString();
  console.log(`  content-type: ${ContentType ?? "?"}`);
  console.log(`  content: ${text?.trim() ?? "<empty>"}`);
}

async function presignedDownloadUrl(client: S3Client, bucket: string, key: string): Promise<void> {
  section(`Presigned download URL (GET, expires in ${SIGNED_URL_EXPIRES}s): ${key}`);
  const url = await getSignedUrl(client, new GetObjectCommand({ Bucket: bucket, Key: key }), {
    expiresIn: SIGNED_URL_EXPIRES,
  });
  console.log(`  ${url}`);
}

async function presignedUploadUrl(client: S3Client, bucket: string, key: string): Promise<void> {
  // A presigned PUT URL lets anyone with the link upload to this key until
  // it expires. The SigV4 signature binds the HTTP method and the object
  // key; Content-Type is *not* part of an S3-style presigned signature, so
  // a plain curl PUT works without any special headers (passing one anyway
  // only controls the stored object's metadata).
  section(`Presigned upload URL (PUT, expires in ${SIGNED_URL_EXPIRES}s): ${key}`);
  const url = await getSignedUrl(
    client,
    new PutObjectCommand({ Bucket: bucket, Key: key, ContentType: "text/plain" }),
    { expiresIn: SIGNED_URL_EXPIRES },
  );
  console.log(`  ${url}`);
}

async function deleteObject(client: S3Client, bucket: string, key: string): Promise<void> {
  section(`Delete object: ${key}`);
  // S3-style deletion is idempotent: deleting a missing key also succeeds.
  await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key }));
  console.log("  deleted");
}

/** Remove the demo object if present — best-effort cleanup, never throws. */
async function deleteObjectBestEffort(
  client: S3Client,
  bucket: string,
  key: string,
): Promise<void> {
  await deleteObject(client, bucket, key).catch((err: unknown) => {
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

  if (!isConfigured(cfg)) {
    console.log(
      [
        "Cloudflare R2 demo is not configured (dry-run, nothing to do).",
        "",
        "Local test (no Cloudflare account):",
        "  1. pnpm minio:start",
        "  2. in .env.dev.local:",
        "     R2_ENDPOINT=http://127.0.0.1:9000",
        "     R2_FORCE_PATH_STYLE=true",
        "     R2_REGION=us-east-1",
        "     R2_ACCESS_KEY_ID=minioadmin",
        "     R2_SECRET_ACCESS_KEY=minioadmin",
        "     R2_BUCKET=r2-client-demo",
        "  3. pnpm dev",
        "",
        "Real Cloudflare R2: copy .env.example to .env.dev.local and fill in:",
        "  R2_ACCOUNT_ID          your Cloudflare account ID",
        "  R2_ACCESS_KEY_ID       R2 API token access key",
        "  R2_SECRET_ACCESS_KEY   R2 API token secret",
        "  R2_BUCKET              your bucket name",
        "",
        "See README.md for the full setup.",
      ].join("\n"),
    );
    return;
  }

  const client = createClient(cfg);
  const bucket = cfg.bucket;
  const key = `${cfg.demoPrefix}hello.txt`;
  // Tracks whether this run created the bucket. Cleanup always removes the
  // demo object, but deletes the bucket only when this run created it — a
  // pre-existing bucket may hold unrelated data and must not be deleted.
  let bucketCreated = false;
  // Whether this run reached the bucket check: an early failure (e.g. MinIO
  // down) never touched the bucket, so cleanup messages must not claim
  // anything about it.
  let bucketChecked = false;
  // Whether this run uploaded the demo object (drives the keep message).
  let objectUploaded = false;

  try {
    await listBuckets(client);
    bucketCreated = await ensureBucket(client, bucket);
    bucketChecked = true;
    await listObjects(client, bucket, cfg.demoPrefix);
    await putObject(client, bucket, key);
    objectUploaded = true;
    await getObject(client, bucket, key);
    await presignedDownloadUrl(client, bucket, key);
    await presignedUploadUrl(client, bucket, key);
  } finally {
    // Clean up so repeated runs never accumulate files or buckets (skip with
    // R2_KEEP_DEMO_OBJECT=true, e.g. to curl-test the presigned upload URL
    // after the demo exits — see README). Messages stay honest on early
    // failures: a run that aborted before the bucket check has nothing to
    // clean up and must not claim the bucket pre-existed.
    if (cfg.keepDemoObject) {
      if (objectUploaded) {
        console.log("\n(keeping demo object and bucket — R2_KEEP_DEMO_OBJECT is set)");
      } else {
        console.log("\n(R2_KEEP_DEMO_OBJECT is set — nothing was uploaded this run)");
      }
    } else if (bucketCreated) {
      // Deleting a non-empty bucket fails; the object removal above runs
      // first. If the object cleanup failed the bucket deletion will too —
      // both are best-effort.
      await deleteObjectBestEffort(client, bucket, key);
      try {
        await client.send(new DeleteBucketCommand({ Bucket: bucket }));
        console.log("  (demo bucket deleted)");
      } catch (err) {
        console.error(`  (cleanup of bucket failed: ${describeError(err)})`);
      }
    } else if (bucketChecked) {
      // Bucket pre-existed: this run only touched keys under the demo prefix,
      // so remove the demo object and leave the bucket in place.
      await deleteObjectBestEffort(client, bucket, key);
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
