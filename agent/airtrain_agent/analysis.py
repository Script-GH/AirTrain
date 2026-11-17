"""Match the job catalog against a machine profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .jobs import CATALOG, GB, MEMORY_BUDGET, Job, estimate_memory, estimate_samples_per_s, min_memory_gb, recommend_batch
from .profile import free_memory_bytes

DISK_MARGIN_GB = 0.5  # checkpoints and logs on top of the dataset
HOT_HEADROOM_C = 10  # below this thermal headroom, expect clocks to drop
HOT_SLOWDOWN = 0.85


@dataclass
class JobFit:
    job: Job
    batch: int | None  # recommended batch size, None if nothing fits
    mem_gb: float  # estimated memory at the recommended (or smallest) batch
    min_mem_gb: float
    free_gb: float
    samples_per_s: float
    status: str  # "ok" | "slow" | "no"
    notes: list[str] = field(default_factory=list)

    @property
    def can_run(self) -> bool:
        return self.status != "no"


def analyze(profile: dict[str, Any]) -> list[JobFit]:
    backend = profile["backend"]
    free = free_memory_bytes(profile)
    fits = []
    for job in CATALOG:
        notes: list[str] = []
        batch = recommend_batch(job, free, backend)
        mem = estimate_memory(job, batch or job.batch_sizes[0], backend).total_gb
        sps = estimate_samples_per_s(job, profile)
        headroom = profile.get("thermal_headroom_c")
        if headroom is not None and headroom < HOT_HEADROOM_C:
            sps *= HOT_SLOWDOWN
            notes.append(f"only {headroom:.0f} C thermal headroom")

        status = "ok"
        if batch is None:
            status = "no"
            where = "VRAM" if backend == "cuda" else "RAM"
            usable = free * MEMORY_BUDGET / GB
            notes.insert(0, f"needs {min_memory_gb(job, backend):.2f} GB {where}, {usable:.2f} GB usable")
        if profile.get("disk_free_gb") is not None and profile["disk_free_gb"] < job.dataset_gb + DISK_MARGIN_GB:
            status = "no"
            notes.insert(0, f"needs {job.dataset_gb + DISK_MARGIN_GB:.1f} GB disk")
        if status == "ok" and sps < job.min_samples_per_s:
            status = "slow"
            notes.append(f"below {job.min_samples_per_s:.0f} samples/s, would slow the cluster")
        fits.append(
            JobFit(
                job=job,
                batch=batch,
                mem_gb=round(mem, 2),
                min_mem_gb=round(min_memory_gb(job, backend), 2),
                free_gb=round(free / GB, 1),
                samples_per_s=round(sps, 1),
                status=status,
                notes=notes,
            )
        )
    return fits


def recommended(fits: list[JobFit]) -> JobFit | None:
    """The heaviest job this machine runs at full speed; else the fastest runnable one."""
    ok = [f for f in fits if f.status == "ok"]
    if ok:
        return max(ok, key=lambda f: f.job.train_flops_per_sample)
    runnable = [f for f in fits if f.can_run]
    return max(runnable, key=lambda f: f.samples_per_s / f.job.min_samples_per_s) if runnable else None
