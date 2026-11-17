"""Score clusters so a device joins the one where it helps most and waits least."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .coordinator import ANY_JOB, Cluster

# Weights add up to 1. Throughput similarity matters because FedAvg rounds wait for the
# slowest member: a device far slower than its cluster becomes a straggler, and one far
# faster spends most of each round idle.
WEIGHTS = {"latency": 0.30, "similarity": 0.25, "match": 0.20, "region": 0.15, "slots": 0.10}
LATENCY_HALF_MS = 60.0  # latency at which the latency score drops to 0.5
SLOTS_FULL_SCORE = 4  # this many free slots or more scores 1.0

REGION_GROUP = {
    "ap-south-1": "india", "ap-south-2": "india",
    "ap-southeast-1": "asia", "ap-southeast-2": "oceania", "ap-northeast-1": "asia",
    "eu-central-1": "europe", "eu-west-1": "europe",
    "us-east-1": "americas", "us-west-2": "americas", "sa-east-1": "americas",
}
NEAR_GROUPS = {frozenset(("india", "asia")), frozenset(("asia", "oceania"))}


def guess_region() -> str:
    """Rough region from the local UTC offset; override with `airtrain config --set region=...`."""
    offset = -(time.altzone if time.daylight and time.localtime().tm_isdst else time.timezone) / 3600
    if 5 <= offset < 6.5:
        return "ap-south-1"
    if 6.5 <= offset < 9:
        return "ap-southeast-1"
    if 9 <= offset < 10:
        return "ap-northeast-1"
    if offset >= 10:
        return "ap-southeast-2"
    if -1 <= offset < 4:
        return "eu-central-1"
    if offset <= -6.5:
        return "us-west-2"
    return "us-east-1"


def region_score(mine: str, theirs: str) -> float:
    if mine == theirs:
        return 1.0
    a, b = REGION_GROUP.get(mine), REGION_GROUP.get(theirs)
    if a and a == b:
        return 0.7
    if a and b and frozenset((a, b)) in NEAR_GROUPS:
        return 0.4
    return 0.1


@dataclass
class Ranked:
    cluster: Cluster
    latency_ms: float
    measured: bool
    score: float
    parts: dict[str, float] = field(default_factory=dict)
    eligible: bool = True
    reason: str = ""


def score_cluster(
    c: Cluster, job_id: str, my_samples_per_s: float, latency_ms: float, measured: bool, region: str
) -> Ranked:
    match = 1.0 if c.job_id == job_id else 0.6 if c.job_id == ANY_JOB else 0.0
    hi = max(my_samples_per_s, c.avg_samples_per_s, 1e-9)
    parts = {
        "latency": 1 / (1 + latency_ms / LATENCY_HALF_MS),
        "similarity": min(my_samples_per_s, c.avg_samples_per_s) / hi,
        "match": match,
        "region": region_score(region, c.region),
        "slots": min(c.free_slots, SLOTS_FULL_SCORE) / SLOTS_FULL_SCORE,
    }
    score = sum(WEIGHTS[k] * v for k, v in parts.items())
    reason = "full" if c.free_slots == 0 else "different job" if match == 0 else ""
    return Ranked(c, latency_ms, measured, round(score, 3), parts, eligible=not reason, reason=reason)


def rank(
    clusters: list[Cluster],
    job_id: str,
    my_samples_per_s: float,
    latencies: dict[str, tuple[float, bool]],
    region: str,
) -> list[Ranked]:
    """Eligible clusters by score (best first), then the ones this device cannot join."""
    ranked = [
        score_cluster(c, job_id, my_samples_per_s, *latencies.get(c.id, (c.simulated_latency_ms, False)), region)
        for c in clusters
    ]
    return sorted(ranked, key=lambda r: (not r.eligible, -r.score))
