// film-tv-core.js — pure helpers for the film & TV archive pages.
//
// Loaded as a classic <script> before film-tv.js (see mkdocs.yml
// extra_javascript), so its functions are page globals there; the
// `module.exports` guard lets Node unit-test the same file
// (tests/test_film_tv_core.cjs).

// "2026-09-25" -> "2026-09"; anything unusable -> "undated".
function monthKey(date) {
  const value = String(date || "");
  return /^\d{4}-\d{2}/.test(value) ? value.slice(0, 7) : "undated";
}

// Release-year bucket used by the 上映年代 filter: 1994 -> "1990s".
function decadeOf(year) {
  const value = Number(year);
  if (!Number.isFinite(value) || value <= 0) return "unknown";
  return `${Math.floor(value / 10) * 10}s`;
}

// DOM helper shared by film-tv.js and film-tv-chart.js (both load this file
// first): create an element with an optional class and text.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

// One promise per URL: the archive page and the chart both read `index.json`, and
// a chart is not worth a second request. A failure is evicted, so a retry (e.g.
// reopening the chart) really retries.
const jsonCache = new Map();
function fetchJsonOnce(url) {
  if (!jsonCache.has(url)) {
    const pending = fetch(url, { cache: "no-cache" }).then((response) => {
      if (!response.ok) throw new Error(`${response.status} ${url}`);
      return response.json();
    });
    jsonCache.set(url, pending);
    pending.catch(() => jsonCache.delete(url));
  }
  return jsonCache.get(url);
}

// Keys that activate a focused `role="button"` element: Enter and Space (the
// modern `key` value for the space bar is a single space).
function isActivationKey(key) {
  return key === "Enter" || key === " ";
}

// 5 -> "★★★★★", 3 -> "★★★☆☆", null -> "" (unrated).
function starsOf(rating) {
  const value = Number(rating);
  if (!Number.isFinite(value) || value <= 0) return "";
  return "★".repeat(value) + "☆".repeat(Math.max(0, 5 - value));
}

// Search across title / original title / directors / casts.
// Tags are deliberately NOT searched: the archived Douban tags are legacy and
// inaccurate, so matching on them only adds noise (the data stays in the record
// and is still shown in the detail dialog).
function matchesQuery(record, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  const haystack = [
    record.title,
    record.original_title,
    ...(record.directors || []),
    ...(record.casts || []),
    ...(record.writers || []),
  ]
    .filter(Boolean)
    .join(" ");
  return haystack.toLowerCase().includes(needle);
}

// All people credited on a record (used by the 影人 filter and by the dialog).
function peopleOf(record) {
  return [...(record.directors || []), ...(record.casts || []), ...(record.writers || [])];
}

// Apply every active filter. `filters` keys (all optional):
//   q, type, category, region, decade, rating (minimum), from, to (YYYY-MM),
//   person (a director/cast/writer name), status
function filterRecords(items, filters) {
  const f = filters || {};
  return (items || []).filter((record) => {
    if (f.type && record.type !== f.type) return false;
    if (f.category && record.category !== f.category) return false;
    if (f.status && record.status !== f.status) return false;
    if (f.region && !(record.regions || []).includes(f.region)) return false;
    if (f.person && !peopleOf(record).includes(f.person)) return false;
    if (f.decade && decadeOf(record.year) !== f.decade) return false;
    if (f.rating && (record.rating == null || record.rating < Number(f.rating))) return false;
    if (f.from || f.to) {
      const month = monthKey(record.date);
      if (month === "undated") return false;
      if (f.from && month < f.from) return false;
      if (f.to && month > f.to) return false;
    }
    return matchesQuery(record, f.q);
  });
}

// Sort modes: "date" (watching date, newest first), "year" (release year),
// "rating" (my rating, unrated last), "title".
function sortRecords(items, mode) {
  const records = (items || []).slice();
  const byText = (a, b) => String(a).localeCompare(String(b), "zh-Hans-CN");
  if (mode === "year") {
    records.sort((a, b) => (b.year || 0) - (a.year || 0) || byText(a.title, b.title));
  } else if (mode === "rating") {
    records.sort((a, b) => (b.rating || 0) - (a.rating || 0) || byText(a.title, b.title));
  } else if (mode === "title") {
    records.sort((a, b) => byText(a.title, b.title));
  } else {
    records.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")) ||
      String(b.id || "").localeCompare(String(a.id || "")));
  }
  return records;
}

