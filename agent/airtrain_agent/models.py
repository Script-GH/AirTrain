"""Models and datasets for the job catalog. torch is passed in so this module imports without it."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_model(job_id: str, torch: Any) -> Any:
    nn = torch.nn
    if job_id == "cifar10-cnn":
        return nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(128 * 4 * 4, 256), nn.ReLU(), nn.Linear(256, 10),
        )
    raise KeyError(f"no model for job '{job_id}'")


def has_real_dataset(job_id: str) -> bool:
    return job_id == "cifar10-cnn"


def real_data(job_id: str, torch: Any, torchvision: Any, root: Path) -> tuple[Any, Any]:
    T = torchvision.transforms
    if job_id == "cifar10-cnn":
        norm = T.Normalize((0.4914, 0.4822, 0.4465), (0.247, 0.243, 0.261))
        train_tf = T.Compose([T.RandomCrop(32, padding=4), T.RandomHorizontalFlip(), T.ToTensor(), norm])
        test_tf = T.Compose([T.ToTensor(), norm])
        train = torchvision.datasets.CIFAR10(str(root), train=True, download=True, transform=train_tf)
        test = torchvision.datasets.CIFAR10(str(root), train=False, download=True, transform=test_tf)
        return train, torch.utils.data.Subset(test, range(2000))
    raise KeyError(f"no real dataset for job '{job_id}'")


def synthetic_data(job_id: str, torch: Any) -> tuple[Any, Any]:
    """Small generated datasets with a learnable signal, for testing without downloads."""
    g = torch.Generator().manual_seed(0)
    if job_id == "cifar10-cnn":
        x = torch.randn(4096, 3, 32, 32, generator=g)
        y = torch.randint(0, 10, (4096,), generator=g)
        x += y.view(-1, 1, 1, 1).float() * 0.1
        ds = torch.utils.data.TensorDataset(x, y)
        return tuple(torch.utils.data.random_split(ds, [3584, 512], generator=g))
    raise KeyError(f"no synthetic data for job '{job_id}'")
