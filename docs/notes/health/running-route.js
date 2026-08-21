// Running route map — MapLibre GL JS polyline viewer with PMTiles basemap

// Cached dependency load: the script/link are appended once, the pmtiles
// protocol registered once per page, not on every map open. A failed load
// resets the cache so the next open retries (transient network errors must
// not permanently break the map until reload).
let depsPromise = null;
function loadDeps() {
  if (!depsPromise) {
    depsPromise = (async () => {
      await Promise.all([
        new Promise((resolve) => {
          const link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css";
          link.onload = resolve;
          document.head.appendChild(link);
        }),
        new Promise((resolve, reject) => {
          const s = document.createElement("script");
          s.src = "https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js";
          s.onload = resolve;
          s.onerror = () => reject(new Error("MapLibre JS failed to load"));
          document.head.appendChild(s);
        }),
      ]);
      // register the pmtiles protocol exactly once
      const pmtiles = await import("https://esm.sh/pmtiles@4.4.1");
      const protocol = new pmtiles.Protocol();
      window.maplibregl.addProtocol("pmtiles", protocol.tile);
    })().catch((err) => {
      depsPromise = null; // allow retry on the next open
      throw err;
    });
  }
  return depsPromise;
}

function decodePolyline(encoded) {
  const coords = [];
  let index = 0, lat = 0, lng = 0, len = encoded.length;
  while (index < len) {
    let result = 0, shift = 0, byte;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;
    result = 0; shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;
    coords.push([lng / 1e5, lat / 1e5]);
  }
  return coords;
}

const pending = new Map();

async function openRouteMap(btn) {
  const runId = btn.dataset.routeId;
  const whenDur = btn.dataset.when || "";
  const splitsUrl = btn.dataset.splits;
  const pmtilesPrefix = btn.dataset.pmtiles;
  const glyphsUrl = btn.dataset.glyphs;
  if (pending.get(runId)) return;
  pending.set(runId, true);

  // Create the dialog lazily (no hidden <dialog> nodes in the DOM); removed
  // on close so repeated opens never accumulate. The close listener is
  // attached immediately so early-return paths (no data / few points) and
  // closes within the map's 100 ms init window can't leak the node.
  const dialog = document.createElement("dialog");
  dialog.style.cssText = "border:none;border-radius:8px;padding:0.5em;width:90vw;max-width:800px;";
  dialog.onclick = (e) => { if (e.target === dialog) dialog.close(); };
  document.body.appendChild(dialog);
  dialog.addEventListener("close", () => dialog.remove(), { once: true });

  try {
    await loadDeps();
    const maplibregl = window.maplibregl;
    if (!maplibregl) throw new Error("MapLibre not loaded");

    const resp = await fetch(splitsUrl);
    const data = await resp.json();
    const activity = data.activities.find((a) => a.run_id === runId);
    if (!activity || !activity.summary_polyline) {
      dialog.innerHTML = '<p style="padding:2em;text-align:center;color:var(--md-default-fg-color--light)">暂无路线数据</p>';
      dialog.showModal();
      return;
    }

    const coords = decodePolyline(activity.summary_polyline);
    if (coords.length < 2) {
      dialog.innerHTML = '<p style="padding:2em;text-align:center;color:var(--md-default-fg-color--light)">路线坐标不足</p>';
      dialog.showModal();
      return;
    }

    const bounds = coords.reduce(
      (b, c) => [[Math.min(b[0][0], c[0]), Math.min(b[0][1], c[1])], [Math.max(b[1][0], c[0]), Math.max(b[1][1], c[1])]],
      [coords[0], coords[0]]
    );

    const mapId = `route-map-${runId}`;
    dialog.innerHTML = `
      <style>
        #${mapId} .maplibregl-ctrl-attrib { display: none !important; }
      </style>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:0 0.5em 0.5em;border-bottom:1px solid var(--md-default-fg-color--lightest,#eee);margin-bottom:0.5em">
        <span style="font-size:0.9em;color:var(--md-default-fg-color--light)">🗺️ ${whenDur}</span>
        <form method="dialog" style="margin:0">
          <button style="border:none;background:none;cursor:pointer;font-size:1.2em;padding:0;line-height:1" aria-label="关闭">✕</button>
        </form>
      </div>
      <div id="${mapId}" style="width:100%;height:400px;border-radius:8px;overflow:hidden"></div>
      <div style="text-align:center;padding:0.5em 0 0.2em">
        <button id="reset-${runId}" style="padding:4px 14px;font-size:13px;border:1px solid var(--md-default-fg-color--lightest,#ddd);border-radius:6px;cursor:pointer;background:var(--md-default-bg-color,#fff);color:var(--md-typeset-a-color,#448aff)">⌖ 复位</button>
      </div>
    `;
    dialog.showModal();

    setTimeout(() => {
      const map = new maplibregl.Map({
        container: mapId,
        style: {
          version: 8,
          sources: {
            basemap: {
              type: "vector",
              url: pmtilesPrefix + "shanghai.pmtiles",
              attribution: '',
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#f8f4f0" } },
            { id: "water", type: "fill", source: "basemap", "source-layer": "water", paint: { "fill-color": "#a0c8e0" } },
            { id: "landuse", type: "fill", source: "basemap", "source-layer": "landuse", paint: { "fill-color": "#e8e0d8" } },
            { id: "roads", type: "line", source: "basemap", "source-layer": "roads", paint: { "line-color": "#fff", "line-width": 1.5 } },
            { id: "buildings", type: "fill", source: "basemap", "source-layer": "buildings", paint: { "fill-color": "#d4c8b8", "fill-opacity": 0.5 } },
          ],
          glyphs: glyphsUrl,
        },
        bounds: bounds,
        fitBoundsOptions: { padding: 40 },
      });

      document.getElementById(`reset-${runId}`).onclick = () => map.fitBounds(bounds, { padding: 40 });

      map.on("load", () => {
        map.addSource("route", {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } },
        });
        map.addLayer({
          id: "route-line", type: "line", source: "route",
          layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#40c463", "line-width": 4, "line-opacity": 0.8 },
        });
        new maplibregl.Marker({ color: "#30a14e" }).setLngLat(coords[0])
          .setPopup(new maplibregl.Popup({ offset: 25 }).setText("起点")).addTo(map);
        new maplibregl.Marker({ color: "#d73a49" }).setLngLat(coords[coords.length - 1])
          .setPopup(new maplibregl.Popup({ offset: 25 }).setText("终点")).addTo(map);
      });
      dialog.addEventListener("close", () => map.remove(), { once: true });
    }, 100);
  } catch (err) {
    console.error("Route map error:", err);
    dialog.innerHTML = `<p style="padding:2em;text-align:center;color:var(--md-default-fg-color--light)">地图加载失败${err.message ? ": " + err.message : ""}</p>`;
    dialog.showModal();
  } finally {
    pending.delete(runId);
  }
}

