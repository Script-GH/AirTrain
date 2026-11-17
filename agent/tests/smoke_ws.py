"""Smoke test: start `airtrain serve`, connect like the app, check telemetry and pause/resume.

Usage:  python tests/smoke_ws.py            (uses the installed `airtrain` command)
Exits non-zero on failure. Runs against a throwaway config dir.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile

import websockets

PORT = int(os.environ.get("SMOKE_PORT", "18765"))
TOKEN = "smoke-token"
REQUIRED = {"type", "v", "ts", "device", "gpu", "cpu", "ram", "battery", "idle", "state", "paused"}


async def wait_listening(timeout: float = 20) -> None:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while True:
        try:
            _, w = await asyncio.open_connection("127.0.0.1", PORT)
            w.close()
            return
        except OSError:
            if loop.time() > end:
                raise
            await asyncio.sleep(0.3)


async def check() -> None:
    url = f"ws://127.0.0.1:{PORT}/?token={TOKEN}"
    await wait_listening()

    # Wrong token must be refused.
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/?token=wrong"):
            raise AssertionError("connection with a bad token was accepted")
    except websockets.InvalidStatus as e:
        assert e.response.status_code == 401, e.response.status_code
        print("ok  bad token rejected (401)")

    async with websockets.connect(url) as ws:
        hello = json.loads(await ws.recv())
        assert hello["type"] == "hello", hello
        print(f"ok  hello from device {hello['device_id']}")

        snaps = []
        while len(snaps) < 3:
            m = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if m["type"] == "telemetry":
                missing = REQUIRED - m.keys()
                assert not missing, f"missing keys {missing}"
                snaps.append(m)
                train = m.get("train") or {}
                print(f"ok  telemetry: state={m['state']} cpu={m['cpu']['util']}% "
                      f"ram={m['ram']['used_gb']}/{m['ram']['total_gb']}GB gpu={m['gpu'].get('name')}"
                      + (f" train={train.get('status')} round={train.get('round')} "
                         f"{train.get('samples_per_s')} samples/s" if train else ""))

        for cmd, expect in (("pause", True), ("resume", False)):
            await ws.send(json.dumps({"cmd": cmd}))
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if m["type"] == "ack":
                    assert m["ok"] and m["cmd"] == cmd and m["paused"] is expect, m
                if m["type"] == "telemetry" and m["paused"] is expect:
                    print(f"ok  {cmd}: telemetry paused={m['paused']}")
                    break
            if cmd == "pause" and m.get("train"):
                # Training must stop: sample count frozen over the next snapshots.
                await asyncio.sleep(1.5)
                counts = []
                while len(counts) < 2:
                    t = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if t["type"] == "telemetry":
                        counts.append(t["train"]["samples"])
                        assert t["train"]["status"] == "waiting", t["train"]["status"]
                assert counts[0] == counts[1], counts
                print(f"ok  training halted while paused (samples stay at {counts[0]})")

        await ws.send(json.dumps({"cmd": "explode"}))
        m = json.loads(await asyncio.wait_for(ws.recv(), 5))
        while m["type"] != "ack":
            m = json.loads(await asyncio.wait_for(ws.recv(), 5))
        assert m["ok"] is False
        print("ok  unknown command rejected")


def main() -> int:
    exe = shutil.which("airtrain") or os.path.join(os.path.dirname(sys.executable), "airtrain")
    home = tempfile.mkdtemp(prefix="airtrain-smoke-")
    env = {**os.environ, "AIRTRAIN_HOME": home}
    extra = sys.argv[1:]
    proc = subprocess.Popen(
        [exe, "serve", "--host", "127.0.0.1", "--port", str(PORT), "--token", TOKEN, *extra],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        for _ in range(50):
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                print("    " + line.rstrip())
            if "Ctrl+C" in line or proc.poll() is not None:
                break
        asyncio.run(asyncio.wait_for(check(), 45))
        print("PASS")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
