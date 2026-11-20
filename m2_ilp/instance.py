"""M2 sets, parameters and simulated preferences (req 2.1 and 2.6).

Run from the repository root: python -m m2_ilp.instance
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from random import Random

from m1_logic.data_loader import PROJECT_FOLDER, load_dataset
from tools.make_seed import seed_for, soft_weights


TEAM_ID = "CO2011-261-A01-2551896"
DEFAULT_FLIP_RATE = 0.30  # V1 choice for previously unobserved person/shift pairs.
SOFT_WEIGHT_NAMES = ("location", "fatigue", "travel")


@dataclass
class Instance:
    seed: int
    availability: str
    staff_ids: list[str]
    session_names: list[str]
    demand: list[int]
    campus: list[str]
    day: list[date]
    intervals: list[tuple[datetime, datetime]]
    overlaps: list[tuple[int, int]]
    baseline: list[tuple[int, int]]
    A: set[tuple[int, int]]
    preferences: list[str]
    soft_weights: list[float]
    flip_rate: float | None = None
    sessions_by_day: dict[date, list[int]] = field(init=False)

    def __post_init__(self):
        self.sessions_by_day = {day: [] for day in sorted(set(self.day))}
        for j, day in enumerate(self.day):
            self.sessions_by_day[day].append(j)

    @property
    def soft_weight_map(self):
        """All three weights must be used by the downstream soft objective."""
        return dict(zip(SOFT_WEIGHT_NAMES, self.soft_weights))


def _team_seed(seed=None):
    if seed is None:
        seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    if isinstance(seed, bool) or not isinstance(seed, int) or seed != seed_for(TEAM_ID):
        raise ValueError("The seed must match tools.make_seed.seed_for(TEAM_ID)")
    return seed


def _checked_pairs(pairs, n, m, label):
    """Reject malformed indices instead of silently dropping a hard restriction."""
    result = set()
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"{label}: expected an (i, j) pair")
        i, j = pair
        if (type(i) is not int or type(j) is not int or
                not 0 <= i < n or not 0 <= j < m):
            raise ValueError(f"{label}: index outside the instance: {pair}")
        result.add((i, j))
    return result


def available_pairs(data, mode, *, seed=None, flip_rate=DEFAULT_FLIP_RATE):
    """Return A using explicit Busy, the old day policy, or seeded baseline expansion."""
    n, m = len(data["staff_ids"]), len(data["session_ids"])
    if mode == "shift":
        if data["busy"] is None:
            raise ValueError("Busy is unknown; supply explicit M1 Busy pairs for shift mode")
        busy = _checked_pairs(data["busy"], n, m, "Busy")
        return {(i, j) for i in range(n) for j in range(m) if (i, j) not in busy}
    if mode == "day":
        days = [start.date() for start, end in data["intervals"]]
        baseline = _checked_pairs(data["baseline"], n, m, "Baseline")
        attended = {(i, days[j]) for i, j in baseline}
        return {(i, j) for i in range(n) for j in range(m) if (i, days[j]) in attended}
    if mode == "seeded":
        if data.get("busy") is not None:
            raise ValueError("Use shift mode to retain explicitly supplied Busy pairs")
        if type(flip_rate) not in (int, float) or not 0 <= flip_rate <= 1:
            raise ValueError("flip_rate must be a finite probability between 0 and 1")
        baseline = _checked_pairs(data["baseline"], n, m, "Baseline")
        codes = sorted({code for code, campus in data["session_ids"]})
        observed = {(i, data["session_ids"][j][0]) for i, j in baseline}
        available_shifts = set(observed)
        rng = Random(_team_seed(seed))
        # One draw per UNOBSERVED person/shift, in stable ID order. Keep the
        # baseline available; share each result across campuses of the same shift.
        for i in sorted(range(n), key=lambda i: data["staff_ids"][i]):
            for code in codes:
                if (i, code) not in observed and rng.random() < flip_rate:
                    available_shifts.add((i, code))
        return {(i, j) for i in range(n) for j, (code, campus) in enumerate(data["session_ids"])
                if (i, code) in available_shifts}
    raise ValueError("Availability must be day, shift or seeded")


def simulate_preferences(data, seed):
    """Use baseline campus frequencies as a sampling prior, never as eligibility."""
    rng = Random(seed)
    counts = [{"CS1": 0, "CS2": 0} for _ in data["staff_ids"]]
    for i, j in data["baseline"]:
        counts[i][data["session_ids"][j][1]] += 1
    preferences = [""] * len(counts)
    for i in sorted(range(len(counts)), key=lambda i: data["staff_ids"][i]):
        cs1, cs2 = counts[i]["CS1"], counts[i]["CS2"]
        total = cs1 + cs2
        # P(BAL)=1/3; split the other 2/3 by observed campus frequency.
        weights = [2 * cs1, 2 * cs2, total] if total else [1, 1, 1]
        preferences[i] = rng.choices(["CS1", "CS2", "BAL"], weights=weights, k=1)[0]
    return preferences


def build_instance(seed=None, availability="seeded", *, data=None, flip_rate=DEFAULT_FLIP_RATE):
    """Reuse the M1 loader. Optional data accepts a prepared M1 scenario with Busy."""
    seed = _team_seed(seed)
    data = dict(load_dataset() if data is None else data)
    # M1's loader returns datetimes; prepared scenarios serialize them as ISO strings.
    intervals = []
    for start, end in data["intervals"]:
        start = datetime.fromisoformat(start) if isinstance(start, str) else start
        end = datetime.fromisoformat(end) if isinstance(end, str) else end
        if not isinstance(start, datetime) or not isinstance(end, datetime) or start >= end:
            raise ValueError("Each session needs a valid start/end datetime interval")
        intervals.append((start, end))
    data["intervals"] = intervals
    n, m = len(data["staff_ids"]), len(data["session_ids"])
    if not n or not m or len(intervals) != m or len(data["shift_demands"]) != m:
        raise ValueError("Staff, sessions, demand and intervals must have matching nonempty sizes")
    if any(type(d) is not int or d <= 0 for d in data["shift_demands"]):
        raise ValueError("Every real session must have positive integer demand")
    if any(campus not in ("CS1", "CS2") for code, campus in data["session_ids"]):
        raise ValueError("Only CS1 and CS2 are supported")
    data["baseline"] = sorted(_checked_pairs(data["baseline"], n, m, "Baseline"))
    overlaps = sorted(_checked_pairs(data["overlaps"], m, m, "Overlap"))
    return Instance(
        seed=seed, availability=availability, staff_ids=list(data["staff_ids"]),
        session_names=[f"{code}_{campus}" for code, campus in data["session_ids"]],
        demand=list(data["shift_demands"]), campus=[campus for code, campus in data["session_ids"]],
        day=[start.date() for start, end in intervals], intervals=intervals,
        overlaps=overlaps, baseline=data["baseline"],
        A=available_pairs(data, availability, seed=seed, flip_rate=flip_rate),
        preferences=simulate_preferences(data, seed), soft_weights=soft_weights(TEAM_ID),
        flip_rate=flip_rate if availability == "seeded" else None,
    )


def toy_instance():
    """Brief p.2: three staff, two sessions requiring two staff; CB1 busy in Morning.

    Times/campus and a feasible baseline below are illustrative test metadata.
    This is different from the four-shift worked example on brief p.5.
    """
    seed = _team_seed()
    return Instance(
        seed=seed, availability="explicit", staff_ids=["CB1", "CB2", "CB3"],
        session_names=["Morning", "Afternoon"], demand=[2, 2], campus=["CS1", "CS1"],
        day=[date(2026, 5, 18)] * 2,
        intervals=[(datetime(2026, 5, 18, 7), datetime(2026, 5, 18, 9)),
                   (datetime(2026, 5, 18, 13), datetime(2026, 5, 18, 15))],
        overlaps=[], baseline=[(0, 1), (1, 0), (1, 1), (2, 0)],
        A={(0, 1), (1, 0), (1, 1), (2, 0), (2, 1)},
        preferences=["BAL"] * 3, soft_weights=soft_weights(TEAM_ID),
    )


def small_slice(inst, n_days=1):
    """Keep the earliest n_days, all their candidates, and inherited parameter values."""
    if type(n_days) is not int or n_days < 1:
        raise ValueError("n_days must be a positive integer")
    days = sorted(inst.sessions_by_day)[:n_days]
    sessions = [j for j, day in enumerate(inst.day) if day in days]
    session_map = {old: new for new, old in enumerate(sessions)}
    # Keep available staff even if they were not assigned in the selected baseline.
    people = sorted({i for i, j in inst.A | set(inst.baseline) if j in session_map})
    staff_map = {old: new for new, old in enumerate(people)}
    return replace(
        inst, staff_ids=[inst.staff_ids[i] for i in people],
        session_names=[inst.session_names[j] for j in sessions],
        demand=[inst.demand[j] for j in sessions], campus=[inst.campus[j] for j in sessions],
        day=[inst.day[j] for j in sessions], intervals=[inst.intervals[j] for j in sessions],
        overlaps=[(session_map[j], session_map[k]) for j, k in inst.overlaps
                  if j in session_map and k in session_map],
        baseline=[(staff_map[i], session_map[j]) for i, j in inst.baseline if j in session_map],
        A={(staff_map[i], session_map[j]) for i, j in inst.A if j in session_map},
        preferences=[inst.preferences[i] for i in people], soft_weights=list(inst.soft_weights),
    )


def write_preferences(inst, path=PROJECT_FOLDER / "data/simulated_preferences.csv"):
    """Export the already generated preferences without drawing random values again."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["staff_id", "preference", "seed", "source"])
        for i, person in enumerate(inst.staff_ids):
            writer.writerow([person, inst.preferences[i], inst.seed, "simulated"])


