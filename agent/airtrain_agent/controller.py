"""Ties telemetry, idle detection and the trainer together."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from .config import Config, config_dir
from .idle import evaluate
from .telemetry import Sampler, own_pids

SCHEMA_VERSION = 1


class Controller:
    def __init__(
        self,
        cfg: Config,
        train: bool = False,
        rounds: int = 50,
        dataset: str = "cifar10",
        require_idle: bool = True,
        steps_per_round: int = 100,
    ) -> None:
        self.cfg = cfg
        self.sampler = Sampler(cfg.gpu_index)
        self.paused = False
        self.require_idle = require_idle
        self._too_hot = False
        self.started = time.time()
        self.trainer = None
        if train:
            from .trainer import Trainer, check_available

            check_available()
            self.trainer = Trainer(
                config_dir() / "data", rounds=rounds, dataset=dataset, steps_per_round=steps_per_round
            )

    def start(self) -> None:
        if self.trainer:
            self.trainer.start()

    def stop(self) -> None:
        if self.trainer:
            self.trainer.stop()
        self.sampler.close()

    def command(self, cmd: str) -> dict[str, Any]:
        if cmd == "pause":
            self.paused = True
            if self.trainer:
                self.trainer.allow(False)
        elif cmd == "resume":
            self.paused = False
        elif cmd not in ("ping", "snapshot"):
            return {"ok": False, "error": f"unknown command '{cmd}'"}
        return {"ok": True, "paused": self.paused}

    def snapshot(self) -> dict[str, Any]:
        t = self.sampler.sample()
        training = bool(self.trainer and self.trainer.active)
        idle = evaluate(self.cfg, t, own_pids(), training, self._too_hot)
        self._too_hot = idle["too_hot"]

        blockers = idle["reasons"] if self.require_idle else (["too hot"] if idle["too_hot"] else [])
        may_train = not self.paused and not blockers
        if self.trainer:
            self.trainer.allow(may_train)
            training = may_train and self.trainer.p["status"] in ("running", "waiting", "loading")

        if training:
            state = "training"
        elif blockers:
            state = "busy"
        else:
            state = "idle"

        t["device"].update(
            id=self.cfg.device_id,
            name=self.cfg.name or t["device"]["hostname"],
        )
        return {
            "type": "telemetry",
            "v": SCHEMA_VERSION,
            **t,
            "idle": {k: v for k, v in idle.items() if k != "too_hot"},
            "blockers": blockers,
            "state": state,
            "paused": self.paused,
            "uptime_s": round(time.time() - self.started),
            "limits": {
                "max_temp_c": self.cfg.max_temp_c,
                "idle_minutes": self.cfg.idle_minutes,
                "min_battery_pct": self.cfg.min_battery_pct,
            },
            "train": self.trainer.progress() if self.trainer else None,
        }

    async def run(self, on_snapshot: Callable[[dict[str, Any]], Awaitable[None] | None], interval: float = 1.0) -> None:
        loop = asyncio.get_running_loop()
        while True:
            snap = await loop.run_in_executor(None, self.snapshot)
            r = on_snapshot(snap)
            if asyncio.iscoroutine(r):
                await r
            await asyncio.sleep(interval)
