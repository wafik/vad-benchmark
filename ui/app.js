/* VAD Benchmark dashboard — vanilla JS, no build.
   Sister project: ocr-benchmark/ui/app.js (same patterns). */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// ─── i18n ───────────────────────────────────────────────────
const I18N = {
  en: {
    "topbar.title":         "VAD Benchmark",
    "topbar.sub":           "ai4db · Indonesian · declared VAD modes",
    "nav.skip":             "Skip to main content",
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
    "run.control":          "Control",
    "run.candidate":        "Candidate",
    "run.emptyAlert":       "Add at least one config.",
    "run.staleNote":        " · (looks stuck — already-running lock older than stale threshold)",
    "run.runningPrefix":    "Running · ",
    "run.donePrefix":       "Done · ",
    "run.errorPrefix":      "Error: ",
    "field.whisper":        "Whisper model",
    "field.language":       "Language",
    "field.threads":        "Threads",
    "field.vadThreshold":   "VAD threshold",
    "field.rmsThreshold":   "RMS threshold (% of peak)",
    "field.minSpeech":      "Min speech (ms)",
    "field.minSilence":     "Min silence (ms)",
    "field.speechPad":      "Speech pad (ms)",
    "field.maxSpeech":      "Max speech (s, 0=∞)",
    "field.vadOn":          "VAD on",
    "field.vadOff":         "VAD off",
    "field.remove":         "remove",
    "results.title":        "Results",
    "results.rowLabel":     "Show details for {name}",
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
    "results.cpuPeak":      "CPU peak",
    "results.rssPeak":      "Process RSS peak",
    "results.gpuMemoryPeak": "GPU memory peak",
    "results.gpuTempPeak":  "GPU temperature peak",
    "table.config":         "Config",
    "table.vad":            "VAD",
    "table.wer":            "WER",
    "table.cer":            "CER",
    "table.rtf":            "RTF",
    "table.avgSeg":         "Avg seg",
    "table.model":          "Model",
    "table.runtime":        "Total",
    "table.components":     "Components",
    "table.metric":         "Metric status",
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
    "history.sub":          "Newest first · paginated",
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
    "vad.metrics.referenceCaption": "Reference-caption WER/CER",
    "vad.timeline.vad":     "Whisper regions (VAD output)",
    "vad.timeline.gt":      "Reference-caption regions",
    "vad.timeline.axis":    "Time (mm:ss)",
    "vad.regions.idx":      "#",
    "vad.regions.range":    "Range",
    "vad.regions.duration": "Dur.",
    "vad.regions.gtText":   "Reference-caption text",
    "vad.regions.hypText":  "Whisper text",
    "vad.regions.wer":      "WER",
    "vad.regions.cer":      "CER",
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
    "footer.line1":         "VAD benchmark for <code>ai4db</code>'s Whisper pipeline on Indonesian audio. Compares declared <strong>off</strong>, <strong>builtin</strong>, <strong>presegmented</strong>, and <strong>rms_energy</strong> modes.",
    "footer.line2":         "Caveat: this is an exploratory one-clip dataset with <strong>silver reference captions</strong>. WER/CER are relative comparisons, not absolute accuracy or VAD-boundary quality.",
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
    "topbar.sub":           "ai4db · Bahasa Indonesia · mode VAD eksplisit",
    "nav.skip":             "Langsung ke konten utama",
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
    "run.control":          "Kontrol",
    "run.candidate":        "Kandidat",
    "run.emptyAlert":       "Tambahkan minimal satu config.",
    "run.staleNote":        " · (terlihat macet — lock berjalan terlalu lama)",
    "run.runningPrefix":    "Berjalan · ",
    "run.donePrefix":       "Selesai · ",
    "run.errorPrefix":      "Error: ",
    "field.whisper":        "Model Whisper",
    "field.language":       "Bahasa",
    "field.threads":        "Thread",
    "field.vadThreshold":   "Ambang VAD",
    "field.rmsThreshold":   "Ambang RMS (% dari puncak)",
    "field.minSpeech":      "Min speech (ms)",
    "field.minSilence":     "Min silence (ms)",
    "field.speechPad":      "Speech pad (ms)",
    "field.maxSpeech":      "Max speech (s, 0=∞)",
    "field.vadOn":          "VAD nyala",
    "field.vadOff":         "VAD mati",
    "field.remove":         "hapus",
    "results.title":        "Hasil",
    "results.rowLabel":     "Tampilkan detail untuk {name}",
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
    "results.cpuPeak":      "CPU puncak",
    "results.rssPeak":      "RSS proses puncak",
    "results.gpuMemoryPeak": "Memori GPU puncak",
    "results.gpuTempPeak":  "Suhu GPU puncak",
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
    "table.runtime":        "Total",
    "table.components":     "Komponen",
    "table.metric":         "Status metrik",
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
    "history.sub":          "Terbaru dulu · berpaginasi",
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
    "vad.metrics.referenceCaption": "WER/CER keterangan referensi",
    "vad.timeline.vad":     "Wilayah Whisper (keluaran VAD)",
    "vad.timeline.gt":      "Wilayah keterangan referensi",
    "vad.timeline.axis":    "Waktu (mm:ss)",
    "vad.regions.idx":      "#",
    "vad.regions.range":    "Rentang",
    "vad.regions.duration": "Dur.",
    "vad.regions.gtText":   "Teks keterangan referensi",
    "vad.regions.hypText":  "Teks Whisper",
    "vad.regions.wer":      "WER",
    "vad.regions.cer":      "CER",
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
    "footer.line1":         "Benchmark VAD untuk pipeline Whisper <code>ai4db</code> pada audio Bahasa Indonesia. Membandingkan mode eksplisit <strong>off</strong>, <strong>builtin</strong>, <strong>presegmented</strong>, dan <strong>rms_energy</strong>.",
    "footer.line2":         "Catatan: ini dataset eksploratif satu klip dengan <strong>keterangan referensi silver</strong>. WER/CER adalah perbandingan relatif, bukan akurasi absolut atau kualitas batas VAD.",
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
  { name: "baseline_novad", overrides: { vad_mode: "off" } },
  { name: "silero_vad",     overrides: { vad_mode: "builtin" } },
]);

