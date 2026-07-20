from types import SimpleNamespace

import vad_bench.sysmon as sysmon
from vad_bench.sysmon import (
    GpuSample,
    ResourceMonitor,
    SystemSample,
    parse_tegrastats,
    warning_state,
)


def test_parse_tegrastats_normalizes_jetson_fields():
    sample = parse_tegrastats(
        "RAM 1200/3964MB (lfb 2x4MB) SWAP 32/1982MB (cached 0MB) "
        "CPU [12%@1479,25%@1479,off,50%@1479] EMC_FREQ 5%@1600 "
        "GR3D_FREQ 71%@921 CPU@51C GPU@49C VDD_IN 2840/2750"
    )

    assert sample == {
        "cpu_cores_percent": [12.0, 25.0, None, 50.0],
        "cpu_clocks_mhz": [1479.0, 1479.0, None, 1479.0],
        "ram_used_mb": 1200.0,
        "ram_total_mb": 3964.0,
        "swap_used_mb": 32.0,
        "swap_total_mb": 1982.0,
        "emc_percent": 5.0,
        "emc_mhz": 1600.0,
        "gpu_util_percent": 71.0,
        "gpu_clock_mhz": 921.0,
        "cpu_temp_c": 51.0,
        "gpu_temp_c": 49.0,
        "power_mw": 2840.0,
    }


def test_parse_tegrastats_rejects_unrecognized_output():
    assert parse_tegrastats("not a tegrastats record") is None


def test_warning_state_marks_load_and_temperature_thresholds():
    assert warning_state(cpu_percent=90.0, gpu_percent=None, temp_c=None) == "critical"
    assert warning_state(cpu_percent=12.0, gpu_percent=76.0, temp_c=None) == "warning"
    assert warning_state(cpu_percent=12.0, gpu_percent=None, temp_c=80.0) == "warning"
    assert warning_state(cpu_percent=12.0, gpu_percent=None, temp_c=40.0) == "normal"


def test_sample_prefers_tegrastats_for_jetson_values(monkeypatch):
    monkeypatch.setattr(sysmon, "_read_tegrastats", lambda: {
        "cpu_cores_percent": [12.0, 25.0],
        "cpu_clocks_mhz": [1479.0, 1479.0],
        "ram_used_mb": 1200.0,
        "ram_total_mb": 3964.0,
        "swap_used_mb": 32.0,
        "swap_total_mb": 1982.0,
        "emc_percent": 5.0,
        "emc_mhz": 1600.0,
        "gpu_util_percent": 71.0,
        "gpu_clock_mhz": 921.0,
        "cpu_temp_c": 51.0,
        "gpu_temp_c": 49.0,
        "power_mw": 2840.0,
    })
    monkeypatch.setattr(sysmon.psutil, "cpu_percent", lambda interval=None: 1.0)
    monkeypatch.setattr(sysmon.psutil, "cpu_count", lambda logical=True: 6)
    monkeypatch.setattr(sysmon.psutil, "virtual_memory", lambda: SimpleNamespace(percent=10.0, used=1, total=2))
    monkeypatch.setattr(sysmon.psutil, "disk_usage", lambda path: SimpleNamespace(percent=11.0))
    monkeypatch.setattr(sysmon.psutil, "Process", lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=1)))

    sample = sysmon._sample()

    assert sample.cpu_percent == 18.5
    assert sample.ram_percent == 30.3
    assert sample.gpus[0].name == "Jetson GPU (GR3D)"
    assert sample.gpu_util_percent == 71.0
    assert sample.gpu_temp_c == 49.0
    assert sample.swap_used_mb == 32.0
    assert sample.warning_state == "normal"


def test_resource_summary_uses_normalized_process_and_gpu_peaks():
    monitor = ResourceMonitor()
    monitor._samples = [
        SystemSample(10.0, 4, 50.0, 100.0, 200.0, None, None, process_rss_mib=256.0, gpus=[
            GpuSample(0, "gpu", 50.0, 512.0, 1024.0, 60.0),
        ]),
        SystemSample(20.0, 4, 60.0, 120.0, 200.0, None, None, process_rss_mib=384.0, gpus=[
            GpuSample(0, "gpu", 70.0, 768.0, 1024.0, 65.0),
        ]),
    ]

    assert {key: monitor.summary()[key] for key in (
        "cpu_avg_percent", "cpu_peak_percent", "rss_peak_mib", "gpu_memory_peak_mib", "gpu_temp_peak_c",
    )} == {
        "cpu_avg_percent": 15.0,
        "cpu_peak_percent": 20.0,
        "rss_peak_mib": 384.0,
        "gpu_memory_peak_mib": 768.0,
        "gpu_temp_peak_c": 65.0,
    }


def test_resource_summary_preserves_unavailable_gpu_values_as_null():
    monitor = ResourceMonitor()
    monitor._samples = [
        SystemSample(10.0, 4, 50.0, 100.0, 200.0, None, None, process_rss_mib=256.0),
    ]

    assert monitor.summary()["gpu_memory_peak_mib"] is None
    assert monitor.summary()["gpu_temp_peak_c"] is None


def test_resource_summary_aggregates_jetson_fields_and_elapsed_status():
    monitor = ResourceMonitor(interval_s=2.0)
    monitor._samples = [
        SystemSample(
            50.0, 4, 40.0, 100.0, 200.0, None, 60.0, process_rss_mib=128.0,
            swap_used_mb=10.0, gpu_util_percent=20.0, gpu_temp_c=55.0,
            power_mw=2000.0, warning_state="normal",
        ),
        SystemSample(
            95.0, 4, 60.0, 120.0, 200.0, None, 82.0, process_rss_mib=256.0,
            swap_used_mb=30.0, gpu_util_percent=80.0, gpu_temp_c=75.0,
            power_mw=3000.0, warning_state="critical",
        ),
    ]

    summary = monitor.summary()

    assert summary["ram_peak_percent"] == 60.0
    assert summary["swap_peak_mib"] == 30.0
    assert summary["gpu_peak_percent"] == 80.0
    assert summary["cpu_temp_peak_c"] == 82.0
    assert summary["power_peak_mw"] == 3000.0
    assert summary["high_load_seconds"] == 2.0
    assert summary["thermal_warning_seconds"] == 2.0
