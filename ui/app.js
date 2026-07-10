/* VAD Benchmark dashboard — vanilla JS, no build.
   Sister project: ocr-benchmark/ui/app.js (same patterns). */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ─── i18n ───────────────────────────────────────────────────
const I18N = {
  en: {
    "topbar.title":         "VAD Benchmark",
    "topbar.sub":           "ai4db · Indonesian · Silero VAD vs none",
    "stepper.1":            "Configure",
    "stepper.2":            "Run",
    "stepper.3":            "Compare results",
    "audio.title":          "Audio under test",
    "audio.meta":           "podcast.mp3 · 16 kHz mono",
    "run.title":            "Run benchmark",
    "run.sub":              "Configure each config's VAD knobs, then click Run.",
    "run.addConfig":        "+ Add config",
    "run.reset":            "Reset to baseline vs silero",
    "run.runBtn":           "Run benchmark",
    "run.running":          "Running…",
    "run.idle":             "Idle.",
    "run.started":          "Started.",
    "run.submitting":       "Submitting…",
    "run.failed":           "Failed: ",
    "run.alreadyRunning":   "Already running — wait for it to finish.",
    "run.notReady":         "Not ready: ",
    "run.emptyAlert":       "Add at least one config.",
    "run.staleNote":        " · (looks stuck — already-running lock older than stale threshold)",
    "run.runningPrefix":    "Running · ",
    "run.donePrefix":       "Done · ",
    "run.errorPrefix":      "Error: ",
    "field.whisper":        "Whisper model",
    "field.language":       "Language",
    "field.threads":        "Threads",
    "field.vadThreshold":   "VAD threshold",
    "field.minSpeech":      "Min speech (ms)",
    "field.minSilence":     "Min silence (ms)",
    "field.speechPad":      "Speech pad (ms)",
    "field.maxSpeech":      "Max speech (s, 0=∞)",
    "field.vadOn":          "VAD on",
    "field.vadOff":         "VAD off",
    "field.remove":         "remove",
    "results.title":        "Results",
    "results.metaFmt":      "{audio}s audio · {n} configs · last {ts}",
    "results.bestLineFmt":  "Best WER: {wer} ({werV:.3f}). Best CER: {cer} ({cerV:.3f}). Fastest: {fast}.",
    "tile.bestWer":         "Best WER",
    "tile.bestCer":         "Best CER",
    "tile.fastestRtf":      "Fastest RTF",
    "tile.totalRuntime":    "Total runtime",
    "tile.segments":        "Segments",
    "tile.speechCoverage":  "Speech coverage",
    "results.modelsFmt":    "Models: {models}",
    "results.resourceTitle":"Run resources",
    "results.cpuAvg":       "CPU avg",
    "results.ramPeak":      "RAM peak",
    "results.gpuAvg":       "GPU avg",
    "table.config":         "Config",
    "table.vad":            "VAD",
    "table.wer":            "WER",
    "table.cer":            "CER",
    "table.rtf":            "RTF",
    "table.avgSeg":         "Avg seg",
    "table.model":          "Model",
    "table.runtime":        "Runtime",
    "table.silence":        "Silence removed",
    "table.segments":       "Segments",
    "table.model":          "Model",
    "verdict.label":        "Verdict",
    "verdict.empty":        "(no verdict for this run)",
    "diff.title":           "Diff vs reference",
    "diff.legend.eq":       "equal",
    "diff.legend.sub":      "substitute",
    "diff.legend.ins":      "insert",
    "diff.legend.del":      "delete",
    "diff.transcriptFmt":   "Transcript — {name} (VAD {vad})",
    "diff.emptyTranscript": "(empty)",
    "diff.noReference":     "(no reference text)",
    "history.title":        "Run history",
    "history.sub":          "Newest first · up to 50 runs",
    "history.colWhen":      "When",
    "history.colConfigs":   "Configs",
    "history.colBestWer":   "Best WER",
    "history.colBestCer":   "Best CER",
    "history.colRuntime":   "Total runtime",
    "history.colAudio":     "Audio",
    "history.detail.title": "Run detail — {ts}",
    "history.detail.colConfig": "Config",
    "history.detail.colVad": "VAD",
    "history.detail.colWer": "WER",
    "history.detail.colCer": "CER",
    "history.detail.colRtf": "RTF",
    "history.detail.colRuntime": "Runtime",
    "history.detail.colSegments": "Segments",
    "history.detail.segmentsNote": "Segment audio isn't kept from past runs — only the most recent run's chunks are playable, under \"VAD breakdown\".",
    "history.detail.transcript":  "Transcript",
    "history.detail.segTable":    "Segments",
    "history.detail.segIdx":      "#",
    "history.detail.segRange":    "Time",
    "history.detail.segDur":      "Dur.",
    "history.detail.segText":     "Text",
    "tab.comparison":       "Comparison",
    "tab.vadBreakdown":     "VAD breakdown",
    "vad.title":            "VAD breakdown — {config}",
    "vad.noSegments":       "(no per-region data for this run — whisper-cli was run without timestamps, or parsing failed)",
    "vad.metrics.regions":  "Regions",
    "vad.metrics.meanDur":  "Mean region duration",
    "vad.metrics.totalSpeech": "Total speech",
    "vad.metrics.silenceRemoved": "Silence removed",
    "vad.timeline.vad":     "Whisper regions (VAD output)",
    "vad.timeline.gt":      "Reference regions (ground truth)",
    "vad.timeline.axis":    "Time (mm:ss)",
    "vad.regions.idx":      "#",
    "vad.regions.range":    "Range",
    "vad.regions.duration": "Dur.",
    "vad.regions.gtText":   "Reference text",
    "vad.regions.hypText":  "Whisper text",
    "vad.regions.wer":      "WER",
    "vad.regions.cer":      "CER",
    "vad.regions.match":    "Match",
    "vad.match.good":       "good overlap",
    "vad.match.partial":    "partial",
    "vad.match.none":       "no overlap",
    "vad.subtab.regions":   "VAD Regions",
    "vad.subtab.chunks":    "Audio Chunks",
    "vad.emptyTimeline":    "(audio timeline)",
    "vad.chunks.title":     "Audio chunks sent to Whisper",
    "vad.chunks.idx":       "#",
    "vad.chunks.range":     "Time",
    "vad.chunks.duration":  "Dur.",
    "vad.chunks.text":      "Whisper text",
    "vad.chunks.audio":     "Audio",
    "vad.chunks.unavailable": "Chunk audio is only available for VAD-on configs from the most recent run.",
    "sysmon.title":         "System resources",
    "sysmon.cores":         " cores",
    "sysmon.ramFmt":        "{used} / {total} MB",
    "sysmon.gpuFmt":        "{name} · {used}/{total} MB",
    "sysmon.gpuNone":       "no NVIDIA GPU",
    "sysmon.tempNone":      "no sensor",
    "topbar.vadOn":         "VAD on (default)",
    "topbar.vadOff":        "VAD off (default)",
    "footer.line1":         "VAD benchmark for <code>ai4db</code>'s Whisper + Silero VAD pipeline on Indonesian audio. Compares <strong>vad enabled vs disabled</strong> via <code>whisper-cli</code>'s built-in <code>--vad --vad-model</code> flags.",
    "footer.line2":         "Caveats: ground truth is a YouTube auto-transcript — WER is <em>relative</em> between configs, not absolute accuracy. <code>tiny.id</code> is a small model — the <strong>VAD on/off delta</strong> is the real signal, not the raw number.",
    // Tooltips (the ? button labels)
    "tip.wer":              "Word Error Rate vs the reference transcript. Lower is better. The reference is a YouTube auto-transcript, not gold — compare configs against each other, not to an absolute target.",
    "tip.cer":              "Character Error Rate. Like WER, but on individual characters — more robust to Indonesian word-segmentation differences.",
    "tip.rtf":              "Real-Time Factor = runtime ÷ audio length. Below 1.0 means faster than real-time. Above 1.0 is slower than real-time and may need a smaller model or a faster device.",
    "tip.runtime":          "Wall-clock seconds for the full whisper-cli invocation, including VAD pre-processing when enabled.",
    "tip.silence":          "Share of audio that VAD dropped as silence. Higher means more aggressive trimming — but too aggressive can also drop real speech. Compare WER alongside this number, not in isolation.",
    "tip.segments":         "Number of speech regions VAD found in the audio. Not 'good' or 'bad' on its own — depends on the speaker's style.",
    "tip.totalRuntime":     "Sum of wall-clock seconds across all configs in this run (not the audio length).",
    "aria.wer":             "What is WER?",
    "aria.cer":             "What is CER?",
    "aria.rtf":             "What is RTF?",
    "aria.runtime":         "What is runtime?",
    "aria.silence":         "What is silence removed?",
    "aria.segments":        "What are segments?",
    "aria.totalRuntime":    "What is total runtime?",
  },
  id: {
    "topbar.title":         "VAD Benchmark",
    "topbar.sub":           "ai4db · Bahasa Indonesia · Silero VAD vs tanpa",
    "stepper.1":            "Konfigurasi",
    "stepper.2":            "Jalankan",
    "stepper.3":            "Bandingkan hasil",
    "audio.title":          "Audio yang diuji",
    "audio.meta":           "podcast.mp3 · 16 kHz mono",
    "run.title":            "Jalankan benchmark",
    "run.sub":              "Atur knob VAD tiap config, lalu klik Jalankan.",
    "run.addConfig":        "+ Tambah config",
    "run.reset":            "Reset ke baseline vs silero",
    "run.runBtn":           "Jalankan benchmark",
    "run.running":          "Menjalankan…",
    "run.idle":             "Siap.",
    "run.started":          "Dimulai.",
    "run.submitting":       "Mengirim…",
    "run.failed":           "Gagal: ",
    "run.alreadyRunning":   "Sudah berjalan — tunggu sampai selesai.",
    "run.notReady":         "Belum siap: ",
    "run.emptyAlert":       "Tambahkan minimal satu config.",
    "run.staleNote":        " · (terlihat macet — lock berjalan terlalu lama)",
    "run.runningPrefix":    "Berjalan · ",
    "run.donePrefix":       "Selesai · ",
    "run.errorPrefix":      "Error: ",
    "field.whisper":        "Model Whisper",
    "field.language":       "Bahasa",
    "field.threads":        "Thread",
    "field.vadThreshold":   "Ambang VAD",
    "field.minSpeech":      "Min speech (ms)",
    "field.minSilence":     "Min silence (ms)",
    "field.speechPad":      "Speech pad (ms)",
    "field.maxSpeech":      "Max speech (s, 0=∞)",
    "field.vadOn":          "VAD nyala",
    "field.vadOff":         "VAD mati",
    "field.remove":         "hapus",
    "results.title":        "Hasil",
    "results.metaFmt":      "{audio}s audio · {n} config · terakhir {ts}",
    "results.bestLineFmt":  "WER terbaik: {wer} ({werV:.3f}). CER terbaik: {cer} ({cerV:.3f}). Tercepat: {fast}.",
    "tile.bestWer":         "WER terbaik",
    "tile.bestCer":         "CER terbaik",
    "tile.fastestRtf":      "RTF tercepat",
    "tile.totalRuntime":    "Total runtime",
    "tile.segments":        "Segmen",
    "tile.speechCoverage":  "Cakupan bicara",
    "results.modelsFmt":    "Model: {models}",
    "results.resourceTitle":"Sumber daya run",
    "results.cpuAvg":       "CPU rata-rata",
    "results.ramPeak":      "RAM puncak",
    "results.gpuAvg":       "GPU rata-rata",
    "table.config":         "Config",
    "table.vad":            "VAD",
    "table.wer":            "WER",
    "table.cer":            "CER",
    "table.rtf":            "RTF",
    "table.avgSeg":         "Rerata seg",
    "table.model":          "Model",
    "table.config":         "Config",
    "table.vad":            "VAD",
    "table.wer":            "WER",
    "table.cer":            "CER",
    "table.rtf":            "RTF",
    "table.runtime":        "Runtime",
    "table.silence":        "Silence dihapus",
    "table.segments":       "Segmen",
    "table.model":          "Model",
    "verdict.label":        "Kesimpulan",
    "verdict.empty":        "(tidak ada kesimpulan untuk run ini)",
    "diff.title":           "Selisih vs referensi",
    "diff.legend.eq":       "sama",
    "diff.legend.sub":      "substitusi",
    "diff.legend.ins":      "sisipan",
    "diff.legend.del":      "hapus",
    "diff.transcriptFmt":   "Transkrip — {name} (VAD {vad})",
    "diff.emptyTranscript": "(kosong)",
    "diff.noReference":     "(tidak ada teks referensi)",
    "history.title":        "Riwayat run",
    "history.sub":          "Terbaru dulu · sampai 50 run",
    "history.colWhen":      "Waktu",
    "history.colConfigs":   "Config",
    "history.colBestWer":   "WER terbaik",
    "history.colBestCer":   "CER terbaik",
    "history.colRuntime":   "Total runtime",
    "history.colAudio":     "Audio",
    "history.detail.title": "Detail run — {ts}",
    "history.detail.colConfig": "Config",
    "history.detail.colVad": "VAD",
    "history.detail.colWer": "WER",
    "history.detail.colCer": "CER",
    "history.detail.colRtf": "RTF",
    "history.detail.colRuntime": "Runtime",
    "history.detail.colSegments": "Segmen",
    "history.detail.segmentsNote": "Audio potongan tidak disimpan dari run lampau — hanya potongan dari run terakhir yang bisa diputar, di tab \"Rincian VAD\".",
    "history.detail.transcript":  "Transkrip",
    "history.detail.segTable":    "Segmen",
    "history.detail.segIdx":      "#",
    "history.detail.segRange":    "Waktu",
    "history.detail.segDur":      "Durasi",
    "history.detail.segText":     "Teks",
    "tab.comparison":       "Perbandingan",
    "tab.vadBreakdown":     "Rincian VAD",
    "vad.title":            "Rincian VAD — {config}",
    "vad.noSegments":       "(tidak ada data per-region untuk run ini — whisper-cli dijalankan tanpa timestamp, atau parsing gagal)",
    "vad.metrics.regions":  "Wilayah",
    "vad.metrics.meanDur":  "Rerata durasi wilayah",
    "vad.metrics.totalSpeech": "Total bicara",
    "vad.metrics.silenceRemoved": "Silence dihapus",
    "vad.timeline.vad":     "Wilayah Whisper (keluaran VAD)",
    "vad.timeline.gt":      "Wilayah referensi (ground truth)",
    "vad.timeline.axis":    "Waktu (mm:ss)",
    "vad.regions.idx":      "#",
    "vad.regions.range":    "Rentang",
    "vad.regions.duration": "Dur.",
    "vad.regions.gtText":   "Teks referensi",
    "vad.regions.hypText":  "Teks Whisper",
    "vad.regions.wer":      "WER",
    "vad.regions.cer":      "CER",
    "vad.regions.match":    "Cocok",
    "vad.match.good":       "tumpang tindih baik",
    "vad.match.partial":    "sebagian",
    "vad.match.none":       "tidak ada tumpang tindih",
    "vad.subtab.regions":   "Rincian VAD",
    "vad.subtab.chunks":    "Potongan Audio",
    "vad.emptyTimeline":    "(timeline audio)",
    "vad.chunks.title":     "Potongan audio yang dikirim ke Whisper",
    "vad.chunks.idx":       "#",
    "vad.chunks.range":     "Waktu",
    "vad.chunks.duration":  "Durasi",
    "vad.chunks.text":      "Teks Whisper",
    "vad.chunks.audio":     "Audio",
    "vad.chunks.unavailable": "Potongan audio hanya tersedia untuk config VAD-on pada run terakhir.",
    "sysmon.title":         "Resource sistem",
    "sysmon.cores":         " core",
    "sysmon.ramFmt":        "{used} / {total} MB",
    "sysmon.gpuFmt":        "{name} · {used}/{total} MB",
    "sysmon.gpuNone":       "tidak ada GPU NVIDIA",
    "sysmon.tempNone":      "tanpa sensor",
    "topbar.vadOn":         "VAD nyala (default)",
    "topbar.vadOff":        "VAD mati (default)",
    "footer.line1":         "Benchmark VAD untuk pipeline Whisper + Silero VAD milik <code>ai4db</code> pada audio Bahasa Indonesia. Membandingkan <strong>vad nyala vs mati</strong> lewat flag bawaan <code>whisper-cli</code>: <code>--vad --vad-model</code>.",
    "footer.line2":         "Catatan: ground truth adalah auto-transkrip YouTube — WER bersifat <em>relatif</em> antar config, bukan akurasi absolut. <code>tiny.id</code> adalah model kecil — yang jadi sinyal sebenarnya adalah <strong>selisih VAD on/off</strong>, bukan angka mentahnya.",
    "tip.wer":              "Word Error Rate vs transkrip referensi. Semakin rendah semakin baik. Referensi adalah auto-transkrip YouTube, bukan gold — bandingkan config satu sama lain, bukan ke target absolut.",
    "tip.cer":              "Character Error Rate. Seperti WER, tapi dihitung per karakter — lebih tahan terhadap perbedaan segmentasi kata Bahasa Indonesia.",
    "tip.rtf":              "Real-Time Factor = runtime ÷ panjang audio. Di bawah 1.0 berarti lebih cepat dari real-time. Di atas 1.0 lebih lambat dari real-time — mungkin perlu model lebih kecil atau device lebih cepat.",
    "tip.runtime":          "Detik wall-clock untuk seluruh pemanggilan whisper-cli, termasuk praproses VAD saat diaktifkan.",
    "tip.silence":          "Bagian audio yang dibuang VAD sebagai silence. Lebih tinggi berarti trimming lebih agresif — tapi terlalu agresif bisa memotong ucapan asli. Bandingkan bersama WER, jangan sendirian.",
    "tip.segments":         "Jumlah region bicara yang ditemukan VAD. Bukan 'baik' atau 'buruk' dengan sendirinya — tergantung gaya pembicara.",
    "tip.totalRuntime":     "Jumlah detik wall-clock untuk semua config dalam run ini (bukan panjang audio).",
    "aria.wer":             "Apa itu WER?",
    "aria.cer":             "Apa itu CER?",
    "aria.rtf":             "Apa itu RTF?",
    "aria.runtime":         "Apa itu runtime?",
    "aria.silence":         "Apa itu silence dihapus?",
    "aria.segments":        "Apa itu segmen?",
    "aria.totalRuntime":    "Apa itu total runtime?",
  },
};

