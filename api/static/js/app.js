/* Bot Control Panel — vanilla ES2020, no build step, no auth. */

const $ = (id) => document.getElementById(id);

let currentTask = null;
let currentRunId = null;
let source = null;

// Recent Runs refresh: 2 s while a run is active, 30 s when idle — a
// running row must update promptly (and flip to its final status) even if
// the SSE stream is closed or disconnected.
let historyTimer = null;
let historyIntervalMs = 30_000;
const HISTORY_ACTIVE_MS = 2_000;
const HISTORY_IDLE_MS = 30_000;

function scheduleHistory(ms) {
  if (ms === historyIntervalMs) return;
  historyIntervalMs = ms;
  if (historyTimer) clearInterval(historyTimer);
  historyTimer = setInterval(refreshHistory, ms);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

async function init() {
  try {
    const info = await api("/api/version");
    $("version").textContent = `v${info.version} · ${info.git_hash || ""}`.trim();
    $("online").classList.add("online");
  } catch { /* server reachable? health will show */ }
  try {
    const { tasks } = await api("/api/tasks");
    const list = $("task-list");
    for (const name of tasks) {
      const li = document.createElement("li");
      li.textContent = name;
      li.onclick = () => selectTask(name, li);
      list.appendChild(li);
    }
  } catch (err) {
    const li = document.createElement("li");
    li.className = "err";
    li.textContent = `⚠ cannot load tasks: ${err.message}`;
    $("task-list").appendChild(li);
  }
  refreshHistory();
  scheduleHistory(HISTORY_IDLE_MS);
}

async function selectTask(name, li) {
  document.querySelectorAll("#task-list li").forEach((n) => n.classList.remove("active"));
  li.classList.add("active");
  currentTask = name;
  $("task-title").textContent = name;
  $("form-hint").hidden = true;
  $("run-form").hidden = false;
  try {
    const schema = await api(`/api/schema/${name}`);
    renderFields(schema.fields || []);
  } catch (err) {
    const p = document.createElement("p");
    p.className = "err";
    p.textContent = `⚠ cannot load schema: ${err.message}`;
    $("fields").appendChild(p);
  }
}

function renderFields(fields) {
  const box = $("fields");
  box.textContent = "";
  // group by schema tab (fields without a tab collapse into one pane)
  const tabs = new Map();
  for (const f of fields) {
    const tab = f.tab || "General";
    if (!tabs.has(tab)) tabs.set(tab, []);
    tabs.get(tab).push(f);
  }
  if (tabs.size <= 1) {
    renderFieldList(box, fields);
  } else {
    const bar = document.createElement("div");
    bar.className = "tab-bar";
    [...tabs.keys()].forEach((tab, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tab-btn" + (i === 0 ? " active" : "");
      btn.textContent = tab;
      btn.dataset.tab = tab;
      btn.addEventListener("click", () => switchTab(bar, box, tab));
      bar.appendChild(btn);
    });
    box.appendChild(bar);
    [...tabs.keys()].forEach((tab, i) => {
      const pane = document.createElement("div");
      pane.className = "tab-pane" + (i === 0 ? " active" : "");
      pane.dataset.pane = tab;
      renderFieldList(pane, tabs.get(tab));
      box.appendChild(pane);
    });
  }
  pairGatedFields(box);
  syncGatedFields(box);
}

function switchTab(bar, box, tab) {
  for (const btn of bar.querySelectorAll(".tab-btn")) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  for (const pane of box.querySelectorAll(".tab-pane")) {
    pane.classList.toggle("active", pane.dataset.pane === tab);
  }
}

function renderFieldList(container, fields) {
  for (const f of fields) {
    const labelText = f.label + (f.required ? " *" : "");
    const label = document.createElement("label");
    let input;
    if (f.type === "select") {
      input = document.createElement("select");
      for (const opt of f.options || []) {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        if (opt === f.default) o.selected = true;
        input.appendChild(o);
      }
    } else if (f.type === "checkbox") {
      label.className = "row";
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = f.default !== false;
      if (f.enables) {
        input.dataset.enables = f.enables;
        input.addEventListener("change", () => syncGatedFields(container));
      }
    } else if (f.type === "repeat") {
      // repeatable value list (--image / --meta): a text input + add button;
      // added values become removable rows collected as an array below
      const wrap = document.createElement("div");
      wrap.className = "repeat-wrap";
      wrap.dataset.name = f.name;
      const row = document.createElement("div");
      row.className = "repeat-row";
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = f.label;
      input.dataset.name = f.name;
      input.dataset.type = "repeat"; // base input — never collected directly
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          addFromBase(wrap, input);
        }
      });
      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "repeat-add";
      addBtn.textContent = "＋";
      addBtn.title = "Add value";
      addBtn.addEventListener("click", () => addFromBase(wrap, input));
      row.appendChild(input);
      row.appendChild(addBtn);
      wrap.appendChild(row);
      label.textContent = labelText;
      container.appendChild(label);
      container.appendChild(wrap);
      continue;
    } else if (f.type === "images") {
      // paired image rows: each row = [path | caption | ×] — the image↔
      // caption relationship is explicit. 📁 Upload images is the single
      // primary action (top); a muted "add path manually" link below the
      // rows appends an empty row for typing an already-staged path.
      const wrap = document.createElement("div");
      wrap.className = "images-wrap";
      wrap.dataset.name = f.name;
      if (f.upload) {
        const bar = document.createElement("div");
        bar.className = "images-bar";
        const fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.accept = "image/*";
        fileInput.multiple = true;
        fileInput.hidden = true;
        const saveAsInput = document.createElement("input");
        saveAsInput.type = "text";
        saveAsInput.placeholder = "save as (optional)";
        saveAsInput.className = "image-saveas";
        saveAsInput.title =
          "Custom save filename for the uploads (extension kept from the original; " +
          "empty = keep original names)";
        fileInput.addEventListener("change", () => uploadImages(wrap, fileInput, saveAsInput));
        const upBtn = document.createElement("button");
        upBtn.type = "button";
        upBtn.className = "upload-btn";
        upBtn.textContent = "📁 Upload images";
        upBtn.title = "Pick image files from this computer — each file becomes a row";
        upBtn.addEventListener("click", () => fileInput.click());
        bar.appendChild(upBtn);
        bar.appendChild(saveAsInput);
        bar.appendChild(fileInput);
        wrap.appendChild(bar);
      }
      const manual = document.createElement("button");
      manual.type = "button";
      manual.className = "images-add";
      manual.textContent = "＋ add image path manually";
      manual.title = "Add a row and type an image path (e.g. a .bot-api/uploads/… file)";
      manual.addEventListener("click", () => {
        const row = addImageRow(wrap);
        if (row) row.querySelector(".image-path").focus();
      });
      wrap.appendChild(manual);
      label.textContent = labelText;
      container.appendChild(label);
      container.appendChild(wrap);
      continue;
    } else if (f.type === "textarea") {
      input = document.createElement("textarea");
      input.placeholder = f.label;
    } else {
      input = document.createElement("input");
      input.type = f.type || "text";
      if (f.step) input.step = f.step;
    }
    input.dataset.name = f.name;
    input.dataset.type = f.type;
    label.textContent = labelText; // set once — checkbox prepends its input
    if (f.type === "checkbox") label.prepend(input);
    else label.appendChild(input);
    container.appendChild(label);
  }
}

