---
icon: material/map-marker
hide:
  - tags
---

# 📍 GPS 位置记录

用手机**临时记录**当前位置（如地铁站、出行点位），支持多个地点标记、一键清空；
也可以在**地图上点击 / 拖动十字线 / 手动输入**来指定任意位置。数据仅存本地浏览器，不会上传。

______________________________________________________________________

<style>
    .gps-wrap {
        max-width: 46em;
    }
    .gps-map-host {
        position: relative;
        width: 100%;
        height: 480px;
        border-radius: 8px;
        overflow: hidden;
        margin: 1em 0 0.5em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
    }
    .gps-map-loading {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--md-default-fg-color--light, #757575);
        background: var(--md-default-bg-color, #fff);
        font-size: 0.95em;
    }
    /* attribution hidden — same as moment pages (extra.moment.map.hide_attribution) */
    .gps-map-host .maplibregl-ctrl-attrib { display: none !important; }
    .gps-regions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4em;
        margin-bottom: 0.6em;
    }
    .gps-region {
        font-size: 0.85em;
        padding: 0.25em 0.9em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
        border-radius: 6px;
        background: var(--md-default-bg-color, #fff);
        color: var(--md-default-fg-color, #374151);
        cursor: pointer;
    }
    .gps-region:hover {
        background: var(--md-default-fg-color--lightest, #e0e0e0);
    }
    .gps-region.active {
        background: var(--md-typeset-a-color, #448aff);
        color: #fff;
        border-color: transparent;
    }
    .gps-status {
        font-size: 0.9em;
        color: var(--md-default-fg-color--light, #757575);
        margin: 0.4em 0 0.8em;
        min-height: 1.4em;
    }
    .gps-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em;
        margin-bottom: 1em;
    }
    .gps-btn {
        font-size: 0.95em;
        padding: 0.45em 1.1em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
        border-radius: 8px;
        background: var(--md-default-bg-color, #fff);
        color: var(--md-default-fg-color, #374151);
        cursor: pointer;
    }
    .gps-btn:hover:not(:disabled) {
        background: var(--md-default-fg-color--lightest, #e0e0e0);
    }
    .gps-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
    .gps-btn.gps-primary {
        background: var(--md-typeset-a-color, #448aff);
        color: #fff;
        border-color: transparent;
    }
    .gps-btn.gps-primary:hover:not(:disabled) {
        filter: brightness(0.94);
        background: var(--md-typeset-a-color, #448aff);
    }
    .gps-btn.gps-danger {
        color: #d93025;
        border-color: #e8b4b0;
    }
    .gps-pick {
        margin: 0 0 1em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
        border-radius: 8px;
        padding: 0.4em 0.9em;
        background: var(--md-default-bg-color--lvl0, #fff);
    }
    .gps-pick summary {
        cursor: pointer;
        font-weight: 500;
        padding: 0.3em 0;
    }
    .gps-pick-form {
        padding: 0.6em 0 0.8em;
    }
    .gps-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em;
        margin-bottom: 0.5em;
    }
    .gps-input {
        font-size: 0.92em;
        padding: 0.4em 0.7em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
        border-radius: 6px;
        background: var(--md-default-bg-color, #fff);
        color: var(--md-default-fg-color, #374151);
        min-width: 0;
        flex: 1 1 12em;
    }
    .gps-input.gps-coord {
        flex: 1 1 8em;
        font-family: var(--md-code-font-family, monospace);
    }
    .gps-input.gps-crs {
        flex: 0 1 auto;
    }
    .gps-hint {
        font-size: 0.82em;
        color: var(--md-default-fg-color--light, #757575);
        line-height: 1.5;
    }
    .gps-section-title {
        font-weight: 600;
        margin: 0.8em 0 0.4em;
    }
    .gps-count {
        font-weight: 400;
        color: var(--md-default-fg-color--light, #757575);
    }
    .gps-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    .gps-empty {
        color: var(--md-default-fg-color--light, #757575);
        font-size: 0.9em;
        padding: 0.5em 0;
    }
    .gps-item {
        display: flex;
        align-items: center;
        gap: 0.8em;
        padding: 0.55em 0;
        border-bottom: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
    }
    .gps-item-main {
        flex: 1;
        min-width: 0;
    }
    .gps-item-top {
        display: flex;
        justify-content: space-between;
        gap: 0.6em;
    }
    .gps-item-name {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .gps-item-time {
        color: var(--md-default-fg-color--light, #757575);
        font-size: 0.82em;
        flex-shrink: 0;
    }
    .gps-item-meta {
        font-size: 0.85em;
        color: var(--md-default-fg-color--light, #757575);
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.4em;
    }
    .gps-item-coord {
        font-size: 0.9em;
    }
    .gps-badge {
        font-size: 0.78em;
        padding: 0.08em 0.6em;
        border-radius: 10px;
        background: var(--md-default-fg-color--lightest, #e0e0e0);
        color: var(--md-default-fg-color, #374151);
    }
    .gps-badge-warn {
        background: #fff3cd;
        color: #8a6d1a;
    }
    .gps-osm {
        font-size: 0.85em;
        text-decoration: none;
    }
    .gps-copy {
        flex-shrink: 0;
        font-size: 0.82em;
        padding: 0.25em 0.8em;
        border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
        border-radius: 6px;
        background: var(--md-default-bg-color, #fff);
        color: var(--md-typeset-a-color, #448aff);
        cursor: pointer;
    }
    .gps-copy:hover {
        background: var(--md-default-fg-color--lightest, #e0e0e0);
    }
    .gps-item-btns {
        display: flex;
        gap: 0.4em;
        flex-shrink: 0;
    }
    .gps-copy.gps-del {
        color: #d93025;
        border-color: #e8b4b0;
    }
    .gps-rename {
        flex: 1 1 auto;
        min-width: 4em;
        font-size: 0.92em;
        padding: 0.12em 0.5em;
    }
    .gps-toast {
        position: fixed;
        left: 50%;
        bottom: 2em;
        transform: translateX(-50%) translateY(0.8em);
        background: var(--md-default-fg-color, #374151);
        color: var(--md-default-bg-color, #fff);
        padding: 0.55em 1.2em;
        border-radius: 8px;
        font-size: 0.9em;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s, transform 0.2s;
        z-index: 60;
        max-width: 90vw;
    }
    .gps-toast.show {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
    }
    @media (max-width: 640px) {
        .gps-map-host { height: 360px; }
        .gps-btn { flex: 1 1 45%; }
    }
</style>

<div class="gps-wrap">
  <div class="gps-map-host" id="gps-map-host">
    <div class="gps-map-loading" id="gps-map-loading">⌛ 地图加载中…</div>
  </div>
  <div class="gps-regions" id="gps-regions"></div>
  <div class="gps-status" id="gps-status">📍 点击「获取当前位置」开始定位</div>
  <div class="gps-actions">
    <button class="gps-btn" id="gps-locate" type="button">📍 获取当前位置</button>
    <button class="gps-btn gps-primary" id="gps-record-now" type="button">➕ 记录当前位置</button>
    <button class="gps-btn" id="gps-record-center" type="button" disabled>🎯 以地图中心记录</button>
    <button class="gps-btn gps-danger" id="gps-clear" type="button">🗑 清空全部</button>
  </div>
  <details class="gps-pick" open>
    <summary>✏️ 指定位置（地图点击 / 中心十字线 / 手动输入）</summary>
    <div class="gps-pick-form">
      <div class="gps-row">
        <input class="gps-input" id="gps-name" type="text" placeholder="名称（可选，如 龙华中路站）" autocomplete="off" />
        <input class="gps-input" id="gps-paste" type="text" placeholder="粘贴坐标文本，如 31.2304, 121.4737（自动识别）" autocomplete="off" />
      </div>
      <div class="gps-row">
        <input class="gps-input gps-coord" id="gps-lat" type="text" inputmode="decimal" placeholder="纬度 lat" autocomplete="off" />
        <input class="gps-input gps-coord" id="gps-lng" type="text" inputmode="decimal" placeholder="经度 lng" autocomplete="off" />
        <select class="gps-input gps-crs" id="gps-crs" title="坐标系">
          <option value="wgs84">WGS-84</option>
          <option value="gcj02">GCJ-02（高德）</option>
        </select>
        <button class="gps-btn gps-primary" id="gps-add-pick" type="button">✅ 记录此位置</button>
      </div>
      <div class="gps-hint">
        💡 点击地图直接取点；拖动地图使目标对准中心十字线后点「以地图中心记录」；
        从高德/百度 App 复制的是 <b>GCJ-02/BD-09 加密坐标</b>，手动输入时请选择对应坐标系，
        否则地图上会偏移几百米（浏览器定位不受影响，原生 WGS-84）。
      </div>
    </div>
  </details>
  <div class="gps-section-title">记录列表 <span class="gps-count" id="gps-count"></span></div>
  <ul class="gps-list" id="gps-list">
    <li class="gps-empty">还没有记录：点「📍 获取当前位置」后「➕ 记录当前位置」，或在地图上点选一个位置</li>
  </ul>
</div>

<div class="gps-toast" id="gps-toast" role="status" aria-live="polite"></div>

<script>
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Map config — mirror of `mkdocs.yml` → extra.moment.map.
  // KEEP IN SYNC: a new vine release changes the hashed widget URLs and
  // possibly the region table; update both places together.
  // ------------------------------------------------------------------
  var MAP = {
    widget_js: "https://pub-b2aff5be2d184901860b85a97a002a8c.r2.dev/vine/widget/map-widget-885e9d424bea.js",
    widget_css: "https://pub-b2aff5be2d184901860b85a97a002a8c.r2.dev/vine/widget/map-widget-6d4cf0bf511b.css",
    pmtiles_prefix: "pmtiles://https://pub-b2aff5be2d184901860b85a97a002a8c.r2.dev/vine/pmtiles/",
    glyphs_url: "https://pub-b2aff5be2d184901860b85a97a002a8c.r2.dev/vine/glyphs/{fontstack}/{range}.pbf",
    attribution: "© recycle.bin · Protomaps",
    default_region: "shanghai",
    regions: {
      shanghai: { bbox: [120.8, 30.6, 122.2, 31.8], center: [121.5, 31.2], zoom: 12, label: "上海" },
      tokyo: { bbox: [139.4, 35.4, 140.2, 35.9], center: [139.8, 35.65], zoom: 12, label: "东京" }
    }
  };

  var STORAGE_KEY = "gps_tracker_v1";
  var POI_ZOOM = 14; // zoom when focusing a record / picked point

  // --- state ----------------------------------------------------------
  var points = [];        // [{ name, lng, lat, ts, accuracy?, region? }]
  var widget = null;      // vine map widget
  var mapReady = false;
  var currentRegion = MAP.default_region;
  var currentFix = null;  // latest geolocation fix { lng, lat, accuracy, ts }
  var tempPick = null;    // { lng, lat } from map click
  var centerPick = null;  // map center (crosshair) read on idle
  var locating = false;

  // --- DOM refs ---------------------------------------------------------
  var mapHost = document.getElementById("gps-map-host");
  var mapLoading = document.getElementById("gps-map-loading");
  var regionsEl = document.getElementById("gps-regions");
  var statusEl = document.getElementById("gps-status");
  var listEl = document.getElementById("gps-list");
  var countEl = document.getElementById("gps-count");
  var toastEl = document.getElementById("gps-toast");
  var nameInput = document.getElementById("gps-name");
  var pasteInput = document.getElementById("gps-paste");
  var latInput = document.getElementById("gps-lat");
  var lngInput = document.getElementById("gps-lng");
  var crsSelect = document.getElementById("gps-crs");
  var btnLocate = document.getElementById("gps-locate");
  var btnRecordNow = document.getElementById("gps-record-now");
  var btnRecordCenter = document.getElementById("gps-record-center");
  var btnAddPick = document.getElementById("gps-add-pick");
  var btnClear = document.getElementById("gps-clear");

  // --- small helpers ----------------------------------------------------
  function fmtDecimal(n, d) { return Number(n).toFixed(d === undefined ? 6 : d); }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function fmtTime(ts) {
    var d = new Date(ts);
    if (!isFinite(d.getTime())) return "";
    return pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " +
      pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  }
  function fmtCoord(lng, lat) { return fmtDecimal(lng) + ", " + fmtDecimal(lat); }

  var toastTimer = null;
  function toast(msg, ms) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
      toastEl.textContent = ""; // clear so aria-live doesn't re-announce stale text
      toastTimer = null;
    }, ms || 2600);
  }

  // --- storage -----------------------------------------------------------
  function load() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!Array.isArray(raw)) return;
      // clean: keep only well-formed records
      points = raw.filter(function (p) {
        return p && typeof p === "object" &&
          p.lng !== null && p.lat !== null &&
          Number.isFinite(+p.lng) && Number.isFinite(+p.lat) &&
          +p.lng >= -180 && +p.lng <= 180 && +p.lat >= -90 && +p.lat <= 90 &&
          !isNaN(new Date(p.ts).getTime());
      }).map(function (p) {
        return {
          name: typeof p.name === "string" ? p.name.slice(0, 100) : "",
          lng: +p.lng, lat: +p.lat,
          ts: new Date(p.ts).getTime(),
          accuracy: Number.isFinite(+p.accuracy) ? +p.accuracy : undefined,
          // only keep regions that exist as own keys of the config — anything
          // else (incl. inherited names like "__proto__"/"constructor") is
          // treated as out-of-region (never trust raw storage values)
          region: Object.prototype.hasOwnProperty.call(MAP.regions, p.region)
            ? p.region : undefined
        };
      });
    } catch (e) {
      points = [];
    }
  }
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(points));
      return true;
    } catch (e) {
      return false; // blocked/full storage: keep in-memory only
    }
  }

  // --- geo: region probe (port of moment plugin _probe_region) -----------
  // Unlike the moment plugin (which falls back to default_region on miss),
  // this returns null → explicit "out-of-region" handling.
  function probeRegion(lng, lat) {
    var names = Object.keys(MAP.regions);
    for (var i = 0; i < names.length; i++) {
      var b = MAP.regions[names[i]].bbox;
      if (b[0] <= lng && lng <= b[2] && b[1] <= lat && lat <= b[3]) return names[i];
    }
    return null;
  }
  function regionLabel(name) {
    return (MAP.regions[name] && MAP.regions[name].label) || name;
  }

  // --- geo: gcj02 → wgs84 (JS port of shared/gcj02.py) ---------------------
  var GCJ_A = 6378245.0;
  var GCJ_EE = 0.00669342162296594323;
  function gcjTransformLat(x, y) {
    var r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    r += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
    r += ((20 * Math.sin(y * Math.PI) + 40 * Math.sin((y / 3) * Math.PI)) * 2) / 3;
    r += ((160 * Math.sin((y / 12) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30)) * 2) / 3;
    return r;
  }
  function gcjTransformLng(x, y) {
    var r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    r += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
    r += ((20 * Math.sin(x * Math.PI) + 40 * Math.sin((x / 3) * Math.PI)) * 2) / 3;
    r += ((150 * Math.sin((x / 12) * Math.PI) + 300 * Math.sin((x / 30) * Math.PI)) * 2) / 3;
    return r;
  }
  function gcj02ToWgs84(lng, lat) {
    var dLat = gcjTransformLat(lng - 105, lat - 35);
    var dLng = gcjTransformLng(lng - 105, lat - 35);
    var radLat = (lat / 180) * Math.PI;
    var magic = Math.sin(radLat);
    magic = 1 - GCJ_EE * magic * magic;
    var sqrtMagic = Math.sqrt(magic);
    var dLatFinal = (dLat * 180) / (((GCJ_A * (1 - GCJ_EE)) / (magic * sqrtMagic)) * Math.PI);
    var dLngFinal = (dLng * 180) / ((GCJ_A / sqrtMagic) * Math.cos(radLat) * Math.PI);
    return [lng * 2 - (lng + dLngFinal), lat * 2 - (lat + dLatFinal)];
  }

  // --- recording -----------------------------------------------------------
  function addPoint(lng, lat, name, accuracy) {
    var region = probeRegion(lng, lat); // null = out-of-region
    points.push({
      name: name || "",
      lng: lng, lat: lat,
      ts: Date.now(),
      accuracy: Number.isFinite(accuracy) ? accuracy : undefined,
      region: region || undefined
    });
    var saved = save();
    render();
    updateMarkers();
    flyToCoord(lng, lat);
    var rLabel = region ? regionLabel(region) : "⚠️ 暂无区域地图（仅记录 GPS）";
    toast((saved ? "已记录：" : "⚠ 已记录（存储不可用，仅本次会话）：") + rLabel);
    return region;
  }

  // --- geolocation ----------------------------------------------------------
  function locateNow(silent, cb) {
    if (!navigator.geolocation) {
      statusEl.textContent = "⚠️ 当前浏览器不支持定位，请使用「指定位置」或手动输入坐标";
      return;
    }
    if (locating) return;
    locating = true;
    if (!silent) statusEl.textContent = "⏳ 定位中…";
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        locating = false;
        var c = pos.coords;
        currentFix = { lng: c.longitude, lat: c.latitude, accuracy: c.accuracy, ts: Date.now() };
        var acc = Number.isFinite(c.accuracy) ? "±" + Math.round(c.accuracy) + " m" : "";
        statusEl.textContent = "📍 当前位置：" + fmtCoord(c.longitude, c.latitude) +
          (acc ? "（精度 " + acc + "）" : "") + " · 时间 " + fmtTime(currentFix.ts);
        btnRecordNow.disabled = false;
        flyToCoord(c.longitude, c.latitude);
        updateMarkers();
        if (cb) cb(currentFix);
      },
      function (err) {
        locating = false;
        var msg = {
          1: "定位权限被拒绝：请在浏览器地址栏允许位置访问后重试",
          2: "定位失败：当前位置不可用（请检查 GPS / 网络）",
          3: "定位超时：请移动到信号更好的地方重试"
        }[err.code] || "定位失败：" + err.message;
        statusEl.textContent = "⚠️ " + msg;
        if (!silent) toast(msg);
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  }

  // --- map -------------------------------------------------------------------
  function initMap() {
    // load the widget stylesheet alongside the bundle (moment pages load it
    // in <head>; tools pages are plain markdown, so inject it here). Without
    // it the map layout collapses and markers render off-position.
    if (MAP.widget_css && !document.querySelector('link[href="' + MAP.widget_css + '"]')) {
      var l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = MAP.widget_css;
      document.head.appendChild(l);
    }
    import(MAP.widget_js).then(function (mod) {
      var createMapWidget = mod.createMapWidget;
      var last = points.length > 0 ? points[points.length - 1] : null;
      var focus = last ? { lng: last.lng, lat: last.lat } : null;
      var regionCfg = MAP.regions[focus && last.region ? last.region : MAP.default_region] ||
        MAP.regions[MAP.default_region];
      if (last && last.region) currentRegion = last.region;

      widget = createMapWidget(mapHost, {
        basemapUrl: MAP.pmtiles_prefix + currentRegion + ".pmtiles",
        glyphsUrl: MAP.glyphs_url,
        attribution: MAP.attribution || undefined,
        center: focus ? [focus.lng, focus.lat] : regionCfg.center,
        zoom: focus ? POI_ZOOM : regionCfg.zoom,
        markers: [],
        showCenterHud: true,
        navControl: true,
        onClick: function (e) {
          pickPoint(e.lngLat.lng, e.lngLat.lat);
        },
        onIdle: function (e) {
          var c = e.target.getCenter();
          centerPick = { lng: c.lng, lat: c.lat };
          btnRecordCenter.disabled = false;
        }
      });
      mapReady = true;
      if (mapLoading) mapLoading.remove();
      renderRegions();
      updateMarkers();
      // no records → default to current position when the browser already
      // holds the geolocation permission (avoids an unexpected prompt)
      if (points.length === 0 && navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: "geolocation" }).then(function (p) {
          if (p.state === "granted") locateNow(true);
        }).catch(function () {});
      }
    }).catch(function (err) {
      console.error("[gps-tracker] map widget failed to load:", err);
      if (mapLoading) mapLoading.textContent = "地图加载失败（请检查网络/控制台）";
    });
  }

  // map click pick → fill the form, show a temp marker
  function pickPoint(lng, lat) {
    tempPick = { lng: lng, lat: lat };
    latInput.value = fmtDecimal(lat);
    lngInput.value = fmtDecimal(lng);
    crsSelect.value = "wgs84";
    var region = probeRegion(lng, lat);
    if (!region) {
      toast("⚠️ 该点超出「上海/东京」区域地图，将仅记录 GPS 信息（记录后可通过 OSM 链接查看）");
    } else if (region !== currentRegion) {
      toast("该点位于" + regionLabel(region) + "，切换区域后可见地图标记");
    }
    updateMarkers();
    // the clicked point may be outside the current basemap region — keep the
    // map where it is, the form still carries the coordinates
  }

  function flyToCoord(lng, lat) {
    if (!widget) return;
    widget.flyTo({ center: [lng, lat], zoom: POI_ZOOM });
  }

  function updateMarkers() {
    if (!widget) return;
    var markers = [];
    // current position: green dot, distinct from recorded 📍 pins
    if (currentFix && probeRegion(currentFix.lng, currentFix.lat) === currentRegion) {
      markers.push({
        lng: currentFix.lng, lat: currentFix.lat,
        color: "#22c55e",
        label: "当前位置",
        popupText: "当前位置\n" + fmtCoord(currentFix.lng, currentFix.lat) +
          (Number.isFinite(currentFix.accuracy) ? "（±" + Math.round(currentFix.accuracy) + " m）" : "") +
          "\n" + fmtTime(currentFix.ts)
      });
    }
    points.forEach(function (p) {
      if (p.region === currentRegion) {
        markers.push({
          lng: p.lng, lat: p.lat,
          emoji: "📍",
          label: p.name || undefined,
          popupText: (p.name ? p.name + "\n" : "") +
            fmtCoord(p.lng, p.lat) + "\n" + fmtTime(p.ts) +
            (Number.isFinite(p.accuracy) ? "（±" + Math.round(p.accuracy) + " m）" : "")
        });
      }
    });
    if (tempPick && probeRegion(tempPick.lng, tempPick.lat) === currentRegion) {
      markers.push({ lng: tempPick.lng, lat: tempPick.lat, emoji: "🎯", label: "选点" });
    }
    widget.setData({ markers: markers });
  }

  function renderRegions() {
    regionsEl.innerHTML = "";
    Object.keys(MAP.regions).forEach(function (name) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "gps-region" + (name === currentRegion ? " active" : "");
      b.textContent = MAP.regions[name].label;
      b.addEventListener("click", function () { switchRegion(name); });
      regionsEl.appendChild(b);
    });
  }

  function switchRegion(name) {
    if (name === currentRegion) return;
    currentRegion = name;
    var cfg = MAP.regions[name];
    if (widget) {
      widget.setBasemap(MAP.pmtiles_prefix + name + ".pmtiles", {
        center: cfg.center,
        zoom: cfg.zoom
      });
      updateMarkers();
    }
    renderRegions();
  }

  // --- render list ------------------------------------------------------------
  function render() {
    countEl.textContent = points.length ? "（" + points.length + "）" : "";
    btnClear.disabled = points.length === 0;
    if (points.length === 0) {
      listEl.innerHTML = '<li class="gps-empty">还没有记录：点「📍 获取当前位置」后「➕ 记录当前位置」，或在地图上点选一个位置</li>';
      return;
    }
    var rows = points.slice().reverse().map(function (p, ri) {
      var pi = points.length - 1 - ri; // index into `points` (list is reversed)
      var rLabel, badge, extra = "";
      if (p.region) {
        rLabel = regionLabel(p.region);
        badge = '<span class="gps-badge">' + esc(rLabel) + "</span>";
      } else {
        rLabel = "暂无区域地图";
        badge = '<span class="gps-badge gps-badge-warn">⚠️ 暂无区域地图</span>';
        extra = ' <a class="gps-osm" target="_blank" rel="noopener" href="https://www.openstreetmap.org/?mlat=' +
          p.lat + "&mlon=" + p.lng + '#map=16/' + p.lat + "/" + p.lng + '">OSM ↗</a>';
      }
      var acc = Number.isFinite(p.accuracy) ? "（±" + Math.round(p.accuracy) + " m）" : "";
      return '<li class="gps-item">' +
        '<div class="gps-item-main">' +
          '<div class="gps-item-top">' +
            '<span class="gps-item-name">' + esc(p.name || "未命名") + "</span>" +
            '<span class="gps-item-time">' + fmtTime(p.ts) + "</span>" +
          "</div>" +
          '<div class="gps-item-meta">' +
            '<code class="gps-item-coord">' + fmtCoord(p.lng, p.lat) + "</code>" +
            acc + " " + badge + extra +
          "</div>" +
        "</div>" +
        '<div class="gps-item-btns">' +
        '<button class="gps-copy" type="button" data-focus="' + pi + '" title="在地图上定位到此点">🧭</button>' +
        '<button class="gps-copy" type="button" data-edit="' + pi + '" title="修改名称">✏️</button>' +
        '<button class="gps-copy" type="button" data-lng="' + p.lng + '" data-lat="' + p.lat + '">📋 复制</button>' +
        '<button class="gps-copy gps-del" type="button" data-del="' + pi + '" title="删除此条">🗑</button>' +
      "</div>" +
      "</li>";
    });
    listEl.innerHTML = rows.join("");
  }

  // --- rename a recorded point (inline edit) ---------------------------------
  var editing = -1; // index of the point being renamed (or -1)
  function startEdit(pi) {
    if (editing !== -1 || pi < 0 || pi >= points.length) return;
    var li = listEl.children[points.length - 1 - pi];
    var nameEl = li && li.querySelector(".gps-item-name");
    if (!li || !nameEl) return;
    editing = pi;
    var input = document.createElement("input");
    input.type = "text";
    input.className = "gps-input gps-rename";
    input.maxLength = 100;
    input.value = points[pi].name;
    input.placeholder = "未命名";
    nameEl.replaceWith(input);
    input.focus();
    input.select();
    var done = false;
    var commit = function () {
      if (done) return;
      done = true;
      editing = -1;
      renamePoint(pi, input.value);
    };
    var cancel = function () {
      if (done) return;
      done = true;
      editing = -1;
      render();
    };
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === "NumpadEnter") { e.preventDefault(); commit(); }
      else if (e.key === "Escape") { cancel(); }
    });
    input.addEventListener("blur", commit);
  }

  function renamePoint(pi, newName) {
    points[pi].name = String(newName || "").trim().slice(0, 100);
    save();
    render();
    updateMarkers();
    toast("已更新名称");
  }

  function deletePoint(pi) {
    if (pi < 0 || pi >= points.length) return;
    var label = points[pi].name || "未命名";
    if (!window.confirm("确定删除「" + label + "」这条记录？")) return;
    points.splice(pi, 1);
    save();
    render();
    updateMarkers();
    toast("已删除记录");
  }

  function focusPointTo(pi) {
    if (pi < 0 || pi >= points.length || !widget) return;
    var p = points[pi];
    if (!p.region) {
      toast("⚠️ 该点暂无区域地图，请用 OSM ↗ 链接查看", 3000);
      return;
    }
    if (p.region !== currentRegion) {
      switchRegion(p.region); // setBasemap + markers; flyTo is queued until the new basemap is ready
    }
    widget.flyTo({ center: [p.lng, p.lat], zoom: POI_ZOOM });
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // --- actions -----------------------------------------------------------------
  function copyCoord(lng, lat) {
    var text = fmtCoord(lng, lat);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        toast("已复制：" + text);
      }, function () {
        toast("复制失败，请手动复制：" + text, 4000);
      });
    } else {
      toast("请手动复制：" + text, 4000);
    }
  }

  // manual / paste path: read the form, convert gcj02, validate, record
  function addPick() {
    var lat = parseFloat(latInput.value);
    var lng = parseFloat(lngInput.value);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) ||
        lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      toast("⚠️ 坐标无效：纬度应在 -90~90，经度应在 -180~180");
      return;
    }
    if (crsSelect.value === "gcj02") {
      var w = gcj02ToWgs84(lng, lat);
      lng = w[0]; lat = w[1];
    }
    var region = addPoint(lng, lat, nameInput.value.trim(), undefined);
    // keep the form for the next pick, but clear the point-specific fields
    pasteInput.value = "";
    latInput.value = "";
    lngInput.value = "";
    tempPick = null;
    updateMarkers();
  }

  function recordNow() {
    var name = nameInput.value.trim();
    if (currentFix) {
      addPoint(currentFix.lng, currentFix.lat, name, currentFix.accuracy);
      nameInput.value = "";
      return;
    }
    toast("⏳ 正在定位，成功后自动记录…", 3000);
    locateNow(false, function (fix) {
      addPoint(fix.lng, fix.lat, name, fix.accuracy);
      nameInput.value = "";
    });
  }

  function recordCenter() {
    if (!mapReady || !centerPick) return;
    addPoint(centerPick.lng, centerPick.lat, nameInput.value.trim(), undefined);
    nameInput.value = "";
  }

  function clearAll() {
    if (points.length === 0) return;
    if (!window.confirm("确定清空全部 " + points.length + " 条位置记录？此操作不可恢复。")) return;
    points = [];
    save();
    tempPick = null;
    currentFix = null;
    btnRecordNow.disabled = true;
    render();
    updateMarkers();
    toast("已清空全部记录");
  }

  // paste auto-detect: extract two numbers, fill as (lat, lng) like Google Maps
  var pasteTimer = null;
  function onPasteInput() {
    if (pasteTimer) clearTimeout(pasteTimer);
    pasteTimer = setTimeout(function () {
      pasteTimer = null;
      var text = pasteInput.value.trim();
      if (!text) return;
      var nums = text.match(/-?\d+(?:\.\d+)?/g);
      if (nums && nums.length >= 2) {
        latInput.value = nums[0];
        lngInput.value = nums[1];
        crsSelect.value = "wgs84";
        toast("已识别坐标（按 纬度,经度 填入），请核对后记录", 3000);
      } else {
        toast("未识别到坐标，请直接输入纬度/经度", 3000);
      }
    }, 300);
  }

  // --- wire up ----------------------------------------------------------------
  btnLocate.addEventListener("click", function () { locateNow(false); });
  btnRecordNow.addEventListener("click", recordNow);
  btnRecordCenter.addEventListener("click", recordCenter);
  btnAddPick.addEventListener("click", addPick);
  btnClear.addEventListener("click", clearAll);
  pasteInput.addEventListener("input", onPasteInput);
  // delegated: copy / rename buttons inside the list
  listEl.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b || !listEl.contains(b)) return;
    if (b.dataset.edit !== undefined) startEdit(parseInt(b.dataset.edit, 10));
    else if (b.dataset.focus !== undefined) focusPointTo(parseInt(b.dataset.focus, 10));
    else if (b.dataset.del !== undefined) deletePoint(parseInt(b.dataset.del, 10));
    else if (b.dataset.lng !== undefined) copyCoord(parseFloat(b.dataset.lng), parseFloat(b.dataset.lat));
  });
  // Enter in the manual form records the position
  [latInput, lngInput].forEach(function (el) {
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === "NumpadEnter") {
        e.preventDefault();
        btnAddPick.click();
      }
    });
  });

  load();
  render();
  initMap();
})();
</script>

