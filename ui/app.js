/* VAD Benchmark dashboard — vanilla JS, no build.
   Sister project: ocr-benchmark/ui/app.js (same patterns). */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ─── State ──────────────────────────────────────────────────
let CFG = null;            // runtime config from /api/config
let MODELS = [];           // available .bin files
let LAST_SUMMARY = null;   // latest /api/summary
let RUNNING = false;
let sseSource = null;

// Default 2-config comparison (mirrors scripts/run_benchmark.py)
const DEFAULT_CONFIGS = () => ([
  { name: "baseline_novad", overrides: { vad_enabled: false } },
  { name: "silero_vad",     overrides: { vad_enabled: true  } },
]);

// ─── Init ───────────────────────────────────────────────────
async function init() {
  await Promise.all([loadConfig(), loadModels(), refreshSystem()]);
  pollSystem();
  openSSE();
  // Render run panel.
  renderConfigs(DEFAULT_CONFIGS());
  // Try to load last results if present.
  await tryLoadLastResults();
  await refreshHistory();
}

async function loadConfig() {
  CFG = await fetch("/api/config").then(r => r.json());
  $("#model-badge-text").textContent = CFG.whisper_model;
  const vad = $("#vad-badge");
  vad.classList.toggle("is-on",  CFG.vad_enabled);
  vad.classList.toggle("is-off", !CFG.vad_enabled);
  $("#vad-badge-text").textContent = CFG.vad_enabled ? "VAD on (default)" : "VAD off (default)";
}

async function loadModels() {
  try {
    const data = await fetch("/api/models").then(r => r.json());
    MODELS = data.available || [];
  } catch { MODELS = []; }
}

// ─── System resources ──────────────────────────────────────
let sysmonTimer = null;
function pollSystem() {
  if (sysmonTimer) clearInterval(sysmonTimer);
  sysmonTimer = setInterval(refreshSystem, 4000);
}
async function refreshSystem() {
  try {
    const s = await fetch("/api/system").then(r => r.json());
    setSysmon("cpu",      s.cpu_percent, s.cpu_count,  "%", 100);
    setSysmon("ram",      s.ram_percent, null,         "%", 100, `${s.ram_used_mb.toFixed(0)} / ${s.ram_total_mb.toFixed(0)} MB`);
    setSysmon("cputemp",  s.cpu_temp_c,  null,         "°C", 100, s.cpu_temp_c != null ? `${s.cpu_temp_c.toFixed(1)} °C` : "no sensor");
    const gpu = (s.gpus && s.gpus[0]) || null;
    setSysmon("gpu", gpu ? gpu.util_percent : null, null, "%", 100,
              gpu ? `${gpu.name} · ${(gpu.mem_used_mb ?? 0).toFixed(0)}/${(gpu.mem_total_mb ?? 0).toFixed(0)} MB` : "no NVIDIA GPU");
    $("#sysmon-updated").textContent = s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : "–";
  } catch (e) { /* swallow */ }
}
function setSysmon(metric, value, count, unit, max, sub) {
  const val = value == null ? "–" : (metric === "cputemp" ? value.toFixed(1) + unit : value.toFixed(0) + unit);
  $(`#sysmon-${metric === "cputemp" ? "cputemp" : metric}-val`).textContent = val;
  const pct = value == null ? 0 : Math.min(100, (value / max) * 100);
  $(`#sysmon-${metric === "cputemp" ? "cputemp" : metric}-bar`).style.width = pct + "%";
  $(`#sysmon-${metric === "cputemp" ? "cputemp" : metric}-sub`).textContent = sub || (count ? `${count} cores` : "");
}

// ─── SSE progress ──────────────────────────────────────────
function openSSE() {
  if (sseSource) try { sseSource.close(); } catch {}
  sseSource = new EventSource("/api/progress/stream");
  sseSource.onmessage = (ev) => {
    try {
      const status = JSON.parse(ev.data);
      onProgress(status);
    } catch (e) { /* ignore */ }
  };
  sseSource.onerror = () => { /* EventSource auto-reconnects */ };
}

function onProgress(status) {
  const el = $("#run-status");
  if (status.running) {
    RUNNING = true;
    el.classList.add("is-running"); el.classList.remove("is-error");
    const cur = status.current ? status.current.name : "—";
    const done = (status.completed || []).length;
    const total = status.total || "?";
    el.textContent = `Running · ${done}/${total} · now: ${cur}${status.stale ? " · (looks stuck — already-running lock older than stale threshold)" : ""}`;
    $("#btn-run").disabled = true;
    $("#btn-run").textContent = "Running…";
  } else {
    RUNNING = false;
    $("#btn-run").disabled = false;
    $("#btn-run").textContent = "Run benchmark";
    if (status.error) {
      el.classList.add("is-error"); el.classList.remove("is-running");
      el.textContent = `Error: ${status.error}`;
    } else if (status.finished_at) {
      el.classList.remove("is-error", "is-running");
      const done = (status.completed || []).length;
      el.textContent = `Done · ${done} configs · ${status.finished_at}`;
      // Refresh results + history.
      tryLoadLastResults();
      refreshHistory();
    } else {
      el.classList.remove("is-error", "is-running");
      el.textContent = "Idle.";
    }
  }
}

