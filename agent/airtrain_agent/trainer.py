"""Local training loop for the catalog jobs, run in a background thread.

torch/torchvision are imported lazily so the rest of the agent works without the
[train] extra. Training only advances while `allow(True)` is set; the controller
flips that off the moment the user comes back, the device gets too hot, or the
app sends "pause". The check happens between batches, so it stops within a
fraction of a second.

TODO(coordinator): replace the local-only rounds with a Flower NumPyClient that
fetches global weights from the AirTrain coordinator at the start of each round
and sends the updated weights (plus sample count) back at the end, so FedAvg runs
across all devices instead of on this machine alone.
"""

from __future__ import annotations

import importlib.util
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


class TrainUnavailable(RuntimeError):
    pass


def check_available() -> None:
    missing = [m for m in ("torch", "torchvision") if importlib.util.find_spec(m) is None]
    if missing:
        raise TrainUnavailable(
            f"Training needs {' and '.join(missing)}. Install the extra:  pip install \"./agent[train]\""
        )


class Trainer:
    def __init__(
        self,
        data_dir: Path,
        rounds: int = 50,
        steps_per_round: int = 100,
        batch_size: int = 64,
        dataset: str = "cifar10",
        device: str = "auto",
        job: str = "cifar10-cnn",
        lr: float = 1e-3,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.rounds = rounds
        self.steps_per_round = steps_per_round
        self.batch_size = batch_size
        self.job = job
        self.lr = lr
        from .models import has_real_dataset

        # Jobs without a real dataset loader yet train on generated data.
        # TODO(datasets): Tiny Shakespeare for char-gpt-tiny, Imagenette for resnet18-ft.
        self.dataset = dataset if has_real_dataset(job) else "synthetic"
        self.device_pref = device
        self._allowed = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._rate: deque[tuple[float, int]] = deque(maxlen=20)
        self.p: dict[str, Any] = {
            "status": "starting",  # starting | loading | waiting | running | done | error | stopped
            "round": 0,
            "total_rounds": rounds,
            "step": 0,
            "steps_per_round": steps_per_round,
            "loss": None,
            "accuracy": None,
            "samples": 0,
            "samples_per_s": 0.0,
            "device": None,
            "job": job,
            "batch_size": batch_size,
            "dataset": self.dataset,
            "history": [],  # [{round, loss, accuracy, samples}]
            "error": None,
        }

    # ---- control ----
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="airtrain-trainer", daemon=True)
        self._thread.start()

    def allow(self, on: bool) -> None:
        if on:
            self._allowed.set()
        else:
            self._allowed.clear()

    def stop(self) -> None:
        self._stop.set()
        self._allowed.set()
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def active(self) -> bool:
        return self.p["status"] == "running"

    def progress(self) -> dict[str, Any]:
        with self._lock:
            out = dict(self.p)
            out["history"] = list(self.p["history"][-50:])
            return out

    def _set(self, **kw: Any) -> None:
        with self._lock:
            self.p.update(kw)

    # ---- work ----
    def _wait_allowed(self) -> bool:
        """Block until allowed or stopped. Returns False if stopped."""
        if not self._allowed.is_set():
            self._set(status="waiting", samples_per_s=0.0)
            self._rate.clear()
        while not self._allowed.wait(0.25):
            if self._stop.is_set():
                return False
        if self._stop.is_set():
            return False
        if self.p["status"] != "running":
            self._set(status="running")
        return True

    def _run(self) -> None:
        try:
            self._train()
        except Exception as e:  # report instead of killing the agent
            self._set(status="error", error=f"{type(e).__name__}: {e}")

    def _data(self, torch: Any, torchvision: Any) -> tuple[Any, Any]:
        from . import models

        if self.dataset == "synthetic":
            return models.synthetic_data(self.job, torch)
        return models.real_data(self.job, torch, torchvision, self.data_dir)

    def _train(self) -> None:
        check_available()
        import torch
        import torchvision
        from torch import nn

        if self.device_pref == "auto":
            dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            dev = torch.device(self.device_pref)
        name = torch.cuda.get_device_name(dev) if dev.type == "cuda" else "cpu"
        self._set(status="loading", device=f"{dev.type}:{name}" if dev.type == "cuda" else "cpu")

        train, test = self._data(torch, torchvision)
        loader = torch.utils.data.DataLoader(train, batch_size=self.batch_size, shuffle=True, drop_last=True)
        test_loader = torch.utils.data.DataLoader(test, batch_size=256)

        from .models import build_model

        model = build_model(self.job, torch).to(dev)
        # Adam, as assumed by the memory estimate in `airtrain analysis`.
        opt = torch.optim.AdamW(model.parameters(), lr=self.lr, weight_decay=1e-4)
        loss_fn = nn.CrossEntropyLoss()
        batches = iter(loader)

        for rnd in range(1, self.rounds + 1):
            # TODO(coordinator): load global weights from the coordinator here.
            model.train()
            running, seen = 0.0, 0
            for step in range(1, self.steps_per_round + 1):
                if not self._wait_allowed():
                    self._set(status="stopped")
                    return
                try:
                    x, y = next(batches)
                except StopIteration:
                    batches = iter(loader)
                    x, y = next(batches)
                x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
                opt.zero_grad(set_to_none=True)
                loss = loss_fn(*_flat(model(x), y))
                loss.backward()
                opt.step()
                running += loss.item() * len(y)
                seen += len(y)
                now = time.monotonic()
                self._rate.append((now, len(y)))
                rate = 0.0
                if len(self._rate) > 1:
                    span = now - self._rate[0][0]
                    rate = sum(n for _, n in list(self._rate)[1:]) / span if span > 0 else 0.0
                with self._lock:
                    self.p["samples"] += len(y)
                    self.p["step"] = step
                    self.p["samples_per_s"] = round(rate, 1)

            acc = self._evaluate(torch, model, test_loader, dev)
            avg = running / max(seen, 1)
            # TODO(coordinator): send model.state_dict() and `seen` to the coordinator here.
            with self._lock:
                self.p["round"] = rnd
                self.p["loss"] = round(avg, 4)
                self.p["accuracy"] = round(acc, 4)
                self.p["history"].append(
                    {"round": rnd, "loss": round(avg, 4), "accuracy": round(acc, 4), "samples": self.p["samples"]}
                )
        self._set(status="done", samples_per_s=0.0)

    @staticmethod
    def _evaluate(torch: Any, model: Any, loader: Any, dev: Any) -> float:
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in loader:
                x, y = x.to(dev), y.to(dev)
                logits, target = _flat(model(x), y)
                correct += (logits.argmax(1) == target).sum().item()
                total += target.numel()
        return correct / max(total, 1)


def _flat(logits: Any, y: Any) -> tuple[Any, Any]:
    """(batch, classes) stays as is; sequence outputs (batch, time, vocab) are flattened per token."""
    if logits.dim() == 3:
        return logits.flatten(0, 1), y.flatten()
    return logits, y
