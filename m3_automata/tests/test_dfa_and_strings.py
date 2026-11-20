import json
import random

import pytest

from m3_automata.dfa import ALPHABET, DFA
from m3_automata.encode_strings import day_symbol, encode_strings, summary

W = ("M", "A", "N")


def r1():
    t = {"q0": {**{a: "q1" for a in W}, "-": "q0"},
         "q1": {**{a: "q2" for a in W}, "-": "q0"},
         "q2": {**{a: "dead" for a in W}, "-": "q0"},
         "dead": {a: "dead" for a in ALPHABET}}
    return DFA(["q0", "q1", "q2", "dead"], ALPHABET, "q0", ["q0", "q1", "q2"], t)


def r2():
    t = {"ok": {"M": "ok", "A": "ok", "N": "afterN", "-": "ok"},
         "afterN": {"M": "dead", "A": "dead", "N": "dead", "-": "ok"},
         "dead": {a: "dead" for a in ALPHABET}}
    return DFA(["ok", "afterN", "dead"], ALPHABET, "ok", ["ok", "afterN"], t)


def ref_r1(w):
    run = 0
    for a in w:
        run = run + 1 if a in W else 0
        if run > 2:
            return False
    return True


def ref_r2(w):
    return "N" not in w[:-1] or all(w[i + 1] == "-" for i, a in enumerate(w[:-1]) if a == "N")


def words(n=3000, seed=1):
    rng = random.Random(seed)
    return ["".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 27))) for _ in range(n)]


def test_matches_reference_on_random_strings():
    a, b = r1(), r2()
    for w in words():
        assert a.accepts(w) == ref_r1(w), w
        assert b.accepts(w) == ref_r2(w), w


def test_brief_examples():
    assert r1().accepts("WW-WW".replace("W", "M")) and not r1().accepts("MMM")
    assert r1().accepts("")


def test_json_roundtrip_and_file(tmp_path):
    d = r1()
    assert DFA.from_dict(json.loads(d.to_json())).to_dict() == d.to_dict()
    p = tmp_path / "r.json"
    d.save(p)
    e = DFA.load(p)
    assert all(e.accepts(w) == d.accepts(w) for w in words(200))
    assert set(json.loads(p.read_text())) == {"states", "alphabet", "start", "accepting", "transitions"}


def test_structure_helpers():
    assert r1().trap_states() == ["dead"] and r2().trap_states() == ["dead"]
    assert set(r1().reachable_states()) == {"q0", "q1", "q2", "dead"}


@pytest.mark.parametrize("change", [
    lambda d: d.update(start="zz"),
    lambda d: d.update(accepting=["zz"]),
    lambda d: d["transitions"]["q0"].pop("M"),
    lambda d: d["transitions"]["q0"].update(M="zz"),
    lambda d: d["transitions"].pop("dead"),
    lambda d: d.update(states=["q0", "q0", "q1", "q2", "dead"]),
    lambda d: d.update(alphabet=["M", "A", "N", "--"]),
])
def test_invalid_dfa_rejected(change):
    d = r1().to_dict()
    change(d)
    with pytest.raises(ValueError):
        DFA.from_dict(d)


def test_missing_key_and_bad_symbol():
    with pytest.raises(ValueError):
        DFA.from_dict({"states": ["q"]})
    with pytest.raises(ValueError):
        r1().accepts("MX")


def test_day_symbol_priority():
    assert day_symbol(set()) == "-"
    assert day_symbol({"M"}) == "M" and day_symbol({"M", "A"}) == "A"
    assert day_symbol({"A", "N"}) == "N" and day_symbol({"M", "N"}) == "N"
    assert day_symbol({"M", "A", "N"}) == "N"


def test_real_data_numbers():
    s = summary()
    assert (s["rows"], s["staff"], s["days"], s["person_days"]) == (769, 73, 27, 472)
    assert s["two_class_days"] == 169 and s["two_class_by_pair"] == {"AM": 168, "AN": 1}
    strings = encode_strings()
    assert set(strings) and all(len(v) == 27 and set(v) <= set(ALPHABET) for v in strings.values())


HEADER = 'Ca thi,Ngày,GIỜ,MS Ca thi,Nhiệm vụ,MS của CÁN BỘ COI THI,Thời gian,Thứ,Cơ sở\n'


def row(day, start, who):
    return f'x,2026-05-{day:02d} 00:00:00,{start},c{day}{start},LTK_CBCT,{who},150,Thứ,Cơ sở 1\n'


def test_synthetic_csv_gaps_and_two_shifts(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text(HEADER + row(18, "07g00", "P1") + row(18, "13g00", "P1") + row(21, "18g15", "P1")
                 + row(19, "09g30", "P2"), encoding="utf-8")
    s = encode_strings(p)
    assert s == {"P1": "A--N", "P2": "-M--"}


def test_unknown_start_time_rejected(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text(HEADER + row(18, "10g00", "P1"), encoding="utf-8")
    with pytest.raises(ValueError):
        encode_strings(p)