//: rows per page — the same for every sort mode (month headings are just
//: separators inside a page, never a page boundary). 12 = 4 rows of the card
//: grid's 3 columns, so a page fills the space without a ragged last row.
const PAGE_SIZE = 12;
// [[month, [records]], ...] newest month first — the timeline separators.
// Undated records sink to the end regardless of collation order.
function groupByMonth(items) {
  const groups = new Map();
  for (const record of items || []) {
    const key = monthKey(record.date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  }
  return [...groups.entries()].sort((a, b) => {
    if (a[0] === "undated") return 1;
    if (b[0] === "undated") return -1;
    return b[0].localeCompare(a[0]);
  });
}

// "YYYY-MM" shifted by `delta` months (across year boundaries).
function monthAdd(month, delta) {
  const [year, number] = String(month).split("-").map(Number);
  if (!Number.isFinite(year) || !Number.isFinite(number)) return "";
  const total = year * 12 + (number - 1) + delta;
  const shiftedYear = Math.floor(total / 12);
  const shiftedMonth = (total % 12 + 12) % 12 + 1;
  return `${shiftedYear}-${String(shiftedMonth).padStart(2, "0")}`;
}

// Every month from `from` to `to`, ascending (inclusive; [] when reversed).
function monthSpan(from, to) {
  if (!from || !to || from > to) return [];
  const months = [];
  for (let month = from; month <= to; month = monthAdd(month, 1)) {
    months.push(month);
    if (months.length > 1200) break;  // guard against a bad range
  }
  return months;
}

// The `count` calendar months ending at `newest` (the chart's default window).
function lastMonths(newest, count) {
  return monthSpan(monthAdd(newest, -(count - 1)), newest);
}

// Month buckets for the chart controls. `counts` is {"YYYY-MM": {movie, tv}};
// returns the months to draw (ascending) plus the peak bucket total, so the
// caller can scale the bars. `mode`: "last" | "year" | "range".
function chartBuckets(counts, options) {
  const opts = options || {};
  const dated = Object.keys(counts || {}).filter((month) => /^\d{4}-\d{2}$/.test(month));
  if (!dated.length) return { months: [], peak: 0, newest: "", oldest: "" };
  const sorted = dated.sort();
  const newest = opts.newest || sorted[sorted.length - 1];
  const oldest = sorted[0];
  let months;
  if (opts.mode === "year") {
    const year = Number(opts.year) || Number(newest.slice(0, 4));
    months = monthSpan(`${year}-01`, `${year}-12`);
  } else if (opts.mode === "range") {
    const from = opts.from && opts.from > oldest ? opts.from : oldest;
    const to = opts.to && opts.to < newest ? opts.to : newest;
    months = monthSpan(from, to);
  } else {
    months = lastMonths(newest, Number(opts.last) || 12);
  }
  const peak = months.reduce((best, month) => {
    const bucket = counts[month] || {};
    return Math.max(best, (bucket.movie || 0) + (bucket.tv || 0));
  }, 0);
  return { months, peak, newest, oldest };
}

// Item count revealed for the first `pages` pages of a list.
function pageTarget(records, pages, pageSize) {
  const size = pageSize || PAGE_SIZE;
  return Math.min((records || []).length, Math.max(1, pages) * size);
}

// One-line summary under the chart: the drawn window plus its volume. `counts` is
// {"YYYY-MM": {movie, tv}} and `kind` (""/"movie"/"tv") reports only that
// scope's share, so a movies-page chart does not read as "共 0 条（剧集 0）".
function chartSummary(kind, months, counts) {
  if (!months || !months.length) return "";
  const totals = months.reduce(
    (acc, month) => {
      const value = (counts || {})[month] || {};
      acc.movie += value.movie || 0;
      acc.tv += value.tv || 0;
      return acc;
    },
    { movie: 0, tv: 0 }
  );
  let total = totals.movie + totals.tv;
  let split = `电影 ${totals.movie} · 剧集 ${totals.tv}`;
  if (kind === "movie") {
    total = totals.movie;
    split = `电影 ${totals.movie}`;
  } else if (kind === "tv") {
    total = totals.tv;
    split = `剧集 ${totals.tv}`;
  }
  return `${months[0]} ~ ${months[months.length - 1]} · 共 ${total} 条（${split}）`;
}

// Values of one facet for a record. `key` is either a plain field name or one of
// the two derived facets the UI exposes: "decade" (from year) and "month".
function facetValues(record, key) {
  if (key === "decade") return [decadeOf(record.year)];
  if (key === "month") return [monthKey(record.date)];
  const raw = record[key];
  if (Array.isArray(raw)) return raw;
  return raw == null || raw === "" ? [] : [raw];
}

// Distinct values for a facet, by frequency: used to build the filter selects.
function facetCounts(items, key) {
  const counts = new Map();
  for (const record of items || []) {
    for (const value of facetValues(record, key)) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
}

// Month → count map for the calendar cells. When `kind` ("movie" / "tv") is
// given, per-type counts are used so a scoped page does not show the other
// type's volume.
function monthCounts(months, kind) {
  const counts = {};
  for (const [month, info] of Object.entries(months || {})) {
    if (kind && info && info.by_type) {
      counts[month] = info.by_type[kind] || 0;
    } else {
      counts[month] = (info && info.count) || 0;
    }
  }
  return counts;
}

// Self-check the shard contract: count / first_date / last_date must agree.
function shardProblem(shard, expectedSize) {
  if (!shard || !Array.isArray(shard.items)) return "shard has no items array";
  if (expectedSize && shard.items.length > expectedSize) {
    return `shard oversized: ${shard.items.length} > ${expectedSize}`;
  }
  if (shard.count != null && shard.count !== shard.items.length) {
    return `count=${shard.count} but ${shard.items.length} items`;
  }
  const dates = shard.items.map((item) => item.date).filter(Boolean);
  if (dates.length) {
    if (shard.first_date && dates[0] !== shard.first_date) {
      return `first_date=${shard.first_date} != ${dates[0]}`;
    }
    if (shard.last_date && dates[dates.length - 1] !== shard.last_date) {
      return `last_date=${shard.last_date} != ${dates[dates.length - 1]}`;
    }
  }
  return "";
}

const FilmTvCoreApi = {
  el,
  fetchJsonOnce,
  monthKey,
  monthAdd,
  monthSpan,
  lastMonths,
  chartBuckets,
  chartSummary,
  decadeOf,
  isActivationKey,
  starsOf,
  matchesQuery,
  peopleOf,
  filterRecords,
  sortRecords,
  groupByMonth,
  pageTarget,
  PAGE_SIZE,
  facetValues,
  facetCounts,
  monthCounts,
  shardProblem,
};

// classic <script>: expose the API for film-tv.js (running-route-core.js instead
// declares plain globals — an object keeps this file's surface explicit)
if (typeof window !== "undefined") {
  window.FilmTvCore = FilmTvCoreApi;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = FilmTvCoreApi;
}
