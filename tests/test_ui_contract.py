"""Static UI contract for benchmark config requests."""
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "ui" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[1] / "ui" / "index.html"
STYLE_CSS = Path(__file__).resolve().parents[1] / "ui" / "style.css"

SUMMARY_WITH_UNAVAILABLE_FACTS = {
    "configs": [{
        "config": "candidate",
        "vad_mode": None,
        "wer": None,
        "cer": None,
        "rtf": None,
        "total_s": None,
        "segment_prep_s": None,
        "staging_s": None,
        "transcription_s": None,
        "metric_status": "error",
        "metric_error": "reference timestamps could not be parsed",
    }],
    "run_id": None,
    "manifest_path": None,
    "reference_quality": None,
    "resources": {"gpu_memory_peak_mib": None},
    "vad_summary": None,
}


def test_config_cards_submit_explicit_vad_modes_only():
    source = APP_JS.read_text(encoding="utf-8")
    collect_configs = source[source.index("function collectConfigs()"):source.index('$("#btn-add-config")')]

    assert '{ name: "baseline_novad", overrides: { vad_mode: "off" } }' in source
    assert '{ name: "silero_vad",     overrides: { vad_mode: "builtin" } }' in source
    assert '<select data-role="vad_mode"' in source
    assert '<option value="off"' in source
    assert '<option value="builtin"' in source
    assert '<option value="presegmented"' in source
    assert '<option value="rms_energy"' in source
    assert 'vad_enabled' not in collect_configs


def test_ui_submits_pair_selection_and_normalized_resources():
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="control-name"' in html
    assert 'id="candidate-name"' in html
    assert 'params.set("control_name", controlName)' in source
    assert 'params.set("candidate_name", candidateName)' in source
    for key in (
        "cpu_avg_percent",
        "cpu_peak_percent",
        "rss_peak_mib",
        "gpu_memory_peak_mib",
        "gpu_temp_peak_c",
    ):
        assert key in source
    assert '"unavailable"' in source
    assert "MiB" in source
    assert "C" in source


def test_ui_omits_pair_parameters_without_two_distinct_configs():
    source = APP_JS.read_text(encoding="utf-8")
    run_handler = source[source.index('$("#btn-run").addEventListener'):]

    assert "const pairNames = new Set(configs.map(({ name }) => name));" in run_handler
    assert "if (configs.length === 2 && pairNames.size === 2)" in run_handler
    assert run_handler.index('if (configs.length === 2 && pairNames.size === 2)') < run_handler.index(
        'params.set("control_name", controlName)'
    )


def test_ui_renders_result_identity_limits_and_server_metrics_only():
    source = APP_JS.read_text(encoding="utf-8")

    for field in (
        "run_id",
        "manifest_path",
        "reference_quality",
        "total_s",
        "segment_prep_s",
        "staging_s",
        "transcription_s",
        "metric_status",
        "metric_error",
    ):
        assert field in source
    assert "silver reference - exploratory dataset" in source
    assert "Reference-caption WER/CER" in source
    assert "function computePerRegion(" not in source
    assert "matchScore" not in source


def test_ui_contract_requires_server_aggregates_and_explicit_unavailable_facts():
    source = APP_JS.read_text(encoding="utf-8")
    render_results = source[source.index("function renderResults(sum)"):source.index("let SELECTED")]
    render_vad_breakdown = source[source.index("function renderVadBreakdown"):source.index("function renderChunkList")]
    render_history = source[source.index("function renderHistoryDetail"):source.index("// ─── Helpers")]
    metric_status = source[source.index("function metricStatus"):source.index("function isRtfRealTime")]

    assert SUMMARY_WITH_UNAVAILABLE_FACTS["configs"][0]["metric_status"] == "error"
    assert SUMMARY_WITH_UNAVAILABLE_FACTS["configs"][0]["metric_error"]
    assert SUMMARY_WITH_UNAVAILABLE_FACTS["run_id"] is None
    assert SUMMARY_WITH_UNAVAILABLE_FACTS["manifest_path"] is None
    assert SUMMARY_WITH_UNAVAILABLE_FACTS["reference_quality"] is None
    assert SUMMARY_WITH_UNAVAILABLE_FACTS["resources"]["gpu_memory_peak_mib"] is None
    assert "sum.vad_summary" in render_results
    assert "sum.best_wer" in render_results
    assert "sum.best_cer" in render_results
    assert "sum.fastest_rtf" in render_results
    assert "formatFact(sum.reference_quality)" in render_results
    assert "formatFact(sum.run_id)" in render_results
    assert "formatFact(sum.manifest_path)" in render_results
    assert "formatDuration(c.total_s)" in render_results
    assert "formatDuration(c.segment_prep_s)" in render_results
    assert "formatDuration(c.staging_s)" in render_results
    assert "formatDuration(c.transcription_s)" in render_results
    assert "reference timestamps could not be parsed" not in render_results
    assert "metricStatus(c)" in render_results
    assert 'status === "error" && c.metric_error' in metric_status
    assert "escapeHtml(status + detail)" in metric_status
    assert "formatCount(d.n_segments)" in render_vad_breakdown
    assert "formatDuration(d.avg_seg_duration)" in render_vad_breakdown
    assert "formatDuration(d.speech_seconds)" in render_vad_breakdown
    assert "formatPercent(d.silence_removed)" in render_vad_breakdown
    assert "hypSegs.reduce" not in render_vad_breakdown
    assert "c.vad_mode || \"off\"" not in render_history
    assert "(c.runtime_s ?? 0)" not in render_history
    assert 'const vadConfigs = sum.configs.filter(c => c.n_segments != null);' not in render_results
    assert "const totalSegs = vadConfigs.reduce" not in render_results
    assert "const avgSegDur = vadConfigs" not in render_results
    assert "const speechCov = vadConfigs" not in render_results
    assert "minOf(sum.configs" not in render_results
    assert "maxOf(sum.configs" not in render_results
    assert "function minOf(" not in source
    assert "function maxOf(" not in source


