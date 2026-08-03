---
icon: material/pill
hide:
  - tags
---

# 💊 吃药助记

解决的核心问题不是"忘了吃药"，而是 **"忘记自己吃没吃"**。原则是 **记录即确认** ——
药进嘴的同时点击按钮，留下不可抵赖的时间戳，让"到底吃没吃"有迹可查。

______________________________________________________________________

<div class="med-tracker">
  <div class="med-header">
    <div class="med-date" id="med-current-date"></div>
  </div>
  <div class="med-status-card" id="med-status-card">
    <div class="med-status-icon" id="med-status-icon">💊</div>
    <div class="med-status-text" id="med-status-text">今日尚未服药</div>
    <div class="med-status-time" id="med-status-time"></div>
  </div>
  <button class="med-btn med-btn-primary" id="med-take-btn" type="button">✅ 确认已服药</button>
  <div class="med-section-title">
    <span>今日记录</span>
    <span class="med-section-actions med-hide" id="med-section-actions">
      <button class="med-mini-btn" id="med-undo-btn" type="button">↩ 撤销上次</button>
      <button class="med-mini-btn" id="med-clear-btn" type="button">🗑 清空今日</button>
    </span>
  </div>
  <div class="med-today-list" id="med-today-list">
    <div class="med-empty">今天还没有服药记录</div>
  </div>
  <div class="med-section-title">近 7 天</div>
  <div class="med-history" id="med-history"></div>
</div>

<div class="med-toast" id="med-toast" role="status" aria-live="polite"></div>

<script>
(function () {
  "use strict";

  var STORAGE_KEY = "med_tracker_v1";
  var DEDUP_MS = 5 * 60 * 1000;

  // 内存缓存：localStorage 不可用时降级为仅本次会话有效
  var cache = null;

  function pad2(n) { return (n < 10 ? "0" : "") + n; }

  function getData() {
    if (cache) return cache;
    try {
      var d = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
      if (typeof d !== "object" || d === null || Array.isArray(d)) {
        cache = {};
        return {};
      }
      // 数据清洗：仅保留 YYYY-MM-DD 格式的日期 key 与 ISO 时间戳条目，避免渲染/记录时崩溃
      Object.keys(d).forEach(function (k) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(k) || !Array.isArray(d[k])) {
          delete d[k];
          return;
        }
        d[k] = d[k].filter(function (e) {
          return typeof e === "string" &&
            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(e) &&
            !isNaN(new Date(e).getTime());
        });
        if (d[k].length === 0) delete d[k];
      });
      cache = d;
      return d;
    } catch (e) {
      // 存储不可读：缓存空对象，本次会话内不再尝试读取
      cache = {};
      return {};
    }
  }

  function saveData(data) {
    cache = data;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      return true;
    } catch (e) {
      // blocked/full storage: keep in-memory only; report failure to caller
      return false;
    }
  }

  function getTodayKey(d) {
    d = d || new Date();
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }

  function formatTime(date) {
    return pad2(date.getHours()) + ":" + pad2(date.getMinutes()) + ":" + pad2(date.getSeconds());
  }

  function weekdayLabel(dateStr) {
    var days = ["日", "一", "二", "三", "四", "五", "六"];
    return days[new Date(dateStr + "T00:00:00").getDay()];
  }

  var toastEl = document.getElementById("med-toast");
  var toastTimer = null;
  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
      toastTimer = null;
    }, 2000);
  }

  function recordDose() {
    var data = getData();
    var today = getTodayKey();
    if (!data[today]) data[today] = [];

    var now = new Date();
    var list = data[today];
    var lastDose = list.length > 0 ? new Date(list[list.length - 1]) : null;

    // 5 分钟防重复：仅当上次记录有效且为过去 5 分钟内才拦截；
    // 记录无效或时钟回拨时跳过去重，允许记录而非给出误导性提示
    if (lastDose && isFinite(lastDose.getTime()) &&
        (now - lastDose) >= 0 && (now - lastDose) < DEDUP_MS) {
      var secs = Math.floor((now - lastDose) / 1000);
      var msg = "5 分钟内刚吃过" + (secs < 60 ? "" : "（" + Math.floor(secs / 60) + " 分钟前）") + "，无需重复";
      showToast(msg);
      return;
    }

    list.push(now.toISOString());
    var saved = saveData(data);
    showToast(saved ? "已记录：" + formatTime(now) : "⚠ 已记录，但存储不可用（仅本次会话有效）");
    render();
  }

  // 撤销最近一次记录（误点恢复）
  function undoLast() {
    var data = getData();
    var today = getTodayKey();
    var list = data[today];
    if (!list || list.length === 0) return;
    var removed = list.pop();
    if (list.length === 0) delete data[today];
    var saved = saveData(data);
    showToast(saved ? "已撤销：" + formatTime(new Date(removed)) : "⚠ 已撤销，但存储不可用（仅本次会话有效）");
    render();
  }

  // 清空今天的全部记录（需二次确认）
  function clearToday() {
    var data = getData();
    var today = getTodayKey();
    if (!data[today] || data[today].length === 0) return;
    if (!window.confirm("确定清空今天的全部服药记录？此操作不可恢复。")) return;
    delete data[today];
    var saved = saveData(data);
    showToast(saved ? "已清空今日记录" : "⚠ 已清空，但存储不可用（仅本次会话有效）");
    render();
  }

  function render() {
    var data = getData();
    var now = new Date();
    var today = getTodayKey(now);
    var todayDoses = data[today] || [];

    // 今日记录区的操作按钮：有记录才显示
    document.getElementById("med-section-actions").classList.toggle("med-hide", todayDoses.length === 0);

    // 日期头部
    document.getElementById("med-current-date").textContent =
      now.getFullYear() + "年" + (now.getMonth() + 1) + "月" + now.getDate() + "日";

    // 状态卡片
    var card = document.getElementById("med-status-card");
    var icon = document.getElementById("med-status-icon");
    var text = document.getElementById("med-status-text");
    var time = document.getElementById("med-status-time");

    if (todayDoses.length > 0) {
      var last = new Date(todayDoses[todayDoses.length - 1]);
      card.classList.add("taken");
      icon.textContent = "✓";
      text.textContent = "今日已服药 " + todayDoses.length + " 次";
      time.textContent = "上次：" + formatTime(last);
    } else {
      card.classList.remove("taken");
      icon.textContent = "💊";
      text.textContent = "今日尚未服药";
      time.textContent = "";
    }

    // 今日记录列表（时间倒序）
    var listEl = document.getElementById("med-today-list");
    if (todayDoses.length === 0) {
      listEl.innerHTML = '<div class="med-empty">今天还没有服药记录</div>';
    } else {
      var rows = todayDoses.map(function (iso, i) {
        var d = new Date(iso);
        return '<div class="med-record">' +
          '<span class="med-record-time">' + formatTime(d) + "</span>" +
          '<span class="med-record-badge">第 ' + (i + 1) + " 次</span>" +
          "</div>";
      });
      listEl.innerHTML = rows.reverse().join("");
    }

    // 近 7 天历史
    var historyEl = document.getElementById("med-history");
    var daysHtml = [];
    for (var i = 6; i >= 0; i--) {
      var d = new Date();
      d.setDate(d.getDate() - i);
      var key = getTodayKey(d);
      var doses = data[key] || [];
      var isToday = i === 0;
      var label = isToday ? "今天" : weekdayLabel(key);
      // 今天还没记录 → 待定（灰色）；过去某天有记录 → 已吃；过去某天无记录 → 未吃
      var dotClass = isToday && doses.length === 0
        ? "pending"
        : (doses.length > 0 ? "taken" : "missed");
      var count = doses.length > 0 ? doses.length + "次" : (isToday ? "-" : "未");
      daysHtml.push(
        '<div class="med-history-day' + (isToday ? " today" : "") + '">' +
          '<div class="med-history-dot ' + dotClass + '"></div>' +
          '<div class="med-history-label">' + label + "</div>" +
          '<div class="med-history-count">' + count + "</div>" +
        "</div>"
      );
    }
    historyEl.innerHTML = daysHtml.join("");
  }

  document.getElementById("med-take-btn").addEventListener("click", recordDose);
  document.getElementById("med-undo-btn").addEventListener("click", undoLast);
  document.getElementById("med-clear-btn").addEventListener("click", clearToday);

  // 被动刷新事件（visibilitychange / focus / storage）可能同一批次触发，
  // 合并为一次渲染，避免冗余重绘
  var pendingRender = false;
  function scheduleRender() {
    if (pendingRender) return;
    pendingRender = true;
    setTimeout(function () {
      pendingRender = false;
      render();
    }, 0);
  }

  // 重新聚焦页面时刷新（跨天、跨 tab 场景）
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) scheduleRender();
  });
  // 部分浏览器从后台恢复时不触发 visibilitychange，监听 focus 兜底刷新
  window.addEventListener("focus", scheduleRender);
  // 其他标签页写入时同步刷新（清缓存后重读 storage）
  window.addEventListener("storage", function (e) {
    if (e.key === STORAGE_KEY || e.key === null) {
      cache = null;
      scheduleRender();
    }
  });

  // 零点自动刷新：页面常驻（如平板挂在药盒旁）时，跨天后无需手动操作
  function scheduleRollover() {
    var now = new Date();
    var nextMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime();
    setTimeout(function () {
      render();
      scheduleRollover();
    }, nextMidnight - Date.now() + 1000);
  }
  scheduleRollover();

  render();
})();
</script>