// ─── i18n helpers ───────────────────────────────────────────
function t(key) { return (I18N[LANG] && I18N[LANG][key]) || (I18N.en[key]) || key; }

function setLanguage(lang) {
  if (!I18N[lang]) return;
  LANG = lang;
  try { localStorage.setItem("vad-bench.lang", lang); } catch {}
  applyLanguage();
}

function applyLanguage() {
  document.documentElement.lang = LANG;
  $$(".lang-toggle [data-lang]").forEach(b => {
    b.classList.toggle("is-active", b.dataset.lang === LANG);
    b.setAttribute("aria-pressed", String(b.dataset.lang === LANG));
  });

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
  $("#vad-badge-text").textContent = `mode: ${CFG.vad_mode}`;
}

// ─── Init ───────────────────────────────────────────────────
async function init() {
  try { LANG = localStorage.getItem("vad-bench.lang") || "id"; } catch {}
  applyLanguage();                     // first pass on static DOM
  await Promise.all([loadConfig(), loadModels(), refreshSystem(), loadRefSegments()]);
  pollSystem();
  openSSE();
  renderConfigs(DEFAULT_CONFIGS());
  await tryLoadLastResults();
  await refreshHistory();
  $("#history-prev").addEventListener("click", () => refreshHistory(historyPage - 1));
  $("#history-next").addEventListener("click", () => refreshHistory(historyPage + 1));
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
    btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
  });
}

// ─── Results tabs (Comparison / VAD breakdown) ──────────────
function wireResultsTabs() {
  $$(".results-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      $$(".results-tab").forEach(t => {
        const selected = t === tab;
        t.classList.toggle("is-active", selected);
        t.setAttribute("aria-selected", String(selected));
      });
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
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (target) target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
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
  $("#model-badge-text").textContent = CFG.whisper_model;
  refreshBadges();
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
  sysmonTimer = setInterval(refreshSystem, 3000);
}
async function refreshSystem() {
  try {
    const response = await fetch("/api/system");
    if (!response.ok) return;
    const s = await response.json();
    const gpu = (s.gpus && s.gpus[0]) || null;
    const gpuPercent = s.gpu_util_percent ?? gpu?.util_percent;
    const gpuTemp = s.gpu_temp_c ?? gpu?.temp_c;
    const cores = (s.cpu_cores_percent || []).map((value, index) =>
      value == null ? `C${index + 1}: off` : `C${index + 1}: ${value.toFixed(0)}%`
    ).join(" · ");
    const cpuDetail = [cores || `${s.cpu_count || "?"} cores`, s.emc_percent != null ? `EMC ${s.emc_percent.toFixed(0)}%` : ""].filter(Boolean).join(" · ");
    setSysmonCard("cpu", s.cpu_percent, 100, percentText(s.cpu_percent), cpuDetail, s.cpu_percent != null);
    setSysmonCard("ram", s.ram_percent, 100, percentText(s.ram_percent),
      mibPair(s.ram_used_mb, s.ram_total_mb), s.ram_percent != null);
    const swapPercent = s.swap_used_mb != null && s.swap_total_mb ? (s.swap_used_mb / s.swap_total_mb) * 100 : null;
    setSysmonCard("swap", swapPercent, 100, percentText(swapPercent),
      mibPair(s.swap_used_mb, s.swap_total_mb), swapPercent != null);
    setSysmonCard("cpu-temp", s.cpu_temp_c, 100, tempText(s.cpu_temp_c),
      s.cpu_clocks_mhz?.filter(Boolean).length ? `clock ${Math.max(...s.cpu_clocks_mhz.filter(Boolean)).toFixed(0)} MHz` : "",
      s.cpu_temp_c != null, true);
    setSysmonCard("gpu", gpuPercent, 100, percentText(gpuPercent),
      [s.gpu_clock_mhz != null ? `clock ${s.gpu_clock_mhz.toFixed(0)} MHz` : "", s.power_mw != null ? `${(s.power_mw / 1000).toFixed(1)} W` : ""].filter(Boolean).join(" · "),
      gpuPercent != null);
    const hasGpuMemory = gpu?.mem_used_mb != null && gpu?.mem_total_mb != null;
    setSysmonCard("gpu-memory", hasGpuMemory ? (gpu.mem_used_mb / gpu.mem_total_mb) * 100 : null, 100,
      hasGpuMemory ? percentText((gpu.mem_used_mb / gpu.mem_total_mb) * 100) : "shared",
      hasGpuMemory ? mibPair(gpu.mem_used_mb, gpu.mem_total_mb) : "Unified system RAM on Jetson", true);
    setSysmonCard("gpu-temp", gpuTemp, 100, tempText(gpuTemp), "GPU die", gpuTemp != null, true);
    setSysmonCard("disk", s.disk_percent, 100, percentText(s.disk_percent), "root filesystem", s.disk_percent != null);
    $("#sysmon-grid").dataset.state = s.warning_state || "normal";
    $("#sysmon-updated").textContent = s.timestamp ? new Date(s.timestamp).toLocaleTimeString() : "unavailable";
  } catch (e) { /* swallow */ }
}
function percentText(value) { return value == null ? "unavailable" : `${value.toFixed(0)}%`; }
function tempText(value) { return value == null ? "unavailable" : `${value.toFixed(1)}°C`; }
function mibPair(used, total) { return used == null || total == null ? "" : `${used.toFixed(0)} / ${total.toFixed(0)} MiB`; }
function setSysmonCard(metric, value, max, label, sub, available, temperature = false) {
  const val = $(`#sysmon-${metric}-val`);
  const bar = $(`#sysmon-${metric}-bar`);
  const detail = $(`#sysmon-${metric}-sub`);
  const card = val?.closest(".sysmon-card");
  const pct = value == null ? 0 : Math.min(100, (value / max) * 100);
  const severity = value != null && (value >= (temperature ? 80 : 90) ? "critical" : value >= 75 ? "warn" : "");
  if (val) val.textContent = available ? label : "unavailable";
  if (detail) detail.textContent = available ? sub : "not available on this host";
  if (bar) {
    bar.style.width = `${pct}%`;
    bar.classList.toggle("sysmon-warn", severity === "warn");
    bar.classList.toggle("sysmon-critical", severity === "critical");
  }
  if (card) card.classList.toggle("is-unavailable", !available);
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
  syncPairSelects();
}

