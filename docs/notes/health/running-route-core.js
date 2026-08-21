// running-route-core.js — pure helpers for the running page route maps.
//
// Loaded as a classic <script> before running-route.js (see mkdocs.yml
// extra_javascript), so its functions are page globals there; the
// `module.exports` guard lets Node unit-test the same file
// (tests/test_running_route_core.cjs).

// Decode Google Polyline to [[lng, lat], ...] coordinates.
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

// First polyline point as [lng, lat] — decodes only the first pair, cheap
// enough to gate every table row. Throws on a truncated/invalid polyline.
function firstPolylinePoint(encoded) {
  if (!encoded) return null;
  let i = 0, lat = 0, lng = 0;
  const next = () => {
    let r = 0, shift = 0, b;
    do {
      if (i >= encoded.length) throw new Error("bad polyline");
      b = encoded.charCodeAt(i++) - 63;
      r |= (b & 0x1f) << shift;
      shift += 5;
    } while (b >= 0x20);
    return r & 1 ? ~(r >> 1) : r >> 1;
  };
  lat += next();
  lng += next();
  return [lng / 1e5, lat / 1e5];
}

// Region bbox index containing a [lng, lat] point; 0 when no regions are
// configured (show all); -1 when outside every region.
function regionIndexFor(pt, regions) {
  if (!pt) return -1;
  if (!regions || !regions.length) return 0;
  for (let i = 0; i < regions.length; i++) {
    const b = regions[i];
    if (b && b.length === 4 && b[0] <= pt[0] && pt[0] <= b[2] && b[1] <= pt[1] && pt[1] <= b[3]) return i;
  }
  return -1;
}

// Seconds → "M:SS" (e.g. 332 → "5:32"); "—" when absent/zero/negative.
function fmtClock(sec) {
  if (!sec || sec <= 0) return "—";
  const total = Math.round(sec);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

// Per-km pace dialog rows [km, duration, pace, hr] for a splits entry.
function paceRowsFor(entry) {
  return (entry.splits || []).map((s) => {
    const km = Number(s.km);
    const kmStr = km < 1 ? km.toFixed(2) : String(Math.round(km));
    return [kmStr, fmtClock(s.duration), s.pace || "—", s.hr ? String(Math.round(s.hr)) : "—"];
  });
}

// HTML-escape a string for safe innerHTML embedding.
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    decodePolyline,
    firstPolylinePoint,
    regionIndexFor,
    fmtClock,
    paceRowsFor,
    esc,
  };
}