______________________________________________________________________

## 📝 使用说明

| 操作             | 说明                                                         |
| ---------------- | ------------------------------------------------------------ |
| **确认已服药**   | 药进嘴的同时点击按钮，立刻记录时间戳（精确到秒）             |
| **防重复**       | 5 分钟内重复点击会提示"5 分钟内刚吃过（N 分钟前），无需重复" |
| **今日记录**     | 按时间倒序列出今天的每一次服药，带「第 N 次」标记            |
| **近 7 天**      | 圆点颜色回顾服药规律：绿=已吃，淡红=未吃，灰=今天还没记录    |
| **清空今日**     | 删除今天的全部记录，需二次确认（🗑 清空今日按钮）             |
| **撤销上次**     | 误点后删除最近一条记录（今日有记录时，标题旁显示按钮）       |
| **次日自动重置** | 跨天后状态卡片自动回到"今日尚未服药"，历史记录保留           |

## 💾 数据说明

- 数据保存在浏览器 **localStorage**（键名 `med_tracker_v1`），纯本地、不上传
- 刷新页面 / 关闭浏览器 / 重启电脑均**保留**；清除浏览器数据、换设备则丢失
- 备份：每周截图保存到相册 / 备忘录；换设备可复制 localStorage 中 `med_tracker_v1` 的值迁移

## 🧭 使用建议

1. **绑定动作链**：打开药盒 → 拿药 → 吞药 → 点确认，关键是"药进嘴的同时"就点，不要等吃完再点
1. **配合 7 天分装药盒**：本工具解决"有没有吃"，分装药盒解决"今天该吃哪格"，双重保险
1. **给老人使用**：按钮足够大、状态用颜色和图标双重提示、历史一目了然
