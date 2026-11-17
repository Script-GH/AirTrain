"""Unit checks that run without a GPU: python -m unittest discover -s tests"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from airtrain_agent import idle, telemetry
from airtrain_agent.config import Config, load_config


def fake_pynvml(fail_fan: bool = True) -> types.ModuleType:
    m = types.ModuleType("pynvml")
    gb = 1024**3
    m.NVML_TEMPERATURE_GPU = 0
    m.NVML_TEMPERATURE_THRESHOLD_SHUTDOWN = 0
    m.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN = 1
    m.NVML_CLOCK_GRAPHICS = 0
    m.nvmlInit = lambda: None
    m.nvmlShutdown = lambda: None
    m.nvmlDeviceGetCount = lambda: 1
    m.nvmlDeviceGetHandleByIndex = lambda i: "h"
    m.nvmlDeviceGetName = lambda h: b"NVIDIA GeForce RTX 3060"
    m.nvmlSystemGetDriverVersion = lambda: "555.42"
    m.nvmlDeviceGetTemperatureThreshold = lambda h, k: {1: 93, 0: 98}[k]
    m.nvmlDeviceGetMemoryInfo = lambda h: NS(total=12 * gb, used=3 * gb)
    m.nvmlDeviceGetMaxClockInfo = lambda h, k: 2100
    m.nvmlDeviceGetUtilizationRates = lambda h: NS(gpu=97, memory=40)
    m.nvmlDeviceGetTemperature = lambda h, k: 71
    m.nvmlDeviceGetPowerUsage = lambda h: 151_500
    m.nvmlDeviceGetEnforcedPowerLimit = lambda h: 170_000

    def fan(h):
        if fail_fan:
            raise RuntimeError("Not Supported")  # laptops
        return 55

    m.nvmlDeviceGetFanSpeed = fan
    m.nvmlDeviceGetClockInfo = lambda h, k: 1890
    m.nvmlDeviceGetCurrentClocksThrottleReasons = lambda h: 0x4 | 0x20
    m.nvmlDeviceGetComputeRunningProcesses = lambda h: [NS(pid=4242, usedGpuMemory=2 * gb)]
    m.nvmlDeviceGetGraphicsRunningProcesses = lambda h: []
    return m


class GpuProbe(unittest.TestCase):
    def test_nvml_mapping(self):
        with mock.patch.dict(sys.modules, {"pynvml": fake_pynvml()}):
            g = telemetry.Sampler().gpu()
        self.assertTrue(g["available"])
        self.assertEqual(g["name"], "NVIDIA GeForce RTX 3060")
        self.assertEqual(g["util"], 97)
        self.assertEqual((g["vram_used_gb"], g["vram_total_gb"]), (3.0, 12.0))
        self.assertEqual((g["temp_c"], g["temp_limit_c"]), (71, 93))
        self.assertEqual((g["power_w"], g["power_limit_w"]), (151.5, 170.0))
        self.assertIsNone(g["fan_pct"])  # unsupported sensor -> None, no crash
        self.assertEqual(g["throttle_reasons"], ["sw_power_cap", "sw_thermal"])
        self.assertTrue(g["throttled"])
        self.assertEqual(g["processes"][0]["pid"], 4242)

    def test_no_nvml(self):
        broken = types.ModuleType("pynvml")

        def boom():
            raise RuntimeError("NVML Shared Library Not Found")

        broken.nvmlInit = boom
        with mock.patch.dict(sys.modules, {"pynvml": broken}):
            s = telemetry.Sampler()
            snap = s.sample()
        self.assertFalse(snap["gpu"]["available"])
        self.assertIn("NVML", snap["gpu"]["reason"])
        self.assertGreater(snap["ram"]["total_gb"], 0)


def snap(util=0.0, temp=50, procs=(), battery=None):
    return {
        "gpu": {"available": True, "util": util, "temp_c": temp, "processes": list(procs)},
        "cpu": {"temp_c": None},
        "battery": battery or {"present": False, "percent": None, "plugged": None},
    }


class IdleRules(unittest.TestCase):
    cfg = Config(idle_minutes=5, max_temp_c=83, min_battery_pct=50, gpu_busy_util=30)

    def run_eval(self, idle_s, t, training=False, hot=False):
        with mock.patch.object(idle, "user_idle_seconds", return_value=(idle_s, "test")):
            return idle.evaluate(self.cfg, t, {1}, training, hot)

    def test_idle_and_cool_is_eligible(self):
        self.assertTrue(self.run_eval(600, snap())["eligible"])

    def test_user_active(self):
        r = self.run_eval(3, snap())
        self.assertFalse(r["eligible"])
        self.assertIn("user active", r["reasons"])

    def test_unknown_idle_falls_back_to_gpu(self):
        self.assertTrue(self.run_eval(None, snap())["eligible"])
        self.assertIn("GPU in use", self.run_eval(None, snap(util=80))["reasons"])

    def test_other_gpu_process(self):
        procs = [{"pid": 99, "kind": "compute"}]
        r = self.run_eval(600, snap(util=90, procs=procs), training=True)
        self.assertIn("another process is using the GPU", r["reasons"])
        # our own process at high util while training is fine
        own = [{"pid": 1, "kind": "compute"}]
        self.assertTrue(self.run_eval(600, snap(util=90, procs=own), training=True)["eligible"])

    def test_battery(self):
        low = {"present": True, "percent": 30, "plugged": False}
        self.assertFalse(self.run_eval(600, snap(battery=low))["eligible"])
        charging = {"present": True, "percent": 30, "plugged": True}
        self.assertTrue(self.run_eval(600, snap(battery=charging))["eligible"])

    def test_temperature_hysteresis(self):
        r = self.run_eval(600, snap(temp=84))
        self.assertTrue(r["too_hot"])
        self.assertTrue(self.run_eval(600, snap(temp=80), hot=True)["too_hot"])  # still latched
        self.assertFalse(self.run_eval(600, snap(temp=77), hot=True)["too_hot"])


class ConfigFile(unittest.TestCase):
    def test_first_run_creates_token(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"AIRTRAIN_HOME": d}):
            cfg, created = load_config()
            self.assertTrue(created)
            self.assertTrue(cfg.token)
            again, created2 = load_config()
            self.assertFalse(created2)
            self.assertEqual(again.token, cfg.token)


if __name__ == "__main__":
    unittest.main()
