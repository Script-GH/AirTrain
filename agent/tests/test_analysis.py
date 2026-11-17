"""Checks for the job memory/throughput estimates and the analysis verdicts."""

from __future__ import annotations

import importlib.util
import unittest

from airtrain_agent import jobs
from airtrain_agent.analysis import analyze, recommended
from airtrain_agent.jobs import GB, estimate_memory, get_job, recommend_batch


def profile(**kw):
    p = {
        "backend": "cpu",
        "cpu_physical_cores": 8,
        "cpu_freq_mhz": 3000,
        "ram_free_gb": 12.0,
        "vram_free_gb": None,
        "disk_free_gb": 100.0,
        "thermal_headroom_c": None,
    }
    p.update(kw)
    return p


class MemoryEstimate(unittest.TestCase):
    def test_formula(self):
        job = get_job("cifar10-cnn")
        m = estimate_memory(job, 64, "cuda")
        self.assertEqual(m.weights, job.params * 4)
        self.assertEqual(m.grads, job.params * 4)
        self.assertEqual(m.optimizer, job.params * 8)  # Adam: two fp32 moments
        self.assertAlmostEqual(m.activations, job.act_bytes_per_sample * 64 * 1.25)
        self.assertEqual(m.overhead, 0.6 * GB)
        self.assertAlmostEqual(m.total, 16 * job.params + job.act_bytes_per_sample * 80 + 0.6 * GB)

    def test_grows_with_batch(self):
        job = get_job("resnet18-ft")
        self.assertLess(estimate_memory(job, 8).total, estimate_memory(job, 64).total)

    def test_recommended_batch_fits_budget(self):
        for job in jobs.CATALOG:
            for free_gb in (1, 2, 4, 8, 24):
                b = recommend_batch(job, free_gb * GB, "cuda")
                if b is None:
                    self.assertGreater(estimate_memory(job, job.batch_sizes[0]).total, 0.8 * free_gb * GB)
                    continue
                self.assertIn(b, job.batch_sizes)
                self.assertLessEqual(estimate_memory(job, b).total, 0.8 * free_gb * GB)
                bigger = [x for x in job.batch_sizes if x > b]
                if bigger:
                    self.assertGreater(estimate_memory(job, bigger[0]).total, 0.8 * free_gb * GB)


class Throughput(unittest.TestCase):
    def test_gpu_faster_than_cpu(self):
        gpu = profile(backend="cuda", gpu_name="NVIDIA GeForce RTX 3060", vram_free_gb=11.0)
        for job in jobs.CATALOG:
            self.assertGreater(jobs.estimate_samples_per_s(job, gpu), jobs.estimate_samples_per_s(job, profile()))

    def test_gpu_lookup(self):
        self.assertEqual(jobs.gpu_peak_flops("NVIDIA GeForce RTX 3060 Ti"), 16.2e12)  # not the plain 3060
        self.assertEqual(jobs.gpu_peak_flops("NVIDIA GeForce RTX 3060"), 12.7e12)
        self.assertEqual(jobs.gpu_peak_flops("Mystery GPU"), jobs.DEFAULT_GPU_TFLOPS * 1e12)

    def test_benchmark_overrides_specs(self):
        p = profile(bench_flops=1e12)
        job = get_job("cifar10-cnn")
        self.assertAlmostEqual(jobs.estimate_samples_per_s(job, p), 1e12 * jobs.BENCH_EFFICIENCY / 65e6)


class Verdicts(unittest.TestCase):
    def test_small_gpu_rules_out_big_jobs(self):
        fits = {f.job.id: f for f in analyze(profile(backend="cuda", gpu_name="GTX 1650", vram_free_gb=0.85))}
        self.assertTrue(fits["cifar10-cnn"].can_run)
        self.assertEqual(fits["resnet18-ft"].status, "no")
        self.assertIn("VRAM", fits["resnet18-ft"].notes[0])

    def test_disk(self):
        fits = analyze(profile(disk_free_gb=0.3))
        self.assertTrue(all(f.status == "no" for f in fits if f.job.dataset_gb + 0.5 > 0.3))

    def test_slow_cpu(self):
        fits = {f.job.id: f for f in analyze(profile(cpu_physical_cores=1, cpu_freq_mhz=1000))}
        self.assertEqual(fits["char-gpt-tiny"].status, "slow")

    def test_hot_machine_is_slower(self):
        cool = analyze(profile(thermal_headroom_c=30))[0].samples_per_s
        hot = analyze(profile(thermal_headroom_c=4))[0].samples_per_s
        self.assertLess(hot, cool)

    def test_recommendation_prefers_heaviest_full_speed_job(self):
        rec = recommended(analyze(profile(backend="cuda", gpu_name="RTX 4090", vram_free_gb=22.0)))
        self.assertEqual(rec.job.id, "char-gpt-tiny")
        self.assertIsNone(recommended(analyze(profile(ram_free_gb=0.1))))


@unittest.skipUnless(importlib.util.find_spec("torch"), "needs torch")
class CatalogMatchesModels(unittest.TestCase):
    def test_param_counts(self):
        import torch

        from airtrain_agent.models import build_model

        for job in jobs.CATALOG:
            n = sum(p.numel() for p in build_model(job.id, torch).parameters())
            self.assertEqual(n, job.params, job.id)


if __name__ == "__main__":
    unittest.main()