// add a value row from the base input; an empty input shows visible
// feedback instead of silently doing nothing (the reported "＋ no response")
function addFromBase(wrap, baseInput) {
  if (addRepeatValue(wrap, baseInput.value)) {
    baseInput.value = "";
    baseInput.focus();
    return;
  }
  baseInput.classList.add("flash");
  setTimeout(() => baseInput.classList.remove("flash"), 700);
  appendLog({ time: "--:--:--", level: "warn", msg: "type a value first, then ＋" });
  baseInput.focus();
}

// append one removable value row carrying *text*; returns false when empty
function addRepeatValue(wrap, text) {
  const value = (text || "").trim();
  if (!value) return false;
  const row = document.createElement("div");
  row.className = "repeat-value-row";
  const input = document.createElement("input");
  input.type = "text";
  input.value = value;
  input.dataset.name = wrap.dataset.name;
  input.className = "repeat-value";
  const del = document.createElement("button");
  del.type = "button";
  del.className = "repeat-del";
  del.textContent = "×";
  del.title = "Remove";
  del.addEventListener("click", () => row.remove());
  row.appendChild(input);
  row.appendChild(del);
  wrap.appendChild(row);
  return true;
}

// append one image row (path + optional caption) to the paired list; *path*
// pre-fills the path input (e.g. from an upload). Returns the row.
function addImageRow(wrap, path) {
  const row = document.createElement("div");
  row.className = "image-row";
  const pathInput = document.createElement("input");
  pathInput.type = "text";
  pathInput.placeholder = "image path";
  pathInput.className = "image-path";
  if (path) pathInput.value = path;
  const capInput = document.createElement("input");
  capInput.type = "text";
  capInput.placeholder = "caption (optional, no spaces)";
  capInput.className = "image-caption";
  const del = document.createElement("button");
  del.type = "button";
  del.className = "repeat-del";
  del.textContent = "×";
  del.title = "Remove this image";
  del.addEventListener("click", () => row.remove());
  row.appendChild(pathInput);
  row.appendChild(capInput);
  row.appendChild(del);
  wrap.appendChild(row);
  return row;
}

