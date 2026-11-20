"""Product and minimization of complete DFAs (M3, requirement 3.2).

`product` builds the reachable product of complete DFAs, accepting iff every factor accepts.
`minimize` removes unreachable states, then refines the partition {accepting, rejecting} until
no block splits (Moore / Myhill-Nerode). `counts_table` reports the state counts used in 3.2.md.

Run from the repository root: python -m m3_automata.product_min
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from m3_automata.dfa import DFA
from m3_automata.rules import RULE_FILES

M3_DIR = Path(__file__).resolve().parent


def product(machines) -> DFA:
    """Reachable product; a state is named 'p|q|...' after its components."""
    machines = list(machines)
    alphabet = machines[0].alphabet
    if any(m.alphabet != alphabet for m in machines):
        raise ValueError("every factor must use the same alphabet")
    start = tuple(m.start for m in machines)
    order, rows, queue = [start], {}, deque([start])
    seen = {start}
    while queue:
        state = queue.popleft()
        rows[state] = {}
        for a in alphabet:
            target = tuple(m.transitions[q][a] for m, q in zip(machines, state))
            rows[state][a] = target
            if target not in seen:
                seen.add(target)
                order.append(target)
                queue.append(target)
    name = "|".join
    accepting = [name(s) for s in order if all(q in m.accepting for m, q in zip(machines, s))]
    return DFA([name(s) for s in order], alphabet, name(start), accepting,
               {name(s): {a: name(t) for a, t in row.items()} for s, row in rows.items()})


def minimize(dfa) -> DFA:
    """Minimal complete DFA of L(dfa); the trap block, if any, is named 'dead'."""
    states = dfa.reachable_states()
    block = {q: int(q in dfa.accepting) for q in states}
    count = len(set(block.values()))
    while True:
        signature = {q: (block[q],) + tuple(block[dfa.transitions[q][a]] for a in dfa.alphabet)
                     for q in states}
        ids = {}
        refined = {q: ids.setdefault(signature[q], len(ids)) for q in states}
        if len(ids) == count:
            break
        block, count = refined, len(ids)
    rep = {}
    for q in states:
        rep.setdefault(block[q], q)
    start = block[dfa.start]
    order, queue = [start], deque([start])
    while queue:
        b = queue.popleft()
        for a in dfa.alphabet:
            target = block[dfa.transitions[rep[b]][a]]
            if target not in order:
                order.append(target)
                queue.append(target)
    accepting = {b for b in order if rep[b] in dfa.accepting}
    traps = [b for b in order if b not in accepting
             and all(block[dfa.transitions[rep[b]][a]] == b for a in dfa.alphabet)]
    label = {b: f"m{k}" for k, b in enumerate(order)}
    if len(traps) == 1:
        label[traps[0]] = "dead"
    return DFA([label[b] for b in order], dfa.alphabet, label[start],
               [label[b] for b in order if b in accepting],
               {label[b]: {a: label[block[dfa.transitions[rep[b]][a]]] for a in dfa.alphabet}
                for b in order})


def load_rule(name) -> DFA:
    return DFA.load(M3_DIR / RULE_FILES[name])


def counts_table(names=("R1", "R2", "R3", "R4")):
    """Rows (label, reachable, minimal) for each rule and for the products R1xR2, R1xR2xR3, ...

    Rules whose JSON file is missing are skipped, so the table grows as the files are merged.
    """
    machines = {n: load_rule(n) for n in names if (M3_DIR / RULE_FILES[n]).exists()}
    rows = []
    for n, m in machines.items():
        rows.append((n, len(m.reachable_states()), len(minimize(m).states)))
    keys = list(machines)
    for k in range(2, len(keys) + 1):
        full = product([machines[n] for n in keys[:k]])
        rows.append((" x ".join(keys[:k]), len(full.states), len(minimize(full).states)))
    return rows


def write_minimization(path=None):
    """Write the R1 x R2 x R3 counts (reachable product, minimal) to minimization.json."""
    full = product([load_rule(n) for n in ("R1", "R2", "R3")])
    counts = {"product_states": len(full.states), "minimized_states": len(minimize(full).states)}
    path = Path(path or M3_DIR / "minimization.json")
    path.write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return counts


def main():
    print(f"{'automaton':<20}{'reachable':>10}{'minimal':>9}")
    for label, reachable, minimal in counts_table():
        print(f"{label:<20}{reachable:>10}{minimal:>9}")


if __name__ == "__main__":
    main()