// ─── Run panel (configurable surface) ──────────────────────
function renderConfigs(list) {
  const root = $("#configs-list");
  root.innerHTML = "";
  list.forEach((cfg, i) => root.appendChild(configCard(cfg, i)));
}

function configCard(cfg, index) {
  const card = document.createElement("div");
  card.className = "config-card";
  const vadOn = !!(cfg.overrides && cfg.overrides.vad_enabled);
  const ov = cfg.overrides || {};
  card.innerHTML = `
    <div class="config-card-head">
      <input class="config-name-input" type="text" value="${escapeAttr(cfg.name)}" placeholder="config name" />
      <button class="config-vad-toggle ${vadOn ? "is-on" : ""}" data-role="vad-toggle">
        <span class="toggle-dot"></span>
        <span data-role="vad-label">${vadOn ? "VAD on" : "VAD off"}</span>
      </button>
      <button class="btn-icon" data-role="remove" title="Remove this config">remove</button>
    </div>
    <div class="config-card-grid">
      <div class="field">
        <span class="field-label">Whisper model</span>
        <select data-role="whisper_model">
          ${MODELS.length === 0
              ? `<option value="${escapeAttr(CFG.whisper_model)}">${escapeHtml(CFG.whisper_model)}</option>`
              : MODELS.filter(m => !/silero/i.test(m)).map(m =>
                  `<option value="${escapeAttr(m)}" ${m === (ov.whisper_model || CFG.whisper_model) ? "selected" : ""}>${escapeHtml(m)}</option>`
                ).join("")}
        </select>
      </div>
      <div class="field">
        <span class="field-label">Language</span>
        <select data-role="language">
          <option value="id"   ${(ov.language || CFG.language) === "id"   ? "selected" : ""}>id (Indonesian)</option>
          <option value="auto" ${(ov.language || CFG.language) === "auto" ? "selected" : ""}>auto</option>
          <option value="en"   ${(ov.language || CFG.language) === "en"   ? "selected" : ""}>en</option>
        </select>
      </div>
      <div class="field">
        <span class="field-label">Threads</span>
        <input type="number" min="1" max="32" step="1" data-role="threads" value="${ov.threads ?? CFG.threads}" />
      </div>
      <div class="field">
        <span class="field-label">VAD threshold <span class="field-value" data-role="vad_threshold_val">${ov.vad_threshold ?? CFG.vad_threshold}</span></span>
        <input type="range" min="0.10" max="0.90" step="0.05" data-role="vad_threshold" value="${ov.vad_threshold ?? CFG.vad_threshold}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label">Min speech (ms) <span class="field-value" data-role="vad_min_speech_ms_val">${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_speech_ms" value="${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label">Min silence (ms) <span class="field-value" data-role="vad_min_silence_ms_val">${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_silence_ms" value="${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label">Speech pad (ms) <span class="field-value" data-role="vad_speech_pad_ms_val">${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}</span></span>
        <input type="range" min="0" max="500" step="10" data-role="vad_speech_pad_ms" value="${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label">Max speech (s, 0=∞)</span>
        <input type="number" min="0" step="1" data-role="vad_max_speech_s" value="${ov.vad_max_speech_s ?? CFG.vad_max_speech_s}" ${vadOn ? "" : "disabled"} />
      </div>
    </div>
  `;

  // Wire up events
  const vadBtn = card.querySelector('[data-role="vad-toggle"]');
  const vadLabel = card.querySelector('[data-role="vad-label"]');
  const ranges = card.querySelectorAll('input[type="range"]');
  vadBtn.addEventListener("click", () => {
    const on = !vadBtn.classList.contains("is-on");
    vadBtn.classList.toggle("is-on", on);
    vadLabel.textContent = on ? "VAD on" : "VAD off";
    ranges.forEach(r => r.disabled = !on);
    card.querySelector('[data-role="vad_max_speech_s"]').disabled = !on;
  });
  ranges.forEach(r => {
    r.addEventListener("input", () => {
      const valEl = card.querySelector(`[data-role="${r.dataset.role}_val"]`);
      if (valEl) valEl.textContent = r.value;
    });
  });
  card.querySelector('[data-role="remove"]').addEventListener("click", () => {
    card.remove();
  });

  return card;
}