______________________________________________________________________

## 📝 使用说明

| 操作                  | 说明                                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------- |
| **📍 获取当前位置**   | 浏览器定位（手机 GPS 优先），显示坐标与精度；「记录当前位置」用它落一条记录              |
| **➕ 记录当前位置**   | 将最近一次定位保存到列表；先在名称框填好备注（如站名）会一起记录；未定位过则先定位再记录 |
| **🎯 以地图中心记录** | 拖动地图使目标对准中心十字线后点击（移动端更精确），名称框备注会一起记录                 |
| **✏️ 地图点击取点**   | 点击地图任意位置，坐标自动填入下方表单，「记录此位置」保存                               |
| **手动输入**          | 直接填纬度/经度；坐标系默认 WGS-84，从高德复制的选 **GCJ-02（高德）**                    |
| **粘贴识别**          | 粘贴外部 App 复制的坐标文本（如 Google Maps 的 `纬度, 经度`），自动填入表单              |
| **📋 复制**           | 复制单条记录的 `经度, 纬度` 文本                                                         |
| **🧭 定位**           | 地图跳转到该记录点的位置（跨区域自动切换底图）                                           |
| **✏️ 改名**           | 修改已记录点的名称/备注：回车或失焦保存，Esc 取消                                        |
| **🗑 删除**            | 单独删除一条记录（需确认）；「清空全部」删除所有记录                                     |
| **🗑 清空全部**        | 删除全部记录，需二次确认                                                                 |

