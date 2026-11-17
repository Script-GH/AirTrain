"""`airtrain` command line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
import time
from typing import Any

from . import __version__
from .config import config_dir, load_config, new_token


def lan_ip() -> str:
    """Best guess at this machine's LAN address (no packets are sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _fmt(v: Any, unit: str = "", nd: int = 0) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        v = f"{v:.{nd}f}"
    return f"{v}{unit}"


def print_status(s: dict[str, Any]) -> None:
    d, g, c, r, b, i = s["device"], s["gpu"], s["cpu"], s["ram"], s["battery"], s["idle"]
    rows: list[tuple[str, str]] = [
        ("Device", f"{d['name']} ({d['kind']})"),
        ("OS", d["os"]),
    ]
    if g.get("available"):
        rows += [
            ("GPU", f"{g['name']}  (driver {_fmt(g.get('driver'))})"),
            ("GPU util", _fmt(g.get("util"), "%")),
            ("VRAM", f"{_fmt(g.get('vram_used_gb'), nd=1)} / {_fmt(g.get('vram_total_gb'), ' GB', 1)}"),
            ("GPU temp", f"{_fmt(g.get('temp_c'), ' C')}  (slowdown {_fmt(g.get('temp_limit_c'), ' C')}, "
                         f"shutdown {_fmt(g.get('temp_shutdown_c'), ' C')})"),
            ("Power", f"{_fmt(g.get('power_w'), ' W', 1)} / limit {_fmt(g.get('power_limit_w'), ' W', 0)}"),
            ("Fan", _fmt(g.get("fan_pct"), "%")),
            ("Clock", f"{_fmt(g.get('clock_mhz'), ' MHz')} / max {_fmt(g.get('clock_max_mhz'), ' MHz')}"),
            ("Throttle", ", ".join(g.get("throttle_reasons") or []) or "none"),
        ]
    else:
        rows.append(("GPU", f"none detected ({g.get('reason')}); CPU only"))
    rows += [
        ("CPU", f"{c['name']}  ({c['cores']} threads)"),
        ("CPU util", _fmt(c.get("util"), "%", 1)),
        ("CPU temp", _fmt(c.get("temp_c"), " C", 0)),
        ("RAM", f"{_fmt(r['used_gb'], nd=1)} / {_fmt(r['total_gb'], ' GB', 1)}"),
        ("Battery", "none" if not b["present"] else f"{_fmt(b['percent'], '%')} ({'plugged in' if b['plugged'] else 'on battery'})"),
        ("User idle", f"{_fmt(i['user_idle_s'], ' s')} via {i['method']}"),
        ("State", s["state"] + (f"  ({', '.join(s['blockers'])})" if s["blockers"] else "")),
    ]
    w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k.ljust(w)}  {v}")


# ---------------- commands ----------------

def cmd_status(args: argparse.Namespace) -> int:
    from .controller import Controller

    cfg, _ = load_config()
    ctrl = Controller(cfg)
    try:
        time.sleep(0.5)  # let the CPU counter collect a sample
        snap = ctrl.snapshot()
    finally:
        ctrl.stop()
    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        print(f"AirTrain agent {__version__}")
        print_status(snap)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .controller import Controller
    from .server import run_server

    cfg, created = load_config()
    ctrl = Controller(cfg)
    token = args.token or cfg.token
    port = args.port or cfg.port
    ip = lan_ip() if args.host in ("0.0.0.0", "") else args.host
    url = f"ws://{ip}:{port}/?token={token}"
    if created:
        print(f"First run: created config in {config_dir()}")
    print(f"AirTrain agent {__version__} on {cfg.name or socket.gethostname()}")
    print(f"  GPU      {ctrl.sampler.gpu().get('name') or 'none (CPU only)'}")
    print(f"  Listen   {args.host}:{port}")
    print(f"  LAN IP   {ip}")
    print(f"  Token    {token}")
    print(f"  App URL  {url}")
    print("In the app: Overview > + > paste the URL (or host:port and token). Ctrl+C to stop.", flush=True)
    try:
        asyncio.run(run_server(ctrl, args.host, port, token, quiet=args.quiet))
    except KeyboardInterrupt:
        pass
    except OSError as e:
        print(f"error: could not listen on {args.host}:{port}: {e}", file=sys.stderr)
        return 1
    finally:
        ctrl.stop()
    return 0


def cmd_token(args: argparse.Namespace) -> int:
    cfg, _ = load_config()
    if args.reset:
        cfg.token = new_token()
        cfg.save()
        print("New token generated. Re-pair the app.")
    print(cfg.token)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airtrain", description="AirTrain device agent")
    p.add_argument("--version", action="version", version=f"airtrain {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="print a one-shot hardware and idle snapshot")
    s.add_argument("--json", action="store_true", help="print the raw telemetry JSON")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("serve", help="stream telemetry to the phone app over WebSocket")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=0, help="default from config (8765)")
    s.add_argument("--token", help="override the pairing token for this run")
    s.add_argument("--quiet", action="store_true", help="do not log connections")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("token", help="show the pairing token")
    s.add_argument("--reset", action="store_true", help="generate a new token")
    s.set_defaults(func=cmd_token)
    return p


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "darwin":
        print("AirTrain agent supports Windows and Linux for now. macOS support is coming later.", file=sys.stderr)
        return 1
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
