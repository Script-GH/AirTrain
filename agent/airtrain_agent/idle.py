"""User idle detection and the busy/idle decision."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _windows_idle_seconds() -> float | None:
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
        return None
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF  # type: ignore[attr-defined]
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


def _xprintidle_seconds() -> float | None:
    if not os.environ.get("DISPLAY") or not shutil.which("xprintidle"):
        return None
    try:
        out = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=2)
        if out.returncode == 0:
            return int(out.stdout.strip()) / 1000.0
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _gnome_idle_seconds() -> float | None:
    """GNOME (X11 or Wayland) exposes idle time over D-Bus."""
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not shutil.which("gdbus"):
        return None
    try:
        out = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Mutter.IdleMonitor",
                "--object-path", "/org/gnome/Mutter/IdleMonitor/Core",
                "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:  # prints "(uint64 12345,)"
            return int(out.stdout.split()[1].rstrip(",)")) / 1000.0
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return None


def _tty_idle_seconds() -> float | None:
    """Same idea as `w`: time since the most recent input on any terminal device."""
    newest = 0.0
    for pattern in ("/dev/pts/*", "/dev/tty[0-9]*"):
        for p in Path("/").glob(pattern.lstrip("/")):
            try:
                newest = max(newest, p.stat().st_atime)
            except OSError:
                continue
    if newest == 0.0:
        return None
    return max(0.0, time.time() - newest)


def user_idle_seconds() -> tuple[float | None, str]:
    """Seconds since last keyboard/mouse input, and the method used."""
    if sys.platform == "win32":
        try:
            return _windows_idle_seconds(), "GetLastInputInfo"
        except Exception:
            return None, "unavailable"
    v = _xprintidle_seconds()
    if v is not None:
        return v, "xprintidle"
    v = _gnome_idle_seconds()
    if v is not None:
        return v, "gnome"
    v = _tty_idle_seconds()
    if v is not None:
        return v, "tty"
    return None, "unavailable"


def evaluate(cfg: Any, t: dict[str, Any], own: set[int], training: bool, too_hot_latched: bool) -> dict[str, Any]:
    """Decide whether this device may train right now.

    Returns {"user_idle_s", "method", "idle", "eligible", "reasons", "too_hot"}.
    """
    reasons: list[str] = []
    idle_s, method = user_idle_seconds()
    need = cfg.idle_minutes * 60
    if idle_s is None:
        user_idle = True  # cannot tell; rely on the GPU/battery checks below
    else:
        user_idle = idle_s >= need
        if not user_idle:
            reasons.append("user active")

    gpu = t["gpu"]
    if gpu.get("available"):
        util = gpu.get("util") or 0
        others = [p for p in gpu.get("processes", []) if p["pid"] not in own and p["kind"] == "compute"]
        if others and util >= cfg.gpu_busy_util:
            reasons.append("another process is using the GPU")
        elif not training and util >= cfg.gpu_busy_util:
            reasons.append("GPU in use")

    b = t["battery"]
    if b["present"] and b["plugged"] is False and (b["percent"] or 0) < cfg.min_battery_pct:
        reasons.append(f"on battery below {cfg.min_battery_pct:.0f}%")

    temp = gpu.get("temp_c") if gpu.get("available") else t["cpu"].get("temp_c")
    too_hot = too_hot_latched
    if temp is not None:
        if temp >= cfg.max_temp_c:
            too_hot = True
        elif temp <= cfg.max_temp_c - cfg.resume_temp_margin_c:
            too_hot = False
    if too_hot:
        reasons.append("too hot")

    return {
        "user_idle_s": None if idle_s is None else round(idle_s, 1),
        "method": method,
        "idle": user_idle,
        "eligible": not reasons,
        "reasons": reasons,
        "too_hot": too_hot,
    }