function collectConfigs() {
  const cards = $$("#configs-list .config-card");
  return cards.map(card => {
    const overrides = {
      vad_enabled: card.querySelector('[data-role="vad-toggle"]').classList.contains("is-on"),
    };
    const roleToField = {
      "whisper_model": "whisper_model",
      "language":      "language",
      "threads":       "threads",
      "vad_threshold": "vad_threshold",
      "vad_min_speech_ms": "vad_min_speech_ms",
      "vad_min_silence_ms": "vad_min_silence_ms",
      "vad_speech_pad_ms":  "vad_speech_pad_ms",
      "vad_max_speech_s":   "vad_max_speech_s",
    };
    for (const [role, field] of Object.entries(roleToField)) {
      const el = card.querySelector(`[data-role="${role}"]`);
      if (!el) continue;
      const v = el.value;
      if (field === "threads" || field.endsWith("_ms") || field.endsWith("_s")) {
        const n = Number(v);
        if (!Number.isNaN(n)) overrides[field] = n;
      } else if (field === "vad_threshold") {
        const n = Number(v);
        if (!Number.isNaN(n)) overrides[field] = n;
      } else {
        overrides[field] = v;
      }
    }
    const name = card.querySelector(".config-name-input").value.trim() || `config_${cards.indexOf(card) + 1}`;
    return { name, overrides };
  });
}

$("#btn-add-config").addEventListener("click", () => {
  const root = $("#configs-list");
  root.appendChild(configCard({ name: `config_${root.children.length + 1}`, overrides: { vad_enabled: true } }, root.children.length));
});
$("#btn-default-compare").addEventListener("click", () => renderConfigs(DEFAULT_CONFIGS()));

$("#btn-run").addEventListener("click", async () => {
  const configs = collectConfigs();
  if (configs.length === 0) { alert("Add at least one config."); return; }
  if (RUNNING) { return; }
  $("#run-status").textContent = "Submitting…";
  $("#run-status").classList.remove("is-error"); $("#run-status").classList.add("is-running");
  try {
    const resp = await fetch(`/api/run?configs=${encodeURIComponent(JSON.stringify(configs))}`, { method: "POST" });
    const data = await resp.json();
    if (!data.ok && data.already_running) {
      $("#run-status").textContent = "Already running — open Progress / wait for it to finish.";
    } else {
      $("#run-status").textContent = "Started.";
    }
  } catch (e) {
    $("#run-status").textContent = "Failed: " + e.message;
    $("#run-status").classList.add("is-error");
  }
});

// ─── Results ───────────────────────────────────────────────
async function tryLoadLastResults() {
  try {
    const sum = await fetch("/api/summary").then(r => r.json());
    if (!sum || !sum.configs) return;
    LAST_SUMMARY = sum;
    renderResults(sum);
    $("#results-panel").hidden = false;
    $("#last-run").textContent = formatTs(sum.last_run);
    $("#audio-meta").textContent = `podcast.mp3 · 16 kHz mono · ${(sum.audio_duration_s || 0).toFixed(1)}s`;
  } catch (e) { /* no summary yet */ }
}

function renderResults(sum) {
  $("#results-meta").textContent = `${(sum.audio_duration_s || 0).toFixed(1)}s audio · ${sum.configs.length} configs · last ${formatTs(sum.last_run)}`;
  $("#results-summary").innerHTML = `
    <div class="summary-tile">
      <div class="tile-label">Best WER</div>
      <div class="tile-value">${sum.best_wer_config || "–"}</div>
      <div class="tile-sub">${(minOf(sum.configs, "wer") ?? 0).toFixed(3)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">Best CER</div>
      <div class="tile-value">${sum.best_cer_config || "–"}</div>
      <div class="tile-sub">${(minOf(sum.configs, "cer") ?? 0).toFixed(3)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">Fastest RTF</div>
      <div class="tile-value">${sum.fastest_rtf_config || "–"}</div>
      <div class="tile-sub">${(minOf(sum.configs, "rtf") ?? 0).toFixed(3)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">Total runtime</div>
      <div class="tile-value">${(sum.total_runtime_s || 0).toFixed(1)}s</div>
      <div class="tile-sub">${sum.configs.length} configs</div>
    </div>
  `;

  const tbody = $("#results-table tbody");
  tbody.innerHTML = "";
  const bestWer = minOf(sum.configs, "wer");
  const bestCer = minOf(sum.configs, "cer");
  sum.configs.forEach(c => {
    const tr = document.createElement("tr");
    tr.dataset.config = c.config;
    const isBest = (c.wer === bestWer);
    if (isBest) tr.classList.add("is-best");
    tr.innerHTML = `
      <td>${escapeHtml(c.config)}</td>
      <td><span class="config-vad-toggle ${c.vad_enabled ? "is-on" : ""}"><span class="toggle-dot"></span>${c.vad_enabled ? "on" : "off"}</span></td>
      <td class="num metric-cell metric-wer">${(c.wer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-cer">${(c.cer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-rtf">${(c.rtf ?? 0).toFixed(3)}</td>
      <td class="num">${(c.runtime_s ?? 0).toFixed(1)}s</td>
      <td class="num">${c.silence_removed != null ? (c.silence_removed * 100).toFixed(1) + "%" : "–"}</td>
      <td class="num">${c.n_segments ?? "–"}</td>
      <td>${escapeHtml(c.whisper_model || "–")}</td>
    `;
    tr.addEventListener("click", () => selectConfig(c.config));
    tbody.appendChild(tr);
  });

  $("#best-line").textContent =
    `Best WER: ${sum.best_wer_config} (${bestWer?.toFixed(3) ?? "–"}). ` +
    `Best CER: ${sum.best_cer_config} (${bestCer?.toFixed(3) ?? "–"}). ` +
    `Fastest: ${sum.fastest_rtf_config}.`;

  // Auto-select first row.
  if (sum.configs.length > 0) selectConfig(sum.configs[0].config);
}

