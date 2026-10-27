#!/usr/bin/env node
/**
 * Parallel, resumable download of the Camoufox Firefox build, then install it.
 *
 * Why this exists: the asset is ~1.3 GB on GitHub releases. A plain request is
 * redirected to release-assets.githubusercontent.com (dropped on many networks),
 * and the mirrors that do serve it cap a single connection at roughly 1.3 MB/s.
 * Range requests are served directly (no redirect) and adding connections lifts
 * the ceiling to ~1.7 MB/s here, so this splits the file into chunks, keeps each
 * finished chunk on disk (a dropped connection resumes instead of restarting)
 * and verifies the sha256 the release advertises.
 *
 *   pnpm camoufox:download                      # mirror chunks → install
 *   CAMOUFOX_MIRROR=https://gh-proxy.com/ pnpm camoufox:download
 *   CONCURRENCY=32 pnpm camoufox:download       # more connections
 *   pnpm camoufox:download --no-install         # only produce the zip
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { CamoufoxFetcher } from "camoufox";

const MIRROR = process.env.CAMOUFOX_MIRROR ?? "https://ghfast.top/";
const CONCURRENCY = Number(process.env.CONCURRENCY ?? 8);
const CHUNK = Number(process.env.CHUNK_MB ?? 16) * 1024 * 1024;
const RETRIES = Number(process.env.RETRIES ?? 8);
const installAfter = !process.argv.includes("--no-install");

const mb = (bytes) => `${(bytes / 1048576).toFixed(1)} MB`;

/** Resolves the pinned asset URL/digest without downloading the build itself. */
class Resolver extends CamoufoxFetcher {
  static async downloadFile() {
    throw new Error("resolver never downloads");
  }

  async acceptRelease() {
    this.installedInterface = 1;
    return true;
  }
}

async function sha256(file) {
  const hash = createHash("sha256");
  await pipeline(createReadStream(file), hash);
  return hash.digest("hex");
}

async function main() {
  const fetcher = await new Resolver().init();
  const url = `${MIRROR}${fetcher.url}`;
  const out = join(
    tmpdir(),
    `camoufox-${fetcher.verstr}-${process.platform}-${process.arch}.zip`,
  );
  const partsDir = `${out}.parts`;

  const head = await fetch(url, { method: "HEAD", redirect: "follow" });
  const size = Number(head.headers.get("content-length"));
  if (!size) {
    throw new Error(`no content-length from ${url} (HTTP ${head.status})`);
  }
  const total = Math.ceil(size / CHUNK);

  console.log(`camoufox ${fetcher.verstr}`);
  console.log(`  source : ${url}`);
  console.log(`  target : ${out}`);
  console.log(
    `  size   : ${mb(size)} · ${total} chunks · ${CONCURRENCY} at a time`,
  );

  const existingZip = await stat(out).catch(() => null);
  if (existingZip?.size !== size) {
    await mkdir(partsDir, { recursive: true });
    await rm(out, { force: true });

    const chunkPath = (index) =>
      join(partsDir, `${String(index).padStart(4, "0")}.part`);
    const chunkSize = (index) => Math.min(CHUNK, size - index * CHUNK);
    const startedAt = Date.now();
    let finished = 0;
    let bytes = 0;

    const progress = () => {
      const rate = bytes / ((Date.now() - startedAt) / 1000 || 1);
      const eta = rate > 0 ? (size - bytes) / rate : 0;
      process.stdout.write(
        `\r  ${finished}/${total} chunks  ${mb(bytes)}/${mb(size)}  ${mb(rate)}/s  ` +
          `ETA ${Math.ceil(eta / 60)}m      `,
      );
    };

    const downloadChunk = async (index) => {
      const file = chunkPath(index);
      const expected = chunkSize(index);

      const done = await stat(file).catch(() => null);
      if (done?.size === expected) {
        finished += 1;
        bytes += expected;
        progress();
        return;
      }
      bytes -= done?.size ?? 0;

      const from = index * CHUNK;
      const to = from + expected - 1;
      for (let attempt = 1; attempt <= RETRIES; attempt += 1) {
        try {
          const response = await fetch(url, {
            headers: { Range: `bytes=${from}-${to}` },
            signal: AbortSignal.timeout(120_000),
          });
          if (response.status !== 206 && response.status !== 200) {
            const retryAfter = Number(response.headers.get("retry-after"));
            const wait =
              Number.isFinite(retryAfter) && retryAfter > 0
                ? retryAfter * 1_000
                : 2_000 * attempt;
            throw new Error(`HTTP ${response.status} (retry in ${wait}ms)`);
          }
          if (!response.body) {
            throw new Error("empty body");
          }
          await pipeline(
            Readable.fromWeb(response.body),
            createWriteStream(file),
          );
          const written = (await stat(file)).size;
          if (written !== expected) {
            throw new Error(`short read ${written}/${expected}`);
          }
          finished += 1;
          bytes += written;
          progress();
          return;
        } catch (error) {
          if (attempt === RETRIES) {
            throw new Error(
              `chunk ${index} failed after ${RETRIES} tries: ${error.message}`,
              { cause: error },
            );
          }
          // 429s mean the mirror wants fewer simultaneous requests: back off
          // harder the more often we hit them.
          const backoff = /HTTP 429/.test(String(error))
            ? 5_000 * attempt
            : 1_000 * attempt;
          await new Promise((resolve) => setTimeout(resolve, backoff));
        }
      }
    };

    const queue = Array.from({ length: total }, (_, index) => index);
    await Promise.all(
      Array.from({ length: Math.min(CONCURRENCY, total) }, async () => {
        for (
          let index = queue.shift();
          index !== undefined;
          index = queue.shift()
        ) {
          await downloadChunk(index);
        }
      }),
    );
    process.stdout.write("\n");

    const parts = (await readdir(partsDir)).sort();
    for (const part of parts) {
      await pipeline(
        createReadStream(join(partsDir, part)),
        createWriteStream(out, { flags: "a" }),
      );
    }
    await rm(partsDir, { recursive: true, force: true });
  } else {
    console.log("  zip already downloaded.");
  }

  const digest = await sha256(out);
  const expected = fetcher.installedSha256;
  if (expected && digest !== expected) {
    await rm(out, { force: true });
    throw new Error(
      `sha256 mismatch (got ${digest}, expected ${expected}) — zip removed`,
    );
  }
  console.log(
    `  sha256 : ${digest.slice(0, 16)}… ${expected ? "verified" : "not advertised"}`,
  );

  if (!installAfter) {
    console.log(`\nInstall later:\n  CAMOUFOX_ZIP=${out} pnpm camoufox:fetch`);
    return;
  }

  console.log("\nInstalling…");
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["scripts/fetch-camoufox.mjs"], {
      stdio: "inherit",
      env: { ...process.env, CAMOUFOX_ZIP: out },
    });
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`install exited with ${code}`)),
    );
  });
}

main().catch((error) => {
  console.error(`\ncamoufox:download failed: ${error.message}`);
  process.exit(1);
});
