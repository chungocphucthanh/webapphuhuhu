import csv
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parent.parent
DEFAULT_PATH = PROJECT_FOLDER / "data" / "Dataset_Anonymized_Invigilator_Assignment_Problem.xlsx - Sheet1.csv"
STAFF_COLUMN = "MS của CÁN BỘ COI THI"
# Infer campus from the duty prefix and check it against the dataset campus label.
CAMPUS_BY_PREFIX = {"LTK": "CS1", "DiAn": "CS2"}
ROLES = ("CBCT", "Thư ký", "Trưởng HĐ")
CAMPUS_LABEL = {"CS1": "Cơ sở 1", "CS2": "Cơ sở 2"}
REQUIRED_COLUMNS = [STAFF_COLUMN, "MS Ca thi", "Nhiệm vụ", "Ngày", "GIỜ", "Thời gian", "Cơ sở"]


def _parse_duration(text, line):
    """Convert the duration cell text to a positive finite number of minutes."""
    try:
        duration = float(text)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Row {line}: duration must be numeric") from error
    if not 0 < duration < float("inf"):
        raise ValueError("Duration must be a finite positive number of minutes")
    return duration


def _parse_interval(row, line):
    """Convert date, start time and duration to (start, end); report the row on error."""
    try:
        day = datetime.strptime(row["Ngày"].strip(), "%Y-%m-%d %H:%M:%S")
        duration = _parse_duration(row["Thời gian"], line)
        time_text = row["GIỜ"]
        if not isinstance(time_text, str):
            raise ValueError("Start time must be a string such as 07g00")
        clock = datetime.strptime(time_text.strip(), "%Hg%M").time()
        start = datetime.combine(day.date(), clock)
        end = start + timedelta(minutes=duration)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"Row {line}: invalid date, start time or duration") from error
    return (start, end)


