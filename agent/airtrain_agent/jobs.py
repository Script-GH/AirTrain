"""Catalog of training jobs a device can join, with the numbers needed to size them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    task: str
    dataset: str
    dataset_gb: float  # disk needed for the dataset (download + extracted)
    params: int  # trainable parameters
    act_bytes_per_sample: float  # fp32 activations kept for the backward pass, per sample
    train_flops_per_sample: float  # forward + backward FLOPs per sample
    batch_sizes: tuple[int, ...]  # batch sizes the job accepts, smallest first
    min_samples_per_s: float  # below this a device would drag the cluster down


CATALOG: tuple[Job, ...] = (
    Job(
        id="cifar10-cnn",
        name="CIFAR-10 CNN",
        task="image classification, 3 conv + 2 fc layers, 32x32 input",
        dataset="CIFAR-10",
        dataset_gb=0.4,
        params=620_362,
        # conv/relu/pool outputs: 2*32*32*32 + 32*16*16 + 2*64*16*16 + 64*8*8 + 2*128*8*8 + ... = 132,608 floats
        act_bytes_per_sample=132_608 * 4,
        # forward ~21.6 MFLOPs; backward ~2x forward
        train_flops_per_sample=65e6,
        batch_sizes=(16, 32, 64, 128, 256, 512),
        min_samples_per_s=200,
    ),
    Job(
        id="char-gpt-tiny",
        name="Tiny char-level GPT",
        task="next-character prediction, 4 layers, d=256, 4 heads, context 128",
        dataset="Tiny Shakespeare",
        dataset_gb=0.01,
        params=3_241_568,
        # per layer: s*h*(34 + 5*a*s/h) values at 2 bytes each -> doubled for fp32: 128*256*44*4 bytes, x4 layers, + logits
        act_bytes_per_sample=4 * 128 * 256 * 44 * 2 + 128 * 96 * 8,
        # 6 * params * tokens + attention (12 * layers * ctx^2 * d)
        train_flops_per_sample=6 * 3_241_568 * 128 + 12 * 4 * 128 * 128 * 256,
        batch_sizes=(4, 8, 16, 32, 64, 128),
        min_samples_per_s=20,
    ),
    Job(
        id="resnet18-ft",
        name="ResNet-18 fine-tune",
        task="fine-tune ResNet-18 on 10 classes, 128x128 input",
        dataset="Imagenette (160 px)",
        dataset_gb=0.5,
        params=11_181_642,
        # ~60 MB per sample at 224 px, scaled by (128/224)^2
        act_bytes_per_sample=60e6 * (128 / 224) ** 2,
        # forward 1.82 GFLOPs at 224 px, scaled to 128 px, x3 for training
        train_flops_per_sample=3 * 1.82e9 * (128 / 224) ** 2,
        batch_sizes=(4, 8, 16, 32, 64, 128),
        min_samples_per_s=30,
    ),
)


def get_job(job_id: str) -> Job:
    for j in CATALOG:
        if j.id == job_id:
            return j
    raise KeyError(f"unknown job '{job_id}'. Choose one of: {', '.join(j.id for j in CATALOG)}")
