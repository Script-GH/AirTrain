"""Live terminal view for `airtrain start training`."""

from __future__ import annotations

import sys
import time
from typing import Any, TextIO


def enable_ansi(stream: TextIO) -> bool:
    """True if the stream is a terminal that understands ANSI cursor codes (turns them on for Windows 10+)."""
    if not stream.isatty():
        return False
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = k32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(k32.SetConsoleMode(handle, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


def _bar(frac: float, width: int = 24) -> str:
    n = int(round(max(0.0, min(frac, 1.0)) * width))
    return "[" + "#" * n + "." * (width - n) + "]"


def _num(v: Any, fmt: str, missing: str = "n/a") -> str:
    return missing if v is None else fmt.format(v)


def render(snap: dict[str, Any], apps: int) -> list[str]:
    p = snap.get("train") or {}
    g, c = snap["gpu"], snap["cpu"]
    total = max(p.get("total_rounds") or 1, 1)
    rnd = p.get("round", 0)
    in_round = (p.get("step", 0) / max(p.get("steps_per_round") or 1, 1)) if p.get("status") == "running" else 0
    hist = p.get("history") or []
    best = max((h["accuracy"] for h in hist), default=None)
    acc = p.get("accuracy")

    if g.get("available"):
        hw = (f"GPU     {_num(g.get('util'), '{:.0f}%')} util  {_num(g.get('temp_c'), '{:.0f} C')}"
              f"  {_num(g.get('power_w'), '{:.0f} W')}  VRAM {_num(g.get('vram_used_gb'), '{:.1f}')}/"
              f"{_num(g.get('vram_total_gb'), '{:.0f}')} GB" + ("  THROTTLED" if g.get("throttled") else ""))
    else:
        hw = f"CPU     {_num(c.get('util'), '{:.0f}%')} util  {_num(c.get('temp_c'), '{:.0f} C', 'temp n/a')}  (no GPU)"

    status = p.get("status", "?")
    if snap.get("paused"):
        state = "paused from the phone app"
    elif snap.get("blockers"):
        state = "waiting: " + ", ".join(snap["blockers"])
    else:
        state = {"running": "training", "loading": "loading data", "starting": "starting"}.get(status, status)

    job = (snap.get("job") or {}).get("name", p.get("job", ""))
    cl = snap.get("cluster") or {}
    return [
        f"{job} @ {cl.get('name', 'local')} ({cl.get('region', '-')}, {_num(cl.get('latency_ms'), '{:.0f} ms')})",
        f"Round   {rnd}/{total}  {_bar((rnd + in_round) / total)} {100 * (rnd + in_round) / total:4.0f}%"
        f"   step {p.get('step', 0)}/{p.get('steps_per_round', 0)}",
        f"Loss    {_num(p.get('loss'), '{:.3f}'):<8} Accuracy {_num(acc and acc * 100, '{:.1f}%'):<7}"
        f" best {_num(best and best * 100, '{:.1f}%')}",
        f"Speed   {p.get('samples_per_s', 0):,.0f} samples/s   {p.get('samples', 0):,} samples total"
        f"   {p.get('device') or ''}",
        hw,
        f"State   {state}",
        f"Phone   {apps} app{'s' if apps != 1 else ''} connected",
    ]


class ProgressView:
    """Redraws a block in place on terminals; prints a line per round (or every 10 s) otherwise."""

    def __init__(self, stream: TextIO = sys.stdout, live: bool | None = None) -> None:
        self.stream = stream
        self.live = enable_ansi(stream) if live is None else live
        self._lines = 0
        self._last_key: tuple | None = None
        self._last_print = 0.0

    def update(self, snap: dict[str, Any], apps: int) -> None:
        lines = render(snap, apps)
        if self.live:
            if self._lines:
                self.stream.write(f"\x1b[{self._lines}F\x1b[J")
            self.stream.write("\n".join(lines) + "\n")
            self._lines = len(lines)
        else:
            p = snap.get("train") or {}
            key = (p.get("round"), p.get("status"), tuple(snap.get("blockers") or ()), snap.get("paused"))
            if key != self._last_key or time.monotonic() - self._last_print >= 10:
                self.stream.write(" | ".join(x.strip() for x in lines[1:6]) + "\n")
                self._last_key, self._last_print = key, time.monotonic()
        self.stream.flush()
