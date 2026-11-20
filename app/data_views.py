"""Dataset presets, CSV upload validation and weekly assignment tables (M5, Vinh)."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from m1_logic.data_loader import DEFAULT_PATH, PROJECT_FOLDER, load_dataset
from m1_logic.prepare_instances import prepare_instances
from m2_ilp.config import TEAM_ID
from m2_ilp.fixtures import week_slice
from m2_ilp.instance import DEFAULT_FLIP_RATE, Instance, build_instance, toy_instance
from m3_automata.encode_strings import SYMBOL_BY_START
from m4_dynamics.workload import read_schedule, week_layout
from tools.make_seed import seed_for

DATASET_PRESETS = {
    "full": "Full Faculty Dataset (73 staff, 83 sessions, 27 days)",
    "week1": "1-Week Real Slice (61 staff, 5 sessions)",
    "week2": "2-Week Real Slice (73 staff, 26 sessions)",
    "m1_slice": "M1 Seeded Real Slice (3 shifts, SAT / UNSAT)",
    "toy": "Toy Instance (Brief p.2: 3 staff, 2 sessions)",
    "upload": "Upload Custom Dataset CSV",
}


def read_team_seed(seed_path: Path | None = None) -> int:
    """Read and verify the deterministic team seed from data/seed.txt."""
    path = PROJECT_FOLDER / "data" / "seed.txt" if seed_path is None else Path(seed_path)
    seed = int(path.read_text(encoding="utf-8-sig").strip())
    if seed != seed_for(TEAM_ID):
        raise ValueError("Seed in data/seed.txt does not match TEAM_ID")
    return seed


def session_symbol(start: datetime) -> str:
    """Map session start time to M, A or N, with hour fallback for custom uploads."""
    key = f"{start:%H}g{start:%M}"
    if key in SYMBOL_BY_START:
        return SYMBOL_BY_START[key]
    if start.hour < 12:
        return "M"
    if start.hour < 17:
        return "A"
    return "N"


def instance_to_m1_data(inst: Instance) -> dict:
    """Convert any M2 Instance into the exact M1 solver input contract."""
    n, m = len(inst.staff_ids), len(inst.session_names)
    session_ids = []
    for j, name in enumerate(inst.session_names):
        suffix = "_" + inst.campus[j]
        code = name[: -len(suffix)] if name.endswith(suffix) else name
        session_ids.append([code, inst.campus[j]])
    busy = [(i, j) for i in range(n) for j in range(m) if (i, j) not in inst.A]
    return {
        "staff_ids": list(inst.staff_ids),
        "session_ids": session_ids,
        "shift_demands": list(inst.demand),
        "busy": busy,
        "overlaps": list(inst.overlaps),
        "baseline": list(inst.baseline),
    }


def load_csv_bytes(
    raw_bytes: bytes,
    *,
    seed: int | None = None,
    availability: str = "seeded",
    flip_rate: float = DEFAULT_FLIP_RATE,
) -> tuple[dict, Instance]:
    """Validate uploaded Faculty CSV bytes via M1's loader without touching repo files."""
    if not isinstance(raw_bytes, (bytes, bytearray)) or not bytes(raw_bytes).strip():
        raise ValueError("Uploaded dataset CSV is empty")
    team_seed = read_team_seed() if seed is None else seed
    with tempfile.TemporaryDirectory() as folder:
        csv_path = Path(folder) / "uploaded_dataset.csv"
        csv_path.write_bytes(bytes(raw_bytes))
        raw = load_dataset(csv_path)
    inst = build_instance(team_seed, availability, data=raw, flip_rate=flip_rate)
    return instance_to_m1_data(inst), inst


def load_preset_instance(
    preset: str,
    *,
    seed: int | None = None,
    availability: str = "seeded",
    flip_rate: float = DEFAULT_FLIP_RATE,
    m1_scenario: str = "sat",
) -> tuple[dict, Instance]:
    """Load one of the built-in dataset presets without mutating tracked files."""
    if m1_scenario not in ("sat", "unsat"):
        raise ValueError("m1_scenario must be 'sat' or 'unsat'")
    team_seed = read_team_seed() if seed is None else seed
    if preset == "full":
        raw = load_dataset(DEFAULT_PATH)
        inst = build_instance(team_seed, availability, data=raw, flip_rate=flip_rate)
        return instance_to_m1_data(inst), inst
    if preset in ("week1", "week2"):
        full = build_instance(team_seed, availability, flip_rate=flip_rate)
        inst = week_slice(full, 1 if preset == "week1" else 2)
        return instance_to_m1_data(inst), inst
    if preset == "m1_slice":
        with tempfile.TemporaryDirectory() as folder:
            cases = prepare_instances(team_seed, output_dir=Path(folder))
        case = cases[m1_scenario]
        inst = build_instance(team_seed, "shift", data=case)
        return case, inst
    if preset == "toy":
        inst = toy_instance()
        if m1_scenario == "unsat":
            inst = replace(inst, A=set(inst.A) - {(1, 0)})
        return instance_to_m1_data(inst), inst
    raise ValueError(f"Unsupported preset: {preset!r}")


