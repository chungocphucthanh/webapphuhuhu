"""Checks for the autograder outputs and reproducibility (req 2.7)."""

import csv
import hashlib
import json

import pytest

import m2_ilp.run as run
from m2_ilp.instance import build_instance
from m2_ilp.metrics import compute_metrics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_runs_write_identical_files(tmp_path):
    seed = build_instance().seed
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir(), second.mkdir()
    metrics = run.run_m2(seed, out_dir=first, extras=False)
    run.run_m2(seed, out_dir=second, extras=False)
    for name in ("schedule.csv", "metrics.json"):
        assert sha(first / name) == sha(second / name)

    raw = (first / "schedule.csv").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    with (first / "schedule.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["invigilator_id", "session_id", "assigned"]
    inst = build_instance()
    assert len(rows) - 1 == len(inst.staff_ids) * len(inst.session_names) == 6059
    assert [r[:2] for r in rows[1:3]] == [["CB001", inst.session_names[0]],
                                          ["CB001", inst.session_names[1]]]
    assigned = {(inst.staff_ids.index(p), inst.session_names.index(s))
                for p, s, flag in rows[1:] if flag == "1"}
    assert {flag for p, s, flag in rows[1:]} == {"0", "1"} and len(assigned) == 769

    text = (first / "metrics.json").read_text(encoding="utf-8")
    stored = json.loads(text)
    assert text.endswith("}\n") and list(stored) == sorted(stored)
    assert stored == {k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()}
    assert stored["beats_baseline"] is True and stored["baseline_max_load"] == 19
    assert stored["max_load"] == stored["t_star"] < 19
    assert compute_metrics(inst, assigned, stored["fatigue_k"])["l1"] == pytest.approx(stored["l1"])


def test_nothing_is_written_when_the_validator_objects(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "check_schedule", lambda inst, assigned: ["H3: forced failure"])
    with pytest.raises(RuntimeError, match="forced failure"):
        run.run_m2(build_instance().seed, out_dir=tmp_path, extras=False)
    assert list(tmp_path.iterdir()) == []
