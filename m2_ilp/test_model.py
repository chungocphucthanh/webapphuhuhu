"""Checks for model assembly and ModelConfig (Lead, req 2.7)."""

from dataclasses import FrozenInstanceError, replace

import pytest

from m2_ilp.config import ModelConfig
from m2_ilp.instance import build_instance, toy_instance
from m2_ilp.model import build_model, family

FAMILIES = {"x", "t", "dev", "s", "z", "v", "u",
            "H2", "H3", "MAX", "TCAP", "DEVP", "DEVN", "DEVC", "FAT", "TRVZ", "TRV"}


def test_config_is_frozen_and_validated():
    config = ModelConfig()
    with pytest.raises(FrozenInstanceError):
        config.stage = 2
    assert replace(config, stage=2, t_cap=11).t_cap == 11
    for bad in ({"stage": 3}, {"fatigue_k": -1}, {"use_soft": 1}, {"weight_scale": (1, 1)}):
        with pytest.raises(ValueError):
            ModelConfig(**bad)
    assert config.lambdas(toy_instance()) == tuple(toy_instance().soft_weights)


def test_toy_families_per_stage():
    toy = toy_instance()
    prob, x, handles = build_model(toy, ModelConfig())
    assert handles.n_vars == {"t": 1, "x": 5}
    assert handles.n_rows == {"H3": 2, "MAX": 3}
    assert handles.dev == {} and handles.l1 is None and handles.soft is None
    prob, x, handles = build_model(toy, ModelConfig(stage=2, t_cap=2))
    assert handles.n_vars == {"dev": 3, "t": 1, "x": 5}
    assert handles.n_rows == {"DEVC": 3, "DEVN": 3, "DEVP": 3, "H3": 2, "MAX": 3, "TCAP": 1}
    assert set(handles.soft_terms) == {"location", "fatigue", "travel"}


def test_use_soft_false_and_elastic_change_only_their_families():
    inst = build_instance()
    with_soft = build_model(inst, ModelConfig(stage=2, t_cap=11))[2]
    without = build_model(inst, ModelConfig(stage=2, t_cap=11, use_soft=False))[2]
    assert without.soft_terms is None and without.soft is None
    assert {k: v for k, v in with_soft.n_rows.items() if k not in ("FAT", "TRV", "TRVZ")} \
        == without.n_rows
    elastic = build_model(inst, ModelConfig(elastic=True))[2]
    assert elastic.n_vars["u"] == 83 and len(elastic.slack) == 83


def test_every_name_follows_the_family_convention():
    inst = build_instance()
    prob, x, handles = build_model(inst, ModelConfig(stage=2, t_cap=11, elastic=True))
    assert {family(v.name) for v in prob.variables()} <= FAMILIES
    assert {family(name) for name in prob.constraints} <= FAMILIES
    assert handles.n_vars["x"] == len(x) == len(inst.A)
    assert handles.h2_pairwise == handles.n_rows["H2"] == 642
    assert len(handles.cliques) == 18
