// Node unit tests for docs/assets/javascripts/film-tv-core.js — the pure
// filtering / sorting / grouping helpers of the film & TV archive pages.
//
//     node tests/test_film_tv_core.cjs        (or `uv run poe test-js`)

const assert = require("node:assert");
const core = require("../docs/assets/javascripts/film-tv-core.js");

const RECORDS = [
  {
    id: "1", slug: "dune", title: "Dune", original_title: "Dune",
    type: "movie", category: "feature", status: "collect", rating: 5,
    year: 2021, date: "2021-10-01", regions: ["美国"], tags: ["Scifi"],
    genres: ["科幻"], directors: ["Denis Villeneuve"], casts: ["Timothée Chalamet"],
  },
  {
    id: "2", slug: "three-body", title: "三体", type: "tv", category: "series",
    status: "collect", rating: 4, year: 2023, date: "2023-02-05", regions: ["中国"],
    tags: ["SciFi", "中文"], genres: ["剧情"], directors: ["杨磊"], casts: ["张鲁一"],
  },
  {
    id: "3", slug: "akira", title: "Akira", type: "movie", category: "anime",
    status: "collect", rating: null, year: 1988, date: "2019-05-05", regions: ["日本"],
    tags: [], genres: ["动画"], directors: [], casts: [],
  },
  {
    id: "4", slug: "undated", title: "无日期", type: "movie", category: "other",
    status: "collect", rating: 3, year: null, date: "", regions: [], tags: [],
    genres: [], directors: [], casts: [],
  },
];

let failures = 0;
const pending = [];  // async checks: awaited before the summary below
function check(name, fn) {
  const passed = () => console.log(`  ok   ${name}`);
  const failed = (error) => {
    failures += 1;
    console.error(`  FAIL ${name}: ${error.message}`);
  };
  try {
    const result = fn();
    if (result && typeof result.then === "function") {
      pending.push(result.then(passed, failed));
      return;
    }
    passed();
  } catch (error) {
    failed(error);
  }
}

console.log("film-tv-core.js");

check("monthKey", () => {
  assert.strictEqual(core.monthKey("2021-10-01"), "2021-10");
  assert.strictEqual(core.monthKey(""), "undated");
  assert.strictEqual(core.monthKey(null), "undated");
});

check("decadeOf", () => {
  assert.strictEqual(core.decadeOf(1994), "1990s");
  assert.strictEqual(core.decadeOf(2021), "2020s");
  assert.strictEqual(core.decadeOf(null), "unknown");
  assert.strictEqual(core.decadeOf("2023"), "2020s");
});

check("starsOf", () => {
  assert.strictEqual(core.starsOf(5), "★★★★★");
  assert.strictEqual(core.starsOf(3), "★★★☆☆");
  assert.strictEqual(core.starsOf(null), "");
  assert.strictEqual(core.starsOf(0), "");
});

check("matchesQuery searches title / original title / cast / director / writer", () => {
  assert.strictEqual(core.matchesQuery(RECORDS[0], "dune"), true);
  assert.strictEqual(core.matchesQuery(RECORDS[1], "杨磊"), true);       // director
  assert.strictEqual(core.matchesQuery(RECORDS[1], "张鲁一"), true);     // cast
  assert.strictEqual(core.matchesQuery(RECORDS[0], "scifi"), false);     // tag only → no match
  assert.strictEqual(core.matchesQuery(RECORDS[0], "三体"), false);
  assert.strictEqual(core.matchesQuery(RECORDS[0], ""), true);
});

check("filterRecords by type / category / region / person", () => {
  assert.strictEqual(core.filterRecords(RECORDS, { type: "movie" }).length, 3);
  assert.strictEqual(core.filterRecords(RECORDS, { category: "anime" }).length, 1);
  assert.strictEqual(core.filterRecords(RECORDS, { region: "中国" }).length, 1);
  assert.strictEqual(core.filterRecords(RECORDS, { decade: "1980s" }).length, 1);
  // 影人 filter: matches director / actor / writer names
  assert.deepStrictEqual(core.filterRecords(RECORDS, { person: "杨磊" }).map((r) => r.id), ["2"]);
  assert.deepStrictEqual(
    core.filterRecords(RECORDS, { person: "Timothée Chalamet" }).map((r) => r.id),
    ["1"]
  );
  assert.strictEqual(core.filterRecords(RECORDS, { person: "查无此人" }).length, 0);
});

