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
    probe_host: str | None = None  # host:port of an HTTPS endpoint answering GET /ping
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

# Approximate location of each region's data centers, used to place a cluster's coordinator on the map.
REGION_COORDS: dict[str, tuple[float, float]] = {
    "ap-south-1": (19.08, 72.88),  # Mumbai
    "ap-south-2": (17.39, 78.49),  # Hyderabad
    "ap-southeast-1": (1.35, 103.82),  # Singapore
    "ap-southeast-2": (-33.87, 151.21),  # Sydney
    "ap-northeast-1": (35.68, 139.69),  # Tokyo
    "eu-central-1": (50.11, 8.68),  # Frankfurt
    "eu-west-1": (53.35, -6.26),  # Dublin
    "us-east-1": (39.04, -77.49),  # Ashburn
    "us-west-2": (45.84, -119.70),  # Oregon
    "sa-east-1": (-23.55, -46.63),  # Sao Paulo
}


def region_coords(region: str | None) -> tuple[float | None, float | None]:
    return REGION_COORDS.get(region or "", (None, None))

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


def measure_latency(host_port: str, attempts: int = 3, timeout: float = 2.0) -> float | None:
    """Round-trip time in ms to a region endpoint, or None if it cannot be reached.

    Opens one HTTPS keep-alive connection, sends a warm-up GET /ping, then times further
    requests on the same connection. That measures the network round trip without DNS, TCP
    and TLS setup, and is not fooled by proxies that answer TCP connects locally.
    """
    import http.client

    host, _, port = host_port.rpartition(":")
    conn = http.client.HTTPSConnection(host, int(port or 443), timeout=timeout)
    try:
        conn.request("GET", "/ping")
        conn.getresponse().read()
        samples = []
        for _ in range(attempts):
            start = time.perf_counter()
            conn.request("GET", "/ping")
            conn.getresponse().read()
            samples.append((time.perf_counter() - start) * 1000)
        return round(min(samples), 1)
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()


def probe_latencies(clusters: list[Cluster], enabled: bool = True) -> dict[str, tuple[float, bool]]:
    """Latency per cluster id as (ms, measured). Falls back to the simulated value per cluster."""
    from concurrent.futures import ThreadPoolExecutor

    out = {c.id: (c.simulated_latency_ms, False) for c in clusters}
    targets = [c for c in clusters if enabled and c.probe_host]
    if not targets:
        return out
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        for c, ms in zip(targets, pool.map(lambda c: measure_latency(c.probe_host), targets)):
            if ms is not None:
                out[c.id] = (ms, True)
    return out


class CoordinatorError(RuntimeError):
    pass


class HttpCoordinator(Coordinator):
    """Client for the AirTrain coordinator service.

    TODO(coordinator): the FastAPI coordinator does not exist yet. These routes are the
    planned contract and will be finalized with it:
      GET  {url}/v1/clusters?job=<job_id>            -> [Cluster as JSON, ...]
      POST {url}/v1/clusters/<cluster_id>/join       body: device info -> Session as JSON
      POST {url}/v1/clusters/<cluster_id>/leave      body: {"device_id": ...}
    Authentication (device keys) and the Flower SuperLink address returned on join come later.
    """

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url.rstrip("/")
        self.name = self.url
        self.timeout = timeout

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        import json
        import urllib.error
        import urllib.request

        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            self.url + path, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"null")
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise CoordinatorError(f"coordinator {self.url} unavailable: {e}") from e

    def list_clusters(self, job_id: str) -> list[Cluster]:
        from urllib.parse import quote

        rows = self._call("GET", f"/v1/clusters?job={quote(job_id)}") or []
        return [Cluster(**r) for r in rows]

    def join(self, cluster: Cluster, device: dict[str, Any], latency_ms: float, measured: bool) -> Session:
        body = {**device, "latency_ms": latency_ms, "latency_measured": measured}
        r = self._call("POST", f"/v1/clusters/{cluster.id}/join", body)
        return Session(**{**r, "coordinator": self.url})

    def leave(self, session: dict[str, Any]) -> None:
        self._call("POST", f"/v1/clusters/{session['cluster_id']}/leave", {"device_id": session["device_id"]})


def get_coordinator(url: str | None, typical_samples_per_s: float = 500.0) -> Coordinator:
    """HttpCoordinator for a URL, else the local mock."""
    return HttpCoordinator(url) if url else MockCoordinator(typical_samples_per_s)