def test_ui_accessibility_contract_covers_navigation_status_forms_rows_and_tables():
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    config_card = source[source.index("function configCard("):source.index("function collectConfigs()")]
    render_results = source[source.index("function renderResults(sum)"):source.index("let SELECTED")]
    select_config = source[source.index("async function selectConfig("):source.index("function renderDetail(")]

    assert '<a class="skip-link" href="#main-content"' in html
    assert '<main class="container" id="main-content" tabindex="-1">' in html
    assert '<h1 class="title"' in html
    assert 'aria-hidden="true" focusable="false"' in html
    assert 'id="run-status" role="status" aria-live="polite" aria-atomic="true"' in html
    assert ":focus-visible" in css
    assert ".table-scroll" in css
    assert "overflow-x: auto" in css
    assert "@media" in css
    assert html.count('<div class="table-scroll">') == 2
    assert source.count('<div class="table-scroll">') >= 3

    assert 'name="config-name-${index}"' in config_card
    assert 'autocomplete="off"' in config_card
    assert '<label class="field">' in config_card
    assert 'name="config-${index}-vad_mode"' in config_card
    assert 'aria-label="${escapeAttr(t("field.remove"))}"' in config_card

    assert "tr.tabIndex = 0" in render_results
    assert 'tr.setAttribute("aria-controls", "config-detail")' in render_results
    assert 'tr.addEventListener("keydown"' in render_results
    assert 'event.key === "Enter" || event.key === " "' in render_results
    assert 'tr.setAttribute("aria-selected", String(tr.dataset.config === config))' in select_config


def test_ui_accessibility_contract_covers_task_6_review_findings():
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    refresh_history = source[source.index("async function refreshHistory("):source.index("async function selectHistoryRun(")]
    select_history = source[source.index("async function selectHistoryRun("):source.index("function renderHistoryDetail(")]

    assert '<html lang="id">' in html
    assert 'id="control-name" name="control_name" autocomplete="off"' in html
    assert 'id="candidate-name" name="candidate_name" autocomplete="off"' in html
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert 'role="tabpanel"' in html
    assert 'aria-pressed="false"' in html
    assert '<button type="button" data-lang="id" class="lang-btn" aria-pressed="true">ID</button>' in html
    assert 'document.documentElement.lang = LANG' in source
    assert 'b.setAttribute("aria-pressed", String(b.dataset.lang === LANG))' in source
    assert 't.setAttribute("aria-selected", String(selected))' in source

    assert 'tr.tabIndex = 0' in refresh_history
    assert 'tr.setAttribute("aria-controls", "history-detail")' in refresh_history
    assert 'tr.addEventListener("keydown"' in refresh_history
    assert 'event.key === "Enter" || event.key === " "' in refresh_history
    assert 'tr.setAttribute("aria-selected", String(tr.dataset.id === runId))' in select_history

    assert '.tip:focus-visible' in css
    assert 'outline: 3px solid var(--accent)' in css
    assert '--text-muted: #6b6560;' in css
    assert '@media (prefers-reduced-motion: reduce)' in css
    assert 'transition-duration: 0.01ms !important' in css
    assert 'window.matchMedia("(prefers-reduced-motion: reduce)").matches' in source
    assert 'behavior: reducedMotion ? "auto" : "smooth"' in source


def test_ui_has_jetson_telemetry_and_history_pagination_contract():
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    for metric in (
        "cpu", "ram", "swap", "gpu", "gpu-memory", "cpu-temp", "gpu-temp", "disk",
    ):
        assert f'data-metric="{metric}"' in html
    assert 'id="history-pagination"' in html
    assert 'params.set("page", page)' in source
    assert "warning_state" in source
    assert "not available on this host" in source
