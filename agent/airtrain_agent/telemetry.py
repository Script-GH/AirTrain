"""Hardware telemetry: CPU and RAM via psutil."""

from __future__ import annotations

import platform
import socket
import sys
import time
from typing import Any

import psutil

GB = 1024**3

def _r(v: float | None, n: int = 1) -> float | None:
    return None if v is None else round(float(v), n)


def cpu_name() -> str:
    name = ""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        name = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
    return name or platform.processor() or platform.machine() or "CPU"


def os_name() -> str:
    if sys.platform == "win32":
        return f"Windows {platform.release()}"
    try:
        info = platform.freedesktop_os_release()
        return info.get("PRETTY_NAME") or "Linux"
    except (OSError, AttributeError):
        return f"Linux {platform.release()}"


class Sampler:
    """Collects one telemetry snapshot at a time. Never raises on missing sensors."""

    def __init__(self, gpu_index: int = 0) -> None:
        self.hostname = socket.gethostname()
        self.os = os_name()
        self.cpu_model = cpu_name()
        self.cores = psutil.cpu_count(logical=True) or 1
        psutil.cpu_percent(None)  # prime the non-blocking counter

    def cpu(self) -> dict[str, Any]:
        freq = None
        try:
            f = psutil.cpu_freq()
            freq = _r(f.current, 0) if f else None
        except Exception:
            pass
        return {
            "name": self.cpu_model,
            "util": _r(psutil.cpu_percent(None)),
            "cores": self.cores,
            "freq_mhz": freq,
            "temp_c": _cpu_temp(),
        }

    def ram(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        return {"used_gb": _r((vm.total - vm.available) / GB, 2), "total_gb": _r(vm.total / GB, 2)}

    def sample(self) -> dict[str, Any]:
        return {
            "ts": time.time(),
            "device": {
                "hostname": self.hostname,
                "os": self.os,
                "platform": sys.platform,
            },
            "cpu": self.cpu(),
            "ram": self.ram(),
        }

def _cpu_temp() -> float | None:
    fn = getattr(psutil, "sensors_temperatures", None)  # not available on Windows
    if fn is None:
        return None
    try:
        temps = fn()
    except Exception:
        return None
    for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
        for t in temps.get(key, []):
            if t.current:
                return _r(t.current)
    return None