// Pace splits dialog — content arrives as JSON in the button's data-pace
// attribute (escaped by the macro); the <dialog> is created on click.
window.openPaceDialog = function (btn) {
  let data;
  try { data = JSON.parse(btn.dataset.pace); } catch { return; }
  const dlg = document.createElement("dialog");
  dlg.style.cssText = "border:none;border-radius:8px;padding:1em 1.5em;";
  dlg.onclick = (e) => { if (e.target === dlg) dlg.close(); };
  const rows = (data.rows || []).map((r) =>
    `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`
  ).join("");
  dlg.innerHTML =
    '<form method="dialog" style="float:right"><button style="border:none;background:none;cursor:pointer;" aria-label="关闭">✕</button></form>' +
    `<h3 style="margin-top:0">📊 ${data.when}</h3>` +
    `<p style="font-size:0.85em;color:var(--md-default-fg-color--light)">${data.name} · ${data.km} km · 配速 ${data.pace}</p>` +
    '<table style="font-size:0.9em;width:100%"><thead><tr><th>km</th><th>用时</th><th>配速</th><th>心率</th></tr></thead>' +
    `<tbody>${rows}</tbody></table>`;
  dlg.addEventListener("close", () => dlg.remove(), { once: true });
  document.body.appendChild(dlg);
  dlg.showModal();
};

window.openRouteMap = openRouteMap;

const ROUTE_COLORS = [
  "#e6194b", "#3cb44b", "#4363d8", "#f58231",
  "#911eb4", "#42d4f4", "#f032e6", "#bfef45",
  "#fabed4", "#469990",
];

// ── Inline multi-route map (auto-init from data attributes) ──

