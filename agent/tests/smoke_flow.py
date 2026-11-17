"""Smoke test of the three-step flow with the installed `airtrain` command.

    python tests/smoke_flow.py [--job cifar10-cnn] [--rounds 3]

Runs `analysis --job`, `connect` and `start training` (synthetic data, a few rounds) against a
throwaway config dir, prints each command's output, and while training runs it connects like the
phone app to check that telemetry carries the job and cluster. Needs the [train] extra.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import websockets

PORT = int(os.environ.get("SMOKE_PORT", "18780"))
TOKEN = "smoke-flow"


def run(exe: str, args: list[str], env: dict[str, str]) -> str:
    print(f"$ airtrain {' '.join(args)}", flush=True)
    r = subprocess.run([exe, *args], env=env, capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    print(out, flush=True)
    if r.returncode != 0:
        raise SystemExit(f"FAIL: `airtrain {' '.join(args)}` exited {r.returncode}")
    return out


async def watch_telemetry(expect_job: str, expect_cluster: str) -> dict:
    url = f"ws://127.0.0.1:{PORT}/?token={TOKEN}"
    for _ in range(100):
        try:
            async with websockets.connect(url) as ws:
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if m["type"] == "telemetry" and (m.get("train") or {}).get("status") == "running":
                        assert m["job"]["name"] == expect_job, m["job"]
                        assert m["cluster"]["name"] == expect_cluster, m["cluster"]
                        return m
        except OSError:
            await asyncio.sleep(0.2)
    raise AssertionError("never received running telemetry")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default="cifar10-cnn")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--steps", type=int, default=20)
    opts = ap.parse_args()

    exe = shutil.which("airtrain") or os.path.join(os.path.dirname(sys.executable), "airtrain")
    home = tempfile.mkdtemp(prefix="airtrain-flow-")
    env = {**os.environ, "AIRTRAIN_HOME": home}
    try:
        out = run(exe, ["analysis", "--job", opts.job], env)
        assert "Saved. Next step: airtrain connect" in out
        job_name = out.split("Selected ", 1)[1].split(" (", 1)[0]

        out = run(exe, ["connect"], env)
        connected = [ln for ln in out.splitlines() if ln.startswith("Connected to ")]
        assert connected, "no 'Connected to' line"
        cluster_name = connected[0][len("Connected to "):].split(" (", 1)[0]

        result: dict = {}

        def watcher() -> None:
            try:
                result["snap"] = asyncio.run(watch_telemetry(job_name, cluster_name))
            except Exception as e:  # reported below
                result["error"] = e

        t = threading.Thread(target=watcher, daemon=True)
        t.start()
        out = run(exe, ["start", "training", "--dataset", "synthetic", "--rounds", str(opts.rounds),
                        "--steps", str(opts.steps), "--no-idle-check", "--host", "127.0.0.1",
                        "--port", str(PORT), "--token", TOKEN], env)
        t.join(5)
        assert f"Finished {opts.rounds} rounds" in out, "training did not finish"
        if "error" in result:
            raise result["error"]
        snap = result["snap"]
        print(f"ok  phone telemetry during training: job={snap['job']['name']!r} "
              f"cluster={snap['cluster']['name']!r} round={snap['train']['round']} "
              f"{snap['train']['samples_per_s']} samples/s")
        print("PASS")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
