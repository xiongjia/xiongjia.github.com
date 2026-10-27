#!/usr/bin/env node
/**
 * Install the Camoufox Firefox build without ever touching python.
 *
 * `npx camoufox fetch` asks GitHub releases for the zip, and on networks where
 * github.com downloads are dropped that stalls for 20s per repo until it gives
 * up. This script reuses the package's own fetcher (same pin, same sha256
 * verification, same install layout under ~/Library/Caches/camoufox) but routes
 * the asset download through a GitHub mirror.
 *
 *   pnpm camoufox:fetch                                  # default mirror
 *   CAMOUFOX_MIRROR= pnpm camoufox:fetch                 # direct GitHub
 *   CAMOUFOX_MIRROR=https://gh-proxy.com/ pnpm camoufox:fetch
 *   CAMOUFOX_ZIP=/tmp/camoufox.zip pnpm camoufox:fetch   # install a zip you
 *                                                        # downloaded elsewhere
 */
import { createReadStream } from "node:fs";
import { CamoufoxFetcher } from "camoufox";

const MIRROR = process.env.CAMOUFOX_MIRROR ?? "https://ghfast.top/";
const LOCAL_ZIP = process.env.CAMOUFOX_ZIP;
const GITHUB = "https://github.com/";

/** Prefix a GitHub asset URL with the mirror (mirrors expect the full URL). */
const mirrored = (url) =>
  MIRROR && url.startsWith(GITHUB) ? `${MIRROR}${url}` : url;

class MirroredFetcher extends CamoufoxFetcher {
  static async downloadFile(file, url) {
    if (LOCAL_ZIP) {
      // Already downloaded (e.g. from a fast network): copy into the temp file
      // the installer expects; its sha256 check still runs.
      await new Promise((resolve, reject) => {
        const from = createReadStream(LOCAL_ZIP);
        from
          .on("error", reject)
          .pipe(file)
          .on("finish", resolve)
          .on("error", reject);
      });
      return;
    }
    return CamoufoxFetcher.downloadFile(file, mirrored(url));
  }

  // The stock check downloads the release's manifest.json, i.e. the same
  // blocked host. Interface 1 is what every current build declares.
  async acceptRelease() {
    this.installedInterface = 1;
    return true;
  }
}

const fetcher = await new MirroredFetcher().init();
console.log(
  `camoufox ${fetcher.verstr} → installing from ${
    LOCAL_ZIP ?? MIRROR ?? "github.com"
  }`,
);
const installed = await fetcher.install();
console.log(installed ? "installed." : "already installed.");
