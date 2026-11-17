"""User idle detection."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


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
