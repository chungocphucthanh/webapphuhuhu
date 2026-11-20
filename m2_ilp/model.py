"""Assemble the M2 ILP from the four builders (Lead, req 2.7).

Order is fixed: create_variables (TV1) -> add_hard_constraints (TV2)
-> add_soft_terms (TV5, stage 2 with use_soft only) -> add_objective (TV4).
"""

from __future__ import annotations

import contextlib
import io
from collections import Counter
from dataclasses import dataclass

import pulp

from .hard import add_hard_constraints
from .objective import add_objective
from .soft import add_soft_terms
from .variables import create_variables


@dataclass
class ModelHandles:
    w: dict
    t: pulp.LpVariable
    dev: dict
    l1: object
    soft_terms: dict | None
    soft: object
    slack: dict
    cliques: list
    n_vars: dict
    n_rows: dict
    h2_pairwise: int


def family(name: str) -> str:
    """Variable or row family: the text before the first '_'."""
    return name.split("_", 1)[0]


def build_model(inst, config):
    """Return (prob, x, handles) for config.stage. Stage 2 requires config.t_cap."""
    if config.stage == 2 and config.t_cap is None:
        raise ValueError("Stage 2 needs t_cap, the stage-1 optimum t*")
    prob = pulp.LpProblem(f"m2_stage{config.stage}", pulp.LpMinimize)
    with contextlib.redirect_stdout(io.StringIO()) as log:
        x, w = create_variables(prob, inst, config)
    if config.msg:
        print(log.getvalue(), end="")
    hard = add_hard_constraints(prob, x, inst, config)
    soft_terms = None
    if config.stage == 2 and config.use_soft:
        soft_terms = add_soft_terms(prob, x, inst, config)
    objective = add_objective(prob, x, w, inst, config, soft_terms, hard["slack"])
    n_vars = dict(sorted(Counter(family(v.name) for v in prob.variables()
                                 if v.name != "__dummy").items()))
    n_rows = dict(sorted(Counter(family(name) for name in prob.constraints).items()))
    handles = ModelHandles(
        w=w, t=objective["t"], dev=objective["dev"], l1=objective["l1"],
        soft_terms=soft_terms, soft=objective["soft"], slack=hard["slack"],
        cliques=hard["cliques"], n_vars=n_vars, n_rows=n_rows,
        h2_pairwise=hard["rows"]["H2_pairwise"],
    )
    return prob, x, handles
