"""System resource sampling — CPU / RAM / GPU / temperature.

Best-effort only: every stat degrades gracefully to ``None`` when the host
doesn't expose it. Nothing in here should ever raise — a monitoring feature
must never crash a benchmark run.

Two entry points:
  ``sample_dict()``       — one instantaneous reading, used by ``GET /api/system``.
  ``ResourceMonitor``     — background sampler used by ``runner.run()`` to record
                            avg/peak usage for the whole run, saved into history.

Adapted from the sibling ``ocr-benchmark`` project's ``sysmon.py``.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import psutil

log = logging.getLogger(__name__)

# Prime psutil's CPU tracker so the first real sample isn't a meaningless 0.0.
psutil.cpu_percent(interval=None)


@dataclass
class GpuSample:
    index: int
    name: str
    util_percent: float | None
    mem_used_mb: float | None
    mem_total_mb: float | None
    temp_c: float | None


@dataclass
class SystemSample:
    cpu_percent: float
    cpu_count: int
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    disk_percent: float | None
    cpu_temp_c: float | None
    process_rss_mib: float
    gpus: list[GpuSample] = field(default_factory=list)
    timestamp: str = ""
    cpu_cores_percent: list[float | None] = field(default_factory=list)
    cpu_clocks_mhz: list[float | None] = field(default_factory=list)
    swap_used_mb: float | None = None
    swap_total_mb: float | None = None
    emc_percent: float | None = None
    emc_mhz: float | None = None
    gpu_util_percent: float | None = None
    gpu_clock_mhz: float | None = None
    gpu_temp_c: float | None = None
    power_mw: float | None = None
    warning_state: str = "normal"


def _read_nvidia() -> list[GpuSample]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=2,
            text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    samples: list[GpuSample] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        try:
            samples.append(GpuSample(
                index=int(parts[0]),
                name=parts[1],
                util_percent=float(parts[2]) if parts[2] else None,
                mem_used_mb=float(parts[3]) if parts[3] else None,
                mem_total_mb=float(parts[4]) if parts[4] else None,
                temp_c=float(parts[5]) if parts[5] else None,
            ))
        except ValueError:
            continue
    return samples


def parse_tegrastats(line: str) -> dict[str, object] | None:
    """Normalize one Jetson ``tegrastats`` line without requiring every field."""
    ram = re.search(r"\bRAM (\d+)/(\d+)MB", line)
    cpu = re.search(r"\bCPU \[([^]]+)\]", line)
    if not ram or not cpu:
        return None

    core_percent: list[float | None] = []
    core_clocks: list[float | None] = []
    for item in cpu.group(1).split(","):
        match = re.match(r"\s*(\d+(?:\.\d+)?)%@?(\d+(?:\.\d+)?)?", item)
        core_percent.append(float(match.group(1)) if match else None)
        core_clocks.append(float(match.group(2)) if match and match.group(2) else None)

    def number(pattern: str) -> float | None:
        match = re.search(pattern, line, re.IGNORECASE)
        return float(match.group(1)) if match else None

    return {
        "cpu_cores_percent": core_percent,
        "cpu_clocks_mhz": core_clocks,
        "ram_used_mb": float(ram.group(1)),
        "ram_total_mb": float(ram.group(2)),
        "swap_used_mb": number(r"\bSWAP (\d+)/"),
        "swap_total_mb": number(r"\bSWAP \d+/(\d+)MB"),
        "emc_percent": number(r"\bEMC_FREQ (\d+(?:\.\d+)?)%"),
        "emc_mhz": number(r"\bEMC_FREQ \d+(?:\.\d+)?%@?(\d+(?:\.\d+)?)"),
        "gpu_util_percent": number(r"\bGR3D_FREQ (\d+(?:\.\d+)?)%"),
        "gpu_clock_mhz": number(r"\bGR3D_FREQ \d+(?:\.\d+)?%@?(\d+(?:\.\d+)?)"),
        "cpu_temp_c": number(r"\bCPU@(\d+(?:\.\d+)?)C"),
        "gpu_temp_c": number(r"\bGPU@(\d+(?:\.\d+)?)C"),
        "power_mw": number(r"\bVDD_IN (\d+(?:\.\d+)?)/"),
    }


def _read_tegrastats() -> dict[str, object] | None:
    """Read two samples because the first tegrastats line may be stale."""
    executable = shutil.which("tegrastats")
    if not executable:
        return None
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [executable, "--interval", "1000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        line = ""
        for _ in range(2):
            next_line = process.stdout.readline() if process.stdout else ""
            if next_line:
                line = next_line
        return parse_tegrastats(line) if line else None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.SubprocessError:
                process.kill()


def warning_state(*, cpu_percent: float | None, gpu_percent: float | None, temp_c: float | None) -> str:
    """Classify the highest resource condition for the dashboard."""
    if any(value is not None and value >= 90 for value in (cpu_percent, gpu_percent)):
        return "critical"
    if (
        any(value is not None and value >= 75 for value in (cpu_percent, gpu_percent))
        or (temp_c is not None and temp_c >= 80)
    ):
        return "warning"
    return "normal"


def _read_cpu_temp() -> float | None:
    """Best-effort CPU temperature. Linux-only (returns None on Windows)."""
    try:
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    except Exception:  # noqa: BLE001
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        entries = temps.get(key) if temps else None
        if entries:
            return entries[0].current
    return None


def _sample() -> SystemSample:
    jetson = _read_tegrastats()
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cores = jetson["cpu_cores_percent"] if jetson else []
    active_cores = [value for value in cores if value is not None]
    cpu_percent = round(sum(active_cores) / len(active_cores), 1) if active_cores else float(cpu)
    ram_used_mb = float(jetson["ram_used_mb"]) if jetson else round(mem.used / 1024 / 1024, 1)
    ram_total_mb = float(jetson["ram_total_mb"]) if jetson else round(mem.total / 1024 / 1024, 1)
    ram_percent = round((ram_used_mb / ram_total_mb) * 100, 1) if ram_total_mb else float(mem.percent)
    gpu_util = float(jetson["gpu_util_percent"]) if jetson and jetson["gpu_util_percent"] is not None else None
    gpu_temp = float(jetson["gpu_temp_c"]) if jetson and jetson["gpu_temp_c"] is not None else None
    cpu_temp = float(jetson["cpu_temp_c"]) if jetson and jetson["cpu_temp_c"] is not None else _read_cpu_temp()
    gpus = (
        [GpuSample(0, "Jetson GPU (GR3D)", gpu_util, None, None, gpu_temp)]
        if jetson and gpu_util is not None
        else _read_nvidia()
    )
    if gpu_util is None and gpus:
        gpu_util = gpus[0].util_percent
    if gpu_temp is None and gpus:
        gpu_temp = gpus[0].temp_c
    max_temp = max((value for value in (cpu_temp, gpu_temp) if value is not None), default=None)
    return SystemSample(
        cpu_percent=cpu_percent,
        cpu_count=psutil.cpu_count(logical=True) or 1,
        ram_percent=ram_percent,
        ram_used_mb=ram_used_mb,
        ram_total_mb=ram_total_mb,
        disk_percent=float(disk.percent),
        cpu_temp_c=cpu_temp,
        process_rss_mib=round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
        gpus=gpus,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        cpu_cores_percent=list(cores),
        cpu_clocks_mhz=list(jetson["cpu_clocks_mhz"]) if jetson else [],
        swap_used_mb=float(jetson["swap_used_mb"]) if jetson and jetson["swap_used_mb"] is not None else None,
        swap_total_mb=float(jetson["swap_total_mb"]) if jetson and jetson["swap_total_mb"] is not None else None,
        emc_percent=float(jetson["emc_percent"]) if jetson and jetson["emc_percent"] is not None else None,
        emc_mhz=float(jetson["emc_mhz"]) if jetson and jetson["emc_mhz"] is not None else None,
        gpu_util_percent=gpu_util,
        gpu_clock_mhz=float(jetson["gpu_clock_mhz"]) if jetson and jetson["gpu_clock_mhz"] is not None else None,
        gpu_temp_c=gpu_temp,
        power_mw=float(jetson["power_mw"]) if jetson and jetson["power_mw"] is not None else None,
        warning_state=warning_state(cpu_percent=cpu_percent, gpu_percent=gpu_util, temp_c=max_temp),
    )


def sample_dict() -> dict:
    """One-shot snapshot for ``GET /api/system``."""
    return asdict(_sample())


class ResourceMonitor:
    """Background sampler. ``latest`` is updated every ``interval_s`` seconds."""

    def __init__(self, interval_s: float = 2.0):
        self.interval_s = interval_s
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._samples: list[SystemSample] = []
        self.latest: dict | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                s = _sample()
                self._samples.append(s)
                self.latest = asdict(s)
            except Exception:  # noqa: BLE001
                log.exception("sysmon sample failed")
            self._stop.wait(self.interval_s)

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=self.interval_s + 2)
        self._thread = None

    def summary(self) -> dict:
        keys = (
            "cpu_avg_percent", "cpu_peak_percent", "ram_avg_percent", "ram_peak_percent",
            "rss_peak_mib", "swap_avg_mib", "swap_peak_mib", "gpu_avg_percent",
            "gpu_peak_percent", "gpu_memory_peak_mib", "cpu_temp_peak_c", "gpu_temp_peak_c",
            "disk_avg_percent", "disk_peak_percent", "power_avg_mw", "power_peak_mw",
            "high_load_seconds", "thermal_warning_seconds",
        )
        if not self._samples:
            return dict.fromkeys(keys)

        def average(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 1) if values else None

        def peak(values: list[float]) -> float | None:
            return round(max(values), 1) if values else None

        cpus = [s.cpu_percent for s in self._samples]
        ram = [s.ram_percent for s in self._samples]
        rss = [s.process_rss_mib for s in self._samples]
        swap = [s.swap_used_mb for s in self._samples if s.swap_used_mb is not None]
        gpu_util: list[float] = []
        gpu_memory: list[float] = []
        cpu_temps = [s.cpu_temp_c for s in self._samples if s.cpu_temp_c is not None]
        gpu_temps: list[float] = []
        disks = [s.disk_percent for s in self._samples if s.disk_percent is not None]
        power = [s.power_mw for s in self._samples if s.power_mw is not None]
        for s in self._samples:
            if s.gpu_util_percent is not None:
                gpu_util.append(s.gpu_util_percent)
            for g in s.gpus:
                if s.gpu_util_percent is None and g.util_percent is not None:
                    gpu_util.append(g.util_percent)
                if g.mem_used_mb is not None:
                    gpu_memory.append(g.mem_used_mb)
                if s.gpu_temp_c is None and g.temp_c is not None:
                    gpu_temps.append(g.temp_c)
            if s.gpu_temp_c is not None:
                gpu_temps.append(s.gpu_temp_c)
        high_load = sum(
            1 for s in self._samples
            if s.cpu_percent >= 90 or (s.gpu_util_percent is not None and s.gpu_util_percent >= 90)
        )
        thermal_warning = sum(
            1 for s in self._samples
            if any(temp is not None and temp >= 80 for temp in (s.cpu_temp_c, s.gpu_temp_c))
        )
        return {
            "cpu_avg_percent": average(cpus),
            "cpu_peak_percent": peak(cpus),
            "ram_avg_percent": average(ram),
            "ram_peak_percent": peak(ram),
            "rss_peak_mib": peak(rss),
            "swap_avg_mib": average(swap),
            "swap_peak_mib": peak(swap),
            "gpu_avg_percent": average(gpu_util),
            "gpu_peak_percent": peak(gpu_util),
            "gpu_memory_peak_mib": peak(gpu_memory),
            "cpu_temp_peak_c": peak(cpu_temps),
            "gpu_temp_peak_c": peak(gpu_temps),
            "disk_avg_percent": average(disks),
            "disk_peak_percent": peak(disks),
            "power_avg_mw": average(power),
            "power_peak_mw": peak(power),
            "high_load_seconds": round(high_load * self.interval_s, 1),
            "thermal_warning_seconds": round(thermal_warning * self.interval_s, 1),
        }


if __name__ == "__main__":  # self-check
    import json
    print(json.dumps(sample_dict(), indent=2))
