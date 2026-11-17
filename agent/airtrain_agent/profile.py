"""Machine profile used by `airtrain analysis` to decide which jobs this device can run."""

from __future__ import annotations

import importlib.util
import shutil
import time
from typing import Any

import psutil

from .config import Config, config_dir
from .telemetry import GB, Sampler


def _torch_info() -> dict[str, Any]:
    if importlib.util.find_spec("torch") is None:
        return {"torch": None, "torch_cuda": False}
    import torch

    return {"torch": torch.__version__, "torch_cuda": bool(torch.cuda.is_available())}


def _disk_free_gb() -> float:
    path = config_dir()
    while not path.exists() and path != path.parent:
        path = path.parent
    return round(shutil.disk_usage(path).free / GB, 1)


def build_profile(cfg: Config, sampler: Sampler | None = None, benchmark: bool = True) -> dict[str, Any]:
    """Snapshot of what this machine offers for training."""
    own = sampler is None
    sampler = sampler or Sampler(cfg.gpu_index)
    try:
        time.sleep(0.3)  # let the CPU counter settle
        t = sampler.sample()
    finally:
        if own:
            sampler.close()
    g, c, r = t["gpu"], t["cpu"], t["ram"]
    info = _torch_info()
    warnings: list[str] = []

    has_gpu = bool(g.get("available"))
    if info["torch"] is None:
        backend = "cuda" if has_gpu else "cpu"
        warnings.append('PyTorch is not installed; training needs: pip install "./agent[train]"')
    else:
        backend = "cuda" if info["torch_cuda"] else "cpu"
        if has_gpu and not info["torch_cuda"]:
            warnings.append("NVIDIA GPU found but this PyTorch build has no CUDA; install the CUDA wheel to use it")

    temp = g.get("temp_c") if has_gpu else c.get("temp_c")
    temp_limit = (g.get("temp_limit_c") if has_gpu else None) or cfg.max_temp_c
    temp_limit = min(temp_limit, cfg.max_temp_c)
    power, power_limit = g.get("power_w"), g.get("power_limit_w")
    vm = psutil.virtual_memory()

    p: dict[str, Any] = {
        "created_at": time.time(),
        "hostname": t["device"]["hostname"],
        "os": t["device"]["os"],
        "kind": t["device"]["kind"],
        "backend": backend,
        "gpu_name": g.get("name") if has_gpu else None,
        "vram_total_gb": g.get("vram_total_gb") if has_gpu else None,
        "vram_free_gb": (
            round(g["vram_total_gb"] - g["vram_used_gb"], 2)
            if has_gpu and g.get("vram_total_gb") is not None and g.get("vram_used_gb") is not None
            else None
        ),
        "ram_total_gb": r["total_gb"],
        "ram_free_gb": round(vm.available / GB, 2),
        "cpu_name": c["name"],
        "cpu_cores": c["cores"],
        "cpu_physical_cores": psutil.cpu_count(logical=False) or c["cores"],
        "cpu_freq_mhz": c.get("freq_mhz"),
        "disk_free_gb": _disk_free_gb(),
        "temp_c": temp,
        "temp_limit_c": temp_limit,
        "thermal_headroom_c": None if temp is None else round(temp_limit - temp, 1),
        "power_w": power,
        "power_limit_w": power_limit,
        "power_headroom_w": None if power is None or power_limit is None else round(power_limit - power, 1),
        "battery": t["battery"],
        "bench_flops": None,
        "bench_device": None,
        "warnings": warnings,
        **info,
    }
    if benchmark and info["torch"] is not None:
        from .jobs import benchmark_flops

        flops, dev = benchmark_flops()
        if dev == ("cuda" if backend == "cuda" else "cpu"):
            p["bench_flops"], p["bench_device"] = flops, dev
    return p


def free_memory_bytes(profile: dict[str, Any]) -> float:
    """Memory available to a training job on this machine's backend."""
    if profile["backend"] == "cuda" and profile.get("vram_free_gb") is not None:
        return profile["vram_free_gb"] * GB
    return profile["ram_free_gb"] * GB