def print_summary(inst):
    n, m = len(inst.staff_ids), len(inst.session_names)
    print(f"Staff={n}; sessions={m}; total demand={sum(inst.demand)}; "
          f"days={len(inst.sessions_by_day)}; overlaps={len(inst.overlaps)}")
    print(f"Availability={inst.availability}; |A|={len(inst.A)}; "
          f"average available/session={len(inst.A) / m:.2f}; dense pairs={n*m}")
    if inst.flip_rate is not None:
        print(f"Unobserved person/shift flip probability={inst.flip_rate:.0%}")
    print(f"Baseline pairs outside availability={len(set(inst.baseline) - inst.A)}")
    loads = Counter(i for i, j in inst.baseline)
    daily_loads = Counter((i, inst.day[j]) for i, j in inst.baseline)
    print(f"Baseline max_load={max(loads.values(), default=0)}; "
          f"active person/day load distribution={dict(sorted(Counter(daily_loads.values()).items()))}")
    print(f"Simulated preferences={dict(sorted(Counter(inst.preferences).items()))}")
    print(f"Soft weight mapping={inst.soft_weight_map}; seed={inst.seed}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="Defaults to data/seed.txt")
    parser.add_argument("--availability", choices=["day", "shift", "seeded"], default="seeded")
    parser.add_argument("--flip-rate", type=float, default=DEFAULT_FLIP_RATE,
                        help="Seeded probability of making an unobserved person/shift available")
    args = parser.parse_args()
    data = load_dataset()
    inst = build_instance(args.seed, args.availability, data=data, flip_rate=args.flip_rate)
    print_summary(inst)
    print("Availability comparison on the same full dataset:")
    for mode in ("seeded", "day", "shift"):
        try:
            pairs = available_pairs(data, mode, seed=inst.seed, flip_rate=args.flip_rate)
            print(f"  {mode}: |A|={len(pairs)}, average/session={len(pairs)/len(inst.session_names):.2f}")
        except (ValueError, NotImplementedError) as error:
            print(f"  {mode}: unavailable ({error})")
    write_preferences(inst)
    print("Wrote data/simulated_preferences.csv (simulated data, not a solved schedule).")
    print("First-day slice:")
    print_summary(small_slice(inst))


if __name__ == "__main__":
    main()
