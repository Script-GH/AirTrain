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
