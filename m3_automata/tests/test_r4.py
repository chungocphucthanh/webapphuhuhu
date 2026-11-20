"""Checks for the R4 DFA (Thanh, req 3.4).

Run from the repository root: python -m pytest m3_automata/tests/test_r4.py
"""

from itertools import product
from pathlib import Path
from random import Random

import pytest

from m3_automata.dfa import ALPHABET, DFA
from m3_automata.encode_strings import encode_strings
from m3_automata.rules import r4, r4_counts


def bounded(word, c):
    """Direct predicate: |#M - #A| <= c at every prefix."""
    d = 0
    for a in word:
        d += (a == "M") - (a == "A")
        if abs(d) > c:
            return False
    return True


def words():
    for n in range(8):
        yield from ("".join(w) for w in product(ALPHABET, repeat=n))
    rng = Random(0)
    for _ in range(2000):
        yield "".join(rng.choice(ALPHABET) for _ in range(rng.randint(8, 40)))


@pytest.mark.parametrize("c", [0, 1, 2, 3, 5])
def test_dfa_equals_predicate(c):
    machine = r4(c)
    assert len(machine.states) == 2 * c + 2
    for w in words():
        assert machine.accepts(w) == bounded(w, c)


def test_json_is_current():
    path = Path(__file__).resolve().parents[1] / "extra" / "dfa_R4.json"
    assert DFA.load(path).to_dict() == r4(3).to_dict()


def test_baseline_counts():
    assert r4_counts(encode_strings()) == {
        "total": 73, "c": 3, "prefix_rejected": 20, "end_rejected": 19}