function syncPairSelects() {
  const names = $$(".config-name-input").map(input => input.value.trim()).filter(Boolean);
  const selects = [$("#control-name"), $("#candidate-name")];
  selects.forEach((select, index) => {
    const value = select.value;
    select.innerHTML = names.map(name =>
      `<option value="${escapeAttr(name)}">${escapeHtml(name)}</option>`
    ).join("");
    select.value = names.includes(value) ? value : (names[index] || names[0] || "");
  });
}

// Which shared VAD knobs apply to each mode. rms_threshold is rms_energy-only;
// vad_threshold and vad_max_speech_s are whisper.cpp/Silero-only (builtin +
// presegmented both shell out to a Silero-backed binary that takes them).
// min_speech/min_silence/pad are shared by every non-off mode.
const VAD_MODE_FIELDS = {
  off:          [],
  builtin:      ["vad_threshold", "vad_min_speech_ms", "vad_min_silence_ms", "vad_speech_pad_ms", "vad_max_speech_s"],
  presegmented: ["vad_threshold", "vad_min_speech_ms", "vad_min_silence_ms", "vad_speech_pad_ms", "vad_max_speech_s"],
  rms_energy:   ["rms_threshold", "vad_min_speech_ms", "vad_min_silence_ms", "vad_speech_pad_ms"],
};

