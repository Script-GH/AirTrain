"""The three-step flow: `airtrain analysis` -> `airtrain connect` -> `airtrain start training`."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .config import Config, load_config


def _params(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def _opt(v: Any, fmt: str = "{}", missing: str = "n/a") -> str:
    return missing if v is None else fmt.format(v)


# ---------------- step 1: analysis ----------------

def print_profile(p: dict[str, Any]) -> None:
    rows = [
        ("Machine", f"{p['hostname']} ({p['kind']}, {p['os']})"),
        ("Backend", p["backend"].upper() + (f"  (PyTorch {p['torch']})" if p.get("torch") else "  (PyTorch not installed)")),
    ]
    if p.get("gpu_name"):
        rows.append(("GPU", f"{p['gpu_name']}, {_opt(p.get('vram_free_gb'), '{:.1f}')} / "
                            f"{_opt(p.get('vram_total_gb'), '{:.1f}')} GB VRAM free"))
    else:
        rows.append(("GPU", "none usable, training on CPU"))
    rows += [
        ("RAM", f"{p['ram_free_gb']:.1f} / {p['ram_total_gb']:.1f} GB free"),
        ("CPU", f"{p['cpu_name']}, {p['cpu_physical_cores']} cores / {p['cpu_cores']} threads"
                + _opt(p.get("cpu_freq_mhz"), " @ {:.0f} MHz", "")),
        ("Disk", f"{p['disk_free_gb']:.1f} GB free"),
        ("Thermal", "no sensor" if p.get("temp_c") is None
            else f"{p['temp_c']:.0f} C now, limit {p['temp_limit_c']:.0f} C, {p['thermal_headroom_c']:.0f} C headroom"),
        ("Power", "no sensor" if p.get("power_w") is None
            else f"{p['power_w']:.0f} W of {_opt(p.get('power_limit_w'), '{:.0f}')} W, "
                 f"{_opt(p.get('power_headroom_w'), '{:.0f}')} W headroom"),
        ("Compute", f"{p['bench_flops'] / 1e12:.2f} TFLOP/s measured ({p['bench_device']} matmul)"
            if p.get("bench_flops") else "estimated from specs (no benchmark)"),
    ]
    w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k.ljust(w)}  {v}")
    for warn in p.get("warnings", []):
        print(f"  ! {warn}")


def print_fits(fits: list, rec: Any) -> None:
    status_text = {"ok": "can run", "slow": "slow", "no": "cannot run"}
    head = f"  {'#':<3}{'Job':<22}{'Params':>7}{'Batch':>7}{'Memory':>9}{'Min':>8}{'Samples/s':>11}  Status"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for i, f in enumerate(fits, 1):
        mark = "*" if rec is not None and f.job.id == rec.job.id else " "
        print(
            f"{mark} {i:<3}{f.job.name:<22}{_params(f.job.params):>7}{_opt(f.batch):>7}"
            f"{f.mem_gb:>7.2f}GB{f.min_mem_gb:>6.2f}GB{f.samples_per_s:>11,.0f}  {status_text[f.status]}"
        )
        print(f"       {f.job.id}: {f.job.task}; dataset {f.job.dataset}")
        for n in f.notes:
            print(f"       - {n}")
    print("  Memory = params + grads + Adam state + activations at the batch size; Min = at the smallest batch.")
    if rec is not None:
        print("  * recommended")


def _pick(fits: list, rec: Any) -> Any:
    default = fits.index(rec) + 1 if rec is not None else None
    while True:
        hint = f" [1-{len(fits)}, Enter = {default}]" if default else f" [1-{len(fits)}]"
        try:
            raw = input(f"Pick a job{hint}: ").strip()
        except EOFError:
            return None
        if not raw and default:
            return fits[default - 1]
        if raw.isdigit() and 1 <= int(raw) <= len(fits):
            f = fits[int(raw) - 1]
            if f.can_run:
                return f
            print(f"  {f.job.name} cannot run here: {'; '.join(f.notes)}")
        else:
            matches = [f for f in fits if f.job.id == raw]
            if matches and matches[0].can_run:
                return matches[0]
            print("  Enter a number from the table.")


def cmd_analysis(args: argparse.Namespace) -> int:
    from .analysis import analyze, recommended
    from .profile import build_profile

    cfg, _ = load_config()
    print("Analyzing this machine...")
    profile = build_profile(cfg, benchmark=not args.no_benchmark)
    print_profile(profile)
    fits = analyze(profile)
    rec = recommended(fits)
    print()
    print_fits(fits, rec)
    print()

    if args.job:
        chosen = next((f for f in fits if f.job.id == args.job), None)
        if chosen is None:
            print(f"error: unknown job '{args.job}'. Choose one of: {', '.join(f.job.id for f in fits)}",
                  file=sys.stderr)
            return 2
        if not chosen.can_run:
            print(f"error: {chosen.job.name} cannot run on this machine: {'; '.join(chosen.notes)}", file=sys.stderr)
            return 1
    elif sys.stdin.isatty():
        chosen = _pick(fits, rec)
        if chosen is None:
            return 1
    else:
        print("error: no terminal to ask in; pass --job <id>, e.g. --job "
              f"{rec.job.id if rec else fits[0].job.id}", file=sys.stderr)
        return 2

    batch = args.batch or chosen.batch or chosen.job.batch_sizes[0]
    if args.batch and chosen.batch and args.batch > chosen.batch:
        print(f"  ! batch {args.batch} is above the recommended {chosen.batch}; it may run out of memory")
    if cfg.session and cfg.job != chosen.job.id:
        print(f"  Left cluster {cfg.session.get('cluster_name')}: it runs a different job.")
        cfg.session = {}
    cfg.job = chosen.job.id
    cfg.batch_size = batch
    cfg.profile = {k: v for k, v in profile.items() if k != "battery"}
    cfg.profile["samples_per_s"] = chosen.samples_per_s
    cfg.save()
    print(f"Selected {chosen.job.name} ({chosen.job.id}), batch size {batch}, "
          f"~{chosen.samples_per_s:,.0f} samples/s on {profile['backend'].upper()}.")
    print("Saved. Next step: airtrain connect")
    return 0


def require_analysis(cfg: Config) -> bool:
    if cfg.job and cfg.profile:
        return True
    print("error: run `airtrain analysis` first to pick a job for this machine.", file=sys.stderr)
    return False


def add_parsers(sub: Any) -> None:
    s = sub.add_parser("analysis", help="step 1: profile this machine and pick a training job")
    s.add_argument("--job", help="job id to select without asking (e.g. cifar10-cnn)")
    s.add_argument("--batch", type=int, help="override the recommended batch size")
    s.add_argument("--no-benchmark", action="store_true", help="skip the quick compute benchmark")
    s.set_defaults(func=cmd_analysis)
