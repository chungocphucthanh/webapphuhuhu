"""TV5: export a CSV slice and return seeded scenarios and a toy example as dictionaries."""

import argparse
import csv
import hashlib
from pathlib import Path
from random import Random

from .data_loader import DEFAULT_PATH, PROJECT_FOLDER, load_dataset


def prepare_instances(seed, output_dir=PROJECT_FOLDER / "data" / "m1_cases"):
    """Write only real_slice.csv; return sat, unsat and toy input dictionaries."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Seed must be an integer")
    rng = Random(seed)
    full = load_dataset()
    demand = dict.fromkeys(full["shift_ids"], 0)
    intervals = {}
    for j, (code, campus) in enumerate(full["session_ids"]):
        demand[code] += full["shift_demands"][j]
        intervals[code] = full["intervals"][j]

    # Small whole shifts retain every campus and its full original capacity.
    candidates = sorted(code for code in demand if 0 < demand[code] <= 6)
    multicampus = [code for code in candidates
                  if sum(key[0] == code for key in full["session_ids"]) > 1]
    if not multicampus:
        raise ValueError("No small multi-campus shift exists for this selection rule")
    chosen = [rng.choice(multicampus)]
    remaining = [code for code in candidates if code not in chosen]
    rng.shuffle(remaining)
    for code in remaining:
        start, end = intervals[code]
        if all(end <= intervals[other][0] or intervals[other][1] <= start for other in chosen):
            chosen.append(code)
        if len(chosen) == 3:
            break
    if len(chosen) != 3:
        raise ValueError("Need three non-overlapping shift codes for this small example")
    chosen.sort()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    slice_path = output_dir / "real_slice.csv"
    if slice_path.resolve() == DEFAULT_PATH.resolve():
        raise ValueError("The slice must not overwrite the source dataset")
    with DEFAULT_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames
        source_rows = list(reader)
    row_numbers = [i + 2 for i, row in enumerate(source_rows)
                   if row["MS Ca thi"].strip() in chosen]
    with slice_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(source_rows[i - 2] for i in row_numbers)
    data = load_dataset(slice_path)
    people = list(range(len(data["staff_ids"])))

    # Per shift, select at least its total demand as available. Baseline is not fixed.
    available = {}
    for s, code in enumerate(data["shift_ids"]):
        count = rng.randint(demand[code], len(people))
        available[s] = sorted(rng.sample(people, count))
    sat_busy = [(i, s) for i in people for s in range(len(data["shift_ids"]))
                if i not in available[s]]
    # The second scenario keeps the same people/capacity but makes one shift short by one.
    blocked_shift = rng.randrange(len(data["shift_ids"]))
    blocked_code = data["shift_ids"][blocked_shift]
    kept = rng.sample(available[blocked_shift], demand[blocked_code] - 1)
    unsat_busy = sorted(set(sat_busy) | {(i, blocked_shift) for i in people if i not in kept})

    description = {
        "source": "data/" + DEFAULT_PATH.name,
        "source_text_sha256": hashlib.sha256(
            DEFAULT_PATH.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest(),
        "source_hash_rule": "UTF-8 text without BOM, with line endings normalized to LF.",
        "source_csv_rows": row_numbers,
        "selected_shift_codes": chosen,
        "selection": "Random(seed) selects three whole shift codes with total demand <=6; "
                     "one spans campuses. Different selected codes do not overlap in time. "
                     "Keep all source rows and their staff; never reduce capacity.",
        "busy_rule": "On sorted staff and shift IDs, the same RNG selects a uniform integer "
                     "available count from total demand through staff count, then samples "
                     "that many staff. Everyone else is Busy at all campuses of that code. "
                     "This controlled test rule is a team choice, not a teacher-set rate.",
        "unsat_change": "The same RNG selects one shift and keeps only demand-1 of its "
                        "available staff. All other input and Busy pairs remain unchanged.",
        "eligibility": "None; all roles are pooled as invigilators.",
        "overlap": "Strict time intersection; touching endpoints are allowed; no travel buffer.",
        "indices": "Zero-based; Assign(i,j) = i*M+j+1. Higher IDs are CNF auxiliaries.",
    }
    common = {
        "seed": seed, "slice_description": description,
        "staff_ids": data["staff_ids"], "shift_ids": data["shift_ids"],
        "session_ids": data["session_ids"],
        "session_labels": [code + "_" + campus for code, campus in data["session_ids"]],
        "shift_demands": data["shift_demands"],
        "intervals": [[start.isoformat(), end.isoformat()] for start, end in data["intervals"]],
        "baseline": data["baseline"], "overlaps": data["overlaps"],
    }
    shift_index = {code: s for s, code in enumerate(data["shift_ids"])}
    cases = {}
    for name, busy_shifts in (("sat", sat_busy), ("unsat", unsat_busy)):
        lookup = set(busy_shifts)
        case = dict(common)
        case["busy_by_shift"] = busy_shifts
        case["busy"] = [(i, j) for i in people for j, (code, campus) in enumerate(data["session_ids"])
                        if (i, shift_index[code]) in lookup]
        if name == "unsat":
            case["shortage_shift"] = blocked_code
            case["available_at_shortage"] = len(kept)
            case["demand_at_shortage"] = demand[blocked_code]
        cases[name] = case

    toy = {
        "description": "Hand-checkable example: three staff, two non-overlapping sessions, "
                       "two required per session. CB1 is busy in the morning. "
                       "The UNSAT variant also makes CB2 busy in the morning.",
        "staff_ids": ["CB1", "CB2", "CB3"],
        "session_ids": [["Morning", "CS1"], ["Afternoon", "CS1"]],
        "shift_demands": [2, 2], "overlaps": [], "busy": [(0, 0)],
        "unsat_busy": [(0, 0), (1, 0)],
    }
    cases["toy"] = toy
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    seed = args.seed
    if seed is None:
        seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    cases = prepare_instances(seed)
    print(f"Wrote data/m1_cases/real_slice.csv with seed {seed}. No JSON files are written.")
    print("TV4: import prepare_instances(seed) to obtain sat, unsat and toy input dictionaries.")
    for name, case in cases.items():
        print(f"{name}: {len(case['staff_ids'])} staff, {len(case['session_ids'])} sessions, "
              f"demand={case['shift_demands']}, {len(case['busy'])} Busy pairs")