// ─── State ──────────────────────────────────────────────────
let LANG = "id";                     // default ID
let CFG = null;                      // runtime config from /api/config
let MODELS = [];                     // available .bin files
let MODEL_DESCS = {};                // filename -> {name, params, description}
let LAST_SUMMARY = null;             // latest /api/summary
let RUNNING = false;
let sseSource = null;

const DEFAULT_CONFIGS = () => ([
  { name: "baseline_novad", overrides: { vad_enabled: false } },
  { name: "silero_vad",     overrides: { vad_enabled: true  } },
]);

// ─── i18n helpers ───────────────────────────────────────────
function t(key) { return (I18N[LANG] && I18N[LANG][key]) || (I18N.en[key]) || key; }

function setLanguage(lang) {
  if (!I18N[lang]) return;
  LANG = lang;
  try { localStorage.setItem("vad-bench.lang", lang); } catch {}
  $$(".lang-toggle [data-lang]").forEach(b => {
    b.classList.toggle("is-active", b.dataset.lang === lang);
  });
  applyLanguage();
}

function applyLanguage() {
  // Plain text nodes with data-i18n
  $$("[data-i18n]").forEach(el => {
    const k = el.getAttribute("data-i18n");
    if (!k) return;
    const val = t(k);
    // Some values contain inline HTML (footer lines).
    if (val.indexOf("<") !== -1) el.innerHTML = val;
    else el.textContent = val;
  });

  // Tooltip buttons: switch data-tip + aria-label
  $$(".tip[data-tip-key]").forEach(btn => {
    const k = btn.getAttribute("data-tip-key");
    btn.setAttribute("data-tip", t("tip." + k));
    btn.setAttribute("aria-label", t("aria." + k));
  });

  // Re-render dynamic parts so they pick up the new language.
  if (LAST_SUMMARY) renderResults(LAST_SUMMARY);
  refreshHistory().catch(() => {});
  refreshBadges();
}