check("tags are not a filter or a search facet any more", () => {
  // the archived Douban tags are legacy: filtering by them must do nothing
  assert.strictEqual(core.filterRecords(RECORDS, { tag: "SciFi" }).length, RECORDS.length);
  // "SciFi" only exists as a tag → the search must not match on it
  assert.strictEqual(core.matchesQuery(RECORDS[0], "scifi"), false);
  assert.strictEqual(core.matchesQuery(RECORDS[1], "SciFi"), false);
});

check("peopleOf collects directors, casts and writers", () => {
  assert.deepStrictEqual(core.peopleOf(RECORDS[0]), ["Denis Villeneuve", "Timothée Chalamet"]);
  assert.deepStrictEqual(core.peopleOf({}), []);
});

check("dialogFacts: rows, order and person rows", () => {
  const rows = core.dialogFacts(RECORDS[0]);
  assert.deepStrictEqual(
    rows.map((row) => row.label),
    ["状态", "我的评分", "观看日期", "上映年", "类型", "地区", "类型标签", "导演", "主演", "我的标签"]
  );
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row]));
  // every row carries the same three keys — the renderer destructures them
  for (const row of rows) {
    assert.deepStrictEqual(Object.keys(row).sort(), ["label", "people", "value"]);
  }
  // the three credit rows carry `people` — the renderer clicks these, and it
  // must not have to match the label text to find them
  assert.deepStrictEqual(byLabel["导演"].people, ["Denis Villeneuve"]);
  assert.deepStrictEqual(byLabel["主演"].people, ["Timothée Chalamet"]);
  assert.strictEqual(byLabel["导演"].value, "Denis Villeneuve");
  // non-credit rows must never turn into clickable names
  for (const row of rows.filter((r) => !["导演", "主演", "编剧"].includes(r.label))) {
    assert.deepStrictEqual(row.people, []);
  }
  assert.strictEqual(byLabel["状态"].value, "看过");
  assert.strictEqual(byLabel["类型"].value, "电影");
  assert.strictEqual(byLabel["上映年"].value, "2021");
  assert.strictEqual(byLabel["我的评分"].value, `${core.starsOf(5)} 5/5`);
});

check("dialogFacts: drops empty rows, keeps every value a string", () => {
  // year-only / no date / no score: those rows disappear instead of rendering a
  // bare dash (the dialog's 我的评分 row is the one that always has a value)
  const sparse = core.dialogFacts(RECORDS[3]);
  assert.deepStrictEqual(sparse.map((row) => row.label), ["状态", "我的评分", "类型"]);
  assert.strictEqual(sparse.find((row) => row.label === "类型").value, "其他");
  assert.deepStrictEqual(core.dialogFacts({}).map((row) => row.label), ["我的评分"]);
  assert.strictEqual(core.dialogFacts({}).find((row) => row.label === "我的评分").value, "未评分");
  for (const row of core.dialogFacts(RECORDS[0])) {
    assert.strictEqual(typeof row.value, "string");
  }
  // a pending record says so, rather than looking undated
  assert.strictEqual(
    core.dialogFacts({ status: "do", pending: true }).find((row) => row.label === "观看日期").value,
    "待补详情"
  );
  // runtime + episodes share one row
  assert.strictEqual(
    core.dialogFacts({ runtime: 100, episodes: 12 }).find((row) => row.label === "片长/集数").value,
    "100 分钟 / 12 集"
  );
  assert.deepStrictEqual(core.dialogFacts({ runtime: 100 }).map((row) => row.label), [
    "我的评分", "片长/集数",
  ]);
});

check("dialogFacts: empty names never become buttons", () => {
  const row = core.dialogFacts({ casts: ["A", "", null, "B"] }).find((r) => r.label === "主演");
  assert.deepStrictEqual(row.people, ["A", "B"]);
  assert.strictEqual(row.value, "A / B");
  // only empty names: the whole row is dropped
  assert.deepStrictEqual(core.dialogFacts({ casts: ["", null] }).map((r) => r.label), ["我的评分"]);
});

check("filterRecords rating is a minimum", () => {
  assert.deepStrictEqual(core.filterRecords(RECORDS, { rating: "4" }).map((r) => r.id), ["1", "2"]);
  assert.deepStrictEqual(core.filterRecords(RECORDS, { rating: "5" }).map((r) => r.id), ["1"]);
});

check("filterRecords date range drops undated records", () => {
  assert.deepStrictEqual(
    core.filterRecords(RECORDS, { from: "2021-01", to: "2022-12" }).map((r) => r.id),
    ["1"]
  );
  // from 2019-01: everything dated (1, 2, 3) — the undated record is dropped
  assert.deepStrictEqual(
    core.filterRecords(RECORDS, { from: "2019-01" }).map((r) => r.id),
    ["1", "2", "3"]
  );
  assert.deepStrictEqual(
    core.filterRecords(RECORDS, { to: "2020-12" }).map((r) => r.id),
    ["3"]
  );
});

