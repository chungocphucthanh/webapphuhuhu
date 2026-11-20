"""Workload and soft-penalty metrics for a fixed schedule (req 2.9)."""

from __future__ import annotations

from collections import Counter


def loads(inst, assigned) -> list[int]:
    """Count distinct assignments for every staff member, including zero loads."""
    count = Counter(i for i, j in set(assigned))
    return [count[i] for i in range(len(inst.staff_ids))]


def compute_metrics(inst, assigned, fatigue_k: int | None = None) -> dict:
    """Measure max/min/spread/L1/staff_used and location/fatigue/travel.

    Omitting fatigue_k uses ModelConfig.fatigue_k. Materialize the schedule
    once so workload and soft metrics see the same pairs even for a generator.
    """
    from .soft import evaluate_soft

    if fatigue_k is None:
        from .config import ModelConfig

        fatigue_k = ModelConfig.fatigue_k
    assigned = set(assigned)
    w = loads(inst, assigned)
    w_bar = sum(inst.demand) / len(inst.staff_ids)
    return {
        "max_load": max(w), "min_load": min(w), "spread": max(w) - min(w),
        "l1": sum(abs(load - w_bar) for load in w),
        "staff_used": sum(load > 0 for load in w),
        **evaluate_soft(inst, assigned, fatigue_k),
    }


def main():
    from .instance import build_instance
    from .soft import fit_fatigue_k

    inst = build_instance()
    k = fit_fatigue_k(inst)
    metrics = compute_metrics(inst, inst.baseline, k)
    print(f"Baseline metrics (K={k}, mean load {sum(inst.demand) / len(inst.staff_ids):.4f}):")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