function refreshBadges() {
  if (!CFG) return;
  $("#vad-badge-text").textContent = CFG.vad_enabled ? t("topbar.vadOn") : t("topbar.vadOff");
}

// ─── Init ───────────────────────────────────────────────────
async function init() {
  try { LANG = localStorage.getItem("vad-bench.lang") || "id"; } catch {}
  applyLanguage();                     // first pass on static DOM
  await Promise.all([loadConfig(), loadModels(), refreshSystem(), loadRefSegments()]);
  refreshModelBadge();  // needs both CFG and MODEL_DESCS loaded
  pollSystem();
  openSSE();
  renderConfigs(DEFAULT_CONFIGS());
  await tryLoadLastResults();
  await refreshHistory();
  wireFlowStepper();
  wireLangToggle();
  wireResultsTabs();
}

async function loadRefSegments() {
  try {
    const data = await fetch("/api/reference/segments").then(r => r.json());
    REF_SEGMENTS = (data && data.segments) || [];
  } catch { REF_SEGMENTS = []; }
}

// ─── Language toggle (topbar) ───────────────────────────────
function wireLangToggle() {
  $$(".lang-toggle [data-lang]").forEach(btn => {
    btn.classList.toggle("is-active", btn.dataset.lang === LANG);
    btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
  });
}

// ─── Results tabs (Comparison / VAD breakdown) ──────────────
function wireResultsTabs() {
  $$(".results-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      $$(".results-tab").forEach(t => t.classList.toggle("is-active", t === tab));
      $("#results-pane-compare").hidden = (target !== "compare");
      $("#results-pane-vad").hidden = (target !== "vad");
    });
  });
}