// browser file picker → base64 JSON → /api/upload → one image row per file;
// an optional "save as" value renames every uploaded file (extension kept
// from the original)
async function uploadImages(wrap, fileInput, saveAsInput) {
  const files = [...fileInput.files];
  if (!files.length) return;
  const saveAs = (saveAsInput && saveAsInput.value.trim()) || "";
  try {
    const items = [];
    for (const file of files) {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      const comma = dataUrl.indexOf(",");
      const item = { name: file.name, data: comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl };
      if (saveAs) item.save_as = saveAs;
      items.push(item);
    }
    const res = await api("/api/upload", {
      method: "POST",
      body: JSON.stringify({ files: items }),
    });
    for (const path of res.files) addImageRow(wrap, path);
    appendLog({ time: "--:--:--", level: "ok", msg: `📁 uploaded ${res.files.length} image(s)` });
  } catch (err) {
    appendLog({ time: "--:--:--", level: "err", msg: `📁 upload failed: ${err.message}` });
  } finally {
    fileInput.value = ""; // allow re-picking the same file
  }
}

// the sibling fields a checkbox gates (comma-separated `enables`)
function gatedTargets(cb, box) {
  return (cb.dataset.enables || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((name) => box.querySelector(`[data-name="${name}"]`))
    .filter(Boolean);
}

// checkbox-gated option fields (e.g. weight "Specify date" → date picker;
// moment "Set coordinates" → lng/lat/crs): the checkbox and its gated fields
// share one row; the gated fields stay hidden (and value-cleared) until the
// box is checked. A gate covering a coordinate pair (lng+lat) also gets a
// "Use my location" button that fills them from the browser geolocation API.
function pairGatedFields(box) {
  for (const cb of box.querySelectorAll('input[type="checkbox"][data-enables]')) {
    const cbLabel = cb.closest("label");
    if (!cbLabel || cbLabel.parentElement.classList.contains("gate-row")) continue;
    const targets = gatedTargets(cb, box);
    if (!targets.length) continue;
    const names = new Set(targets.map((t) => t.dataset.name));
    const row = document.createElement("div");
    row.className = "gate-row";
    cbLabel.after(row);
    row.appendChild(cbLabel);
    for (const target of targets) row.appendChild(target.closest("label") || target);
    if (names.has("lng") && names.has("lat")) {
      const locate = document.createElement("button");
      locate.type = "button";
      locate.className = "locate-btn";
      locate.textContent = "📍 Use my location";
      locate.title = "Fill coordinates from the browser's current position (WGS-84)";
      locate.addEventListener("click", () => useMyLocation(cb, box));
      row.appendChild(locate);
    }
  }
}

// browser geolocation → lng/lat (WGS-84): auto-checks the gate so the gated
// inputs become editable, fills them, and reports the result in the output
function useMyLocation(gateCb, box) {
  if (!navigator.geolocation) {
    appendLog({ time: "--:--:--", level: "err", msg: "📍 geolocation is not supported by this browser" });
    return;
  }
  appendLog({ time: "--:--:--", level: "info", msg: "📍 requesting browser location…" });
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      gateCb.checked = true;
      syncGatedFields(box); // enable the gated inputs
      const lng = box.querySelector('[data-name="lng"]');
      const lat = box.querySelector('[data-name="lat"]');
      const crs = box.querySelector('[data-name="crs"]');
      if (lng) lng.value = pos.coords.longitude.toFixed(6);
      if (lat) lat.value = pos.coords.latitude.toFixed(6);
      if (crs) crs.value = "wgs84"; // browser coords are already WGS-84
      appendLog({
        time: "--:--:--",
        level: "ok",
        msg: `📍 browser location: ${pos.coords.latitude.toFixed(6)}, ${pos.coords.longitude.toFixed(6)} (WGS-84)`,
      });
    },
    (err) => {
      const why =
        err.code === err.PERMISSION_DENIED
          ? "permission denied — allow location access or type the coordinates"
          : err.message || `code ${err.code}`;
      appendLog({ time: "--:--:--", level: "err", msg: `📍 geolocation failed: ${why}` });
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
  );
}

