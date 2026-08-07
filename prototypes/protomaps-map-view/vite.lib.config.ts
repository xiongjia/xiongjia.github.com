import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Library build for the embeddable map widget (see src/widget.tsx).
 * Produces `dist/widget/map-widget.js` (ESM, react bundled in) +
 * `dist/widget/map-widget.css`. The dev/preview-only plugins
 * (local-tiles, glyph-proxy) are intentionally not included — the widget
 * takes basemap/glyphs URLs as parameters at runtime.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    lib: {
      entry: "src/widget.tsx",
      formats: ["es"],
      fileName: "map-widget",
    },
    cssCodeSplit: false,
    outDir: "dist/widget",
  },
});
