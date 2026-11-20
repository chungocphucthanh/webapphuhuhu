"""Regular constraint -> ILP: DFA flow model linked to the M2 assignment model (M3, req 3.3).

A DFA is unfolded over the T calendar days into a layered graph: layer t holds one node
(t, q) per state and the edge (t, q) -> (t+1, delta(q, a)) carries the day symbol a. A word is
accepted iff its path from (0, q0) ends in an accepting node of layer T, so one unit of flow
turns acceptance into linear rows (see 3.3.md):

    SRC    sum_a y[0, q0, a] = 1
    FLOW   sum_a y[t, q, a] = sum_{(p, a): delta(p, a) = q} y[t-1, p, a]       t = 1..T-1
    accept no flow enters a non-accepting node of layer T (those edges get no variable)
    LINK   sum_q y[t, q, a] = s[t, a]                                     s = day symbol

M2 has x[i, j] per (staff, session) instead of a day symbol, so add_rules_to_m2 adds, for every
staff member i:

    u[i,t,a] >= x[i,j] and u[i,t,a] <= sum_j x[i,j]     over the sessions j of class a on day t
    z[i,t,a] in {0,1} with priority N > A > M, z[i,t,-] = 1 - sum_a z[i,t,a]
    the flow above with s[t, a] = z[i, t, a]

Run from the repository root: python -m m3_automata.regular_to_ilp
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, deque
from dataclasses import dataclass, replace
from datetime import timedelta
from itertools import product as all_words
from pathlib import Path
from random import Random

import pulp

from m2_ilp.config import ModelConfig
from m2_ilp.instance import build_instance
from m2_ilp.metrics import compute_metrics
from m2_ilp.model import build_model, family
from m2_ilp.soft import fit_fatigue_k
from m2_ilp.solve import Solution, _value, run_cbc, solve
from m2_ilp.validate import check_schedule
from m3_automata.dfa import ALPHABET, DFA
from m3_automata.rules import RULE_FILES
from m3_automata.encode_strings import PRIORITY, SYMBOL_BY_START, day_symbol

M3_DIR = Path(__file__).resolve().parent
WORK = ("M", "A", "N")
REST = "-"
LINKED_RULES = ("R1", "R2", "R3")  # R4 (99 states with R1-R3) stays at DFA level, see 3.4
TIME_LIMIT = 150  # seconds per CBC stage
M3_VAR_FAMILIES = ("ucls", "zsym", "yflow")
M3_ROW_FAMILIES = ("CLSLB", "CLSUB", "SYMUB", "SYMLB", "SYMPR", "SRC", "FLOW", "LINK")


# 1. Session classes: which sessions of the M2 instance are M, A or N on each day (task 1)

def session_class(inst) -> list[str]:
    """Class M, A or N of every session j, from its start time (the encoder's table)."""
    classes = []
    for j, (start, end) in enumerate(inst.intervals):
        key = f"{start:%H}g{start:%M}"
        if key not in SYMBOL_BY_START:
            raise ValueError(f"{inst.session_names[j]}: start {key} has no class M, A or N")
        classes.append(SYMBOL_BY_START[key])
    return classes


def calendar(inst) -> list:
    """Every calendar day from the first to the last session day, days without exams included."""
    first, last = min(inst.day), max(inst.day)
    return [first + timedelta(days=k) for k in range((last - first).days + 1)]


def sessions_by_class(inst) -> dict:
    """J[t, a]: the sessions of class a on calendar day t (t indexes calendar(inst))."""
    index = {day: t for t, day in enumerate(calendar(inst))}
    classes = session_class(inst)
    groups = {}
    for j, day in enumerate(inst.day):
        groups.setdefault((index[day], classes[j]), []).append(j)
    return groups


def roster_strings(inst, assigned) -> dict:
    """{staff ID: one symbol per calendar day} of a fixed schedule, priority N > A > M.

    On inst.baseline this is exactly encode_strings() of the CSV, so M2 schedules and the
    CSV are read through the same convention.
    """
    index = {day: t for t, day in enumerate(calendar(inst))}
    classes = session_class(inst)
    worked = {}
    for i, j in set(assigned):
        worked.setdefault((i, index[inst.day[j]]), set()).add(classes[j])
    return {person: "".join(day_symbol(worked.get((i, t), ())) for t in range(len(index)))
            for i, person in enumerate(inst.staff_ids)}


def class_summary(inst) -> dict:
    """Numbers quoted in 3.3.md: sessions, baseline rows and available pairs per class."""
    classes = session_class(inst)
    groups = sessions_by_class(inst)
    return {
        "calendar_days": len(calendar(inst)),
        "exam_days": len(inst.sessions_by_day),
        "sessions": dict(Counter(classes)),
        "baseline_rows": dict(Counter(classes[j] for i, j in inst.baseline)),
        "available_pairs": dict(Counter(classes[j] for i, j in inst.A)),
        "day_class_groups": len(groups),
        "staff_with_night": len({i for i, j in inst.baseline if classes[j] == "N"}),
    }


# 2. The automaton to enforce: the submitted JSON rules and their minimal product

def load_rules(names=LINKED_RULES) -> dict:
    """The submitted JSON automata (3.1), so the ILP enforces exactly what the grader reads."""
    return {name: DFA.load(M3_DIR / RULE_FILES[name]) for name in names}


def _product(machines) -> DFA:
    """Product automaton over the reachable state tuples, accepting iff every factor accepts."""
    start = tuple(m.start for m in machines)
    states, transitions, queue = [start], {}, deque([start])
    seen = {start}
    while queue:
        state = queue.popleft()
        transitions[state] = {}
        for a in ALPHABET:
            target = tuple(m.transitions[q][a] for m, q in zip(machines, state))
            transitions[state][a] = target
            if target not in seen:
                seen.add(target)
                states.append(target)
                queue.append(target)
    name = "|".join
    accepting = [name(s) for s in states if all(q in m.accepting for m, q in zip(machines, s))]
    return DFA([name(s) for s in states], ALPHABET, name(start), accepting,
               {name(s): {a: name(t) for a, t in row.items()} for s, row in transitions.items()})


def _minimize(dfa) -> DFA:
    """Moore partition refinement on the reachable part; trap block named 'dead'."""
    states = dfa.reachable_states()
    block = {q: int(q in dfa.accepting) for q in states}
    while True:
        signature = {q: (block[q],) + tuple(block[dfa.transitions[q][a]] for a in dfa.alphabet)
                     for q in states}
        ids = {}
        refined = {q: ids.setdefault(signature[q], len(ids)) for q in states}
        if len(ids) == len(set(block.values())):
            break
        block = refined
    member = {}
    for q in states:
        member.setdefault(block[q], q)
    order, queue = [block[dfa.start]], deque([block[dfa.start]])
    while queue:
        b = queue.popleft()
        for a in dfa.alphabet:
            target = block[dfa.transitions[member[b]][a]]
            if target not in order:
                order.append(target)
                queue.append(target)
    accepting = {b for b in order if member[b] in dfa.accepting}
    trap = {b for b in order if b not in accepting
            and all(block[dfa.transitions[member[b]][a]] == b for a in dfa.alphabet)}
    label = {b: ("dead" if b in trap and len(trap) == 1 else f"m{k}") for k, b in enumerate(order)}
    return DFA([label[b] for b in order], dfa.alphabet, label[order[0]],
               [label[b] for b in order if b in accepting],
               {label[b]: {a: label[block[dfa.transitions[member[b]][a]]] for a in dfa.alphabet}
                for b in order})


def combined_dfa(machines=None) -> tuple[DFA, DFA]:
    """(minimal DFA of R1 x R2 x R3, the reachable product before minimisation).

    product_min.py (req 3.2) owns the reported state counts; this local product only keeps
    the flow model unblocked and is checked against the 3.2 numbers (259 -> 15).
    """
    full = _product(list((machines or load_rules()).values()))
    return _minimize(full), full


# 3. The flow model on the layered graph (task 2)

def layered_edges(dfa, allowed) -> list[tuple[int, str, str]]:
    """Edges (t, q, a) of the layered graph that lie on at least one accepted path.

    allowed[t] lists the symbols that day t may take. Forward pass: nodes reachable from
    (0, q0). Backward pass: nodes from which an accepting node of layer T can be reached.
    An edge into a trap state fails the backward test on every layer, and an edge into a
    non-accepting node of layer T fails it on the last layer: that is the acceptance row.
    """
    horizon = len(allowed)
    forward = [{dfa.start}]
    for t in range(horizon):
        forward.append({dfa.transitions[q][a] for q in forward[t] for a in allowed[t]})
    backward = [set() for _ in range(horizon)] + [forward[horizon] & dfa.accepting]
    for t in range(horizon - 1, -1, -1):
        backward[t] = {q for q in forward[t]
                       if any(dfa.transitions[q][a] in backward[t + 1] for a in allowed[t])}
    order = {q: k for k, q in enumerate(dfa.states)}
    return [(t, q, a) for t in range(horizon) for q in sorted(backward[t], key=order.get)
            for a in allowed[t] if dfa.transitions[q][a] in backward[t + 1]]


def live_states(dfa) -> set:
    """States from which an accepting state can be reached; the rest behave like the trap."""
    live, grown = set(dfa.accepting), True
    while grown:
        grown = False
        for q in dfa.states:
            if q not in live and any(dfa.transitions[q][a] in live for a in dfa.alphabet):
                live.add(q)
                grown = True
    return live


def full_graph_edges(dfa, horizon: int) -> int:
    """Edges of the unpruned layered graph: every reachable node and symbol, no edge into a
    state that cannot accept any more (the y variables a model without availability needs)."""
    live = live_states(dfa)
    layer, edges = {dfa.start}, 0
    for t in range(horizon):
        edges += sum(dfa.transitions[q][a] in live for q in layer for a in dfa.alphabet)
        layer = {dfa.transitions[q][a] for q in layer for a in dfa.alphabet} & live
    return edges


def add_regular_constraint(prob, dfa, symbols, tag="0") -> dict:
    """Force the word chosen by `symbols` into L(dfa); return {(t, q, a): y}.

    symbols[t] maps every symbol that day t may take to s[t, a]: a 0/1 variable, an
    expression, or the constant 1 for a forced day. A symbol missing from symbols[t] (or the
    constant 0) is not allowed that day. The flow through every layer is 1, so
    sum_a s[t, a] = 1 follows from the LINK rows. y is continuous in [0, 1]: once s is
    integral the DFA fixes the path, so y is integral too. tag keeps names unique when one
    problem holds several flows (the staff index in M2). No accepted word -> infeasible.
    """
    if not symbols:
        raise ValueError("The horizon needs at least one day")
    unknown = {a for row in symbols for a in row} - set(dfa.alphabet)
    if unknown:
        raise ValueError(f"Symbols outside the alphabet: {sorted(unknown)}")
    symbols = [{a: s for a, s in row.items() if not (isinstance(s, (int, float)) and s == 0)}
               for row in symbols]
    allowed = [[a for a in dfa.alphabet if a in row] for row in symbols]
    state = {q: k for k, q in enumerate(dfa.states)}
    letter = {a: k for k, a in enumerate(dfa.alphabet)}
    y = {(t, q, a): pulp.LpVariable(f"yflow_{tag}_{t}_{state[q]}_{letter[a]}", lowBound=0, upBound=1)
         for t, q, a in layered_edges(dfa, allowed)}
    leaving, entering, by_symbol = {}, {}, {}
    for (t, q, a), var in y.items():
        leaving.setdefault((t, q), []).append(var)
        entering.setdefault((t + 1, dfa.transitions[q][a]), []).append(var)
        by_symbol.setdefault((t, a), []).append(var)
    prob += pulp.lpSum(leaving.get((0, dfa.start), [])) == 1, f"SRC_{tag}"
    for (t, q), out in leaving.items():
        if t > 0:
            prob += pulp.lpSum(out) - pulp.lpSum(entering[t, q]) == 0, f"FLOW_{tag}_{t}_{state[q]}"
    for t, row in enumerate(symbols):
        for a, s in row.items():
            if len(row) == 1 and isinstance(s, (int, float)):
                continue  # one forced symbol: the layer's unit of flow already uses it
            prob += pulp.lpSum(by_symbol.get((t, a), [])) == s, f"LINK_{tag}_{t}_{letter[a]}"
    return y


def word_from_flow(dfa, y) -> tuple[str, list[str]]:
    """Follow the edges with y > 0.5 from (0, q0): the word and the visited states."""
    chosen = {(t, q): a for (t, q, a), var in y.items() if (var.varValue or 0) > 0.5}
    word, path = [], [dfa.start]
    for t in range(1 + max((t for t, q, a in y), default=-1)):
        a = chosen.get((t, path[-1]))
        if a is None:
            raise ValueError(f"The flow leaves no edge from ({t}, {path[-1]})")
        word.append(a)
        path.append(dfa.transitions[path[-1]][a])
    return "".join(word), path


# 4. Linking to the M2 variables x[i, j] (task 3)

@dataclass
class RuleHandles:
    u: dict
    z: dict
    y: dict
    n_vars: dict
    n_rows: dict


def add_rules_to_m2(prob, x, inst, dfa, z_binary: bool = True) -> RuleHandles:
    """Add u, z and one flow per staff member to an M2 problem; the objective is unchanged.

    u and z exist only where staff i has an available session of that class on day t; any
    other (i, t, a) is 0. A day without such a session can only be '-'.
    """
    groups = sessions_by_class(inst)
    horizon = len(calendar(inst))
    letter = {a: k for k, a in enumerate(ALPHABET)}
    higher = {a: PRIORITY[:PRIORITY.index(a)] for a in WORK}  # PRIORITY = "NAM"
    category = "Binary" if z_binary else "Continuous"
    u, z, y = {}, {}, {}
    for i in range(len(inst.staff_ids)):
        symbols = []
        for t in range(horizon):
            for a in PRIORITY:
                own = [(j, x[i, j]) for j in groups.get((t, a), []) if (i, j) in x]
                if not own:
                    continue
                u[i, t, a] = pulp.LpVariable(f"ucls_{i}_{t}_{letter[a]}", lowBound=0, upBound=1)
                for j, var in own:
                    prob += u[i, t, a] >= var, f"CLSLB_{i}_{j}"
                prob += u[i, t, a] <= pulp.lpSum(var for j, var in own), f"CLSUB_{i}_{t}_{letter[a]}"
            row = {}
            for a in PRIORITY:
                if (i, t, a) not in u:
                    continue
                key = f"{i}_{t}_{letter[a]}"
                z[i, t, a] = pulp.LpVariable(f"zsym_{key}", lowBound=0, upBound=1, cat=category)
                above = [(h, u[i, t, h]) for h in higher[a] if (i, t, h) in u]
                prob += z[i, t, a] <= u[i, t, a], f"SYMUB_{key}"
                prob += z[i, t, a] >= u[i, t, a] - pulp.lpSum(v for h, v in above), f"SYMLB_{key}"
                for h, v in above:
                    prob += z[i, t, a] <= 1 - v, f"SYMPR_{key}_{letter[h]}"
                row[a] = z[i, t, a]
            row[REST] = 1 - pulp.lpSum(row.values()) if row else 1
            symbols.append(row)
        y[i] = add_regular_constraint(prob, dfa, symbols, tag=str(i))
    n_vars = Counter(family(v.name) for v in prob.variables())
    n_rows = Counter(family(name) for name in prob.constraints)
    return RuleHandles(u, z, y, {f: n_vars[f] for f in M3_VAR_FAMILIES},
                       {f: n_rows[f] for f in M3_ROW_FAMILIES})


def model_size(prob) -> dict:
    """Total variables and rows of a problem, ignoring PuLP's __dummy placeholder."""
    return {"variables": sum(v.name != "__dummy" for v in prob.variables()),
            "rows": len(prob.constraints)}


def _stage(result, size) -> dict:
    return {"status": result.status, "objective": result.objective, "runtime": result.runtime,
            "gap": result.gap, "nodes": result.nodes, **size}


def solve_with_rules(inst, config: ModelConfig, dfa, z_binary: bool = True):
    """m2_ilp.solve.solve with the DFA flow added to both stages.

    Same lexicographic order (min max load, then L1 + soft under t <= t*) and same CBC
    settings. Returns (Solution, {stage: size and solver info}, RuleHandles of the kept stage).
    """
    info = {}
    prob1, x1, h1 = build_model(inst, replace(config, stage=1, t_cap=None))
    rules1 = add_rules_to_m2(prob1, x1, inst, dfa, z_binary)
    stage1 = run_cbc(prob1, config)
    info[1] = _stage(stage1, {**model_size(prob1), "m3_vars": rules1.n_vars, "m3_rows": rules1.n_rows})
    if stage1.status not in ("optimal", "feasible"):
        print(f"[m3/ilp] stage 1 with the rules is {stage1.status}")
        return Solution(stage1.status, frozenset(), None, {}, {1: stage1}, None), info, None
    t_star = round(pulp.value(h1.t))
    if not math.isclose(pulp.value(h1.t), t_star, abs_tol=1e-6):
        raise RuntimeError(f"Stage 1 returned a fractional max load {pulp.value(h1.t)}")
    prob2, x2, h2 = build_model(inst, replace(config, stage=2, t_cap=t_star))
    rules2 = add_rules_to_m2(prob2, x2, inst, dfa, z_binary)
    stage2 = run_cbc(prob2, config)
    info[2] = _stage(stage2, {**model_size(prob2), "m3_vars": rules2.n_vars, "m3_rows": rules2.n_rows})
    if stage2.status in ("optimal", "feasible"):
        x, handles, rules, status, kept = x2, h2, rules2, stage2.status, stage2
    else:
        print(f"[m3/ilp] stage 2 is {stage2.status}; keeping the stage-1 schedule")
        x, handles, rules, status, kept = x1, h1, rules1, "feasible", stage1
    assigned = frozenset(p for p, var in x.items() if var.varValue is not None and var.varValue > 0.5)
    terms = handles.soft_terms or {}
    objective = {"max_load": max((_value(w) for w in handles.w.values()), default=0.0),
                 "l1": _value(handles.l1), "location": _value(terms.get("location")),
                 "fatigue": _value(terms.get("fatigue")), "travel": _value(terms.get("travel")),
                 "total": kept.objective}
    return Solution(status, assigned, t_star, objective, {1: stage1, 2: stage2}, None), info, rules


# 5. Checks on a solution

def violations(strings: dict, machines: dict) -> dict:
    """How many staff strings each DFA rejects, plus 'any' (rejected by one) and 'accepted'."""
    rejected = {name: {p for p, w in strings.items() if not m.accepts(w)} for name, m in machines.items()}
    union = set().union(*rejected.values()) if rejected else set()
    return {**{name: len(r) for name, r in rejected.items()},
            "any": len(union), "accepted": len(strings) - len(union)}


def check_rule_solution(inst, assigned, rules: RuleHandles, dfa) -> list[str]:
    """Empty iff, for every staff member, z equals the symbols rebuilt from x, the flow path
    reads the same word, and the DFA accepts it."""
    strings = roster_strings(inst, assigned)
    problems = []
    for i, person in enumerate(inst.staff_ids):
        word = strings[person]
        from_z = "".join(next((a for a in PRIORITY if (rules.z.get((i, t, a)) is not None
                               and (rules.z[i, t, a].varValue or 0) > 0.5)), REST)
                         for t in range(len(word)))
        flow_word, path = word_from_flow(dfa, rules.y[i])
        if from_z != word:
            problems.append(f"{person}: z reads {from_z}, x gives {word}")
        if flow_word != word:
            problems.append(f"{person}: flow reads {flow_word}, x gives {word}")
        if not dfa.accepts(word) or path[-1] not in dfa.accepting:
            problems.append(f"{person}: {word} is rejected")
    return problems


# 6. Flow ILP against brute force on small instances (required test of task 2)

def brute_force_best(dfa, cost, allowed) -> tuple[float | None, str | None]:
    """Minimum of sum_t cost[t][w_t] over all accepted words w with w_t in allowed[t]."""
    best = (None, None)
    for word in all_words(*allowed):
        if dfa.accepts(word):
            value = sum(cost[t][a] for t, a in enumerate(word))
            if best[0] is None or value < best[0] - 1e-9:
                best = (value, "".join(word))
    return best


def flow_ilp_best(dfa, cost, allowed) -> tuple[float | None, str | None]:
    """Same minimum with binary day symbols s[t, a] and the flow model; (None, None) if infeasible."""
    prob = pulp.LpProblem("flow_check", pulp.LpMinimize)
    s = {(t, a): pulp.LpVariable(f"s_{t}_{ALPHABET.index(a)}", cat="Binary")
         for t, row in enumerate(allowed) for a in row}
    prob += pulp.lpSum(cost[t][a] * var for (t, a), var in s.items())
    y = add_regular_constraint(prob, dfa, [{a: s[t, a] for a in row} for t, row in enumerate(allowed)])
    prob.solve(pulp.PULP_CBC_CMD(msg=False, threads=1, gapRel=0))
    if prob.sol_status != pulp.LpSolutionOptimal:
        return None, None
    word = "".join(next(a for a in row if s[t, a].varValue > 0.5) for t, row in enumerate(allowed))
    if word_from_flow(dfa, y)[0] != word:
        raise AssertionError("The flow path and the day symbols disagree")
    return pulp.value(prob.objective), word


def random_case(rng, horizon, objective, fixed):
    """cost[t][a] and allowed[t] for one test case drawn from rng."""
    if objective == "random":
        cost = [{a: rng.randint(-5, 5) for a in ALPHABET} for _ in range(horizon)]
    else:  # "max_work": as many working days as the rule allows, nights preferred
        cost = [{"M": -1, "A": -1, "N": -1.25, REST: 0} for _ in range(horizon)]
    allowed = [list(ALPHABET) for _ in range(horizon)]
    if fixed:  # one day forced to a working symbol, one day with a symbol forbidden
        forced, limited = rng.sample(range(horizon), 2)
        allowed[forced] = [rng.choice(WORK)]
        banned = rng.choice(ALPHABET)
        allowed[limited] = [a for a in ALPHABET if a != banned]
    return cost, allowed


def brute_force_check(seed: int, machines: dict, horizon: int = 7) -> list[dict]:
    """4 objectives-and-fixing variants on each automaton: the optima must coincide."""
    rng = Random(seed)
    rows = []
    for name, dfa in machines.items():
        for objective in ("random", "max_work"):
            for fixed in (False, True):
                cost, allowed = random_case(rng, horizon, objective, fixed)
                brute, brute_word = brute_force_best(dfa, cost, allowed)
                ilp, ilp_word = flow_ilp_best(dfa, cost, allowed)
                same = (brute is None and ilp is None) or (
                    brute is not None and ilp is not None and math.isclose(brute, ilp, abs_tol=1e-6)
                    and dfa.accepts(ilp_word)
                    and math.isclose(sum(cost[t][a] for t, a in enumerate(ilp_word)), ilp, abs_tol=1e-6))
                rows.append({"dfa": name, "objective": objective, "fixed_days": fixed, "T": horizon,
                             "brute_force": brute, "flow_ilp": ilp, "word": ilp_word, "match": same})
    return rows


# 7. Before/after comparison on the real M2 instance (task 4)

def _variant(inst, assigned, k, lambdas, machines) -> dict:
    metrics = compute_metrics(inst, assigned, k)
    metrics["weighted_objective"] = (metrics["l1"] + lambdas[0] * metrics["location"]
                                     + lambdas[1] * metrics["fatigue"] + lambdas[2] * metrics["travel"])
    metrics["violations"] = violations(roster_strings(inst, assigned), machines)
    metrics["validator_violations"] = len(check_schedule(inst, assigned))
    return metrics


def compare(seed=None, time_limit: int = TIME_LIMIT, z_binary: bool = True,
            ablation: bool = True) -> dict:
    """Baseline, M2 alone and M2 + R1 x R2 x R3 on the same instance, K, weights and solver.

    ablation re-solves with the other type of z, to check that only x needs to be integral.
    """
    inst = build_instance(seed)
    k = fit_fatigue_k(inst)
    config = ModelConfig(fatigue_k=k, time_limit=time_limit)
    rules = load_rules()
    dfa, full = combined_dfa(rules)
    machines = {**rules, "R1xR2xR3": dfa}
    lambdas = config.lambdas(inst)

    before = solve(inst, config)
    sizes_before = {}
    for stage, cap in ((1, None), (2, before.t_star)):
        prob, x, handles = build_model(inst, replace(config, stage=stage, t_cap=cap))
        sizes_before[stage] = model_size(prob)
    after, info, handles = solve_with_rules(inst, config, dfa, z_binary)
    if not after.assigned:
        raise RuntimeError(f"M2 + rules found no schedule (status {after.status})")

    variants = {"baseline": _variant(inst, inst.baseline, k, lambdas, machines),
                "m2": _variant(inst, before.assigned, k, lambdas, machines),
                "m2_rules": _variant(inst, after.assigned, k, lambdas, machines)}
    for name, solution, sizes in (("m2", before, None), ("m2_rules", after, info)):
        variants[name]["status"] = solution.status
        variants[name]["t_star"] = solution.t_star
        for stage, result in solution.stages.items():
            size = sizes[stage] if sizes else {**sizes_before[stage], "m3_vars": {}, "m3_rows": {}}
            variants[name][f"stage{stage}"] = _stage(result, {key: size[key] for key in
                                                              ("variables", "rows", "m3_vars", "m3_rows")})
    other = {}
    if ablation:
        alt, alt_info, alt_handles = solve_with_rules(inst, config, dfa, not z_binary)
        other = {"z_binary": not z_binary, "status": alt.status, "t_star": alt.t_star,
                 "weighted_objective": alt.objective.get("total"),
                 "runtime": {f"stage{s}": r["runtime"] for s, r in alt_info.items()},
                 "nodes": {f"stage{s}": r["nodes"] for s, r in alt_info.items()},
                 "violations": violations(roster_strings(inst, alt.assigned), machines),
                 "rule_solution": (check_rule_solution(inst, alt.assigned, alt_handles, dfa)
                                   if alt.assigned else ["no schedule"])}
    horizon, n = len(calendar(inst)), len(inst.staff_ids)
    return {
        "seed": inst.seed, "time_limit": time_limit, "z_binary": z_binary, "fatigue_k": k,
        "lambdas": list(lambdas), "staff": n, "T": horizon,
        "classes": class_summary(inst),
        "dfa": {"rules": list(LINKED_RULES), "rule_states": {n: len(m.states) for n, m in rules.items()},
                "product_reachable": len(full.states), "minimal_states": len(dfa.states),
                "trap_states": dfa.trap_states(),
                "flow_edges_unpruned_product": n * full_graph_edges(full, horizon),
                "flow_edges_unpruned": n * full_graph_edges(dfa, horizon),
                "flow_edges_kept": sum(len(v) for v in handles.y.values())},
        "variants": variants,
        "ablation": other,
        "checks": {"rule_solution": check_rule_solution(inst, after.assigned, handles, dfa)},
        "brute_force": brute_force_check(inst.seed, machines),
        "strings": {name: roster_strings(inst, assigned) for name, assigned in
                    (("m2", before.assigned), ("m2_rules", after.assigned))},
    }


def comparison_table(result: dict) -> str:
    """The before/after table of 3.3.md, as Markdown, from compare()."""
    v = result["variants"]
    rows = [("max_load", "max_load", "{:d}"), ("L1", "l1", "{:.3f}"), ("LOC", "location", "{:d}"),
            ("FAT", "fatigue", "{:d}"), ("TRV", "travel", "{:d}"),
            ("Stage-2 objective", "weighted_objective", "{:.3f}")]
    lines = ["| Measure | Baseline | M2 alone | M2 + R1xR2xR3 |", "| --- | ---: | ---: | ---: |"]
    for label, key, fmt in rows:
        lines.append(f"| {label} | " + " | ".join(fmt.format(v[n][key]) for n in v) + " |")
    for rule in (*LINKED_RULES, "any", "accepted"):
        label = {"any": "Rejected by R1, R2 or R3", "accepted": "Accepted by all three"}.get(
            rule, f"{rule} violations")
        lines.append(f"| {label} | " + " | ".join(str(v[n]["violations"][rule]) for n in v) + " |")
    for stage in (1, 2):
        s1, s2 = v["m2"][f"stage{stage}"], v["m2_rules"][f"stage{stage}"]
        lines.append(f"| Stage {stage} variables / rows | – | {s1['variables']:,} / {s1['rows']:,} "
                     f"| {s2['variables']:,} / {s2['rows']:,} |")
        lines.append(f"| Stage {stage} status, time | – | {s1['status']}, {s1['runtime']:.2f} s "
                     f"| {s2['status']}, {s2['runtime']:.2f} s |")
    return "\n".join(lines)


def run_m3_ilp(seed: int, out_dir: Path | None = None, time_limit: int = TIME_LIMIT) -> dict:
    """Entry point for run_all.py --stage m3: compare, check, write regular_to_ilp.json."""
    result = compare(seed, time_limit)
    problems = result["checks"]["rule_solution"] + result["ablation"].get("rule_solution", [])
    mismatched = [row for row in result["brute_force"] if not row["match"]]
    if problems or mismatched or result["variants"]["m2_rules"]["validator_violations"]:
        raise RuntimeError(f"M3 ILP checks failed: {problems[:5]} {mismatched[:3]}")
    dfa = result["dfa"]
    print(f"[m3/ilp] R1 x R2 x R3: {dfa['product_reachable']} reachable product states -> "
          f"{dfa['minimal_states']} minimal (trap {dfa['trap_states']}); T = {result['T']} days")
    print(comparison_table(result))
    print(f"[m3/ilp] every rebuilt string is accepted; flow ILP = brute force on "
          f"{len(result['brute_force'])}/{len(result['brute_force'])} small cases")
    other = result["ablation"]
    if other:
        print(f"[m3/ilp] ablation z_binary={other['z_binary']}: {other['status']}, objective "
              f"{other['weighted_objective']:.3f}, time {other['runtime']['stage1']:.2f} + "
              f"{other['runtime']['stage2']:.2f} s, accepted {other['violations']['accepted']}")
    clean = json.loads(json.dumps(result), parse_float=lambda text: round(float(text), 6))
    path = Path(out_dir or M3_DIR / "extra") / "regular_to_ilp.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(clean, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"[m3/ilp] wrote {path.name}")
    return result


if __name__ == "__main__":
    from m1_logic.data_loader import PROJECT_FOLDER

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="defaults to data/seed.txt")
    parser.add_argument("--time-limit", type=int, default=TIME_LIMIT, help="seconds per CBC stage")
    args = parser.parse_args()
    if args.seed is None:
        args.seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    run_m3_ilp(args.seed, time_limit=args.time_limit)
