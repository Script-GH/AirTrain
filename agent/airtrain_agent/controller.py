"""Ties telemetry, idle detection and the trainer together."""

from __future__ import annotations

import asyncio
import threading
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
        job: str = "cifar10-cnn",
        batch_size: int = 64,
        geo: bool = True,
    ) -> None:
        self.cfg = cfg
        self.sampler = Sampler(cfg.gpu_index)
        self.paused = False
        self.require_idle = require_idle
        self._too_hot = False
        self.started = time.time()
        # Location is resolved in the background so a slow or blocked lookup never delays startup.
        self.location: dict[str, Any] | None = None
        self._geo = threading.Thread(target=self._resolve_location, args=(geo,), name="airtrain-geo", daemon=True)
        self._geo.start()
        self.trainer = None
        if train:
            from .trainer import Trainer, check_available

            check_available()
            self.trainer = Trainer(
                config_dir() / "data",
                rounds=rounds,
                dataset=dataset,
                steps_per_round=steps_per_round,
                job=job,
                batch_size=batch_size,
            )

    def _resolve_location(self, allow_lookup: bool) -> None:
        from .geo import resolve_location

        self.location = resolve_location(self.cfg, allow_lookup=allow_lookup)

    def wait_for_location(self, timeout: float = 5.0) -> dict[str, Any] | None:
        self._geo.join(timeout)
        return self.location

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
            "location": self.location,
            "limits": {
                "max_temp_c": self.cfg.max_temp_c,
                "idle_minutes": self.cfg.idle_minutes,
                "min_battery_pct": self.cfg.min_battery_pct,
            },
            "job": self._job_info(),
            "cluster": self._cluster_info(),
            "train": self.trainer.progress() if self.trainer else None,
        }

    def _job_info(self) -> dict[str, Any] | None:
        if not self.cfg.job:
            return None
        from .jobs import get_job

        try:
            name = get_job(self.cfg.job).name
        except KeyError:
            name = self.cfg.job
        return {"id": self.cfg.job, "name": name, "batch_size": self.cfg.batch_size or None}

    def _cluster_info(self) -> dict[str, Any] | None:
        s = self.cfg.session
        if not s:
            return None
        from .coordinator import region_coords

        lat, lon = region_coords(s.get("region"))
        return {
            "id": s.get("cluster_id"),
            "name": s.get("cluster_name"),
            "region": s.get("region"),
            "city": s.get("city"),
            "devices": s.get("devices"),
            "latency_ms": s.get("latency_ms"),
            "coordinator": s.get("coordinator"),
            "lat": s.get("lat", lat),
            "lon": s.get("lon", lon),
        }

    async def run(self, on_snapshot: Callable[[dict[str, Any]], Awaitable[None] | None], interval: float = 1.0) -> None:
        loop = asyncio.get_running_loop()
        while True:
            snap = await loop.run_in_executor(None, self.snapshot)
            r = on_snapshot(snap)
            if asyncio.iscoroutine(r):
                await r
            await asyncio.sleep(interval)