// ─── Flow stepper ───────────────────────────────────────────
function wireFlowStepper() {
  $$("#flow-stepper .flow-step-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.stepTarget);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function updateStepper(stage) {
  $$("#flow-stepper .flow-step").forEach(li => {
    const s = Number(li.dataset.stage);
    li.classList.toggle("is-active", s === stage);
    li.classList.toggle("is-done", s < stage);
  });
}

async function loadConfig() {
  CFG = await fetch("/api/config").then(r => r.json());
  refreshBadges();
}

function refreshModelBadge() {
  if (!CFG) return;
  const raw = CFG.whisper_model || "–";
  const d = MODEL_DESCS[raw];
  const label = d ? `${d.name} (${d.params})` : raw.replace(/^ggml-/, "").replace(/\.bin$/, "");
  $("#model-badge-text").textContent = label;
  $("#model-badge").title = d ? d.description : raw;
}

async function loadModels() {
  try {
    const data = await fetch("/api/models").then(r => r.json());
    MODELS = data.available || [];
    MODEL_DESCS = data.descriptions || {};
  } catch { MODELS = []; MODEL_DESCS = {}; }
}

function modelLabel(filename) {
  const d = MODEL_DESCS[filename];
  return d ? `${d.name} (${d.params}) — ${filename}` : filename;
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
    setSysmon("ram",      s.ram_percent, null,         "%", 100,
              t("sysmon.ramFmt").replace("{used}", s.ram_used_mb.toFixed(0)).replace("{total}", s.ram_total_mb.toFixed(0)));
    setSysmon("cputemp",  s.cpu_temp_c,  null,         "°C", 100,
              s.cpu_temp_c != null ? `${s.cpu_temp_c.toFixed(1)} °C` : t("sysmon.tempNone"));
    const gpu = (s.gpus && s.gpus[0]) || null;
    setSysmon("gpu", gpu ? gpu.util_percent : null, null, "%", 100,
              gpu ? t("sysmon.gpuFmt")
                    .replace("{name}", gpu.name)
                    .replace("{used}", (gpu.mem_used_mb ?? 0).toFixed(0))
                    .replace("{total}", (gpu.mem_total_mb ?? 0).toFixed(0))
                  : t("sysmon.gpuNone"));
    const gpuTemp = gpu ? gpu.temp_c : null;
    setSysmon("gputemp", gpuTemp, null, "°C", 100,
              gpuTemp != null ? `${gpuTemp.toFixed(1)} °C` : t("sysmon.tempNone"));
    $("#sysmon-updated").textContent = s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : "–";
  } catch (e) { /* swallow */ }
}
function setSysmon(metric, value, count, unit, max, sub) {
  const isTemp = metric === "cputemp" || metric === "gputemp";
  const val = value == null ? "–" : (isTemp ? value.toFixed(1) + unit : value.toFixed(0) + unit);
  $(`#sysmon-${metric}-val`).textContent = val;
  const pct = value == null ? 0 : Math.min(100, (value / max) * 100);
  $(`#sysmon-${metric}-bar`).style.width = pct + "%";
  $(`#sysmon-${metric}-sub`).textContent =
    sub || (count ? `${count}${t("sysmon.cores")}` : "");
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
    updateStepper(2);
    el.classList.add("is-running"); el.classList.remove("is-error");
    const cur = status.current ? status.current.name : "—";
    const done = (status.completed || []).length;
    const total = status.total || "?";
    el.textContent = `${t("run.runningPrefix")}${done}/${total} · now: ${cur}${status.stale ? t("run.staleNote") : ""}`;
    $("#btn-run").disabled = true;
    $("#btn-run").textContent = t("run.running");
  } else {
    RUNNING = false;
    $("#btn-run").disabled = false;
    $("#btn-run").textContent = t("run.runBtn");
    if (status.error) {
      el.classList.add("is-error"); el.classList.remove("is-running");
      el.textContent = `${t("run.errorPrefix")}${status.error}`;
      updateStepper(LAST_SUMMARY ? 3 : 1);
    } else if (status.finished_at) {
      el.classList.remove("is-error", "is-running");
      const done = (status.completed || []).length;
      el.textContent = `${t("run.donePrefix")}${done} configs · ${status.finished_at}`;
      tryLoadLastResults();
      refreshHistory();
    } else {
      el.classList.remove("is-error", "is-running");
      el.textContent = t("run.idle");
      updateStepper(LAST_SUMMARY ? 3 : 1);
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
        <span data-role="vad-label">${vadOn ? t("field.vadOn") : t("field.vadOff")}</span>
      </button>
      <button class="btn-icon" data-role="remove" title="${escapeAttr(t("field.remove"))}">${t("field.remove")}</button>
    </div>
    <div class="config-card-grid">
      <div class="field">
        <span class="field-label" data-i18n-key="field.whisper">${t("field.whisper")}</span>
        <select data-role="whisper_model" title="${escapeAttr((MODEL_DESCS[ov.whisper_model || CFG.whisper_model] || {}).description || "")}">
          ${MODELS.length === 0
              ? `<option value="${escapeAttr(CFG.whisper_model)}">${escapeHtml(CFG.whisper_model)}</option>`
              : MODELS.filter(m => !/silero/i.test(m)).map(m =>
                  `<option value="${escapeAttr(m)}" ${m === (ov.whisper_model || CFG.whisper_model) ? "selected" : ""}>${escapeHtml(modelLabel(m))}</option>`
                ).join("")}
        </select>
      </div>
      <div class="field">
        <span class="field-label" data-i18n-key="field.language">${t("field.language")}</span>
        <select data-role="language">
          <option value="id"   ${(ov.language || CFG.language) === "id"   ? "selected" : ""}>id (Indonesian)</option>
          <option value="auto" ${(ov.language || CFG.language) === "auto" ? "selected" : ""}>auto</option>
          <option value="en"   ${(ov.language || CFG.language) === "en"   ? "selected" : ""}>en</option>
        </select>
      </div>
      <div class="field">
        <span class="field-label" data-i18n-key="field.threads">${t("field.threads")}</span>
        <input type="number" min="1" max="32" step="1" data-role="threads" value="${ov.threads ?? CFG.threads}" />
      </div>
      <div class="field">
        <span class="field-label"><span data-i18n-key="field.vadThreshold">${t("field.vadThreshold")}</span> <span class="field-value" data-role="vad_threshold_val">${ov.vad_threshold ?? CFG.vad_threshold}</span></span>
        <input type="range" min="0.10" max="0.90" step="0.05" data-role="vad_threshold" value="${ov.vad_threshold ?? CFG.vad_threshold}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label"><span data-i18n-key="field.minSpeech">${t("field.minSpeech")}</span> <span class="field-value" data-role="vad_min_speech_ms_val">${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_speech_ms" value="${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label"><span data-i18n-key="field.minSilence">${t("field.minSilence")}</span> <span class="field-value" data-role="vad_min_silence_ms_val">${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_silence_ms" value="${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label"><span data-i18n-key="field.speechPad">${t("field.speechPad")}</span> <span class="field-value" data-role="vad_speech_pad_ms_val">${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}</span></span>
        <input type="range" min="0" max="500" step="10" data-role="vad_speech_pad_ms" value="${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}" ${vadOn ? "" : "disabled"} />
      </div>
      <div class="field">
        <span class="field-label" data-i18n-key="field.maxSpeech">${t("field.maxSpeech")}</span>
        <input type="number" min="0" step="1" data-role="vad_max_speech_s" value="${ov.vad_max_speech_s ?? CFG.vad_max_speech_s}" ${vadOn ? "" : "disabled"} />
      </div>
    </div>
  `;

  card.querySelector('[data-role="whisper_model"]').addEventListener("change", (e) => {
    e.target.title = (MODEL_DESCS[e.target.value] || {}).description || "";
  });

  const vadBtn = card.querySelector('[data-role="vad-toggle"]');
  const vadLabel = card.querySelector('[data-role="vad-label"]');
  const ranges = card.querySelectorAll('input[type="range"]');
  vadBtn.addEventListener("click", () => {
    const on = !vadBtn.classList.contains("is-on");
    vadBtn.classList.toggle("is-on", on);
    vadLabel.textContent = on ? t("field.vadOn") : t("field.vadOff");
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
  $("#audio-player").play().catch(() => {});
  const configs = collectConfigs();
  if (configs.length === 0) { alert(t("run.emptyAlert")); return; }
  if (RUNNING) { return; }
  $("#run-status").textContent = t("run.submitting");
  $("#run-status").classList.remove("is-error"); $("#run-status").classList.add("is-running");
  try {
    const resp = await fetch(`/api/run?configs=${encodeURIComponent(JSON.stringify(configs))}`, { method: "POST" });
    const data = await resp.json();
    if (!data.ok && data.already_running) {
      $("#run-status").textContent = t("run.alreadyRunning");
    } else if (!data.ok && data.not_ready) {
      $("#run-status").textContent = t("run.notReady") + (data.issues || []).join("; ");
      $("#run-status").classList.add("is-error"); $("#run-status").classList.remove("is-running");
    } else {
      $("#run-status").textContent = t("run.started");
    }
  } catch (e) {
    $("#run-status").textContent = t("run.failed") + e.message;
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
    $("#audio-meta").textContent = `${t("audio.meta")} · ${(sum.audio_duration_s || 0).toFixed(1)}s`;
    if (!RUNNING) updateStepper(3);
  } catch (e) { /* no summary yet */ }
}

function renderResults(sum) {
  const metaFmt = t("results.metaFmt")
    .replace("{audio}", (sum.audio_duration_s || 0).toFixed(1))
    .replace("{n}", sum.configs.length)
    .replace("{ts}", formatTs(sum.last_run));
  $("#results-meta").textContent = metaFmt;

  // Verdict (if any).
  const verdictEl = $("#results-verdict");
  if (sum.verdict) {
    verdictEl.hidden = false;
    $("#verdict-text").textContent = sum.verdict;
  } else {
    verdictEl.hidden = true;
  }

  // Collect unique models from configs.
  const models = [...new Set(sum.configs.map(c => c.whisper_model).filter(Boolean))];
  const modelPills = models.map(m => {
    const short = MODEL_DESCS[m]?.name || m.replace(/^ggml-/, "").replace(/\.bin$/, "");
    return `<span class="model-pill">${escapeHtml(short)}</span>`;
  }).join(" ");

  // Compute segment & speech stats from VAD-enabled configs.
  const vadConfigs = sum.configs.filter(c => c.n_segments != null);
  const totalSegs = vadConfigs.reduce((a, c) => a + (c.n_segments || 0), 0);
  const avgSegDur = vadConfigs.length
    ? vadConfigs.reduce((a, c) => a + (c.avg_seg_duration || 0), 0) / vadConfigs.length
    : null;
  const speechCov = vadConfigs.length && sum.audio_duration_s
    ? vadConfigs.reduce((a, c) => a + (c.speech_seconds || 0), 0) / vadConfigs.length / sum.audio_duration_s
    : null;

  const bestWerVal = minOf(sum.configs, "wer");
  const bestCerVal = minOf(sum.configs, "cer");
  const fastestRtfVal = minOf(sum.configs, "rtf");
  const werCls = bestWerVal != null ? (bestWerVal <= 0.15 ? "tile-good" : bestWerVal <= 0.30 ? "tile-warn" : "tile-bad") : "";
  const cerCls = bestCerVal != null ? (bestCerVal <= 0.10 ? "tile-good" : bestCerVal <= 0.25 ? "tile-warn" : "tile-bad") : "";
  const rtfCls = fastestRtfVal != null ? (fastestRtfVal < 1.0 ? "tile-good" : fastestRtfVal < 2.0 ? "tile-warn" : "tile-bad") : "";

  $("#results-summary").innerHTML = `
    <div class="summary-tile ${werCls}">
      <div class="tile-label">${t("tile.bestWer")}<button type="button" class="tip" data-tip-key="wer" aria-label="${escapeAttr(t("aria.wer"))}">?</button></div>
      <div class="tile-value">${bestWerVal != null ? bestWerVal.toFixed(3) : "–"}</div>
      <div class="tile-sub">${sum.best_wer_config || "–"}</div>
    </div>
    <div class="summary-tile ${cerCls}">
      <div class="tile-label">${t("tile.bestCer")}<button type="button" class="tip" data-tip-key="cer" aria-label="${escapeAttr(t("aria.cer"))}">?</button></div>
      <div class="tile-value">${bestCerVal != null ? bestCerVal.toFixed(3) : "–"}</div>
      <div class="tile-sub">${sum.best_cer_config || "–"}</div>
    </div>
    <div class="summary-tile ${rtfCls}">
      <div class="tile-label">${t("tile.fastestRtf")}<button type="button" class="tip" data-tip-key="rtf" aria-label="${escapeAttr(t("aria.rtf"))}">?</button></div>
      <div class="tile-value">${fastestRtfVal != null ? fastestRtfVal.toFixed(3) : "–"}</div>
      <div class="tile-sub">${sum.fastest_rtf_config || "–"}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.totalRuntime")}<button type="button" class="tip" data-tip-key="totalRuntime" aria-label="${escapeAttr(t("aria.totalRuntime"))}">?</button></div>
      <div class="tile-value">${(sum.total_runtime_s || 0).toFixed(1)}s</div>
      <div class="tile-sub">${sum.configs.length} ${LANG === "id" ? "config" : "configs"}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.segments")}</div>
      <div class="tile-value">${totalSegs || "–"}</div>
      <div class="tile-sub">${avgSegDur != null ? `avg ${avgSegDur.toFixed(1)}s` : "–"}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.speechCoverage")}</div>
      <div class="tile-value">${speechCov != null ? (speechCov * 100).toFixed(1) + "%" : "–"}</div>
      <div class="tile-sub">${(sum.audio_duration_s || 0).toFixed(0)}s ${LANG === "id" ? "audio" : "audio"}</div>
    </div>
  `;

  // Model pills under summary.
  if (models.length) {
    const modelsLine = t("results.modelsFmt").replace("{models}", modelPills);
    let modelsEl = $("#results-models");
    if (!modelsEl) {
      modelsEl = document.createElement("div");
      modelsEl.id = "results-models";
      modelsEl.className = "results-models";
      $("#results-summary").after(modelsEl);
    }
    modelsEl.innerHTML = modelsLine;
  }

  // Re-bind tooltip text from current language.
  $$(".tip[data-tip-key]").forEach(btn => {
    const k = btn.getAttribute("data-tip-key");
    btn.setAttribute("data-tip", t("tip." + k));
    btn.setAttribute("aria-label", t("aria." + k));
  });

  const tbody = $("#results-table tbody");
  tbody.innerHTML = "";
  const bestWer = minOf(sum.configs, "wer");
  const worstWer = maxOf(sum.configs, "wer");
  const bestCer = minOf(sum.configs, "cer");
  const worstCer = maxOf(sum.configs, "cer");
  sum.configs.forEach(c => {
    const tr = document.createElement("tr");
    tr.dataset.config = c.config;
    const isBest = (c.wer === bestWer);
    if (isBest) tr.classList.add("is-best");
    const werCls = colorClsRelative(c.wer, bestWer, worstWer);
    const cerCls = colorClsRelative(c.cer, bestCer, worstCer);
    const rtfCls = isRtfRealTime(c.rtf) ? "is-good" : (c.rtf == null ? "" : "is-bad");
    const modelShort = MODEL_DESCS[c.whisper_model]?.name || (c.whisper_model || "–").replace(/^ggml-/, "").replace(/\.bin$/, "");
    const modelParams = MODEL_DESCS[c.whisper_model]?.params || "";
    tr.innerHTML = `
      <td>${escapeHtml(c.config)}</td>
      <td><span class="config-vad-toggle ${c.vad_enabled ? "is-on" : ""}"><span class="toggle-dot"></span>${c.vad_enabled ? "on" : "off"}</span></td>
      <td class="num metric-cell metric-wer ${werCls}">${(c.wer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-cer ${cerCls}">${(c.cer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-rtf ${rtfCls}">${(c.rtf ?? 0).toFixed(3)}</td>
      <td class="num">${(c.runtime_s ?? 0).toFixed(1)}s</td>
      <td class="num">${c.silence_removed != null ? (c.silence_removed * 100).toFixed(1) + "%" : "–"}</td>
      <td class="num">${c.n_segments ?? "–"}</td>
      <td class="num">${c.avg_seg_duration != null ? c.avg_seg_duration.toFixed(1) + "s" : "–"}</td>
      <td><span class="model-cell" title="${escapeAttr(c.whisper_model || '')}">${escapeHtml(modelShort)}${modelParams ? ` <span class="model-params">(${modelParams})</span>` : ""}</span></td>
    `;
    tr.addEventListener("click", () => selectConfig(c.config));
    tbody.appendChild(tr);
  });

  $("#best-line").textContent = t("results.bestLineFmt")
    .replace("{wer}", sum.best_wer_config || "–")
    .replace("{werV}", bestWer ?? 0)
    .replace("{cer}", sum.best_cer_config || "–")
    .replace("{cerV}", bestCer ?? 0)
    .replace("{fast}", sum.fastest_rtf_config || "–");

  // Resource summary from the run.
  const res = sum.resources || {};
  let resEl = $("#results-resources");
  if (!resEl) {
    resEl = document.createElement("div");
    resEl.id = "results-resources";
    resEl.className = "results-resources";
    $("#best-line").after(resEl);
  }
  if (res.cpu_avg != null || res.ram_peak_mb != null || res.gpu_avg != null) {
    resEl.innerHTML = `
      <span><span class="res-label">${t("results.cpuAvg")}</span>${res.cpu_avg != null ? res.cpu_avg.toFixed(0) + "%" : "–"}</span>
      <span><span class="res-label">${t("results.ramPeak")}</span>${res.ram_peak_mb != null ? res.ram_peak_mb.toFixed(0) + " MB" : "–"}</span>
      <span><span class="res-label">${t("results.gpuAvg")}</span>${res.gpu_avg != null ? res.gpu_avg.toFixed(0) + "%" : "–"}</span>
    `;
    resEl.hidden = false;
  } else {
    resEl.hidden = true;
  }

  if (sum.configs.length > 0) selectConfig(sum.configs[0].config);
}

let SELECTED = null;
let REF_SEGMENTS = [];   // [{start, end, text}, ...] from references/segments.json
async function selectConfig(config) {
  SELECTED = config;
  $$("#results-table tbody tr").forEach(tr => {
    tr.classList.toggle("is-selected", tr.dataset.config === config);
  });
  try {
    const detail = await fetch(`/api/results/${encodeURIComponent(config)}`).then(r => r.json());
    renderDetail(detail);
    renderVadBreakdown(detail, REF_SEGMENTS);
  } catch (e) { /* ignore */ }
}

function renderDetail(d) {
  const root = $("#config-detail");
  const transcript = d.transcript_raw || "";
  root.innerHTML = `
    <div class="diff-block">
      <div class="diff-block-head">
        <h3>${t("diff.transcriptFmt").replace("{name}", escapeHtml(d.config)).replace("{vad}", d.vad_enabled ? t("field.vadOn") : t("field.vadOff"))}</h3>
        <button class="btn btn-ghost btn-copy" type="button" title="Copy transcript">${LANG === "id" ? "Salin" : "Copy"}</button>
      </div>
      <div class="diff-stream">${escapeHtml(transcript || t("diff.emptyTranscript"))}</div>
    </div>
    <div class="diff-block">
      <h3>${t("diff.title")}</h3>
      <div class="diff-stream">${renderAlignment(d.alignment || [])}</div>
      <div class="diff-legend">
        <span class="diff-eq">${t("diff.legend.eq")}</span>
        <span class="diff-sub">${t("diff.legend.sub")}</span>
        <span class="diff-ins">${t("diff.legend.ins")}</span>
        <span class="diff-del">${t("diff.legend.del")}</span>
      </div>
    </div>
  `;
  root.querySelectorAll(".btn-copy").forEach(btn => {
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(transcript).then(() => {
        btn.textContent = LANG === "id" ? "✓ Tersalin" : "✓ Copied";
        setTimeout(() => { btn.textContent = LANG === "id" ? "Salin" : "Copy"; }, 1500);
      });
    });
  });
}

function renderAlignment(parts) {
  if (!parts.length) return `<span class='muted'>${t("diff.noReference")}</span>`;
  return parts.map(p => {
    if (p.kind === "equal") return `<span class="diff-eq">${escapeHtml(p.ref || p.hyp || "")}</span>`;
    if (p.kind === "substitute") return `<span class="diff-sub">${escapeHtml(p.hyp || p.ref)}</span>`;
    if (p.kind === "insert")    return `<span class="diff-ins">${escapeHtml(p.hyp || "")}</span>`;
    if (p.kind === "delete")    return `<span class="diff-del">${escapeHtml(p.ref || "")}</span>`;
    return "";
  }).join(" ");
}

// ─── VAD breakdown tab ───────────────────────────────────────
function fmtMmSs(secs) {
  if (secs == null || !Number.isFinite(secs)) return "–";
  const s = Math.max(0, Math.floor(secs));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

function matchCls(overlap) {
  if (overlap >= 0.5) return "match-good";
  if (overlap >= 0.1) return "match-partial";
  return "match-none";
}

function computePerRegion(refSegs, hypSegs, iouThreshold = 0.1) {
  const out = [];
  refSegs.forEach((ref, i) => {
    const refDur = Math.max(0, ref.end - ref.start);
    let bestIou = 0;
    let bestHyp = null;
    for (const hyp of hypSegs) {
      const inter = Math.max(0, Math.min(ref.end, hyp.end) - Math.max(ref.start, hyp.start));
      const union = refDur + Math.max(0, hyp.end - hyp.start) - inter;
      const iou = union > 0 ? inter / union : 0;
      if (iou > bestIou) { bestIou = iou; bestHyp = hyp; }
    }
    const matched = bestHyp != null && bestIou >= iouThreshold;
    const hypText = matched ? bestHyp.text : "";
    const hypStart = matched ? bestHyp.start : 0;
    const hypEnd = matched ? bestHyp.end : 0;
    // Inline WER/CER via jiwer… we don't have jiwer in the browser.
    // Use a simple word-level overlap ratio as a proxy indicator:
    //   score = 1 - (unique_mismatches / total_ref_words)
    // Not a real WER but conveys "this region matched well / poorly".
    const refWords = (ref.text || "").toLowerCase().split(/\s+/).filter(Boolean);
    const hypWords = (hypText || "").toLowerCase().split(/\s+/).filter(Boolean);
    let score;
    if (refWords.length === 0) {
      score = hypWords.length === 0 ? 1.0 : 0.0;
    } else if (!matched) {
      score = 0.0;
    } else {
      const refSet = new Set(refWords);
      const hit = hypWords.filter(w => refSet.has(w)).length;
      score = hit / refWords.length;
    }
    out.push({
      index: i,
      start: ref.start, end: ref.end, duration: refDur,
      refText: ref.text || "",
      hypText, hypStart, hypEnd,
      matchScore: score,
      overlap: bestIou,
    });
  });
  return out;
}

function renderVadBreakdown(d, refSegments) {
  const root = $("#vad-breakdown");
  if (!d.segments || !d.segments.length) {
    root.innerHTML = `<div class="vad-empty muted">${t("vad.noSegments")}</div>`;
    return;
  }
  const audioDur = d.audio_duration_s || 0;
  const hypSegs = d.segments.map(s => ({ start: s.start, end: s.end, text: s.text }));
  const refSegs = (refSegments || []).map(s => ({ start: s.start, end: s.end, text: s.text }));
  const perRegion = computePerRegion(refSegs, hypSegs);

  // Summary metrics.
  const totalHypSpeech = hypSegs.reduce((a, s) => a + Math.max(0, s.end - s.start), 0);
  const meanDur = hypSegs.length ? totalHypSpeech / hypSegs.length : 0;
  const silenceRemoved = audioDur > 0 ? Math.max(0, 1 - totalHypSpeech / audioDur) : null;
  const matchedRegions = perRegion.filter(r => r.overlap >= 0.1).length;

  root.innerHTML = `
    <div class="vad-metrics">
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.regions")}</div>
        <div class="tile-value">${hypSegs.length}</div>
        <div class="tile-sub">${matchedRegions}/${refSegs.length || "–"} ${LANG === "id" ? "cocok" : "matched"}</div>
      </div>
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.meanDur")}</div>
        <div class="tile-value">${meanDur.toFixed(1)}s</div>
        <div class="tile-sub">${t("vad.metrics.totalSpeech")}: ${totalHypSpeech.toFixed(0)}s</div>
      </div>
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.silenceRemoved")}</div>
        <div class="tile-value">${silenceRemoved != null ? (silenceRemoved * 100).toFixed(1) + "%" : "–"}</div>
        <div class="tile-sub">${audioDur.toFixed(0)}s ${LANG === "id" ? "audio" : "audio"}</div>
      </div>
    </div>

    <div class="vad-timelines">
      <div class="vad-timeline-block">
        <div class="vad-timeline-label">${t("vad.timeline.vad")}</div>
        <div class="vad-timeline" data-kind="vad">
          <div class="vad-timeline-axis">${renderTimelineAxis(audioDur)}</div>
          <div class="vad-timeline-track">
            ${hypSegs.map(s => renderTimelineRegion(s, audioDur, "vad-region")).join("")}
            ${!hypSegs.length ? `<div class="vad-timeline-empty muted">${t("vad.emptyTimeline")}</div>` : ""}
          </div>
        </div>
      </div>
      <div class="vad-timeline-block">
        <div class="vad-timeline-label">${t("vad.timeline.gt")}</div>
        <div class="vad-timeline" data-kind="gt">
          <div class="vad-timeline-axis">${renderTimelineAxis(audioDur)}</div>
          <div class="vad-timeline-track">
            ${refSegs.map(s => renderTimelineRegion(s, audioDur, "gt-region")).join("")}
            ${!refSegs.length ? `<div class="vad-timeline-empty muted">${t("vad.noSegments")}</div>` : ""}
          </div>
        </div>
      </div>
    </div>

    <div class="vad-subtabs">
      <button type="button" class="vad-subtab is-active" data-subtab="regions">${t("vad.subtab.regions")}</button>
      <button type="button" class="vad-subtab" data-subtab="chunks">${t("vad.subtab.chunks")}</button>
    </div>

    <div class="vad-subpane" data-subpane="regions">
      <table class="vad-regions-table">
        <thead>
          <tr>
            <th>${t("vad.regions.idx")}</th>
            <th>${t("vad.regions.range")}</th>
            <th class="num">${t("vad.regions.duration")}</th>
            <th>${t("vad.regions.gtText")}</th>
            <th>${t("vad.regions.hypText")}</th>
            <th class="num">${t("vad.regions.wer")}</th>
            <th class="num">${t("vad.regions.cer")}</th>
            <th class="num">${t("vad.regions.match")}</th>
          </tr>
        </thead>
        <tbody>
          ${perRegion.map(r => {
            // Use server-side WER/CER if available (real jiwer metrics).
            const pr = (d.per_region_wer || [])[r.index];
            const w = pr != null ? pr.wer : null;
            const c = pr != null ? pr.cer : null;
            const wCls = w != null ? (w <= 0.2 ? "match-good" : w <= 0.5 ? "match-partial" : "match-none") : "";
            const cCls = c != null ? (c <= 0.2 ? "match-good" : c <= 0.5 ? "match-partial" : "match-none") : "";
            return `
            <tr>
              <td>${r.index + 1}</td>
              <td><span class="muted">${fmtMmSs(r.start)}–${fmtMmSs(r.end)}</span></td>
              <td class="num">${r.duration.toFixed(1)}s</td>
              <td>${escapeHtml(truncate(r.refText, 80))}</td>
              <td>${escapeHtml(truncate(r.hypText, 80))}</td>
              <td class="num ${wCls}">${w != null ? (w * 100).toFixed(0) + "%" : "–"}</td>
              <td class="num ${cCls}">${c != null ? (c * 100).toFixed(0) + "%" : "–"}</td>
              <td class="num ${matchCls(r.overlap)}" title="overlap=${r.overlap.toFixed(2)}">${(r.matchScore * 100).toFixed(0)}%</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>

    <div class="vad-subpane" data-subpane="chunks" hidden>
      ${renderChunkList(d)}
    </div>
  `;

  // Wire sub-tab switching.
  root.querySelectorAll(".vad-subtab").forEach(btn => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".vad-subtab").forEach(b => b.classList.toggle("is-active", b === btn));
      root.querySelectorAll(".vad-subpane").forEach(p => p.hidden = (p.dataset.subpane !== btn.dataset.subtab));
    });
  });
}

function renderChunkList(d) {
  if (!d.chunks_available) {
    return `<div class="vad-chunks-unavailable muted">${t("vad.chunks.unavailable")}</div>`;
  }
  const rows = (d.segments || []).map((s, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><span class="muted">${fmtMmSs(s.start)}–${fmtMmSs(s.end)}</span></td>
      <td class="num">${(s.end - s.start).toFixed(1)}s</td>
      <td>${escapeHtml(truncate(s.text, 100))}</td>
      <td><audio controls preload="none" src="/api/chunks/${encodeURIComponent(d.config)}/${i}"></audio></td>
    </tr>
  `).join("");
  return `
    <div class="vad-chunks">
      <h3>${t("vad.chunks.title")}</h3>
      <table class="vad-regions-table vad-chunks-table">
        <thead>
          <tr>
            <th>${t("vad.chunks.idx")}</th>
            <th>${t("vad.chunks.range")}</th>
            <th class="num">${t("vad.chunks.duration")}</th>
            <th>${t("vad.chunks.text")}</th>
            <th>${t("vad.chunks.audio")}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderTimelineAxis(audioDur) {
  // Tick every 60s; up to ~12 ticks for an 11-min podcast.
  const ticks = [];
  for (let s = 0; s <= audioDur; s += 60) {
    const left = audioDur > 0 ? (s / audioDur) * 100 : 0;
    ticks.push(`<span class="vad-timeline-tick" style="left:${left}%">${fmtMmSs(s)}</span>`);
  }
  return ticks.join("");
}

function renderTimelineRegion(seg, audioDur, klass) {
  if (audioDur <= 0) return "";
  const left = Math.max(0, Math.min(100, (seg.start / audioDur) * 100));
  const width = Math.max(0.5, Math.min(100 - left, ((seg.end - seg.start) / audioDur) * 100));
  const dur = (seg.end - seg.start).toFixed(1);
  return `<div class="vad-region ${klass}" style="left:${left}%;width:${width}%" title="${escapeHtml(fmtMmSs(seg.start) + '–' + fmtMmSs(seg.end) + ' (' + dur + 's)')}"></div>`;
}

function truncate(s, n) {
  s = s || "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
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
    $("#history-detail").hidden = true;
    data.runs.forEach(r => {
      const tr = document.createElement("tr");
      tr.dataset.id = r.id;
      tr.innerHTML = `
        <td>${formatTs(r.timestamp)}</td>
        <td class="num">${r.n_configs ?? "–"}</td>
        <td>${escapeHtml(r.best_wer_config || "–")} <span class="muted">(${r.best_wer != null ? r.best_wer.toFixed(3) : "–"})</span></td>
        <td>${escapeHtml(r.best_cer_config || "–")} <span class="muted">(${r.best_cer != null ? r.best_cer.toFixed(3) : "–"})</span></td>
        <td class="num">${(r.total_runtime_s ?? 0).toFixed(1)}s</td>
        <td class="num">${(r.audio_duration_s ?? 0).toFixed(1)}s</td>
      `;
      tr.addEventListener("click", () => selectHistoryRun(r.id));
      body.appendChild(tr);
    });
  } catch { /* ignore */ }
}

async function selectHistoryRun(runId) {
  $$("#history-body tr").forEach(tr => {
    tr.classList.toggle("is-selected", tr.dataset.id === runId);
  });
  try {
    const run = await fetch(`/api/history/${encodeURIComponent(runId)}`).then(r => r.json());
    renderHistoryDetail(run);
  } catch { /* ignore */ }
}

function renderHistoryDetail(run) {
  const root = $("#history-detail");
  const rows = (run.configs || []).map(c => {
    const modelShort = (c.whisper_model || "–").replace(/^ggml-/, "").replace(/\.bin$/, "");
    const vadParams = c.vad_enabled
      ? `thr=${c.vad_threshold ?? 0.5} speech≥${c.vad_min_speech_ms ?? 250}ms silence≥${c.vad_min_silence_ms ?? 100}ms`
      : "";
    return `
    <tr>
      <td>${escapeHtml(c.config)}</td>
      <td><span class="config-vad-toggle ${c.vad_enabled ? "is-on" : ""}"><span class="toggle-dot"></span>${c.vad_enabled ? "on" : "off"}</span></td>
      <td class="num metric-cell metric-wer">${(c.wer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-cer">${(c.cer ?? 0).toFixed(3)}</td>
      <td class="num metric-cell metric-rtf">${(c.rtf ?? 0).toFixed(3)}</td>
      <td class="num">${(c.runtime_s ?? 0).toFixed(1)}s</td>
      <td class="num">${c.n_segments ?? "–"}</td>
      <td title="${escapeAttr(modelShort)}">${escapeHtml(modelShort)}</td>
      <td class="muted" style="font-size:11px">${vadParams}</td>
    </tr>`;
  }).join("");

  const verdict = run.verdict ? `<div class="results-verdict" style="margin:8px 0"><span class="verdict-label">${t("verdict.label")}</span> <span class="verdict-text">${escapeHtml(run.verdict)}</span></div>` : "";

  root.innerHTML = `
    <h3>${t("history.detail.title").replace("{ts}", formatTs(run.timestamp))}</h3>
    ${verdict}
    <table class="history-table">
      <thead>
        <tr>
          <th>${t("history.detail.colConfig")}</th>
          <th>${t("history.detail.colVad")}</th>
          <th class="num">${t("history.detail.colWer")}</th>
          <th class="num">${t("history.detail.colCer")}</th>
          <th class="num">${t("history.detail.colRtf")}</th>
          <th class="num">${t("history.detail.colRuntime")}</th>
          <th class="num">${t("history.detail.colSegments")}</th>
          <th>${t("table.model")}</th>
          <th class="muted" style="font-size:11px">VAD params</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="muted history-detail-note">${t("history.detail.segmentsNote")}</div>

    ${(run.configs || []).map((c, ci) => {
      const transcript = c.transcript_raw || (c.segments || []).map(s => s.text).join(" ");
      const segs = c.segments || [];
      const segRows = segs.map((s, i) => `
        <tr>
          <td>${i + 1}</td>
          <td><span class="muted">${fmtMmSs(s.start)}–${fmtMmSs(s.end)}</span></td>
          <td class="num">${(s.end - s.start).toFixed(1)}s</td>
          <td>${escapeHtml(s.text || "")}</td>
        </tr>
      `).join("");
      const uid = `hcfg-${ci}`;
      return `
        <div class="history-config-block">
          <h4>${escapeHtml(c.config)} <span class="config-vad-toggle ${c.vad_enabled ? "is-on" : ""}" style="font-size:11px"><span class="toggle-dot"></span>${c.vad_enabled ? "on" : "off"}</span></h4>
          <div class="vad-subtabs">
            <button type="button" class="vad-subtab is-active" data-subtab="${uid}-transcript" onclick="this.closest('.history-config-block').querySelectorAll('.vad-subtab').forEach(b=>b.classList.toggle('is-active',b===this));this.closest('.history-config-block').querySelectorAll('.vad-subpane').forEach(p=>p.hidden=(p.dataset.subpane!==this.dataset.subtab))">${t("history.detail.transcript")}</button>
            <button type="button" class="vad-subtab" data-subtab="${uid}-segments" onclick="this.closest('.history-config-block').querySelectorAll('.vad-subtab').forEach(b=>b.classList.toggle('is-active',b===this));this.closest('.history-config-block').querySelectorAll('.vad-subpane').forEach(p=>p.hidden=(p.dataset.subpane!==this.dataset.subtab))">${t("history.detail.segTable")} (${segs.length})</button>
          </div>
          <div class="vad-subpane" data-subpane="${uid}-transcript">
            <div class="diff-block">
              <div class="diff-stream">${escapeHtml(transcript || "(kosong)")}</div>
            </div>
          </div>
          <div class="vad-subpane" data-subpane="${uid}-segments" hidden>
            ${segs.length ? `
              <table class="vad-regions-table">
                <thead>
                  <tr>
                    <th>${t("history.detail.segIdx")}</th>
                    <th>${t("history.detail.segRange")}</th>
                    <th class="num">${t("history.detail.segDur")}</th>
                    <th>${t("history.detail.segText")}</th>
                  </tr>
                </thead>
                <tbody>${segRows}</tbody>
              </table>
            ` : `<div class="muted" style="padding:10px 0;font-size:12px">${t("vad.noSegments")}</div>`}
          </div>
        </div>
      `;
    }).join("")}
  `;
  root.hidden = false;
}

// ─── Helpers ────────────────────────────────────────────────
function escapeHtml(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])); }
function escapeAttr(s) { return escapeHtml(s); }
function minOf(arr, key) { return arr.reduce((m, x) => x[key] < m ? x[key] : m, Infinity); }
function maxOf(arr, key) { return arr.reduce((m, x) => x[key] > m ? x[key] : m, -Infinity); }
function isRtfRealTime(rtf) { return typeof rtf === "number" && rtf < 1.0; }
function colorClsRelative(value, best, worst) {
  if (value == null || best == null || worst == null) return "";
  if (best === worst) return "";
  if (value === best)  return "is-good";
  if (value === worst) return "is-bad";
  return "";
}
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