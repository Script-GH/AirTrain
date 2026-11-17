"""Hardware telemetry: NVIDIA GPU via NVML (optional), CPU, RAM and battery via psutil."""

from __future__ import annotations

import os
import platform
import socket
import sys
import time
from typing import Any

import psutil

GB = 1024**3

# NVML clock throttle / event reason bits.
_THROTTLE_BITS = {
    0x1: "gpu_idle",
    0x2: "app_clock_setting",
    0x4: "sw_power_cap",
    0x8: "hw_slowdown",
    0x10: "sync_boost",
    0x20: "sw_thermal",
    0x40: "hw_thermal",
    0x80: "hw_power_brake",
    0x100: "display_clock",
}
# Reasons that mean the GPU is actually being held back by heat or power.
_LIMITING = {"sw_power_cap", "hw_slowdown", "sw_thermal", "hw_thermal", "hw_power_brake"}


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


class _Nvml:
    """Thin, failure-tolerant wrapper around pynvml for a single GPU."""

    def __init__(self, index: int = 0) -> None:
        self.ok = False
        self.error: str | None = None
        self.nv: Any = None
        self.h: Any = None
        try:
            import pynvml as nv  # provided by nvidia-ml-py

            nv.nvmlInit()
            count = nv.nvmlDeviceGetCount()
            if count == 0:
                self.error = "no NVIDIA GPU found"
                return
            self.h = nv.nvmlDeviceGetHandleByIndex(min(index, count - 1))
            self.nv = nv
            self.ok = True
        except ImportError:
            self.error = "nvidia-ml-py not installed"
        except Exception as e:  # NVMLError: driver missing, no GPU, etc.
            self.error = f"NVML unavailable: {e}"

    def call(self, fn: str, *args: Any) -> Any:
        if not self.ok:
            return None
        f = getattr(self.nv, fn, None)
        if f is None:
            return None
        try:
            return f(self.h, *args)
        except Exception:
            return None

    def throttle_reasons(self) -> list[str]:
        mask = self.call("nvmlDeviceGetCurrentClocksEventReasons")
        if mask is None:
            mask = self.call("nvmlDeviceGetCurrentClocksThrottleReasons")
        if not mask:
            return []
        return [name for bit, name in _THROTTLE_BITS.items() if mask & bit]

    def processes(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for fn, kind in (
            ("nvmlDeviceGetComputeRunningProcesses", "compute"),
            ("nvmlDeviceGetGraphicsRunningProcesses", "graphics"),
        ):
            for p in self.call(fn) or []:
                mem = getattr(p, "usedGpuMemory", None)
                out.append({"pid": p.pid, "kind": kind, "mem_gb": _r(mem / GB, 2) if isinstance(mem, int) else None})
        return out

    def shutdown(self) -> None:
        if self.ok:
            try:
                self.nv.nvmlShutdown()
            except Exception:
                pass


class Sampler:
    """Collects one telemetry snapshot at a time. Never raises on missing sensors."""

    def __init__(self, gpu_index: int = 0) -> None:
        self.nvml = _Nvml(gpu_index)
        self.hostname = socket.gethostname()
        self.os = os_name()
        self.cpu_model = cpu_name()
        self.cores = psutil.cpu_count(logical=True) or 1
        psutil.cpu_percent(None)  # prime the non-blocking counter
        self._static_gpu = self._gpu_static()

    def _gpu_static(self) -> dict[str, Any]:
        n = self.nvml
        if not n.ok:
            return {}
        name = n.call("nvmlDeviceGetName")
        if isinstance(name, bytes):
            name = name.decode()
        slowdown = n.call("nvmlDeviceGetTemperatureThreshold", getattr(n.nv, "NVML_TEMPERATURE_THRESHOLD_SLOWDOWN", 1))
        shutdown = n.call("nvmlDeviceGetTemperatureThreshold", getattr(n.nv, "NVML_TEMPERATURE_THRESHOLD_SHUTDOWN", 0))
        mem = n.call("nvmlDeviceGetMemoryInfo")
        max_clock = n.call("nvmlDeviceGetMaxClockInfo", getattr(n.nv, "NVML_CLOCK_GRAPHICS", 0))
        driver = None
        try:
            driver = n.nv.nvmlSystemGetDriverVersion()
            if isinstance(driver, bytes):
                driver = driver.decode()
        except Exception:
            pass
        return {
            "name": name or "NVIDIA GPU",
            "driver": driver,
            "vram_total_gb": _r(mem.total / GB, 2) if mem else None,
            "temp_slowdown_c": slowdown,
            "temp_shutdown_c": shutdown,
            "clock_max_mhz": max_clock,
        }

    @property
    def has_gpu(self) -> bool:
        return self.nvml.ok

    def gpu(self) -> dict[str, Any]:
        n = self.nvml
        if not n.ok:
            return {"available": False, "vendor": None, "name": None, "reason": n.error}
        util = n.call("nvmlDeviceGetUtilizationRates")
        mem = n.call("nvmlDeviceGetMemoryInfo")
        temp = n.call("nvmlDeviceGetTemperature", getattr(n.nv, "NVML_TEMPERATURE_GPU", 0))
        power_mw = n.call("nvmlDeviceGetPowerUsage")
        limit_mw = n.call("nvmlDeviceGetEnforcedPowerLimit") or n.call("nvmlDeviceGetPowerManagementLimit")
        fan = n.call("nvmlDeviceGetFanSpeed")
        clock = n.call("nvmlDeviceGetClockInfo", getattr(n.nv, "NVML_CLOCK_GRAPHICS", 0))
        reasons = n.throttle_reasons()
        s = self._static_gpu
        return {
            "available": True,
            "vendor": "nvidia",
            "name": s.get("name"),
            "driver": s.get("driver"),
            "util": util.gpu if util else None,
            "vram_used_gb": _r(mem.used / GB, 2) if mem else None,
            "vram_total_gb": _r(mem.total / GB, 2) if mem else s.get("vram_total_gb"),
            "temp_c": temp,
            "temp_limit_c": s.get("temp_slowdown_c"),
            "temp_shutdown_c": s.get("temp_shutdown_c"),
            "power_w": _r(power_mw / 1000) if power_mw is not None else None,
            "power_limit_w": _r(limit_mw / 1000) if limit_mw else None,
            "fan_pct": fan,
            "clock_mhz": clock,
            "clock_max_mhz": s.get("clock_max_mhz"),
            "throttle_reasons": reasons,
            "throttled": any(r in _LIMITING for r in reasons),
            "processes": n.processes(),
        }

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

    def battery(self) -> dict[str, Any]:
        try:
            b = psutil.sensors_battery()
        except Exception:
            b = None
        if b is None:
            return {"present": False, "percent": None, "plugged": None}
        return {"present": True, "percent": _r(b.percent, 0), "plugged": b.power_plugged}

    def sample(self) -> dict[str, Any]:
        battery = self.battery()
        return {
            "ts": time.time(),
            "device": {
                "hostname": self.hostname,
                "os": self.os,
                "platform": sys.platform,
                "kind": "laptop" if battery["present"] else "desktop",
            },
            "gpu": self.gpu(),
            "cpu": self.cpu(),
            "ram": self.ram(),
            "battery": battery,
        }

    def close(self) -> None:
        self.nvml.shutdown()


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


def own_pids() -> set[int]:
    me = os.getpid()
    pids = {me}
    try:
        pids.update(c.pid for c in psutil.Process(me).children(recursive=True))
    except Exception:
        pass
    return pids