function syncGatedFields(box) {
  for (const cb of box.querySelectorAll('input[type="checkbox"][data-enables]')) {
    for (const target of gatedTargets(cb, box)) {
      target.disabled = !cb.checked;
      const targetLabel = target.closest("label") || target;
      targetLabel.classList.toggle("gated-off", !cb.checked);
      if (!cb.checked) target.value = "";
    }
  }
}

function collectFields() {
  const fields = {};
  const box = $("fields");
  for (const input of box.querySelectorAll("[data-name]")) {
    if (input.disabled) continue; // gated-off option (e.g. date / coordinates)
    if (input.dataset.type === "repeat") continue; // base input — values below
    if (input.type === "checkbox") {
      fields[input.dataset.name] = input.checked;
    } else if (input.value !== "") {
      fields[input.dataset.name] = input.value;
    }
  }
  // repeatable fields → the added values as an array (--image / --meta).
  // ORDER MATTERS: the data-name loop above already collected each value
  // row as a scalar (they carry data-name); this array pass must run LAST
  // so it overwrites those scalars with the correct list.
  for (const wrap of box.querySelectorAll(".repeat-wrap")) {
    const name = wrap.dataset.name;
    const values = [...wrap.querySelectorAll(".repeat-value")]
      .map((v) => v.value.trim())
      .filter((v) => v !== "");
    if (values.length) fields[name] = values;
  }
  // paired image rows → [{path, caption}] (only rows with a path)
  for (const wrap of box.querySelectorAll(".images-wrap")) {
    const rows = [...wrap.querySelectorAll(".image-row")]
      .map((row) => ({
        path: row.querySelector(".image-path").value.trim(),
        caption: row.querySelector(".image-caption").value.trim(),
      }))
      .filter((r) => r.path);
    if (rows.length) fields[wrap.dataset.name] = rows;
  }
  return fields;
}

function linkify(text) {
  const esc = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  return esc.replace(/(https?:\/\/[^\s<>"']+)/g, (match) => {
    const clean = match.replace(/[.,;:!?)\]}]+$/, "");
    if (!clean) return match;
    return `<a href="${clean}" target="_blank" rel="noopener">${clean}</a>` + match.slice(clean.length);
  });
}

function appendLog(entry) {
  const pre = $("output");
  const line = document.createElement("div");
  line.className = entry.level || "";
  line.innerHTML = linkify(`[${entry.time}] ${entry.msg}`);
  pre.appendChild(line);
  pre.scrollTop = pre.scrollHeight;
}

function setAbort(run) {
  // label names the exact run this button targets (task + args), so it
  // reads as per-run, not a global control — long flag strings (e.g.
  // --image=/path/…/photo.jpg) are truncated to keep the button compact;
  // the run id stays in the tooltip
  const label = `${run.task}${run.args ? " " + run.args : ""}`.trim();
  const short = label.length > 42 ? label.slice(0, 39) + "…" : label;
  $("abort-btn").textContent = `✖ Abort ${short}`;
  $("abort-btn").title = `Abort run ${run.run_id}`;
  $("abort-btn").hidden = false;
}

function clearAbort() {
  $("abort-btn").hidden = true;
}