function configCard(cfg, index) {
  const card = document.createElement("div");
  card.className = "config-card";
  const ov = cfg.overrides || {};
  const vadMode = ov.vad_mode || "off";
  const activeFields = new Set(VAD_MODE_FIELDS[vadMode] || []);
  card.innerHTML = `
    <div class="config-card-head">
      <label class="field config-name-field">
        <span class="field-label">Config name</span>
        <input class="config-name-input" type="text" name="config-name-${index}" autocomplete="off" value="${escapeAttr(cfg.name)}" placeholder="config name" />
      </label>
      <button class="btn-icon" type="button" data-role="remove" title="${escapeAttr(t("field.remove"))}" aria-label="${escapeAttr(t("field.remove"))}">${t("field.remove")}</button>
    </div>
    <div class="config-card-grid">
      <label class="field">
        <span class="field-label">VAD mode</span>
        <select data-role="vad_mode" name="config-${index}-vad_mode" autocomplete="off">
          <option value="off" ${vadMode === "off" ? "selected" : ""}>off</option>
          <option value="builtin" ${vadMode === "builtin" ? "selected" : ""}>builtin</option>
          <option value="presegmented" ${vadMode === "presegmented" ? "selected" : ""}>presegmented</option>
          <option value="rms_energy" ${vadMode === "rms_energy" ? "selected" : ""}>rms_energy</option>
        </select>
      </label>
      <label class="field">
        <span class="field-label" data-i18n-key="field.whisper">${t("field.whisper")}</span>
        <select data-role="whisper_model" name="config-${index}-whisper_model" autocomplete="off" title="${escapeAttr((MODEL_DESCS[ov.whisper_model || CFG.whisper_model] || {}).description || "")}">
          ${MODELS.length === 0
              ? `<option value="${escapeAttr(CFG.whisper_model)}">${escapeHtml(CFG.whisper_model)}</option>`
              : MODELS.filter(m => !/silero/i.test(m)).map(m =>
                  `<option value="${escapeAttr(m)}" ${m === (ov.whisper_model || CFG.whisper_model) ? "selected" : ""}>${escapeHtml(modelLabel(m))}</option>`
                ).join("")}
        </select>
      </label>
      <label class="field">
        <span class="field-label" data-i18n-key="field.language">${t("field.language")}</span>
        <select data-role="language" name="config-${index}-language" autocomplete="off">
          <option value="id"   ${(ov.language || CFG.language) === "id"   ? "selected" : ""}>id (Indonesian)</option>
          <option value="auto" ${(ov.language || CFG.language) === "auto" ? "selected" : ""}>auto</option>
          <option value="en"   ${(ov.language || CFG.language) === "en"   ? "selected" : ""}>en</option>
        </select>
      </label>
      <label class="field">
        <span class="field-label" data-i18n-key="field.threads">${t("field.threads")}</span>
        <input type="number" min="1" max="32" step="1" data-role="threads" name="config-${index}-threads" autocomplete="off" value="${ov.threads ?? CFG.threads}" />
      </label>
      <label class="field">
        <span class="field-label"><span data-i18n-key="field.vadThreshold">${t("field.vadThreshold")}</span> <span class="field-value" data-role="vad_threshold_val">${ov.vad_threshold ?? CFG.vad_threshold}</span></span>
        <input type="range" min="0.10" max="0.90" step="0.05" data-role="vad_threshold" name="config-${index}-vad_threshold" autocomplete="off" value="${ov.vad_threshold ?? CFG.vad_threshold}" ${activeFields.has("vad_threshold") ? "" : "disabled"} />
      </label>
      <label class="field">
        <span class="field-label"><span data-i18n-key="field.rmsThreshold">${t("field.rmsThreshold")}</span> <span class="field-value" data-role="rms_threshold_val">${ov.rms_threshold ?? CFG.rms_threshold}</span></span>
        <input type="range" min="0.01" max="0.50" step="0.01" data-role="rms_threshold" name="config-${index}-rms_threshold" autocomplete="off" value="${ov.rms_threshold ?? CFG.rms_threshold}" ${activeFields.has("rms_threshold") ? "" : "disabled"} />
      </label>
      <label class="field">
        <span class="field-label"><span data-i18n-key="field.minSpeech">${t("field.minSpeech")}</span> <span class="field-value" data-role="vad_min_speech_ms_val">${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_speech_ms" name="config-${index}-vad_min_speech_ms" autocomplete="off" value="${ov.vad_min_speech_ms ?? CFG.vad_min_speech_ms}" ${activeFields.has("vad_min_speech_ms") ? "" : "disabled"} />
      </label>
      <label class="field">
        <span class="field-label"><span data-i18n-key="field.minSilence">${t("field.minSilence")}</span> <span class="field-value" data-role="vad_min_silence_ms_val">${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}</span></span>
        <input type="range" min="50" max="1000" step="10" data-role="vad_min_silence_ms" name="config-${index}-vad_min_silence_ms" autocomplete="off" value="${ov.vad_min_silence_ms ?? CFG.vad_min_silence_ms}" ${activeFields.has("vad_min_silence_ms") ? "" : "disabled"} />
      </label>
      <label class="field">
        <span class="field-label"><span data-i18n-key="field.speechPad">${t("field.speechPad")}</span> <span class="field-value" data-role="vad_speech_pad_ms_val">${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}</span></span>
        <input type="range" min="0" max="500" step="10" data-role="vad_speech_pad_ms" name="config-${index}-vad_speech_pad_ms" autocomplete="off" value="${ov.vad_speech_pad_ms ?? CFG.vad_speech_pad_ms}" ${activeFields.has("vad_speech_pad_ms") ? "" : "disabled"} />
      </label>
      <label class="field">
        <span class="field-label" data-i18n-key="field.maxSpeech">${t("field.maxSpeech")}</span>
        <input type="number" min="0" step="1" data-role="vad_max_speech_s" name="config-${index}-vad_max_speech_s" autocomplete="off" value="${ov.vad_max_speech_s ?? CFG.vad_max_speech_s}" ${activeFields.has("vad_max_speech_s") ? "" : "disabled"} />
      </label>
    </div>
  `;

  card.querySelector('[data-role="whisper_model"]').addEventListener("change", (e) => {
    e.target.title = (MODEL_DESCS[e.target.value] || {}).description || "";
  });

  const ranges = card.querySelectorAll('input[type="range"]');
  const fieldInput = (role) => card.querySelector(`[data-role="${role}"]`);
  card.querySelector('[data-role="vad_mode"]').addEventListener("change", (e) => {
    const active = new Set(VAD_MODE_FIELDS[e.target.value] || []);
    for (const role of ["vad_threshold", "rms_threshold", "vad_min_speech_ms", "vad_min_silence_ms", "vad_speech_pad_ms", "vad_max_speech_s"]) {
      const el = fieldInput(role);
      if (el) el.disabled = !active.has(role);
    }
  });
  ranges.forEach(r => {
    r.addEventListener("input", () => {
      const valEl = card.querySelector(`[data-role="${r.dataset.role}_val"]`);
      if (valEl) valEl.textContent = r.value;
    });
  });
  card.querySelector('[data-role="remove"]').addEventListener("click", () => {
    card.remove();
    syncPairSelects();
  });
  card.querySelector(".config-name-input").addEventListener("input", syncPairSelects);

  return card;
}

