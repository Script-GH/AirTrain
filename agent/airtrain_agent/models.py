"""Models and datasets for the job catalog. torch is passed in so this module imports without it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

VOCAB = 96  # printable ASCII
CONTEXT = 128
IMAGE = 128  # resnet18-ft input size


def _tiny_gpt(torch: Any) -> Any:
    nn = torch.nn

    class TinyGPT(nn.Module):
        """Decoder-only transformer: 4 layers, d=256, 4 heads, context 128, character vocabulary."""

        def __init__(self, layers: int = 4, d: int = 256, heads: int = 4) -> None:
            super().__init__()
            self.tok = nn.Embedding(VOCAB, d)
            self.pos = nn.Embedding(CONTEXT, d)
            block = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
            self.blocks = nn.TransformerEncoder(block, layers, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(d)
            self.head = nn.Linear(d, VOCAB)

        def forward(self, x: Any) -> Any:
            t = x.shape[1]
            h = self.tok(x) + self.pos(torch.arange(t, device=x.device))
            mask = nn.Transformer.generate_square_subsequent_mask(t, device=x.device)
            return self.head(self.norm(self.blocks(h, mask=mask, is_causal=True)))

    return TinyGPT()


def build_model(job_id: str, torch: Any) -> Any:
    nn = torch.nn
    if job_id == "cifar10-cnn":
        return nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(128 * 4 * 4, 256), nn.ReLU(), nn.Linear(256, 10),
        )
    if job_id == "char-gpt-tiny":
        return _tiny_gpt(torch)
    if job_id == "resnet18-ft":
        import torchvision

        # TODO(datasets): start from ImageNet weights (weights="IMAGENET1K_V1") once Imagenette is wired in;
        # without real images there is nothing to fine-tune from, so it starts from scratch for now.
        return torchvision.models.resnet18(weights=None, num_classes=10)
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
    if job_id == "char-gpt-tiny":
        # A text made of a small set of repeating "words", so next-character prediction is learnable.
        import random

        rng = random.Random(0)
        letters = [chr(c) for c in range(97, 123)]
        words = ["".join(rng.choices(letters, k=rng.randint(3, 7))) for _ in range(60)]
        text = " ".join(rng.choices(words, k=40_000))
        ids = torch.tensor([ord(ch) - 32 for ch in text], dtype=torch.long)
        starts = torch.randint(0, len(ids) - CONTEXT - 1, (4608,), generator=g)
        windows = torch.stack([ids[s : s + CONTEXT + 1] for s in starts.tolist()])
        ds = torch.utils.data.TensorDataset(windows[:, :-1], windows[:, 1:])
        return tuple(torch.utils.data.random_split(ds, [4096, 512], generator=g))
    if job_id == "resnet18-ft":
        return _SyntheticImages(torch, 2048, 0), _SyntheticImages(torch, 256, 10_000)
    raise KeyError(f"no synthetic data for job '{job_id}'")


def _SyntheticImages(torch: Any, n: int, offset: int) -> Any:
    """Images generated on the fly (no large tensors in RAM): noise plus a fixed low-frequency pattern per class."""
    g = torch.Generator().manual_seed(1)
    patterns = torch.nn.functional.interpolate(torch.randn(10, 3, 8, 8, generator=g), size=IMAGE, mode="bilinear")

    class Images(torch.utils.data.Dataset):
        def __len__(self) -> int:
            return n

        def __getitem__(self, i: int) -> tuple[Any, int]:
            y = i % 10
            noise = torch.randn(3, IMAGE, IMAGE, generator=torch.Generator().manual_seed(offset + i))
            return patterns[y] + noise, y

    return Images()