function connectStream(runId, streamUrl) {
  if (source) source.close();
  currentRunId = runId;
  $("run-btn").disabled = true;
  source = new EventSource(streamUrl);
  source.onmessage = (ev) => {
    if (ev.data === "[RESET]") {
      $("output").textContent = "";
    } else if (ev.data === "[DONE]") {
      source.close();
      source = null;
      $("run-btn").disabled = false;
      clearAbort();
      scheduleHistory(HISTORY_IDLE_MS);
      refreshHistory();
      showRunResult(currentRunId);
    } else {
      appendLog(JSON.parse(ev.data));
    }
  };
  source.onerror = () => { /* EventSource reconnects automatically */ };
}

async function showRunResult(runId) {
  try {
    const st = await api(`/api/bot/status/${runId}`);
    appendLog({
      time: "--:--:--",
      level: ["submitted", "merged", "noop"].includes(st.status) ? "ok" : "err",
      msg: `done: ${st.status}${st.pr_url ? " " + st.pr_url : ""}`,
    });
  } catch { /* ignore — history pane still refreshes */ }
}

async function onRun(e) {
  e.preventDefault();
  // guard against double-submit: the run button is disabled while a POST is
  // in flight AND while a run is streaming — but an Enter key in a text
  // field submits the form regardless of the button's disabled state, so
  // check it explicitly here too (otherwise pressing Enter would spawn
  // duplicate runs)
  if (!currentTask || $("run-btn").disabled) return;
  $("run-btn").disabled = true;
  $("output").textContent = "";
  const body = {
    task: currentTask,
    fields: collectFields(),
    handoff: ($("handoff")?.checked) ?? true,
  };
  try {
    const run = await api("/api/bot/run", { method: "POST", body: JSON.stringify(body) });
    connectStream(run.run_id, run.stream_url);
    setAbort(run);
    scheduleHistory(HISTORY_ACTIVE_MS); // fast-poll while the run is active
  } catch (err) {
    $("run-btn").disabled = false;
    appendLog({ time: "--:--:--", level: "err", msg: `❌ ${err.message}` });
  }
}

async function onAbort() {
  if (!currentRunId) return;
  await api(`/api/bot/abort/${currentRunId}`, { method: "POST" });
  appendLog({ time: "--:--:--", level: "warn", msg: "⚠ abort requested" });
}

function showRunLogs(r) {
  if (source) {
    source.close();
    source = null;
  }
  currentRunId = null;
  clearAbort();
  $("run-btn").disabled = false;
  $("output").textContent = "";
  const head = document.createElement("div");
  head.className = "cmd";
  head.innerHTML = linkify(
    `[history] ${r.task} ${r.args || ""} — ${r.status}${r.pr_url ? " " + r.pr_url : ""}`
  );
  $("output").appendChild(head);
  for (const e of r.logs || []) appendLog(e);
  if (!(r.logs || []).length) {
    const p = document.createElement("div");
    p.className = "warn";
    p.textContent = "(no logs recorded)";
    $("output").appendChild(p);
  }
}

async function refreshHistory() {
  try {
    const data = await api("/api/bot/history?limit=15");
    const tbody = $("history").querySelector("tbody");
    tbody.textContent = "";
    const rows = [
      ...data.running.map((r) => ({ ...r, running: true })),
      ...data.records,
    ];
    for (const r of rows.slice(0, 15)) {
      const tr = document.createElement("tr");
      const time = (r.started_at || "").slice(5, 16).replace("T", " ");
      tr.innerHTML = `<td>${time}</td><td>${r.task}</td><td class="status ${r.status}">${r.status}</td>`;
      const last = (r.logs || []).slice(-1)[0];
      if (last) tr.title = `[${last.time}] ${last.msg}`;
      tr.classList.add("clickable");
      tr.onclick = () => {
        if (r.running) connectStream(r.run_id, `/api/bot/stream/${r.run_id}`);
        else showRunLogs(r);
      };
      tbody.appendChild(tr);
    }
    // if nothing is running and we're not streaming, settle back to idle
    // (covers streams closed via showRunLogs where [DONE] never arrives)
    if (currentRunId === null && !data.running.length) scheduleHistory(HISTORY_IDLE_MS);
  } catch { /* console stays silent on history errors */ }
}

$("run-form").addEventListener("submit", onRun);
$("abort-btn").addEventListener("click", onAbort);
init();
