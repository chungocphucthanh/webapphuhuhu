"""Turn the assignment CSV into one roster string per invigilator (M3, req 3.1).

Sigma = {M, A, N, -}, one symbol per day (brief 3.1). A session maps to a symbol by its
start time: 07g00 and 09g30 are M, 13g00 and 15g30 are A, 18g15 is N. A day with no
session is "-". A day with sessions of different classes keeps one symbol with the
priority N > A > M (DECISIONS.md, M3 section), so Sigma is never extended.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta

from m1_logic.data_loader import DEFAULT_PATH, STAFF_COLUMN

SYMBOL_BY_START = {"07g00": "M", "09g30": "M", "13g00": "A", "15g30": "A", "18g15": "N"}
PRIORITY = "NAM"  # most important first; the first class present on a day is kept


def read_days(path=DEFAULT_PATH):
    """Return {(person, date): set of classes} from the CSV, plus the source row count."""
    days = {}
    rows = 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for line, row in enumerate(reader, start=2):
            if all(not (v or "").strip() for v in row.values()):
                continue
            rows += 1
            person = (row.get(STAFF_COLUMN) or "").strip()
            start = (row.get("GIỜ") or "").strip()
            symbol = SYMBOL_BY_START.get(start)
            if not person or symbol is None:
                raise ValueError(f"Row {line}: cannot map staff {person!r}, start {start!r} to M/A/N")
            try:
                date = datetime.strptime((row.get("Ngày") or "").strip(), "%Y-%m-%d %H:%M:%S").date()
            except ValueError as error:
                raise ValueError(f"Row {line}: invalid date") from error
            days.setdefault((person, date), set()).add(symbol)
    return days, rows


def day_symbol(classes):
    """One symbol for a day: '-' if no session, else the highest priority N > A > M."""
    for symbol in PRIORITY:
        if symbol in classes:
            return symbol
    return "-"


def encode_strings(path=DEFAULT_PATH):
    """{person: string} over the full calendar span of the file, sorted by person ID.

    Every person gets a string of the same length (first to last day in the file, every
    calendar day included), so a day off between two sessions is a '-' and not skipped.
    """
    days, _ = read_days(path)
    dates = sorted({d for _, d in days})
    if not dates:
        raise ValueError("no assignments in the file")
    span = [dates[0] + timedelta(days=k) for k in range((dates[-1] - dates[0]).days + 1)]
    people = sorted({p for p, _ in days})
    return {p: "".join(day_symbol(days.get((p, d), ())) for d in span) for p in people}


def summary(path=DEFAULT_PATH):
    """Numbers quoted in DECISIONS.md and the report, recomputed from the file."""
    days, rows = read_days(path)
    strings = encode_strings(path)
    both = Counter("".join(sorted(c)) for c in days.values() if len(c) > 1)
    return {
        "rows": rows,
        "staff": len(strings),
        "days": len(next(iter(strings.values()))),
        "person_days": len(days),
        "two_class_days": sum(both.values()),
        "two_class_by_pair": dict(sorted(both.items())),
        "symbol_counts": dict(Counter("".join(strings.values()))),
        "staff_with_night": sum("N" in s for s in strings.values()),
    }


if __name__ == "__main__":
    for key, value in summary().items():
        print(f"{key}: {value}")