(function() {
  const container = document.getElementById("inline-routes-map");
  if (!container) return;
  const legend = document.getElementById("inline-routes-legend");

  const routesRaw = container.dataset.routes;
  const pmtilesPrefix = container.dataset.pmtiles;
  const glyphsUrl = container.dataset.glyphs;
  if (!routesRaw) return;

  let routes;
  try { routes = JSON.parse(routesRaw); } catch { return; }
  if (!routes.length) return;

  (async () => {
    try {
      await loadDeps();
      const maplibregl = window.maplibregl;
      if (!maplibregl) throw new Error("MapLibre not loaded");

      const decoded = routes.map((r, i) => ({
        ...r,
        coords: decodePolyline(r.polyline),
        color: ROUTE_COLORS[i % ROUTE_COLORS.length],
      })).filter((r) => r.coords.length >= 2);

      if (!decoded.length) return;

      const allCoords = decoded.flatMap((r) => r.coords);
      const bounds = allCoords.reduce(
        (b, c) => [[Math.min(b[0][0], c[0]), Math.min(b[0][1], c[1])], [Math.max(b[1][0], c[0]), Math.max(b[1][1], c[1])]],
        [allCoords[0], allCoords[0]]
      );

      container.style.position = "relative";

      const map = new maplibregl.Map({
        container: container,
        style: {
          version: 8,
          sources: { basemap: { type: "vector", url: pmtilesPrefix + "shanghai.pmtiles", attribution: '' } },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#f8f4f0" } },
            { id: "water", type: "fill", source: "basemap", "source-layer": "water", paint: { "fill-color": "#a0c8e0" } },
            { id: "landuse", type: "fill", source: "basemap", "source-layer": "landuse", paint: { "fill-color": "#e8e0d8" } },
            { id: "roads", type: "line", source: "basemap", "source-layer": "roads", paint: { "line-color": "#fff", "line-width": 1.5 } },
            { id: "buildings", type: "fill", source: "basemap", "source-layer": "buildings", paint: { "fill-color": "#d4c8b8", "fill-opacity": 0.5 } },
          ],
          glyphs: glyphsUrl,
        },
        bounds: bounds,
        fitBoundsOptions: { padding: 40 },
        attributionControl: false,
      });

      // Reset button (top-right of map)
      const resetBtn = document.createElement("button");
      resetBtn.innerHTML = "⌖";
      resetBtn.title = "复位";
      resetBtn.style.cssText = "position:absolute;top:8px;right:8px;z-index:10;width:32px;height:32px;font-size:18px;background:#fff;border:none;border-radius:4px;cursor:pointer;box-shadow:0 0 0 2px rgba(0,0,0,0.1);display:flex;align-items:center;justify-content:center;";
      resetBtn.onmouseenter = () => resetBtn.style.background = "#f0f0f0";
      resetBtn.onmouseleave = () => resetBtn.style.background = "#fff";
      resetBtn.onclick = () => map.fitBounds(bounds, { padding: 40 });
      container.appendChild(resetBtn);

      // Render checkboxes + legend
      if (legend) {
        legend.innerHTML = decoded.map((r, i) => {
          const cid = `rc-${r.run_id}`;
          return (
            `<label style="display:inline-flex;align-items:center;gap:0.3em;cursor:pointer;font-size:12px">` +
            `<input type="checkbox" id="${cid}" checked data-layer="il-${r.run_id}" style="accent-color:${r.color}">` +
            `<span style="width:10px;height:10px;border-radius:2px;background:${r.color};display:inline-block"></span>${r.date}</label>`
          );
        }).join("");

        legend.addEventListener("change", (e) => {
          if (e.target.matches("input[type=checkbox]")) {
            const layerId = e.target.dataset.layer;
            if (map.getLayer(layerId)) {
              map.setLayoutProperty(layerId, "visibility", e.target.checked ? "visible" : "none");
            }
          }
        });
      }

      map.on("load", () => {
        decoded.forEach((r) => {
          const srcId = `ir-${r.run_id}`;
          map.addSource(srcId, {
            type: "geojson",
            data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: r.coords } },
          });
          map.addLayer({
            id: `il-${r.run_id}`, type: "line", source: srcId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: { "line-color": r.color, "line-width": 3, "line-opacity": 0.7 },
          });
        });
      });
    } catch (err) {
      console.error("Inline route map error:", err);
    }
  })();
})();