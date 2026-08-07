import { createReadStream } from "node:fs";
import { mkdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import type { Connect, Plugin } from "vite";
import { parseRange } from "./src/lib/http-range.ts";

/**
 * Serve a local tiles directory (e.g. `.cache/pmtiles/`, gitignored) on the
 * dev AND preview servers, so `pmtiles:///pmtiles/xxx.pmtiles` resolves against the
 * Vite origin (same-origin, no CORS). The pmtiles protocol reads the file via
 * HTTP Range requests, so the middleware implements Range/206 support.
 */
function localTilesPlugin(tilesDir: string): Plugin {
  const root = path.resolve(process.cwd(), tilesDir);
  const segment = tilesDir.split(/[\\/]/).filter(Boolean).pop() ?? "pmtiles";
  const mount = `/${segment}`;

  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const url = (req.url ?? "").split("?")[0];
    if (!url.startsWith(`${mount}/`)) return next();

    let rel: string;
    try {
      rel = decodeURIComponent(url.slice(mount.length + 1));
    } catch {
      return next();
    }
    const file = path.join(root, rel);
    if (!file.startsWith(root + path.sep)) return next();

    void (async () => {
      let info;
      try {
        info = await stat(file);
      } catch {
        return next();
      }
      if (!info.isFile()) return next();

      res.statusCode = 200;
      res.setHeader("Accept-Ranges", "bytes");
      res.setHeader("Content-Type", "application/octet-stream");
      res.setHeader("Content-Length", String(info.size));

      if (req.method === "HEAD") {
        res.end();
        return;
      }

      const range = parseRange(req.headers.range, info.size);
      if (range.status === "ok") {
        res.statusCode = 206;
        res.setHeader("Content-Range", `bytes ${range.start}-${range.end}/${info.size}`);
        res.setHeader("Content-Length", String(range.end - range.start + 1));
        createReadStream(file, { start: range.start, end: range.end }).pipe(res);
        return;
      }
      if (range.status === "unsatisfiable") {
        res.statusCode = 416;
        res.setHeader("Content-Range", `bytes */${info.size}`);
        res.end();
        return;
      }
      // "ignore": no / unparseable / multi-range header — RFC 7233 allows
      // returning the full 200 response.
      createReadStream(file).pipe(res);
    })();
  };

  return {
    name: "local-tiles",
    configureServer(server) {
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
    },
  };
}

/** Glyph upstream per source (mirrors scripts/warm-glyphs.ts). */
const GLYPHS_SOURCES: Record<string, string> = {
  protomaps: "https://protomaps.github.io/basemaps-assets/fonts",
  maplibre: "https://demotiles.maplibre.org/font",
};

/**
 * Serve label glyphs (`/glyphs/{fontstack}/{range}.pbf`) from a gitignored
 * local cache dir, downloading from the upstream fonts host on first request.
 * After a warm-up pass the map runs fully offline (no external requests).
 * Ranges the upstream doesn't provide (404) are not cached.
 */
function glyphProxyPlugin(cacheDir: string, upstream: string): Plugin {
  const cacheRoot = path.resolve(process.cwd(), cacheDir);

  const handler: Connect.NextHandleFunction = (req, res, next) => {
    const url = (req.url ?? "").split("?")[0];
    if (!url.startsWith("/glyphs/")) return next();

    let rel: string;
    try {
      rel = decodeURIComponent(url.slice("/glyphs/".length));
    } catch {
      return next();
    }
    const file = path.join(cacheRoot, rel);
    if (!file.startsWith(cacheRoot + path.sep)) return next();

    void (async () => {
      // Serve from cache when present.
      try {
        const info = await stat(file);
        if (info.isFile()) {
          res.setHeader("Content-Type", "application/x-protobuf");
          res.setHeader("Content-Length", String(info.size));
          createReadStream(file).pipe(res);
          return;
        }
      } catch {
        // not cached yet
      }
      // Download once from upstream, then serve.
      try {
        const r = await fetch(`${upstream}/${rel}`);
        if (!r.ok) {
          res.statusCode = r.status;
          res.end();
          return;
        }
        const buf = Buffer.from(await r.arrayBuffer());
        await mkdir(path.dirname(file), { recursive: true });
        await writeFile(file, buf);
        res.setHeader("Content-Type", "application/x-protobuf");
        res.setHeader("Content-Length", String(buf.length));
        res.end(buf);
      } catch {
        next();
      }
    })();
  };

  return {
    name: "glyph-proxy",
    configureServer(server) {
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [
      react(),
      tailwindcss(),
      localTilesPlugin(env.VITE_PMTILES_DIR ?? ".cache/pmtiles"),
      glyphProxyPlugin(
        env.VITE_GLYPHS_DIR ?? ".cache/glyphs",
        GLYPHS_SOURCES[env.VITE_GLYPHS_SRC ?? "protomaps"] ?? GLYPHS_SOURCES.protomaps,
      ),
    ],
    server: { host: "127.0.0.1", port: 5173 },
    preview: { host: "127.0.0.1", port: 4173 },
  };
});
