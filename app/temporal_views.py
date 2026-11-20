"""Automaton-based temporal validity audit and roster string trace (M5, Phuc)."""

from __future__ import annotations

from datetime import datetime, timedelta

from m2_ilp.instance import Instance
from m2_ilp.validate import check_schedule
from m3_automata import rules as m3_rules
from m3_automata.dfa import DFA
from m3_automata.encode_strings import SYMBOL_BY_START, day_symbol
from m3_automata.product_min import counts_table, minimize, product
from m3_automata.regular_to_ilp import load_rules, violations


def _session_symbol(start: datetime) -> str:
    """Map session start timestamp to M, A or N, with hour fallback for custom CSVs."""
    key = f"{start:%H}g{start:%M}"
    if key in SYMBOL_BY_START:
        return SYMBOL_BY_START[key]
    if start.hour < 12:
        return "M"
    if start.hour < 17:
        return "A"
    return "N"


def build_roster_strings(inst: Instance, assigned) -> tuple[list, dict[str, str]]:
    """Build full calendar span and one daily string over {M, A, N, -} per staff member."""
    first, last = min(inst.day), max(inst.day)
    days = [first + timedelta(days=k) for k in range((last - first).days + 1)]
    day_index = {d: t for t, d in enumerate(days)}
    classes = [_session_symbol(start) for start, _ in inst.intervals]
    worked: dict[tuple[int, int], set[str]] = {}
    for i, j in set(assigned):
        worked.setdefault((i, day_index[inst.day[j]]), set()).add(classes[j])
    strings = {
        person: "".join(day_symbol(worked.get((i, t), ())) for t in range(len(days)))
        for i, person in enumerate(inst.staff_ids)
    }
    return days, strings


def load_automata_suite() -> dict:
    """Load submitted DFAs R1-R3, their minimal product R1xR2xR3, and R4 (c=3)."""
    graded = load_rules()
    full_prod = product(list(graded.values()))
    min_prod = minimize(full_prod)
    r4_dfa = (
        DFA.load(m3_rules.Path(m3_rules.__file__).resolve().parent / m3_rules.RULE_FILES["R4"])
        if (m3_rules.Path(m3_rules.__file__).resolve().parent / m3_rules.RULE_FILES["R4"]).is_file()
        else m3_rules.r4(3)
    )
    return {
        "rules": graded,
        "product": full_prod,
        "minimal": min_prod,
        "r4": r4_dfa,
        "counts_table": counts_table(),
    }


def trace_word(dfa: DFA, word: str) -> dict:
    """Run word step by step on dfa and identify the first day entering a trap state."""
    traps = set(dfa.trap_states())
    q = dfa.start
    states = [q]
    first_violation_day = None
    for idx, symbol in enumerate(word, start=1):
        q = dfa.transitions[q][symbol]
        states.append(q)
        if first_violation_day is None and q in traps:
            first_violation_day = idx
    accepted = q in dfa.accepting
    if not accepted and first_violation_day is None:
        first_violation_day = len(word)
    return {
        "accepted": accepted,
        "final_state": q,
        "states": states,
        "first_violation_day": first_violation_day,
    }


def evaluate_temporal_validity(
    inst: Instance,
    assigned,
    suite: dict | None = None,
) -> dict:
    """Compute the 'schedule valid (DFA-accepted)' flag, rule counts and per-staff traces."""
    suite = load_automata_suite() if suite is None else suite
    days, strings = build_roster_strings(inst, assigned)
    hard_issues = check_schedule(inst, assigned)
    graded = suite["rules"]
    minimal = suite["minimal"]
    r4_dfa = suite["r4"]

    rule_counts = violations(strings, graded)
    r4_info = m3_rules.r4_counts(strings, c=3)
    dfa_accepted_all = rule_counts["any"] == 0

    staff_rows = []
    for person in inst.staff_ids:
        word = strings[person]
        r1_ok = graded["R1"].accepts(word)
        r2_ok = graded["R2"].accepts(word)
        r3_ok = graded["R3"].accepts(word)
        r4_ok = r4_dfa.accepts(word)
        trace = trace_word(minimal, word)
        broken = [
            name for name, ok in (("R1", r1_ok), ("R2", r2_ok), ("R3", r3_ok)) if not ok
        ]
        v_day = trace["first_violation_day"]
        staff_rows.append({
            "staff_id": person,
            "roster_string": word,
            "work_days": sum(ch != "-" for ch in word),
            "M": word.count("M"),
            "A": word.count("A"),
            "N": word.count("N"),
            "R1_ok": r1_ok,
            "R2_ok": r2_ok,
            "R3_ok": r3_ok,
            "R4_ok": r4_ok,
            "dfa_accepted": trace["accepted"],
            "broken_rules": ", ".join(broken) if broken else "None",
            "first_violation_day": v_day,
            "first_violation_date": days[v_day - 1].isoformat() if v_day else None,
        })

    return {
        "schedule_valid": len(hard_issues) == 0 and dfa_accepted_all,
        "dfa_accepted_all": dfa_accepted_all,
        "hard_violations": hard_issues,
        "total_staff": len(inst.staff_ids),
        "accepted_count": rule_counts["accepted"],
        "rejected_count": rule_counts["any"],
        "calendar_days": len(days),
        "rule_violations": {
            **rule_counts,
            "R4_prefix": r4_info["prefix_rejected"],
            "R4_end": r4_info["end_rejected"],
        },
        "state_counts": [
            {"automaton": label, "reachable_states": reach, "minimal_states": mini}
            for label, reach, mini in suite["counts_table"]
        ],
        "staff_rows": staff_rows,
    }


def compare_temporal_schedules(
    inst: Instance,
    schedules: dict[str, object],
    suite: dict | None = None,
) -> list[dict]:
    """Compare DFA temporal validity across multiple named schedules on inst."""
    suite = load_automata_suite() if suite is None else suite
    rows = []
    for label, pairs in schedules.items():
        audit = evaluate_temporal_validity(inst, pairs, suite=suite)
        rv = audit["rule_violations"]
        rows.append({
            "schedule": label,
            "schedule_valid": audit["schedule_valid"],
            "dfa_accepted": f"{audit['accepted_count']}/{audit['total_staff']}",
            "rejected": audit["rejected_count"],
            "R1_violations": rv["R1"],
            "R2_violations": rv["R2"],
            "R3_violations": rv["R3"],
            "R4_prefix_violations": rv["R4_prefix"],
        })
    return rows


def staff_daily_trace_rows(
    inst: Instance,
    assigned,
    staff_id: str,
    suite: dict | None = None,
) -> list[dict]:
    """Return day-by-day state transitions for one invigilator across R1, R2, R3 and product."""
    if staff_id not in inst.staff_ids:
        raise ValueError(f"Unknown staff_id: {staff_id!r}")
    suite = load_automata_suite() if suite is None else suite
    days, strings = build_roster_strings(inst, assigned)
    word = strings[staff_id]
    traces = {
        "R1": trace_word(suite["rules"]["R1"], word)["states"],
        "R2": trace_word(suite["rules"]["R2"], word)["states"],
        "R3": trace_word(suite["rules"]["R3"], word)["states"],
        "R1xR2xR3": trace_word(suite["minimal"], word)["states"],
    }
    return [
        {
            "day_index": idx + 1,
            "date": days[idx].isoformat(),
            "symbol": word[idx],
            "R1_state": traces["R1"][idx + 1],
            "R2_state": traces["R2"][idx + 1],
            "R3_state": traces["R3"][idx + 1],
            "product_state": traces["R1xR2xR3"][idx + 1],
        }
        for idx in range(len(word))
    ]