def load_dataset(path=DEFAULT_PATH):
    """Prepare M1 input data; indices start at 0.

    staff_ids[i]: staff ID, including all roles.
    session_ids[j]: (shift code, campus); all roles count towards one capacity.
    shift_demands[j]: staff required for session j; intervals[j]: its time interval.
    capacity_by_session: (shift code, campus) -> total demand.
    shift_ids[s]: shift code, shared by sessions at different campuses.
    busy and busy_by_shift are None until a seeded scenario supplies availability.
    Baseline absence is not evidence of unavailability. No eligibility is inferred.
    baseline: (i,j) pairs; overlaps: (j,k) pairs.
    """
    try:
        handle = open(path, newline="", encoding="utf-8-sig")
    except OSError as error:
        raise ValueError(f"Cannot open dataset file: {path}") from error
    staff = set()      # I: all staff IDs, including non-invigilator roles.
    sessions = {}      # J: (shift code, campus) -> (start, end).
    shift_intervals = {}  # A shift code must have the same interval across campuses.
    assignments = set()  # Raw (person, key) baseline pairs for duplicate detection.
    source_rows = 0
    cbct_rows = 0
    with handle:
        rows = csv.DictReader(handle)
        headers = rows.fieldnames or ()
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")

        for line, row in enumerate(rows, start=2):
            if None in row:
                raise ValueError(f"Row {line}: more fields than the header row")
            if all(value in (None, "") for value in row.values()):
                continue  # Skip blank rows retained by the export.
            # DictReader leaves missing trailing fields as None; treat them as
            # empty so the row validations below report the real problem.
            row = {key: (value or "").strip() for key, value in row.items()}
            source_rows += 1

            person = row.get(STAFF_COLUMN)
            if not person:
                raise ValueError(f"Row {line}: missing staff ID")
            staff.add(person)

            duty = row.get("Nhiệm vụ") or ""
            prefix, separator, role = duty.partition("_")
            campus = CAMPUS_BY_PREFIX.get(prefix)
            if not separator or campus is None or role not in ROLES:
                raise ValueError(f"Row {line}: unsupported duty: {duty}")
            if role == "CBCT":
                cbct_rows += 1
            if row.get("Cơ sở") not in ("", CAMPUS_LABEL[campus]):
                raise ValueError(f"Row {line}: campus conflicts with the duty prefix")

            code = row.get("MS Ca thi")
            if not code:
                raise ValueError(f"Row {line}: missing shift code")
            # Include invigilators, secretaries and council heads in one capacity.
            key = (code, campus)
            interval = _parse_interval(row, line)
            if code in shift_intervals and shift_intervals[code] != interval:
                raise ValueError(f"Row {line}: shift code {code} has inconsistent time intervals")
            shift_intervals[code] = interval
            sessions[key] = interval
            # Report duplicate assignments so the source file can be checked.
            if (person, key) in assignments:
                raise ValueError(f"Row {line}: duplicate assignment for staff {person} in task {key}")
            assignments.add((person, key))

    # Sort to keep indices stable across runs.
    staff_ids = sorted(staff)
    shift_ids = sorted(shift_intervals)
    session_ids = sorted(sessions)
    staff_index = {p: i for i, p in enumerate(staff_ids)}
    session_index = {k: j for j, k in enumerate(session_ids)}
    baseline = sorted((staff_index[p], session_index[k]) for p, k in assignments)

    # Count people per session without retaining baseline as a solver constraint.
    demands = [0] * len(session_ids)
    for _, j in baseline:
        demands[j] += 1

    capacity_by_session = dict(zip(session_ids, demands))

    intervals = [sessions[k] for k in session_ids]
    # Forum d=33630: touching endpoints do not overlap; travel is a soft M2 cost.
    # ponytail: O(M^2) is sufficient here; use a sweep line for much larger datasets.
    overlaps = []
    for j in range(len(session_ids)):
        for k in range(j + 1, len(session_ids)):
            start_j, end_j = intervals[j]
            start_k, end_k = intervals[k]
            if start_j < end_k and start_k < end_j:
                overlaps.append((j, k))
    return {
        "staff_ids": staff_ids,
        "shift_ids": shift_ids,
        "session_ids": session_ids,
        "shift_demands": demands,
        "capacity_by_session": capacity_by_session,
        "intervals": intervals,
        "baseline": baseline,
        "overlaps": overlaps,
        "busy_by_shift": None,
        "busy": None,
        "source_rows": source_rows,
        "cbct_rows": cbct_rows,
    }


def precheck_feasibility(data):
    """Detect per-shift shortages; passing does not rule out cross-shift conflicts."""
    if data["busy_by_shift"] is None:
        raise ValueError("Generate a seeded Busy scenario before checking feasibility")
    busy = set(map(tuple, data["busy_by_shift"]))
    demand_by_shift = dict.fromkeys(data["shift_ids"], 0)
    for j, (code, campus) in enumerate(data["session_ids"]):
        demand_by_shift[code] += data["shift_demands"][j]
    results = {}
    for s, code in enumerate(data["shift_ids"]):
        available = sum((i, s) not in busy for i in range(len(data["staff_ids"])))
        demand = demand_by_shift[code]
        results[code] = {
            "available_staff": available,
            "total_demand": demand,
            "status": "INFEASIBLE" if available < demand else "OK",
        }
    return results


if __name__ == "__main__":
    data = load_dataset()
    print(f"Rows: {data['source_rows']}; staff: {len(data['staff_ids'])}; "
          f"shift codes: {len(data['shift_ids'])}; sessions: {len(data['session_ids'])}")
    for j, (code, campus) in enumerate(data["session_ids"]):
        start, end = data["intervals"][j]
        print(f"j={j}: {code}_{campus} | {start:%Y-%m-%d %H:%M}-{end:%H:%M} | "
              f"capacity={data['shift_demands'][j]}")
    print(f"Overlap pairs: {len(data['overlaps'])}; eligibility: not used.")
    print("Busy: not provided by CSV; run python -m m1_logic.prepare_instances.")
    assert sum(data["shift_demands"]) == data["source_rows"]
    assert all(demand > 0 for demand in data["shift_demands"])