## 🗺 区域地图说明

地图标记图例：

- 🟢 **绿色圆点** = 当前位置（获取定位后显示）

- 📍 **图钉** = 已记录地点

- 🎯 **选点** = 地图点击时的临时选点（记录后消失）

- 地图底图按区域（region）提供：当前配置 **上海 / 东京**，列表上方按钮切换

- 区域内的地点：列表显示区域徽标，地图上显示 📍 标记

- **区域外的地点**（如在其他城市记录）：仍完整记录坐标与时间，但列表显示
  「⚠️ 暂无区域地图」，并提供 **OSM ↗** 外部地图链接查看；该点不在地图上渲染

- 地图由 [vine](https://github.com/xiongjia/vine) 的 embeddable widget 提供
  （MapLibre + Protomaps pmtiles），无 API key、完全静态

## 💾 数据说明

- 数据保存在浏览器 **localStorage**（键名 `gps_tracker_v1`），纯本地、不上传
- 刷新 / 关闭浏览器 / 重启均保留；清除浏览器数据、换设备则丢失
- 记录的坐标可复制（列表每条右侧 📋 按钮），后续可用 `poe create-moment --lng --lat` 落成 Moment，例如：`poe create-moment "内容" --place 站名 --lng 121.47 --lat 31.23 --crs wgs84`
- 手机定位的精度取决于 GPS 信号（室内/高楼下误差可达数十米），页面会显示 ±精度
