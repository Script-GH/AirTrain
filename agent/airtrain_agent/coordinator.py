"""Client side of the AirTrain coordinator: find clusters for a job and join one."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Cluster:
    id: str
    name: str
    region: str  # cloud-style region code, e.g. ap-south-1
    city: str
    job_id: str
    devices: int
    capacity: int
    avg_samples_per_s: float  # median per-device throughput in this cluster
    probe_host: str | None = None  # host:port to time a TCP connect against
    simulated_latency_ms: float = 0.0  # used when the probe is not possible

    @property
    def free_slots(self) -> int:
        return max(self.capacity - self.devices, 0)


@dataclass
class Session:
    cluster_id: str
    cluster_name: str
    region: str
    city: str
    job_id: str
    devices: int  # including this device
    latency_ms: float
    latency_measured: bool
    coordinator: str
    device_id: str
    joined_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Coordinator(ABC):
    """What the agent needs from a coordinator. Implemented by MockCoordinator and HttpCoordinator."""

    name: str

    @abstractmethod
    def list_clusters(self, job_id: str) -> list[Cluster]:
        """Clusters currently training `job_id`."""

    @abstractmethod
    def join(self, cluster: Cluster, device: dict[str, Any], latency_ms: float, measured: bool) -> Session:
        """Reserve a slot in `cluster` for this device."""

    @abstractmethod
    def leave(self, session: dict[str, Any]) -> None:
        """Release the slot held by `session`."""


ANY_JOB = "*"  # a flexible pool that trains whichever job its members pick

# id, name, region, city, typical latency from India in ms (used only when it cannot be measured)
_MOCK_SITES = (
    ("blr-campus", "Bengaluru Campus Pool", "ap-south-1", "Bengaluru, IN", 18),
    ("mum-labs", "Mumbai Night Labs", "ap-south-1", "Mumbai, IN", 24),
    ("hyd-gamers", "Hyderabad Gamers", "ap-south-2", "Hyderabad, IN", 31),
    ("sg-owls", "Singapore Night Owls", "ap-southeast-1", "Singapore, SG", 62),
    ("fra-club", "Frankfurt GPU Club", "eu-central-1", "Frankfurt, DE", 138),
    ("va-hobby", "Virginia Hobbyists", "us-east-1", "Ashburn, US", 228),
)


class MockCoordinator(Coordinator):
    """Local stand-in for the coordinator so the flow works before the backend exists.

    Clusters are generated deterministically per job, so repeated runs show the same list.
    Each cluster's region gets a real AWS endpoint to time a TCP connect against, which gives
    an honest latency to that region when the network allows it.
    """

    name = "mock"

    def __init__(self, typical_samples_per_s: float = 500.0) -> None:
        self.typical = typical_samples_per_s

    def list_clusters(self, job_id: str) -> list[Cluster]:
        import random

        rng = random.Random(job_id)
        sites = rng.sample(_MOCK_SITES, 5)
        clusters = []
        for i, (cid, name, region, city, lat) in enumerate(sites):
            capacity = rng.choice((8, 12, 16, 24, 32))
            devices = capacity if i == 2 else rng.randint(2, capacity - 1)  # one full cluster
            clusters.append(
                Cluster(
                    id=f"{cid}-{job_id}",
                    name=name,
                    region=region,
                    city=city,
                    job_id=ANY_JOB if i == 4 else job_id,
                    devices=devices,
                    capacity=capacity,
                    avg_samples_per_s=round(self.typical * rng.choice((0.25, 0.5, 0.9, 1.1, 2.0, 4.0)), 1),
                    probe_host=f"dynamodb.{region}.amazonaws.com:443",
                    simulated_latency_ms=round(lat * rng.uniform(0.9, 1.2), 1),
                )
            )
        return clusters

    def join(self, cluster: Cluster, device: dict[str, Any], latency_ms: float, measured: bool) -> Session:
        if cluster.free_slots <= 0:
            raise RuntimeError(f"{cluster.name} is full")
        return Session(
            cluster_id=cluster.id,
            cluster_name=cluster.name,
            region=cluster.region,
            city=cluster.city,
            job_id=device["job_id"],
            devices=cluster.devices + 1,
            latency_ms=round(latency_ms, 1),
            latency_measured=measured,
            coordinator=self.name,
            device_id=device["device_id"],
        )

    def leave(self, session: dict[str, Any]) -> None:
        return None
