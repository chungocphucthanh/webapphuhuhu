"""Real assignment counts on consecutive seven-day blocks, including empty days."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from m2_ilp.validate import check_schedule


@dataclass(frozen=True)
class WeeklyWorkload:
    starts: tuple[date, ...]
    days: np.ndarray
    counts: np.ndarray  # [week, staff], actual assignments, never extrapolated

    @property
    def rates(self) -> np.ndarray:
        """Full-week equivalent loads; the last block can contain fewer than 7 days."""
        return self.counts * (7 / self.days[:, None])

    @property
    def mean_load(self) -> np.ndarray:
        return self.counts.sum(axis=0) * 7 / self.days.sum()

    @property
    def cumulative(self) -> np.ndarray:
        """Descriptive running workload, not a state with a fatigue equilibrium."""
        return np.vstack([np.zeros(self.counts.shape[1]), self.counts.cumsum(axis=0)])


def week_layout(inst) -> tuple[tuple[date, ...], np.ndarray, list[int]]:
    first, last = min(inst.day), max(inst.day)
    span = (last - first).days + 1
    starts = tuple(first + timedelta(days=offset) for offset in range(0, span, 7))
    days = np.array([min(7, span - 7 * k) for k in range(len(starts))])
    index = [(day - first).days // 7 for day in inst.day]
    return starts, days, index


def weekly_workload(inst, assigned) -> WeeklyWorkload:
    assigned = list(assigned)
    if len(set(assigned)) != len(assigned):
        raise ValueError("Duplicate assignments would inflate workload")
    violations = check_schedule(inst, assigned)
    if violations:
        raise ValueError("Invalid schedule:\n" + "\n".join(violations[:20]))
    starts, days, index = week_layout(inst)
    counts = np.zeros((len(starts), len(inst.staff_ids)), dtype=int)
    for i, j in assigned:
        counts[index[j], i] += 1
    return WeeklyWorkload(starts, days, counts)


def read_schedule(inst, path: Path) -> frozenset:
    """Read M2's dense CSV strictly; stale, partial and invalid inputs fail visibly."""
    people = {person: i for i, person in enumerate(inst.staff_ids)}
    sessions = {session: j for j, session in enumerate(inst.session_names)}
    seen, assigned = set(), set()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["invigilator_id", "session_id", "assigned"]:
            raise ValueError("Schedule needs invigilator_id,session_id,assigned columns")
        for line, row in enumerate(reader, start=2):
            person, session, flag = (row.get(key) for key in reader.fieldnames)
            if (None in row or person not in people or session not in sessions
                    or flag not in ("0", "1")):
                raise ValueError(f"Invalid schedule row {line}")
            pair = people[person], sessions[session]
            if pair in seen:
                raise ValueError(f"Duplicate schedule row {line}")
            seen.add(pair)
            if flag == "1":
                assigned.add(pair)
    if len(seen) != len(people) * len(sessions):
        raise ValueError("Schedule must contain every staff/session pair exactly once")
    weekly_workload(inst, assigned)
    return frozenset(assigned)
