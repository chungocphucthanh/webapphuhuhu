"""Checks for product and minimization (Nguyen, req 3.2).

Run from the repository root: python -m pytest m3_automata/tests/test_product_min.py
"""

from itertools import product as all_words
from random import Random

import pytest

from m3_automata.dfa import ALPHABET
from m3_automata.product_min import M3_DIR, RULE_FILES, counts_table, load_rule, minimize, product

NAMES = tuple(n for n in RULE_FILES if (M3_DIR / RULE_FILES[n]).exists())  # R4 once merged


def words():
    for n in range(8):
        yield from ("".join(w) for w in all_words(ALPHABET, repeat=n))
    rng = Random(0)
    for _ in range(2000):
        yield "".join(rng.choice(ALPHABET) for _ in range(rng.randint(8, 40)))


def table_filling(dfa):
    """Number of Myhill-Nerode classes by marking distinguishable pairs (second algorithm)."""
    states = dfa.reachable_states()
    pairs = {frozenset((p, q)) for p in states for q in states if p != q}
    marked = {s for s in pairs if len({p in dfa.accepting for p in s}) == 2}
    changed = True
    while changed:
        changed = False
        for s in pairs - marked:
            p, q = tuple(s)
            if any(frozenset((dfa.transitions[p][a], dfa.transitions[q][a])) in marked
                   for a in ALPHABET):
                marked.add(s)
                changed = True
    parent = {q: q for q in states}

    def find(q):
        while parent[q] != q:
            q = parent[q]
        return q
    for s in pairs - marked:
        p, q = tuple(s)
        parent[find(p)] = find(q)
    return len({find(q) for q in states})


@pytest.fixture(scope="module")
def rules():
    return {n: load_rule(n) for n in NAMES}


def chains():
    return [c for c in [("R1", "R2"), ("R1", "R2", "R3"), ("R1", "R2", "R3", "R4")]
            if set(c) <= set(NAMES)]


@pytest.mark.parametrize("chosen", chains())
def test_product_is_conjunction(rules, chosen):
    machine = product([rules[n] for n in chosen])
    for w in words():
        assert machine.accepts(w) == all(rules[n].accepts(w) for n in chosen)


@pytest.mark.parametrize("chosen", [("R1",), ("R3",)] + chains())
def test_minimal_dfa(rules, chosen):
    full = product([rules[n] for n in chosen])
    small = minimize(full)
    if len(full.states) <= 300:  # the pair table of the 2,072-state product is too slow
        assert len(small.states) == table_filling(full)
    assert table_filling(small) == len(small.states)
    for w in words():
        assert small.accepts(w) == full.accepts(w)


def test_counts():
    rows = dict((label, (r, m)) for label, r, m in counts_table())
    assert rows["R1"] == (4, 4) and rows["R2"] == (3, 3) and rows["R3"] == (58, 36)
    assert rows["R1 x R2"] == (11, 4) and rows["R1 x R2 x R3"] == (259, 15)
    if "R4" in NAMES:
        assert rows["R4"] == (8, 8) and rows["R1 x R2 x R3 x R4"] == (2072, 99)
