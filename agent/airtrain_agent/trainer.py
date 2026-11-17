"""Local training loop (CIFAR-10 CNN) that runs in a background thread.

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
    ) -> None:
        self.data_dir = Path(data_dir)
        self.rounds = rounds
        self.steps_per_round = steps_per_round
        self.batch_size = batch_size
        self.dataset = dataset
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
            "dataset": dataset,
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
        T = torchvision.transforms
        if self.dataset == "synthetic":
            g = torch.Generator().manual_seed(0)
            x = torch.randn(4096, 3, 32, 32, generator=g)
            y = torch.randint(0, 10, (4096,), generator=g)
            x += y.view(-1, 1, 1, 1).float() * 0.1  # learnable signal
            ds = torch.utils.data.TensorDataset(x, y)
            train, test = torch.utils.data.random_split(ds, [3584, 512], generator=g)
            return train, test
        norm = T.Normalize((0.4914, 0.4822, 0.4465), (0.247, 0.243, 0.261))
        train_tf = T.Compose([T.RandomCrop(32, padding=4), T.RandomHorizontalFlip(), T.ToTensor(), norm])
        test_tf = T.Compose([T.ToTensor(), norm])
        root = str(self.data_dir)
        train = torchvision.datasets.CIFAR10(root, train=True, download=True, transform=train_tf)
        test = torchvision.datasets.CIFAR10(root, train=False, download=True, transform=test_tf)
        test = torch.utils.data.Subset(test, range(2000))
        return train, test

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

        model = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(128 * 4 * 4, 256), nn.ReLU(), nn.Linear(256, 10),
        ).to(dev)
        opt = torch.optim.SGD(model.parameters(), lr=0.05, momentum=0.9, weight_decay=5e-4)
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
                loss = loss_fn(model(x), y)
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
                correct += (model(x).argmax(1) == y).sum().item()
                total += len(y)
        return correct / max(total, 1)