check("filterRecords combines filters (AND)", () => {
  const out = core.filterRecords(RECORDS, { type: "movie", rating: "3", q: "dune" });
  assert.deepStrictEqual(out.map((r) => r.id), ["1"]);
});

check("sortRecords modes", () => {
  // date: newest first, the undated record last
  assert.deepStrictEqual(core.sortRecords(RECORDS, "date").map((r) => r.id), ["2", "1", "3", "4"]);
  // year: 2023, 2021, 1988, then the one with no year
  assert.deepStrictEqual(core.sortRecords(RECORDS, "year").map((r) => r.id), ["2", "1", "3", "4"]);
  // rating: 5, 4, 3, then unrated
  assert.deepStrictEqual(core.sortRecords(RECORDS, "rating").map((r) => r.id), ["1", "2", "4", "3"]);
  // title: locale collation, so assert the same set plus a stable id order
  const byTitle = core.sortRecords(RECORDS, "title").map((r) => r.id);
  assert.deepStrictEqual([...byTitle].sort(), ["1", "2", "3", "4"]);
});

check("sortRecords does not mutate its input", () => {
  const input = RECORDS.slice();
  core.sortRecords(input, "rating");
  assert.deepStrictEqual(input.map((r) => r.id), ["1", "2", "3", "4"]);
});

check("groupByMonth keeps months newest-first and undated last", () => {
  const groups = core.groupByMonth(RECORDS);
  assert.deepStrictEqual(groups.map(([month]) => month), ["2023-02", "2021-10", "2019-05", "undated"]);
  assert.deepStrictEqual(groups[0][1].map((r) => r.id), ["2"]);
  assert.deepStrictEqual(groups[3][1].map((r) => r.id), ["4"]);
});

check("PAGE_SIZE is the single page size for every sort mode", () => {
  // 12 = 4 rows of the 3-column card grid
  assert.strictEqual(core.PAGE_SIZE, 12);
});

check("pageTarget reveals a fixed window per page", () => {
  const many = new Array(60).fill({ date: "2026-01-01" });
  assert.strictEqual(core.pageTarget(many, 1), 12);
  assert.strictEqual(core.pageTarget(many, 3), 36);
  assert.strictEqual(core.pageTarget(many, 99), 60);   // clamped to the list
  assert.strictEqual(core.pageTarget([], 1), 0);
  assert.strictEqual(core.pageTarget(many, 0), 12);    // page 0 still shows one page
});

check("facetValues handles plain and derived facets", () => {
  assert.deepStrictEqual(core.facetValues(RECORDS[0], "regions"), ["美国"]);
  assert.deepStrictEqual(core.facetValues(RECORDS[0], "category"), ["feature"]);
  assert.deepStrictEqual(core.facetValues(RECORDS[0], "decade"), ["2020s"]);
  assert.deepStrictEqual(core.facetValues(RECORDS[3], "tags"), []);
});

check("facetCounts counts array and scalar values", () => {
  const regions = core.facetCounts(RECORDS, "regions");
  assert.deepStrictEqual(regions.map(([value, count]) => [value, count]), [["中国", 1], ["日本", 1], ["美国", 1]]);
  assert.deepStrictEqual(
    core.facetCounts(RECORDS, "category").map(([value]) => value),
    ["anime", "feature", "other", "series"]
  );
  // the decade select facets (records without a release year land in "unknown")
  assert.deepStrictEqual(
    core.facetCounts(RECORDS, "decade").map(([value, count]) => [value, count]).sort(),
    [["1980s", 1], ["2020s", 2], ["unknown", 1]]
  );
});

check("monthCounts uses per-type counts when scoped", () => {
  const months = { "2026-09": { count: 3, by_type: { movie: 2, tv: 1 } } };
  assert.deepStrictEqual(core.monthCounts(months), { "2026-09": 3 });
  assert.deepStrictEqual(core.monthCounts(months, "movie"), { "2026-09": 2 });
  assert.deepStrictEqual(core.monthCounts(months, "tv"), { "2026-09": 1 });
});

check("isActivationKey recognises the card activation keys", () => {
  assert.strictEqual(core.isActivationKey("Enter"), true);
  assert.strictEqual(core.isActivationKey(" "), true);
  assert.strictEqual(core.isActivationKey("Spacebar"), false);  // legacy value
  assert.strictEqual(core.isActivationKey("Escape"), false);
  assert.strictEqual(core.isActivationKey("a"), false);
});

