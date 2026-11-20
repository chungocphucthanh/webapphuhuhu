"""Hand-built instances shared by several owners (Lead, 2.7.md section 9).

instance.py was frozen at the TV1 handoff (req 2.1, 2.6), so the brief's Module 2 worked
example lives here instead of in instance.py. Times and campus are illustrative metadata.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from tools.make_seed import seed_for, soft_weights

from .config import TEAM_ID
from .instance import Instance, small_slice


def week_slice(inst: Instance, weeks: int) -> Instance:
    """small_slice over the exam days in the first 7 * weeks calendar days of the period.

    small_slice counts exam days, not calendar days; this converts a calendar horizon
    (1 week, 2 weeks, ...) into that count so performance and tuning use the same horizons.
    """
    days = sorted(inst.sessions_by_day)
    n_days = sum(day < days[0] + timedelta(days=7 * weeks) for day in days)
    return small_slice(inst, n_days)


def lp_gap_instance() -> Instance:
    """Brief p.5: 3 staff, 4 sessions needing 1 person each, full availability.

    Sessions run back to back on one day at CS1 (touching endpoints do not overlap).
    Expected: LP relaxation t = 4/3, ILP t* = 2; min-max alone accepts (2,1,1) and
    (2,2,0); the lexicographic objective keeps only (2,1,1).
    """
    day = date(2026, 5, 18)
    starts = (7, 9, 13, 15)
    return Instance(
        seed=seed_for(TEAM_ID), availability="explicit", staff_ids=["CB1", "CB2", "CB3"],
        session_names=["S1", "S2", "S3", "S4"], demand=[1, 1, 1, 1], campus=["CS1"] * 4,
        day=[day] * 4,
        intervals=[(datetime(2026, 5, 18, h), datetime(2026, 5, 18, h + 2)) for h in starts],
        overlaps=[], baseline=[], A={(i, j) for i in range(3) for j in range(4)},
        preferences=["BAL"] * 3, soft_weights=soft_weights(TEAM_ID),
    )


def clique_instance() -> Instance:
    """3 staff x 4 sessions = 12 pairs, small enough to enumerate (TV2-3).

    S0, S1, S2 pairwise overlap, so they form one clique of size 3; S3 starts when S1
    ends and overlaps nothing. CB1 is busy at S3 and CB3 at S0.
    """
    def at(hour, minute=0):
        return datetime(2026, 5, 18, hour, minute)

    return Instance(
        seed=seed_for(TEAM_ID), availability="explicit", staff_ids=["CB1", "CB2", "CB3"],
        session_names=["S0", "S1", "S2", "S3"], demand=[1, 1, 1, 1],
        campus=["CS1", "CS2", "CS1", "CS1"], day=[date(2026, 5, 18)] * 4,
        intervals=[(at(8), at(10)), (at(9), at(11)), (at(9, 30), at(10, 30)), (at(11), at(12))],
        overlaps=[(0, 1), (0, 2), (1, 2)], baseline=[],
        A={(i, j) for i in range(3) for j in range(4)} - {(0, 3), (2, 0)},
        preferences=["BAL"] * 3, soft_weights=soft_weights(TEAM_ID),
    )


def forced_soft_instance() -> Instance:
    """Every soft term is forced to be positive (TV4, TV5 tests).

    CB1 (prefers CS1) is the only person available; four 1-person sessions on one day
    alternate CS1/CS2, so the optimum pays LOC = 2, FAT = 4 - K = 1 (K = 3) and TRV = 1.
    """
    hours = (7, 9, 13, 15)
    return Instance(
        seed=seed_for(TEAM_ID), availability="explicit", staff_ids=["CB1", "CB2"],
        session_names=["A", "B", "C", "D"], demand=[1, 1, 1, 1],
        campus=["CS1", "CS2", "CS1", "CS2"], day=[date(2026, 5, 18)] * 4,
        intervals=[(datetime(2026, 5, 18, h), datetime(2026, 5, 18, h + 2)) for h in hours],
        overlaps=[], baseline=[(0, j) for j in range(4)], A={(0, j) for j in range(4)},
        preferences=["CS1", "BAL"], soft_weights=soft_weights(TEAM_ID),
    )