let SELECTED = null;
async function selectConfig(config) {
  SELECTED = config;
  $$("#results-table tbody tr").forEach(tr => {
    tr.classList.toggle("is-selected", tr.dataset.config === config);
  });
  try {
    const detail = await fetch(`/api/results/${encodeURIComponent(config)}`).then(r => r.json());
    renderDetail(detail);
  } catch (e) { /* ignore */ }
}

function renderDetail(d) {
  const root = $("#config-detail");
  root.innerHTML = `
    <div class="diff-block">
      <h3>Transcript — ${escapeHtml(d.config)} (VAD ${d.vad_enabled ? "on" : "off"})</h3>
      <div class="diff-stream">${escapeHtml(d.transcript_raw || "(empty)")}</div>
    </div>
    <div class="diff-block">
      <h3>Diff vs reference</h3>
      <div class="diff-stream">${renderAlignment(d.alignment || [])}</div>
      <div class="diff-legend">
        <span class="diff-eq">equal</span>
        <span class="diff-sub">substitute</span>
        <span class="diff-ins">insert</span>
        <span class="diff-del">delete</span>
      </div>
    </div>
  `;
}

function renderAlignment(parts) {
  if (!parts.length) return "<span class='muted'>(no reference text)</span>";
  return parts.map(p => {
    if (p.kind === "equal") return `<span class="diff-eq">${escapeHtml(p.ref || p.hyp || "")}</span>`;
    if (p.kind === "substitute") return `<span class="diff-sub">${escapeHtml(p.hyp || p.ref)}</span>`;
    if (p.kind === "insert")    return `<span class="diff-ins">${escapeHtml(p.hyp || "")}</span>`;
    if (p.kind === "delete")    return `<span class="diff-del">${escapeHtml(p.ref || "")}</span>`;
    return "";
  }).join(" ");
}

// ─── History ───────────────────────────────────────────────
async function refreshHistory() {
  try {
    const data = await fetch("/api/history").then(r => r.json());
    const body = $("#history-body");
    body.innerHTML = "";
    if (!data.runs || data.runs.length === 0) {
      $("#history-panel").hidden = true;
      return;
    }
    $("#history-panel").hidden = false;
    data.runs.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${formatTs(r.timestamp)}</td>
        <td class="num">${r.n_configs ?? "–"}</td>
        <td>${escapeHtml(r.best_wer_config || "–")} <span class="muted">(${r.best_wer != null ? r.best_wer.toFixed(3) : "–"})</span></td>
        <td>${escapeHtml(r.best_cer_config || "–")} <span class="muted">(${r.best_cer != null ? r.best_cer.toFixed(3) : "–"})</span></td>
        <td class="num">${(r.total_runtime_s ?? 0).toFixed(1)}s</td>
        <td class="num">${(r.audio_duration_s ?? 0).toFixed(1)}s</td>
      `;
      body.appendChild(tr);
    });
  } catch { /* ignore */ }
}

// ─── Helpers ────────────────────────────────────────────────
function escapeHtml(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }
function escapeAttr(s) { return escapeHtml(s); }
function minOf(arr, key) { return arr.reduce((m, x) => x[key] < m ? x[key] : m, Infinity); }
function formatTs(iso) {
  if (!iso) return "–";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

// ─── Boot ───────────────────────────────────────────────────
init().catch(err => {
  console.error("init failed", err);
  $("#run-status").textContent = "Init failed: " + err.message;
  $("#run-status").classList.add("is-error");
});