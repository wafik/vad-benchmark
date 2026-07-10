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
    gpus: list[GpuSample] = field(default_factory=list)
    timestamp: str = ""


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


def _read_tegrastats() -> GpuSample | None:
    """One-shot tegrastats sample (runs tegrastats --interval 1000, reads 2 lines).

    On Jetson Nano, nvidia-smi shows N/A for the integrated GPU — tegrastats
    is the only reliable source for GPU utilisation and temperature.
    """
    import re
    exe = shutil.which("tegrastats")
    if not exe:
        return None
    try:
        proc = subprocess.Popen(
            [exe, "--interval", "1000"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        line = ""
        for _ in range(2):
            next_line = proc.stdout.readline()
            if next_line:
                line = next_line
        proc.terminate()
        proc.wait(timeout=2)
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("tegrastats read failed: %s", e)
        return None
    if not line:
        return None
    gpu_m = re.search(r"GR3D_FREQ (\d+)%", line)
    gpu_temp_m = re.search(r"gpu@([\d.]+)C", line)
    if not gpu_m:
        return None
    return GpuSample(
        index=0,
        name="Orin GPU (GR3D)",
        util_percent=float(gpu_m.group(1)),
        mem_used_mb=None,  # tegrastats doesn't expose GPU dedicated mem (unified memory)
        mem_total_mb=None,
        temp_c=float(gpu_temp_m.group(1)) if gpu_temp_m else None,
    )


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


def _read_gpus() -> list[GpuSample]:
    """Read GPU stats — prefer tegrastats on Jetson (nvidia-smi shows N/A for integrated GPU)."""
    tegrastats = _read_tegrastats()
    if tegrastats is not None:
        return [tegrastats]
    return _read_nvidia()


def _sample() -> SystemSample:
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return SystemSample(
        cpu_percent=float(cpu),
        cpu_count=psutil.cpu_count(logical=True) or 1,
        ram_percent=float(mem.percent),
        ram_used_mb=round(mem.used / 1024 / 1024, 1),
        ram_total_mb=round(mem.total / 1024 / 1024, 1),
        disk_percent=float(disk.percent),
        cpu_temp_c=_read_cpu_temp(),
        gpus=_read_gpus(),
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def sample_dict() -> dict:
    """One-shot snapshot for ``GET /api/system``."""
    return asdict(_sample())


class ResourceMonitor:
    """Background sampler. ``latest`` is updated every ``interval_s`` seconds.

    ``latest`` includes running peak/avg for CPU, RAM, GPU so the live
    sysmon widget can display them without waiting for the run to finish.
    """

    def __init__(self, interval_s: float = 2.0):
        self.interval_s = interval_s
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._samples: list[SystemSample] = []
        self.latest: dict | None = None
        # Running peak/avg trackers (exposed in ``latest``).
        self._cpu_sum: float = 0.0
        self._cpu_peak: float = 0.0
        self._ram_sum: float = 0.0
        self._ram_peak: float = 0.0
        self._gpu_sum: float = 0.0
        self._gpu_peak: float = 0.0
        self._gpu_count: int = 0

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
                # Update running stats.
                self._cpu_sum += s.cpu_percent
                self._cpu_peak = max(self._cpu_peak, s.cpu_percent)
                self._ram_sum += s.ram_percent
                self._ram_peak = max(self._ram_peak, s.ram_percent)
                for g in s.gpus:
                    if g.util_percent is not None:
                        self._gpu_sum += g.util_percent
                        self._gpu_peak = max(self._gpu_peak, g.util_percent)
                        self._gpu_count += 1
                n = len(self._samples)
                d = asdict(s)
                d["cpu_avg"] = round(self._cpu_sum / n, 1)
                d["cpu_peak"] = round(self._cpu_peak, 1)
                d["ram_avg"] = round(self._ram_sum / n, 1)
                d["ram_peak"] = round(self._ram_peak, 1)
                d["gpu_avg"] = round(self._gpu_sum / self._gpu_count, 1) if self._gpu_count else None
                d["gpu_peak"] = round(self._gpu_peak, 1) if self._gpu_count else None
                self.latest = d
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
        if not self._samples:
            return {}
        cpus = [s.cpu_percent for s in self._samples]
        rams = [s.ram_percent for s in self._samples]
        gpu_utils: list[float] = []
        for s in self._samples:
            for g in s.gpus:
                if g.util_percent is not None:
                    gpu_utils.append(g.util_percent)
        return {
            "n_samples": len(self._samples),
            "cpu_avg": round(sum(cpus) / len(cpus), 1),
            "cpu_peak": max(cpus),
            "ram_avg": round(sum(rams) / len(rams), 1),
            "ram_peak": max(rams),
            "gpu_avg": round(sum(gpu_utils) / len(gpu_utils), 1) if gpu_utils else None,
            "gpu_peak": max(gpu_utils) if gpu_utils else None,
        }


if __name__ == "__main__":  # self-check
    import json
    print(json.dumps(sample_dict(), indent=2))