function collectConfigs() {
  const cards = $$("#configs-list .config-card");
  return cards.map(card => {
    const overrides = {
      vad_mode: card.querySelector('[data-role="vad_mode"]').value,
    };
    const roleToField = {
      "whisper_model": "whisper_model",
      "language":      "language",
      "threads":       "threads",
      "vad_threshold": "vad_threshold",
      "rms_threshold": "rms_threshold",
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
      } else if (field === "vad_threshold" || field === "rms_threshold") {
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
  root.appendChild(configCard({ name: `config_${root.children.length + 1}`, overrides: { vad_mode: "builtin" } }, root.children.length));
  syncPairSelects();
});
$("#btn-default-compare").addEventListener("click", () => renderConfigs(DEFAULT_CONFIGS()));

$("#btn-run").addEventListener("click", async () => {
  $("#audio-player").play().catch(() => {});
  const configs = collectConfigs();
  const controlName = $("#control-name").value;
  const candidateName = $("#candidate-name").value;
  const pairNames = new Set(configs.map(({ name }) => name));
  if (configs.length === 0) { alert(t("run.emptyAlert")); return; }
  if (RUNNING) { return; }
  $("#run-status").textContent = t("run.submitting");
  $("#run-status").classList.remove("is-error"); $("#run-status").classList.add("is-running");
  try {
    const params = new URLSearchParams({ configs: JSON.stringify(configs) });
    if (configs.length === 2 && pairNames.size === 2) {
      params.set("control_name", controlName);
      params.set("candidate_name", candidateName);
    }
    const resp = await fetch(`/api/run?${params}`, { method: "POST" });
    const data = await resp.json();
    if (!data.ok && data.already_running) {
      $("#run-status").textContent = t("run.alreadyRunning");
    } else if (!data.ok && data.not_ready) {
      $("#run-status").textContent = t("run.notReady") + (data.issues || []).join("; ");
      $("#run-status").classList.add("is-error"); $("#run-status").classList.remove("is-running");
    } else if (!data.ok) {
      $("#run-status").textContent = t("run.failed") + (data.detail || "request rejected");
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
    $("#audio-meta").textContent = `${t("audio.meta")} · ${formatDuration(sum.audio_duration_s)}`;
    if (!RUNNING) updateStepper(3);
  } catch (e) { /* no summary yet */ }
}

function renderResults(sum) {
  const metaFmt = t("results.metaFmt")
    .replace("{audio}", formatDuration(sum.audio_duration_s))
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

  const identityEl = $("#results-identity");
  const referenceLabel = sum.reference_quality === "silver"
    ? "silver reference - exploratory dataset"
    : formatFact(sum.reference_quality);
  identityEl.innerHTML = `
    <span><strong>Run ID</strong> ${escapeHtml(formatFact(sum.run_id))}</span>
    <span><strong>Manifest</strong> ${escapeHtml(formatFact(sum.manifest_path))}</span>
    <span><strong>Reference</strong> ${escapeHtml(referenceLabel)}</span>
  `;

  // Collect unique models from configs.
  const models = [...new Set(sum.configs.map(c => c.whisper_model).filter(Boolean))];
  const modelPills = models.map(m => {
    const short = MODEL_DESCS[m]?.name || m.replace(/^ggml-/, "").replace(/\.bin$/, "");
    return `<span class="model-pill">${escapeHtml(short)}</span>`;
  }).join(" ");

  const vadSummary = sum.vad_summary || {};

  $("#results-summary").innerHTML = `
    <div class="summary-tile">
      <div class="tile-label">${t("tile.bestWer")}<button type="button" class="tip" data-tip-key="wer" aria-label="${escapeAttr(t("aria.wer"))}">?</button></div>
      <div class="tile-value">${sum.best_wer_config || "–"}</div>
       <div class="tile-sub">${formatMetric(sum.best_wer)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.bestCer")}<button type="button" class="tip" data-tip-key="cer" aria-label="${escapeAttr(t("aria.cer"))}">?</button></div>
      <div class="tile-value">${sum.best_cer_config || "–"}</div>
       <div class="tile-sub">${formatMetric(sum.best_cer)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.fastestRtf")}<button type="button" class="tip" data-tip-key="rtf" aria-label="${escapeAttr(t("aria.rtf"))}">?</button></div>
      <div class="tile-value">${sum.fastest_rtf_config || "–"}</div>
       <div class="tile-sub">${formatMetric(sum.fastest_rtf)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.totalRuntime")}<button type="button" class="tip" data-tip-key="totalRuntime" aria-label="${escapeAttr(t("aria.totalRuntime"))}">?</button></div>
       <div class="tile-value">${formatDuration(sum.total_runtime_s)}</div>
      <div class="tile-sub">${sum.configs.length} ${LANG === "id" ? "config" : "configs"}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.segments")}</div>
       <div class="tile-value">${formatCount(vadSummary.total_segments)}</div>
       <div class="tile-sub">avg ${formatDuration(vadSummary.avg_segment_duration)}</div>
    </div>
    <div class="summary-tile">
      <div class="tile-label">${t("tile.speechCoverage")}</div>
       <div class="tile-value">${formatPercent(vadSummary.speech_coverage)}</div>
       <div class="tile-sub">${formatDuration(sum.audio_duration_s)} ${LANG === "id" ? "audio" : "audio"}</div>
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
  sum.configs.forEach(c => {
    const tr = document.createElement("tr");
    tr.dataset.config = c.config;
    tr.tabIndex = 0;
    tr.setAttribute("aria-controls", "config-detail");
    tr.setAttribute("aria-selected", "false");
    tr.setAttribute("aria-label", t("results.rowLabel").replace("{name}", c.config));
    const isBest = c.config === sum.best_wer_config;
    if (isBest) tr.classList.add("is-best");
    const rtfCls = isRtfRealTime(c.rtf) ? "is-good" : (c.rtf == null ? "" : "is-bad");
    const mode = formatFact(c.vad_mode);
    const hasVad = c.vad_mode != null && c.vad_mode !== "off";
    const modelShort = MODEL_DESCS[c.whisper_model]?.name || (c.whisper_model || "–").replace(/^ggml-/, "").replace(/\.bin$/, "");
    const modelParams = MODEL_DESCS[c.whisper_model]?.params || "";
    tr.innerHTML = `
      <td>${escapeHtml(c.config)}</td>
       <td><span class="config-vad-toggle ${hasVad ? "is-on" : ""}"><span class="toggle-dot"></span>${escapeHtml(mode)}</span></td>
       <td class="num metric-cell metric-wer">${formatMetric(c.wer)}</td>
       <td class="num metric-cell metric-cer">${formatMetric(c.cer)}</td>
       <td class="num metric-cell metric-rtf ${rtfCls}">${formatMetric(c.rtf)}</td>
        <td class="num">${formatDuration(c.total_s)}</td>
        <td class="timing-components">prep ${formatDuration(c.segment_prep_s)} · stage ${formatDuration(c.staging_s)} · transcribe ${formatDuration(c.transcription_s)}</td>
       <td>${metricStatus(c)}</td>
       <td class="num">${formatPercent(c.silence_removed)}</td>
       <td class="num">${formatCount(c.n_segments)}</td>
       <td class="num">${formatDuration(c.avg_seg_duration)}</td>
      <td><span class="model-cell" title="${escapeAttr(c.whisper_model || '')}">${escapeHtml(modelShort)}${modelParams ? ` <span class="model-params">(${modelParams})</span>` : ""}</span></td>
    `;
    tr.addEventListener("click", () => selectConfig(c.config));
    tr.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectConfig(c.config);
      }
    });
    tbody.appendChild(tr);
  });

  $("#best-line").textContent = t("results.bestLineFmt")
    .replace("{wer}", sum.best_wer_config || "–")
    .replace("{werV}", formatMetric(sum.best_wer))
    .replace("{cer}", sum.best_cer_config || "–")
    .replace("{cerV}", formatMetric(sum.best_cer))
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
  resEl.innerHTML = resourceSummaryHtml(res);
  resEl.hidden = false;

  if (sum.configs.length > 0) selectConfig(sum.configs[0].config);
}

let SELECTED = null;
let REF_SEGMENTS = [];   // [{start, end, text}, ...] from references/segments.json
async function selectConfig(config) {
  SELECTED = config;
  $$("#results-table tbody tr").forEach(tr => {
    tr.classList.toggle("is-selected", tr.dataset.config === config);
    tr.setAttribute("aria-selected", String(tr.dataset.config === config));
  });
  try {
    const detail = await fetch(`/api/results/${encodeURIComponent(config)}`).then(r => r.json());
    renderDetail(detail);
    renderVadBreakdown(detail, REF_SEGMENTS);
  } catch (e) { /* ignore */ }
}

function renderDetail(d) {
  const root = $("#config-detail");
  root.innerHTML = `
    <div class="diff-block">
      <h3>${t("diff.transcriptFmt").replace("{name}", escapeHtml(formatFact(d.config))).replace("{vad}", escapeHtml(formatFact(d.vad_mode)))}</h3>
      <div class="diff-stream">${escapeHtml(d.transcript_raw || t("diff.emptyTranscript"))}</div>
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

function renderVadBreakdown(d, refSegments) {
  const root = $("#vad-breakdown");
  const audioDur = d.audio_duration_s;
  const hypSegs = (d.segments || []).map(s => ({ start: s.start, end: s.end, text: s.text }));
  const refSegs = (refSegments || []).map(s => ({ start: s.start, end: s.end, text: s.text }));
  const perRegion = d.per_region_wer || [];

  root.innerHTML = `
    <div class="vad-metrics">
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.regions")}</div>
        <div class="tile-value">${formatCount(d.n_segments)}</div>
        <div class="tile-sub">${d.metric_status || "unavailable"}</div>
      </div>
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.meanDur")}</div>
        <div class="tile-value">${formatDuration(d.avg_seg_duration)}</div>
        <div class="tile-sub">${t("vad.metrics.totalSpeech")}: ${formatDuration(d.speech_seconds)}</div>
      </div>
      <div class="summary-tile">
        <div class="tile-label">${t("vad.metrics.silenceRemoved")}</div>
        <div class="tile-value">${formatPercent(d.silence_removed)}</div>
        <div class="tile-sub">${formatDuration(audioDur)} ${LANG === "id" ? "audio" : "audio"}</div>
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
      <div class="table-scroll">
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
          </tr>
        </thead>
        <tbody>
           ${perRegion.map(pr => {
             const w = pr.wer;
             const c = pr.cer;
             const wCls = w != null ? (w <= 0.2 ? "match-good" : w <= 0.5 ? "match-partial" : "match-none") : "";
             const cCls = c != null ? (c <= 0.2 ? "match-good" : c <= 0.5 ? "match-partial" : "match-none") : "";
             return `
            <tr>
              <td>${pr.index + 1}</td>
              <td><span class="muted">${fmtMmSs(pr.start)}–${fmtMmSs(pr.end)}</span></td>
               <td class="num">${formatDuration(pr.duration)}</td>
              <td>${escapeHtml(truncate(pr.ref_text, 80))}</td>
              <td>${escapeHtml(truncate(pr.hyp_text, 80))}</td>
               <td class="num ${wCls}">${formatPercent(w)}</td>
               <td class="num ${cCls}">${formatPercent(c)}</td>
            </tr>`;
           }).join("")}
        </tbody>
        </table>
      </div>
    </div>

    <div class="vad-subpane" data-subpane="chunks" hidden>
      ${renderChunkList(d)}
    </div>
  `;

  const metricHeading = root.querySelector(".vad-metrics");
  metricHeading.insertAdjacentHTML("afterend", `<div class="reference-caption-metric">${t("vad.metrics.referenceCaption")}${d.metric_status === "error" ? `: ${escapeHtml(d.metric_error || "unavailable")}` : ""}</div>`);

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
      <div class="table-scroll">
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
    </div>
  `;
}

function renderTimelineAxis(audioDur) {
  // Tick every 60s; up to ~12 ticks for an 11-min podcast.
  if (!Number.isFinite(audioDur) || audioDur <= 0) return "";
  const ticks = [];
  for (let s = 0; s <= audioDur; s += 60) {
    const left = audioDur > 0 ? (s / audioDur) * 100 : 0;
    ticks.push(`<span class="vad-timeline-tick" style="left:${left}%">${fmtMmSs(s)}</span>`);
  }
  return ticks.join("");
}

function renderTimelineRegion(seg, audioDur, klass) {
  if (!Number.isFinite(audioDur) || audioDur <= 0) return "";
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
let historyPage = 1;
const HISTORY_PAGE_SIZE = 20;

async function refreshHistory(page = historyPage) {
  try {
    const params = new URLSearchParams();
    params.set("page", page);
    params.set("page_size", HISTORY_PAGE_SIZE);
    const data = await fetch(`/api/history?${params}`).then(r => r.json());
    historyPage = data.page || page;
    const body = $("#history-body");
    body.innerHTML = "";
    if (!data.runs || data.runs.length === 0) {
      $("#history-panel").hidden = !(data.total > 0);
      renderHistoryPagination(data);
      return;
    }
    $("#history-panel").hidden = false;
    $("#history-detail").hidden = true;
    data.runs.forEach(r => {
      const tr = document.createElement("tr");
      tr.dataset.id = r.id;
      tr.tabIndex = 0;
      tr.setAttribute("aria-controls", "history-detail");
      tr.setAttribute("aria-selected", "false");
      tr.setAttribute("aria-label", `Show details for ${formatTs(r.timestamp)}`);
      tr.innerHTML = `
        <td>${formatTs(r.timestamp)}</td>
        <td class="num">${r.n_configs ?? "–"}</td>
        <td>${escapeHtml(r.best_wer_config || "–")} <span class="muted">(${r.best_wer != null ? r.best_wer.toFixed(3) : "–"})</span></td>
        <td>${escapeHtml(r.best_cer_config || "–")} <span class="muted">(${r.best_cer != null ? r.best_cer.toFixed(3) : "–"})</span></td>
        <td class="num">${formatDuration(r.total_runtime_s)}</td>
        <td class="num">${formatDuration(r.audio_duration_s)}</td>
      `;
      tr.addEventListener("click", () => selectHistoryRun(r.id));
      tr.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectHistoryRun(r.id);
        }
      });
      body.appendChild(tr);
    });
    renderHistoryPagination(data);
  } catch { /* ignore */ }
}

function renderHistoryPagination(data) {
  const nav = $("#history-pagination");
  const totalPages = data.total_pages || 1;
  nav.hidden = !(data.total > HISTORY_PAGE_SIZE);
  $("#history-prev").disabled = historyPage <= 1;
  $("#history-next").disabled = historyPage >= totalPages;
  $("#history-page-status").textContent = `Page ${historyPage} of ${totalPages} · ${data.total || 0} runs`;
}

async function selectHistoryRun(runId) {
  $$("#history-body tr").forEach(tr => {
    tr.classList.toggle("is-selected", tr.dataset.id === runId);
    tr.setAttribute("aria-selected", String(tr.dataset.id === runId));
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
    const hasVad = c.vad_mode != null && c.vad_mode !== "off";
    const vadParams = hasVad
      ? `thr=${formatFact(c.vad_threshold)} speech≥${formatFact(c.vad_min_speech_ms)}ms silence≥${formatFact(c.vad_min_silence_ms)}ms`
      : "";
    return `
    <tr>
      <td>${escapeHtml(c.config)}</td>
       <td><span class="config-vad-toggle ${hasVad ? "is-on" : ""}"><span class="toggle-dot"></span>${escapeHtml(formatFact(c.vad_mode))}</span></td>
       <td class="num metric-cell metric-wer">${formatMetric(c.wer)}</td>
       <td class="num metric-cell metric-cer">${formatMetric(c.cer)}</td>
       <td class="num metric-cell metric-rtf">${formatMetric(c.rtf)}</td>
       <td class="num">${formatDuration(c.runtime_s)}</td>
       <td class="num">${formatCount(c.n_segments)}</td>
      <td title="${escapeAttr(modelShort)}">${escapeHtml(modelShort)}</td>
      <td class="muted" style="font-size:11px">${vadParams}</td>
    </tr>`;
  }).join("");

  const verdict = run.verdict ? `<div class="results-verdict" style="margin:8px 0"><span class="verdict-label">${t("verdict.label")}</span> <span class="verdict-text">${escapeHtml(run.verdict)}</span></div>` : "";
  const resources = run.resources ? `<div class="results-resources">${resourceSummaryHtml(run.resources)}</div>` : "";

  root.innerHTML = `
    <h3>${t("history.detail.title").replace("{ts}", formatTs(run.timestamp))}</h3>
    ${verdict}
    ${resources}
    <div class="table-scroll">
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
    </div>
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
          <h4>${escapeHtml(formatFact(c.config))} <span class="config-vad-toggle ${hasVad ? "is-on" : ""}" style="font-size:11px"><span class="toggle-dot"></span>${escapeHtml(formatFact(c.vad_mode))}</span></h4>
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
              <div class="table-scroll">
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
              </div>
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
function formatResource(value, unit) { return value == null ? "unavailable" : `${value.toFixed(1)} ${unit}`; }
function resourceSummaryHtml(res) {
  return `
    <span><span class="res-label">CPU avg</span>${formatResource(res.cpu_avg_percent, "%")}</span>
    <span><span class="res-label">CPU peak</span>${formatResource(res.cpu_peak_percent, "%")}</span>
    <span><span class="res-label">RAM peak</span>${formatResource(res.ram_peak_percent, "%")}</span>
    <span><span class="res-label">Process RSS peak</span>${formatResource(res.rss_peak_mib, "MiB")}</span>
    <span><span class="res-label">Swap peak</span>${formatResource(res.swap_peak_mib, "MiB")}</span>
    <span><span class="res-label">GPU avg / peak</span>${formatResource(res.gpu_avg_percent, "%")} / ${formatResource(res.gpu_peak_percent, "%")}</span>
    <span><span class="res-label">GPU memory peak</span>${formatResource(res.gpu_memory_peak_mib, "MiB")}</span>
    <span><span class="res-label">CPU / GPU temp</span>${formatResource(res.cpu_temp_peak_c, "°C")} / ${formatResource(res.gpu_temp_peak_c, "°C")}</span>
    <span><span class="res-label">Disk peak</span>${formatResource(res.disk_peak_percent, "%")}</span>
    <span><span class="res-label">Power peak</span>${formatResource(res.power_peak_mw, "mW")}</span>
    <span><span class="res-label">High load / thermal</span>${formatResource(res.high_load_seconds, "s")} / ${formatResource(res.thermal_warning_seconds, "s")}</span>
  `;
}
function formatFact(value) { return value == null || value === "" ? "unavailable" : String(value); }
function formatMetric(value) { return Number.isFinite(value) ? value.toFixed(3) : "unavailable"; }
function formatDuration(value) { return Number.isFinite(value) ? `${value.toFixed(1)}s` : "unavailable"; }
function formatCount(value) { return Number.isFinite(value) ? String(value) : "unavailable"; }
function formatPercent(value) { return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "unavailable"; }
function metricStatus(c) {
  const status = c.metric_status || "unavailable";
  const detail = status === "error" && c.metric_error ? `: ${c.metric_error}` : "";
  return `<span class="metric-status is-${escapeAttr(status)}">${escapeHtml(status + detail)}</span>`;
}
function isRtfRealTime(rtf) { return typeof rtf === "number" && rtf < 1.0; }
function formatTs(iso) {
  if (!iso) return "unavailable";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

// ─── Boot ───────────────────────────────────────────────────
init().catch(err => {
  console.error("init failed", err);
  $("#run-status").textContent = "Init failed: " + err.message;
  $("#run-status").classList.add("is-error");
});