check("chartSummary reports the drawn window and its volume", () => {
  const counts = {
    "2026-08": { movie: 2, tv: 1 },
    "2026-09": { movie: 1, tv: 0 },
  };
  assert.strictEqual(core.chartSummary("", ["2026-08", "2026-09"], counts),
    "2026-08 ~ 2026-09 · 共 4 条（电影 3 · 剧集 1）");
  // a kind-scoped chart reports only its own volume (not "共 4 条（电影 3）")
  assert.strictEqual(core.chartSummary("movie", ["2026-08", "2026-09"], counts),
    "2026-08 ~ 2026-09 · 共 3 条（电影 3）");
  assert.strictEqual(core.chartSummary("tv", ["2026-08", "2026-09"], counts),
    "2026-08 ~ 2026-09 · 共 1 条（剧集 1）");
  assert.strictEqual(core.chartSummary("", [], counts), "");
  assert.strictEqual(core.chartSummary("", null, counts), "");
});

check("fetchJsonOnce shares one request per url and retries after a failure", async () => {
  const calls = [];
  let fail = true;
  global.fetch = (url) => {
    calls.push(url);
    if (fail && calls.length === 1) {
      return Promise.resolve({ ok: false, status: 500 });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ shard_size: 200 }) });
  };
  // both callers (list + chart) ask for the same index.json
  const first = core.fetchJsonOnce("/a/index.json");
  const second = core.fetchJsonOnce("/a/index.json");
  await assert.rejects(first);
  await assert.rejects(second);
  assert.deepStrictEqual(calls, ["/a/index.json"]);
  await new Promise((resolve) => setTimeout(resolve, 0));  // let the eviction run
  // the rejected promise was evicted, so a later call really retries
  assert.deepStrictEqual(await core.fetchJsonOnce("/a/index.json"), { shard_size: 200 });
  assert.deepStrictEqual(calls, ["/a/index.json", "/a/index.json"]);
});

check("shardProblem accepts a well-formed shard", () => {
  const shard = {
    count: 2,
    first_date: "2026-09-25",
    last_date: "2026-09-01",
    items: [{ id: "1", date: "2026-09-25" }, { id: "2", date: "2026-09-01" }],
  };
  assert.strictEqual(core.shardProblem(shard, 200), "");
});

check("shardProblem catches count / date mismatches", () => {
  const base = { count: 1, first_date: "2026-09-25", last_date: "2026-09-25", items: [{ id: "1", date: "2026-09-25" }] };
  assert.match(core.shardProblem({ ...base, count: 5 }, 200), /count=5/);
  assert.match(core.shardProblem({ ...base, first_date: "2020-01-01" }, 200), /first_date/);
  assert.match(core.shardProblem({ ...base, last_date: "2020-01-01" }, 200), /last_date/);
  const oversized = { items: new Array(300).fill({ id: "x", date: "2026-09-25" }), count: 300 };
  assert.match(core.shardProblem(oversized, 200), /oversized/);
  assert.match(core.shardProblem({ items: null }, 200), /no items array/);
});

check("isMonthKey only accepts real YYYY-MM keys", () => {
  assert.equal(core.isMonthKey("2026-09"), true);
  assert.equal(core.isMonthKey("2008-06"), true);
  // "undated" sliced to four characters is "unda" — the calendar used to
  // advertise that as a year on first render (and the chart in 「按年」 mode)
  assert.equal(core.isMonthKey("undated"), false);
  assert.equal(core.isMonthKey(""), false);
  assert.equal(core.isMonthKey("2026-9"), false);
});

check("calendarYears ignores the undated pseudo-month and sorts oldest-first", () => {
  const months = {
    "2026-09": { count: 12 },
    "2008-06": { count: 63 },
    "2026-07": { count: 5 },
    undated: { count: 19 },
  };

  const years = core.calendarYears(months);

  assert.deepEqual(years, ["2008", "2026"]);
  assert.equal(years[years.length - 1], "2026"); // the fallback year
  assert.deepEqual(core.calendarYears(Object.keys(months)), ["2008", "2026"]);
  assert.deepEqual(core.calendarYears({ undated: { count: 1 } }), []);
  assert.deepEqual(core.calendarYears({}), []);
});

function finish() {
  if (failures) {
    console.error(`\n${failures} film-tv-core test(s) failed`);
    process.exit(1);
  }
  console.log("\nall film-tv-core tests passed");
}

if (pending.length) Promise.all(pending).then(finish);
else finish();