def parse_uploaded_schedule(inst: Instance, raw_bytes: bytes) -> frozenset[tuple[int, int]]:
    """Validate a dense M2 schedule CSV (invigilator_id,session_id,assigned) against inst."""
    if not isinstance(raw_bytes, (bytes, bytearray)) or not bytes(raw_bytes).strip():
        raise ValueError("Uploaded schedule CSV is empty")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "uploaded_schedule.csv"
        path.write_bytes(bytes(raw_bytes))
        return read_schedule(inst, path)


def week_options(inst: Instance) -> list[dict]:
    """Calendar 7-day block descriptors aligned with M4's week_layout."""
    starts, days, index = week_layout(inst)
    counts = Counter(index)
    rows = []
    for k, (start, span) in enumerate(zip(starts, days)):
        end = start + timedelta(days=int(span) - 1)
        rows.append({
            "week": k + 1,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": int(span),
            "sessions": counts[k],
            "label": f"Week {k + 1} ({start.isoformat()} to {end.isoformat()}, {int(span)}d)",
        })
    return rows


def weekly_assignment_rows(
    inst: Instance,
    assigned,
    *,
    week: int | None = None,
    campus: str | None = None,
) -> list[dict]:
    """Session-level weekly assignment table sorted chronologically."""
    starts, _, week_index = week_layout(inst)
    if week is not None and not (1 <= week <= len(starts)):
        raise ValueError(f"week must be in 1..{len(starts)} or None")
    if campus not in (None, "All", "CS1", "CS2"):
        raise ValueError("campus filter must be None, 'All', 'CS1' or 'CS2'")
    by_session: dict[int, list[str]] = {j: [] for j in range(len(inst.session_names))}
    for i, j in sorted(set(assigned)):
        by_session[j].append(inst.staff_ids[i])
    order = sorted(
        range(len(inst.session_names)),
        key=lambda j: (inst.intervals[j][0], inst.campus[j], inst.session_names[j]),
    )
    rows = []
    for j in order:
        wk = week_index[j] + 1
        if week is not None and wk != week:
            continue
        if campus in ("CS1", "CS2") and inst.campus[j] != campus:
            continue
        start, end = inst.intervals[j]
        staff_list = by_session[j]
        demand = inst.demand[j]
        rows.append({
            "week": wk,
            "date": start.date().isoformat(),
            "time": f"{start:%H:%M}-{end:%H:%M}",
            "class": session_symbol(start),
            "session_id": inst.session_names[j],
            "campus": inst.campus[j],
            "demand": demand,
            "assigned": len(staff_list),
            "status": "OK" if len(staff_list) == demand else f"{len(staff_list)}/{demand}",
            "invigilators": ", ".join(staff_list),
        })
    return rows


def staff_workload_rows(inst: Instance, assigned) -> list[dict]:
    """Per-invigilator total, campus and weekly load summary."""
    starts, _, week_index = week_layout(inst)
    pairs = set(assigned)
    total = Counter(i for i, _ in pairs)
    cs1 = Counter(i for i, j in pairs if inst.campus[j] == "CS1")
    cs2 = Counter(i for i, j in pairs if inst.campus[j] == "CS2")
    by_week = Counter((i, week_index[j]) for i, j in pairs)
    mean_load = sum(inst.demand) / len(inst.staff_ids)
    rows = []
    for i, person in enumerate(inst.staff_ids):
        row = {
            "staff_id": person,
            "preference": inst.preferences[i],
            "total_load": total[i],
            "cs1_load": cs1[i],
            "cs2_load": cs2[i],
            "abs_deviation": round(abs(total[i] - mean_load), 4),
        }
        for k in range(len(starts)):
            row[f"W{k + 1}"] = by_week[i, k]
        rows.append(row)
    return rows
