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


# ---------------- memory ----------------

GB = 1024**3
BYTES_PER_PARAM = 4  # fp32
ADAM_STATE_PER_PARAM = 2  # exp_avg and exp_avg_sq
ACTIVATION_SAFETY = 1.25  # allocator fragmentation and temporaries
RUNTIME_OVERHEAD = {"cuda": 0.6 * GB, "cpu": 0.4 * GB}  # CUDA context + cuDNN workspace / torch runtime
MEMORY_BUDGET = 0.8  # use at most this share of free memory


@dataclass(frozen=True)
class MemoryEstimate:
    weights: float
    grads: float
    optimizer: float
    activations: float
    overhead: float

    @property
    def total(self) -> float:
        return self.weights + self.grads + self.optimizer + self.activations + self.overhead

    @property
    def total_gb(self) -> float:
        return self.total / GB


def estimate_memory(job: Job, batch: int, backend: str = "cuda") -> MemoryEstimate:
    """Training memory for one step: params + grads + Adam state + activations + runtime."""
    p = job.params * BYTES_PER_PARAM
    return MemoryEstimate(
        weights=p,
        grads=p,
        optimizer=p * ADAM_STATE_PER_PARAM,
        activations=job.act_bytes_per_sample * batch * ACTIVATION_SAFETY,
        overhead=RUNTIME_OVERHEAD.get(backend, RUNTIME_OVERHEAD["cpu"]),
    )


def min_memory_gb(job: Job, backend: str = "cuda") -> float:
    """Memory needed at the job's smallest batch size."""
    return estimate_memory(job, job.batch_sizes[0], backend).total_gb


def recommend_batch(job: Job, free_bytes: float, backend: str = "cuda") -> int | None:
    """Largest accepted batch size that fits in MEMORY_BUDGET of free memory, or None."""
    best = None
    for b in job.batch_sizes:
        if estimate_memory(job, b, backend).total <= free_bytes * MEMORY_BUDGET:
            best = b
    return best


# ---------------- throughput ----------------

# Peak fp32 TFLOPS for common NVIDIA GPUs (matched by substring, longest first).
GPU_TFLOPS = {
    "4090": 82.6, "4080": 48.7, "4070 ti": 40.1, "4070": 29.1, "4060 ti": 22.1, "4060": 15.1, "4050": 9.0,
    "3090": 35.6, "3080 ti": 34.1, "3080": 29.8, "3070 ti": 21.7, "3070": 20.3, "3060 ti": 16.2, "3060": 12.7,
    "3050": 9.1, "2080 ti": 13.4, "2080": 10.1, "2070": 7.5, "2060": 6.5, "1660": 5.0, "1650": 3.0,
    "1080": 8.9, "1070": 6.5, "a100": 19.5, "h100": 51.0, "a6000": 38.7, "a5000": 27.8, "a4000": 19.2,
    "l4": 30.3, "t4": 8.1, "v100": 15.7,
}
DEFAULT_GPU_TFLOPS = 8.0
CPU_FLOPS_PER_CYCLE = 32  # AVX2: 2 FMA units x 8 fp32 lanes x 2 ops
# Share of peak a small model actually reaches in training (kernel launch, memory bound layers, data loading).
EFFICIENCY = {"cuda": 0.30, "cpu": 0.40}
# Share of a measured matmul rate a full training step reaches.
BENCH_EFFICIENCY = 0.35


def gpu_peak_flops(name: str | None) -> float:
    n = (name or "").lower()
    for key in sorted(GPU_TFLOPS, key=len, reverse=True):
        if key in n:
            return GPU_TFLOPS[key] * 1e12
    return DEFAULT_GPU_TFLOPS * 1e12


def cpu_peak_flops(physical_cores: int, freq_mhz: float | None) -> float:
    ghz = (freq_mhz or 2500) / 1000
    return max(physical_cores, 1) * ghz * 1e9 * CPU_FLOPS_PER_CYCLE


def effective_flops(profile: dict) -> float:
    """Sustained training FLOP/s for this machine, from a benchmark if one ran, else from specs."""
    if profile.get("bench_flops"):
        return profile["bench_flops"] * BENCH_EFFICIENCY
    if profile["backend"] == "cuda":
        return gpu_peak_flops(profile.get("gpu_name")) * EFFICIENCY["cuda"]
    return cpu_peak_flops(profile.get("cpu_physical_cores", 1), profile.get("cpu_freq_mhz")) * EFFICIENCY["cpu"]


def estimate_samples_per_s(job: Job, profile: dict) -> float:
    return effective_flops(profile) / job.train_flops_per_sample


def benchmark_flops(seconds: float = 0.6) -> tuple[float | None, str | None]:
    """Measure fp32 matmul FLOP/s with torch on the training device. Returns (flops, device) or (None, None)."""
    try:
        import torch
    except ImportError:
        return None, None
    import time

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    n = 2048 if dev == "cuda" else 512
    a = torch.randn(n, n, device=dev)
    b = torch.randn(n, n, device=dev)
    (a @ b).sum().item()  # warm up
    iters, start = 0, time.perf_counter()
    while time.perf_counter() - start < seconds:
        a @ b
        iters += 1
    if dev == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    return 2 * n**3 * iters / elapsed, dev
