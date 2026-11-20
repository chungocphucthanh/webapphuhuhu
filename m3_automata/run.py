"""M3 entry point for run_all.py (req 3.1-3.4).

python run_all.py --seed $(cat data/seed.txt) --stage m3
Rebuilds the DFA JSON files and minimization.json, prints the rule violations on the encoded rosters and the
product/minimization counts, then runs the regular-constraint ILP (3.3).
"""

from m3_automata import rules
from m3_automata.encode_strings import encode_strings
from m3_automata.product_min import counts_table, write_minimization
from m3_automata.regular_to_ilp import run_m3_ilp, violations, load_rules


def run_m3(seed: int) -> None:
    rules.main()
    print(f"[m3] minimization.json: {write_minimization()}")
    strings = encode_strings()
    print(f"[m3] R1-R3 violations on {len(strings)} baseline strings: {violations(strings, load_rules())}")
    print(f"[m3] R4 c=3: {rules.r4_counts(strings)}")
    print(f"{'automaton':<20}{'reachable':>10}{'minimal':>9}")
    for label, reachable, minimal in counts_table():
        print(f"{label:<20}{reachable:>10}{minimal:>9}")
    run_m3_ilp(seed)
