// film-tv-chart.js — watch-volume chart: one mermaid `xychart-beta` diagram.
//
// One bar per month = that month's total, drawn by mermaid so the chart comes with
// proper axes, gridlines and auto-scaling — and so it *looks* like a chart rather
// than a row of hand-positioned divs. The bars take the theme's link colour, which
// keeps them readable in both palettes.
//
// Why one series: mermaid's xychart draws a second `bar` dataset *on top of* the
// first (no grouped/stacked bars — verified in a headless browser) and a `bar` +
// `line` combination gives the bars a near-white palette colour. The movie/tv
// split therefore lives in the summary line (and in the detail filters), not in
// the bars.
//
// Range controls: last 12 months (default) / by year / custom month range. The
// data is the derived month index (notes/film-tv/assets/index.json) — the same
// source the list uses, so the chart can never disagree with it.
//
// Pure helpers (month maths, bucketing) live in film-tv-core.js and are
// node-tested in tests/test_film_tv_core.cjs.

(function () {
  "use strict";

  const core = window.FilmTvCore || {};
  const el = core.el;
  const LAST_MONTHS = 12;
  const MODES = [
    ["last", "最近 12 个月"],
    ["year", "按年"],
    ["range", "自定义范围"],
  ];
  let renderSeq = 0;

  // Month → {movie, tv} counts, scoped to one type when the page asks for it.
  // (core.monthCounts returns the scoped *total*; the chart needs the split for
  // the summary line, hence its own bucket shape.)
  function monthTypeCounts(index, kind) {
    const counts = {};
    for (const [month, info] of Object.entries((index && index.months) || {})) {
      if (!/^\d{4}-\d{2}$/.test(month)) continue;  // "undated" is not charted
      const byType = (info && info.by_type) || {};
      const movie = info.by_type ? byType.movie || 0 : info.count || 0;
      const tv = info.by_type ? byType.tv || 0 : 0;
      counts[month] = kind === "movie"
        ? { movie, tv: 0 }
        : kind === "tv"
          ? { movie: 0, tv }
          : { movie, tv };
    }
    return counts;
  }

  // Short x labels: keep the year at the first tick and at every January, so a
  // 12-month window stays readable.
  function tickLabel(month, position) {
    const number = month.slice(5, 7);
    return position === 0 || number === "01" ? `${month.slice(2, 4)}-${number}` : number;
  }

  function cssVar(name, fallback) {
    return getComputedStyle(document.body).getPropertyValue(name).trim() || fallback;
  }

  function isDark() {
    return document.body.getAttribute("data-md-color-scheme") === "slate";
  }

  function chartDefinition(labels, values, peak) {
    // palette: the theme's link colour (readable in both palettes)
    const color = cssVar("--md-typeset-a-color", "#4051b5");
    return (
      "%%{init: {'theme': '" + (isDark() ? "dark" : "default") + "', " +
      "'themeVariables': {'xyChart': {'plotColorPalette': '" + color + "'}}}}%%\n" +
      "xychart-beta\n" +
      "    x-axis [" + labels.join(", ") + "]\n" +
      '    y-axis "条" 0 --> ' + Math.max(1, peak) + "\n" +
      "    bar [" + values.join(", ") + "]"
    );
  }

  async function renderBars(state, bucket) {
    const host = state.canvas;
    host.textContent = "";
    const labels = bucket.months.map(tickLabel);
    const values = bucket.months.map((month) => {
      const value = state.counts[month] || {};
      return (value.movie || 0) + (value.tv || 0);
    });
    const plot = el("div", "film-tv-chart__plot");
    plot.title = bucket.months
      .map((month, index) => {
        const value = state.counts[month] || {};
        return `${month} · ${values[index]} 条（电影 ${value.movie || 0} · 剧集 ${value.tv || 0}）`;
      })
      .join("\n");
    host.appendChild(plot);
    if (!window.mermaid) {
      plot.textContent = "图表需要 mermaid（见 mkdocs.yml 的 mermaid2 插件）。";
      return;
    }
    try {
      const { svg } = await window.mermaid.render(
        `film-tv-chart-${(renderSeq += 1)}`,
        chartDefinition(labels, values, bucket.peak)
      );
      plot.innerHTML = svg;
    } catch (error) {
      plot.textContent = `图表渲染失败：${error.message}`;
      console.error("film-tv-chart:", error);
    }
  }

  function renderControls(host, state, years) {
    host.textContent = "";
    const modeWrap = el("label", "film-tv-chart__control");
    modeWrap.appendChild(el("span", null, "范围"));
    const modeSelect = el("select");
    modeSelect.dataset.chartMode = "";
    for (const [value, label] of MODES) modeSelect.appendChild(new Option(label, value));
    modeSelect.value = state.mode;
    modeWrap.appendChild(modeSelect);
    host.appendChild(modeWrap);

    // the year is rotated with ‹ / › (same idiom as the calendar), never a dropdown
    const yearWrap = el("label", "film-tv-chart__control");
    yearWrap.appendChild(el("span", null, "年份"));
    const position = years.indexOf(String(state.year));
    const prevYear = el("button", "film-tv-chart__year-btn", "‹");
    prevYear.type = "button";
    prevYear.title = "上一年";
    prevYear.disabled = position >= years.length - 1;  // years are newest-first
    prevYear.addEventListener("click", () => {
      state.year = years[position + 1];
      render(state);
    });
    const yearLabel = el("span", "film-tv-chart__year-label", `${state.year} 年`);
    yearLabel.dataset.chartYear = "";
    const nextYear = el("button", "film-tv-chart__year-btn", "›");
    nextYear.type = "button";
    nextYear.title = "下一年";
    nextYear.disabled = position <= 0;
    nextYear.addEventListener("click", () => {
      state.year = years[position - 1];
      render(state);
    });
    yearWrap.appendChild(prevYear);
    yearWrap.appendChild(yearLabel);
    yearWrap.appendChild(nextYear);
    yearWrap.hidden = state.mode !== "year";
    host.appendChild(yearWrap);

    const rangeWrap = el("label", "film-tv-chart__control");
    rangeWrap.appendChild(el("span", null, "从"));
    const fromInput = el("input");
    fromInput.type = "month";
    fromInput.dataset.chartFrom = "";
    rangeWrap.appendChild(fromInput);
    rangeWrap.appendChild(el("span", null, "到"));
    const toInput = el("input");
    toInput.type = "month";
    toInput.dataset.chartTo = "";
    rangeWrap.appendChild(toInput);
    rangeWrap.hidden = state.mode !== "range";
    host.appendChild(rangeWrap);

    const legend = el("span", "film-tv-chart__legend");
    legend.appendChild(document.createTextNode("柱 = 当月总条数"));
    host.appendChild(legend);

    modeSelect.addEventListener("change", () => {
      state.mode = modeSelect.value;
      render(state);
    });
    const readRange = () => {
      state.from = fromInput.value || state.oldest;
      state.to = toInput.value || state.newest;
      render(state);
    };
    fromInput.value = state.from || state.oldest;
    toInput.value = state.to || state.newest;
    for (const input of [fromInput, toInput]) {
      input.min = state.oldest;
      input.max = state.newest;
      input.addEventListener("change", readRange);
    }
  }

  async function render(state) {
    const bucket = core.chartBuckets(state.counts, {
      mode: state.mode,
      year: state.year,
      from: state.from,
      to: state.to,
      last: LAST_MONTHS,
    });
    renderControls(state.controls, state, state.years);
    if (!bucket.months.length) {
      // an empty range must not reach mermaid (an empty x-axis throws there)
      state.summary.textContent = "所选范围内没有记录。";
      state.canvas.textContent = "";
      return;
    }
    if (state.mode === "last") {
      state.from = bucket.months[0] || "";
      state.to = bucket.months[bucket.months.length - 1] || "";
    }
    const summary = core.chartSummary(state.kind, bucket.months, state.counts);
    state.summary.textContent = summary;
    await renderBars(state, bucket);
  }

  async function init(root) {
    const base = root.dataset.jsonBase || "./assets/";
    const kind = root.dataset.kind || "";
    const canvas = root.querySelector(".film-tv-chart__canvas");
    const controls = root.querySelector(".film-tv-chart__controls");
    const summary = root.querySelector(".film-tv-chart__summary");
    if (!canvas || !controls || !summary) return;
    try {
      const index = await core.fetchJsonOnce(base + "index.json");
      const counts = monthTypeCounts(index, kind);
      // the "undated" pseudo-month is not a date: as a month it would stretch the
      // range inputs, sliced it would offer "unda 年" in the year rotation
      const months = Object.keys(counts).filter(core.isMonthKey).sort();
      if (!months.length) {
        summary.textContent = "暂无观影量数据（先跑一次同步与派生）。";
        return;
      }
      const years = core.calendarYears(counts).reverse(); // newest first
      const state = {
        counts,
        kind,
        canvas,
        controls,
        summary,
        mode: "last",
        year: years[0],
        from: "",
        to: "",
        oldest: months[0],
        newest: months[months.length - 1],
        years,
      };
      await render(state);
      const details = root.closest("details");
      if (details) {
        details.addEventListener("toggle", () => {
          if (details.open) render(state);
        });
      }
    } catch (error) {
      summary.textContent = `观影量数据加载失败：${error.message}`;
      console.error("film-tv-chart:", error);
    }
  }

  function boot() {
    for (const root of document.querySelectorAll(".film-tv-chart[data-json-base]")) {
      init(root);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
