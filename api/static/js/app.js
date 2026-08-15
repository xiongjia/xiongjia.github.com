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
        input.addEventListener("change", () => syncGatedFields(box));
      }
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
    box.appendChild(label);
  }
  pairGatedFields(box);
  syncGatedFields(box);
}

// checkbox-gated option fields (e.g. weight "Specify date" → date picker):
// the checkbox and its gated field share one row; the gated field stays
// hidden (and value-cleared) until the box is checked.
function pairGatedFields(box) {
  for (const cb of box.querySelectorAll('input[type="checkbox"][data-enables]')) {
    const target = box.querySelector(`[data-name="${cb.dataset.enables}"]`);
    if (!target) continue;
    const cbLabel = cb.closest("label");
    if (!cbLabel) continue; // checkbox outside a label — nothing to pair
    const targetLabel = target.closest("label") || target;
    if (cbLabel.parentElement.classList.contains("gate-row")) continue; // already paired
    const row = document.createElement("div");
    row.className = "gate-row";
    cbLabel.after(row);
    row.appendChild(cbLabel);
    row.appendChild(targetLabel);
  }
}

function syncGatedFields(box) {
  for (const cb of box.querySelectorAll('input[type="checkbox"][data-enables]')) {
    const target = box.querySelector(`[data-name="${cb.dataset.enables}"]`);
    if (!target) continue;
    target.disabled = !cb.checked;
    const targetLabel = target.closest("label") || target;
    targetLabel.classList.toggle("gated-off", !cb.checked);
    if (!cb.checked) target.value = "";
  }
}

function collectFields() {
  const fields = {};
  for (const input of document.querySelectorAll("#fields [data-name]")) {
    if (input.disabled) continue; // gated-off option (e.g. date picker)
    if (input.type === "checkbox") {
      fields[input.dataset.name] = input.checked;
    } else if (input.value !== "") {
      fields[input.dataset.name] = input.value;
    }
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
  // reads as per-run, not a global control
  $("abort-btn").textContent = `✖ Abort ${run.task}${run.args ? " " + run.args : ""}`.trim();
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
      level: ["submitted", "merged"].includes(st.status) ? "ok" : "err",
      msg: `done: ${st.status}${st.pr_url ? " " + st.pr_url : ""}`,
    });
  } catch { /* ignore — history pane still refreshes */ }
}

async function onRun(e) {
  e.preventDefault();
  if (!currentTask) return;
  $("run-btn").disabled = true; // guard against double-submit while POST is in flight
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
