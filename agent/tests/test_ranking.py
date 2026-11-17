"""Checks for cluster scoring, the mock coordinator and the latency fallback."""

from __future__ import annotations

import unittest

from airtrain_agent.coordinator import ANY_JOB, Cluster, MockCoordinator, probe_latencies
from airtrain_agent.ranking import rank, region_score, score_cluster

JOB = "cifar10-cnn"


def cluster(cid="c", region="ap-south-1", job=JOB, devices=4, capacity=12, sps=1000.0, lat=20.0):
    return Cluster(cid, cid, region, "City", job, devices, capacity, sps, None, lat)


def score(c, mine=1000.0, latency=None, region="ap-south-1"):
    return score_cluster(c, JOB, mine, c.simulated_latency_ms if latency is None else latency, False, region)


class Scoring(unittest.TestCase):
    def test_lower_latency_wins(self):
        self.assertGreater(score(cluster(lat=15)).score, score(cluster(lat=150)).score)

    def test_throughput_similarity_avoids_stragglers(self):
        near = score(cluster(sps=1100), mine=1000).score
        far_slower = score(cluster(sps=100), mine=1000).score
        far_faster = score(cluster(sps=10_000), mine=1000).score
        self.assertGreater(near, far_slower)
        self.assertGreater(near, far_faster)

    def test_free_slots(self):
        self.assertGreater(score(cluster(devices=4)).score, score(cluster(devices=11)).score)
        full = score(cluster(devices=12))
        self.assertFalse(full.eligible)
        self.assertEqual(full.reason, "full")

    def test_job_match(self):
        self.assertGreater(score(cluster()).score, score(cluster(job=ANY_JOB)).score)
        other = score(cluster(job="resnet18-ft"))
        self.assertFalse(other.eligible)
        self.assertEqual(other.reason, "different job")

    def test_region(self):
        self.assertEqual(region_score("ap-south-1", "ap-south-1"), 1.0)
        self.assertEqual(region_score("ap-south-1", "ap-south-2"), 0.7)
        self.assertEqual(region_score("ap-south-1", "ap-southeast-1"), 0.4)
        self.assertEqual(region_score("ap-south-1", "us-east-1"), 0.1)
        self.assertGreater(score(cluster(region="ap-south-1")).score, score(cluster(region="eu-central-1")).score)

    def test_score_is_weighted_sum(self):
        r = score(cluster())
        self.assertTrue(0 <= r.score <= 1)
        self.assertEqual(set(r.parts), {"latency", "similarity", "match", "region", "slots"})


class Ranking(unittest.TestCase):
    def test_order_and_ineligible_last(self):
        cs = [
            cluster("far", region="us-east-1", lat=230),
            cluster("full", devices=12, lat=5),
            cluster("best", lat=12),
            cluster("other-job", job="resnet18-ft", lat=5),
        ]
        lat = {c.id: (c.simulated_latency_ms, False) for c in cs}
        ids = [r.cluster.id for r in rank(cs, JOB, 1000, lat, "ap-south-1")]
        self.assertEqual(ids[:2], ["best", "far"])
        self.assertEqual(set(ids[2:]), {"full", "other-job"})

    def test_measured_latency_overrides_simulated(self):
        a, b = cluster("a", lat=10), cluster("b", lat=300)
        ranked = rank([a, b], JOB, 1000, {"a": (400.0, True), "b": (8.0, True)}, "ap-south-1")
        self.assertEqual(ranked[0].cluster.id, "b")
        self.assertTrue(ranked[0].measured)


class Mock(unittest.TestCase):
    def test_deterministic_with_one_full_and_one_flexible(self):
        a = MockCoordinator(500).list_clusters(JOB)
        b = MockCoordinator(500).list_clusters(JOB)
        self.assertEqual([c.id for c in a], [c.id for c in b])
        self.assertEqual(sum(c.free_slots == 0 for c in a), 1)
        self.assertEqual(sum(c.job_id == ANY_JOB for c in a), 1)

    def test_join_counts_this_device(self):
        m = MockCoordinator()
        c = next(c for c in m.list_clusters(JOB) if c.free_slots)
        s = m.join(c, {"device_id": "d1", "job_id": JOB}, 12.0, True)
        self.assertEqual(s.devices, c.devices + 1)
        full = next(c for c in m.list_clusters(JOB) if not c.free_slots)
        with self.assertRaises(RuntimeError):
            m.join(full, {"device_id": "d1", "job_id": JOB}, 12.0, True)

    def test_unreachable_probe_falls_back(self):
        c = cluster(lat=42.0)
        c.probe_host = "127.0.0.1:1"
        self.assertEqual(probe_latencies([c]), {"c": (42.0, False)})
        self.assertEqual(probe_latencies([c], enabled=False), {"c": (42.0, False)})


if __name__ == "__main__":
    unittest.main()
