"""Two-stage lexicographic solve with PuLP + CBC (Lead, req 2.7; decisions D2, D5).

Stage 1 finds t* = min max_i w_i. Stage 2 keeps t <= t* and minimises L1 plus the weighted
soft penalties. One CBC thread and gapRel = 0 make runs reproducible on one machine.
"""

from __future__ import annotations

import math
import re
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path

import pulp

from .config import ModelConfig
from .model import build_model


@dataclass
class StageResult:
    status: str
    objective: float | None
    runtime: float
    gap: float | None
    nodes: int | None = None


@dataclass
class Solution:
    status: str
    assigned: frozenset
    t_star: int | None
    objective: dict
    stages: dict
    diagnosis: list | None


STATUS = {pulp.LpSolutionOptimal: "optimal", pulp.LpSolutionIntegerFeasible: "feasible",
          pulp.LpSolutionInfeasible: "infeasible"}


def _read_gap(log_text, status):
    """CBC prints 'Gap: g' when it stops early; an optimal run has gap 0."""
    match = re.search(r"^Gap:\s+([-+0-9.eE]+)", log_text, re.MULTILINE)
    if match:
        return float(match.group(1))
    return 0.0 if status == "optimal" else None


def _read_nodes(log_text):
    match = re.search(r"^Enumerated nodes:\s+(\d+)", log_text, re.MULTILINE)
    return int(match.group(1)) if match else None


def run_cbc(prob: pulp.LpProblem, config: ModelConfig) -> StageResult:
    """Solve prob with CBC; the status comes from prob.sol_status (1 optimal, 2 feasible)."""
    with tempfile.TemporaryDirectory() as folder:
        log_path = Path(folder) / "cbc.log"
        solver = pulp.PULP_CBC_CMD(msg=config.msg, timeLimit=config.time_limit,
                                   gapRel=config.gap_rel, threads=config.threads,
                                   logPath=None if config.msg else str(log_path))
        start = time.perf_counter()
        prob.solve(solver)
        runtime = time.perf_counter() - start
        log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
    status = STATUS.get(prob.sol_status, "not_solved")
    objective = pulp.value(prob.objective) if status in ("optimal", "feasible") else None
    return StageResult(status, objective, runtime, _read_gap(log_text, status), _read_nodes(log_text))


def _value(expression):
    return 0.0 if expression is None else float(pulp.value(expression) or 0.0)


def solve(inst, config: ModelConfig = ModelConfig()) -> Solution:
    """Run both stages; config.stage and config.t_cap are ignored."""
    if config.relax_integrality:
        raise ValueError("solve() is the integer model; use build_model + run_cbc for LP bounds")
    prob1, x1, h1 = build_model(inst, replace(config, stage=1, t_cap=None))
    stage1 = run_cbc(prob1, config)
    if stage1.status in ("infeasible", "not_solved"):
        from .tuning import diagnose

        print(f"[m2] stage 1 is {stage1.status}; running the elastic-capacity diagnosis")
        diagnosis = diagnose(inst, config)
        for row in diagnosis:
            print(f"  {row['session']}: demand {row['demand']}, missing {row['missing']:g}")
        return Solution(stage1.status, frozenset(), None, {}, {1: stage1}, diagnosis)

    t_star = round(pulp.value(h1.t))
    if not math.isclose(pulp.value(h1.t), t_star, abs_tol=1e-6):
        raise RuntimeError(f"Stage 1 returned a fractional max load {pulp.value(h1.t)}")
    prob2, x2, h2 = build_model(inst, replace(config, stage=2, t_cap=t_star))
    stage2 = run_cbc(prob2, config)
    stages = {1: stage1, 2: stage2}
    if stage2.status in ("optimal", "feasible"):
        x, handles, status = x2, h2, stage2.status
        if status == "feasible":
            print(f"[m2] stage 2 hit the time limit; keeping the incumbent (gap {stage2.gap})")
    else:
        print(f"[m2] stage 2 is {stage2.status}; falling back to the stage-1 schedule")
        x, handles, status = x1, h1, "feasible"

    assigned = frozenset(pair for pair, var in x.items()
                         if var.varValue is not None and var.varValue > 0.5)
    terms = handles.soft_terms or {}
    objective = {
        "max_load": max((_value(w) for w in handles.w.values()), default=0.0),
        "l1": _value(handles.l1),
        "location": _value(terms.get("location")),
        "fatigue": _value(terms.get("fatigue")),
        "travel": _value(terms.get("travel")),
        "total": (stage2 if x is x2 else stage1).objective,
    }
    return Solution(status, assigned, t_star, objective, stages, None)
