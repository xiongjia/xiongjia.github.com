/**
 * Shared map dialog logic for moment detail & timeline pages.
 *
 * One dialog per page (`#moment-map-dialog` with `#moment-map-host`); any
 * element marked `data-map-toggle` carries the moment's geo data and opens
 * the dialog. The widget is `import()`ed lazily; every open swaps in a
 * BRAND-NEW host element (vine's createMapWidget calls createRoot on the
 * container — reusing one renders duplicate maps), destroying the previous
 * instance first. A `loading` lock ignores re-entry while import() is in
 * flight.
 */
export function initMomentDialog(mapCfg) {
    const dialog = document.getElementById("moment-map-dialog");
    if (!dialog) return;
    let widget = null;
    let loading = false;

    // popupContent is trusted HTML in the widget; moment data is authored
    // markdown, so escape everything dynamic before embedding
    function esc(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[c]));
    }

    // the widget needs a WebGL context; without one maplibre fails asynchronously
    // and the dialog stays a blank box (looks like a dead button). Probe each
    // context type on a FRESH canvas — reusing one canvas after a failed
    // context request is unreliable in some browsers.
    function hasWebgl() {
        const probe = (type) => {
            try {
                return !!document.createElement("canvas").getContext(type);
            } catch {
                return false;
            }
        };
        return (
            !!(window.WebGL2RenderingContext && probe("webgl2")) ||
            !!(window.WebGLRenderingContext &&
                (probe("webgl") || probe("experimental-webgl")))
        );
    }

    // import() can hang on slow/blocked CDNs; never leave the loading lock
    // stuck (that silently kills every later click) — race a timeout and
    // clear the timer once either side settles. The timeout error carries a
    // stable code so the catch below can branch without string matching.
    const importWidget = () => {
        let timer;
        const timeout = new Promise((_, reject) => {
            timer = setTimeout(() => {
                const err = new Error("widget import timed out");
                err.code = "MOMENT_WIDGET_TIMEOUT";
                reject(err);
            }, 15000);
        });
        return Promise.race([import(mapCfg.widget_js), timeout]).finally(() =>
            clearTimeout(timer)
        );
    };

    const open = async (btn) => {
        if (loading) return; // ignore re-entry while import() is in flight
        loading = true;
        if (widget) {
            widget.destroy();
            widget = null;
        }
        const oldHost = document.getElementById("moment-map-host");
        if (!oldHost) {
            loading = false;
            return;
        }
        const newHost = oldHost.cloneNode(false); // fresh div, same data-*
        for (const k of ["lng", "lat", "region", "place", "emoji", "title", "image", "text"]) {
            newHost.dataset[k] = btn.dataset[k] || "";
        }
        oldHost.replaceWith(newHost);
        const title = document.getElementById("moment-dialog-title");
        if (title) title.textContent = "📍 " + (btn.dataset.place || btn.dataset.region || "");
        dialog.showModal();
        newHost.textContent = "⌛ 加载地图…";
        if (!hasWebgl()) {
            newHost.textContent = "浏览器无法创建 WebGL 上下文，无法显示地图";
            loading = false;
            return;
        }
        try {
            const { createMapWidget } = await importWidget();
            if (!newHost.isConnected) return; // dialog closed while loading
            const regionCfg =
                mapCfg.regions[newHost.dataset.region] ||
                mapCfg.regions[mapCfg.default_region] ||
                {};
            const lng = parseFloat(newHost.dataset.lng);
            const lat = parseFloat(newHost.dataset.lat);
            if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
                newHost.textContent = "坐标无效";
                return;
            }
            const img = newHost.dataset.image
                ? `<img class="moment-popup-img" src="${esc(newHost.dataset.image)}" alt="" loading="lazy">`
                : "";
            const txt = newHost.dataset.text || newHost.dataset.place || newHost.dataset.title || "";
            widget = createMapWidget(newHost, {
                basemapUrl:
                    mapCfg.pmtiles_prefix +
                    (newHost.dataset.region || mapCfg.default_region) +
                    ".pmtiles",
                glyphsUrl: mapCfg.glyphs_url,
                attribution: mapCfg.attribution || undefined,
                // auto-center on the moment's marker (POI zoom)
                center: [lng, lat],
                zoom: Math.max(regionCfg.zoom || 12, 14),
                markers: [
                    {
                        lng,
                        lat,
                        label: newHost.dataset.place || undefined,
                        emoji: newHost.dataset.emoji || undefined,
                        popupContent: img + `<div class="moment-popup-text">${esc(txt)}</div>`,
                    },
                ],
            });
        } catch (err) {
            console.error("[moment] map widget failed to load:", err);
            if (newHost.isConnected) {
                newHost.textContent = err.code === "MOMENT_WIDGET_TIMEOUT"
                    ? "地图加载超时，请稍后重试"
                    : "地图加载失败，请查看浏览器控制台";
            }
        } finally {
            loading = false;
        }
    };

    document.querySelectorAll("[data-map-toggle]").forEach((b) =>
        b.addEventListener("click", () => open(b))
    );
    dialog.querySelector("[data-map-close]")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (e) => {
        if (e.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", () => {
        if (widget) {
            widget.destroy();
            widget = null;
        }
        loading = false; // a mid-load close must never strand the button
    });
}
