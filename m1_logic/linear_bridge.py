from dataclasses import dataclass
from itertools import product

# Number of variables that check_bridge() is willing to enumerate (2**20 rows).
MAX_ENUMERATED_VARIABLES = 20
SENSES = ("<=", ">=", "==")

#deliberately check the input type 
def _check_nonnegative_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _check_variable(value, name="variable ID"):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _check_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _distinct_variables(variables, name="variables"):
    ordered = []
    seen = set()
    for variable in variables:
        _check_variable(variable)
        if variable in seen:
            raise ValueError(f"{name} contains variable {variable} twice")
        seen.add(variable)
        ordered.append(variable)
    return ordered


def value_of(assignment, variable):
    if hasattr(assignment, "get"):
        return 1 if assignment.get(variable) else 0
    return 1 if variable in assignment else 0


def model_to_assignment(model, variables):
    true_variables = {literal for literal in model if literal > 0}
    return {variable: (1 if variable in true_variables else 0)
            for variable in variables}


@dataclass(frozen=True)
class LinearConstraint:
    coefficients: dict
    sense: str
    rhs: int
    origin: str = ""

    def __post_init__(self):
        if self.sense not in SENSES:
            raise ValueError(f"sense must be one of {SENSES}")
        _check_int(self.rhs, "rhs")
        coefficients = {}
        for variable, coefficient in self.coefficients.items():
            _check_variable(variable)
            _check_int(coefficient, f"coefficient of variable {variable}")
            coefficients[variable] = coefficient
        object.__setattr__(self, "coefficients", coefficients)

    @property
    def variables(self):
        return tuple(self.coefficients)

    #calculate the left hand side after we create the tuple which cannot change it's value right above
    def lhs(self, assignment):
        return sum(coefficient * value_of(assignment, variable)
                   for variable, coefficient in self.coefficients.items())

    """use to transforms string sense into boolean:
    if True: it continue to using that return to input another func
    if False: it append that return to violate dict and print unfeasible output
    """
    def holds(self, assignment):
        left = self.lhs(assignment)
        if self.sense == "<=":
            return left <= self.rhs
        if self.sense == ">=":
            return left >= self.rhs
        return left == self.rhs

    def is_always_true(self):
        low, high = self._bounds() # ? <= x <= ?
        if self.sense == "<=":
            return high <= self.rhs
        if self.sense == ">=":
            return low >= self.rhs
        return low == self.rhs == high

    def is_never_true(self):
        low, high = self._bounds()
        if self.sense == "<=":
            return low > self.rhs
        if self.sense == ">=":
            return high < self.rhs
        return not low <= self.rhs <= high

    def _bounds(self):
        return (sum(min(c, 0) for c in self.coefficients.values()),
                sum(max(c, 0) for c in self.coefficients.values()))

    def flip(self):
        sense = {"<=": ">=", ">=": "<=", "==": "=="}[self.sense]
        return LinearConstraint(
            {v: -c for v, c in self.coefficients.items()}, sense, -self.rhs, self.origin
        )

    def text(self, name=None):
        if name is None:
            def name(variable):
                return f"x{variable}"
        parts = []
        for variable, coefficient in self.coefficients.items():
            sign = "-" if coefficient < 0 else "+"
            size = abs(coefficient)
            term = name(variable) if size == 1 else f"{size}*{name(variable)}"
            parts.append(term if not parts and sign == "+" else f"{sign} {term}")
        left = " ".join(parts) if parts else "0"
        return f"{left} {self.sense} {self.rhs}"

    def __str__(self):
        return self.text()

# Generic bridge: one grounded clause -> one linear constraint

def clause_to_linear(clause, origin=""):
    positive, negative = [], []
    for literal in clause:
        if isinstance(literal, bool) or not isinstance(literal, int) or literal == 0:
            raise ValueError(f"literal {literal!r} must be a non-zero integer")
        target = positive if literal > 0 else negative
        if abs(literal) not in target:
            target.append(abs(literal))
    if set(positive) & set(negative):
        return LinearConstraint({}, ">=", 0, origin or "tautology")

    coefficients = {}
    for variable in positive:
        coefficients[variable] = 1
    for variable in negative:
        coefficients[variable] = -1
    return LinearConstraint(coefficients, ">=", 1 - len(negative), origin)


def cnf_to_linear(clauses, origin_prefix="clause"):
    clause_list = getattr(clauses, "clauses", clauses)
    return [clause_to_linear(clause, f"{origin_prefix}:{index}")
            for index, clause in enumerate(clause_list)]

# Cardinality patterns, stated directly instead of through a CNF encoding

def at_least(variables, bound, origin=""):
    ordered = _distinct_variables(variables)
    _check_nonnegative_int(bound, "bound")
    return LinearConstraint({v: 1 for v in ordered}, ">=", bound, origin)


def at_most(variables, bound, origin=""):
    ordered = _distinct_variables(variables)
    _check_nonnegative_int(bound, "bound")
    return LinearConstraint({v: 1 for v in ordered}, "<=", bound, origin)


def exactly(variables, bound, origin=""):
    ordered = _distinct_variables(variables)
    _check_nonnegative_int(bound, "bound")
    return LinearConstraint({v: 1 for v in ordered}, "==", bound, origin)


def exactly_one(variables, origin=""):
    return exactly(variables, 1, origin)


def fix_false(variable, origin=""):
    _check_variable(variable)
    return LinearConstraint({variable: 1}, "==", 0, origin)


def fix_true(variable, origin=""):
    _check_variable(variable)
    return LinearConstraint({variable: 1}, "==", 1, origin)


# Structured bridge for the invigilator assignment instance

@dataclass(frozen=True)
class LinearModel:
    staff_count: int
    task_count: int
    constraints: tuple

    def var(self, i, j):
        if not 0 <= i < self.staff_count or not 0 <= j < self.task_count:
            raise ValueError(f"pair {(i, j)} is outside the instance")
        return i * self.task_count + j + 1

    def pair(self, variable):
        if not 1 <= variable <= self.staff_count * self.task_count:
            raise ValueError(f"{variable} is not an assignment variable")
        return divmod(variable - 1, self.task_count)

    def assignment_variables(self):
        return tuple(range(1, self.staff_count * self.task_count + 1))

    def violated(self, assignment):
        return [c for c in self.constraints if not c.holds(assignment)]

    def is_feasible(self, assignment):
        return all(c.holds(assignment) for c in self.constraints)

    def summary(self):
        counts = {}
        for constraint in self.constraints:
            family = constraint.origin.split(":")[0] or "unlabelled"
            counts[family] = counts.get(family, 0) + 1
        return counts


def encode_invigilator_assignment_linear(
    invigilator_count, shift_demands, busy, overlaps
) -> LinearModel:
    _check_nonnegative_int(invigilator_count, "invigilator_count")
    if busy is None:
        raise ValueError("Busy is unknown; supply a seeded scenario or an explicit empty list")
    task_count = len(shift_demands)
    constraints = []

    def var(i, j):
        return i * task_count + j + 1

    for j, demand in enumerate(shift_demands):
        _check_nonnegative_int(demand, f"shift_demands[{j}]")
        constraints.append(exactly(
            [var(i, j) for i in range(invigilator_count)], demand, f"capacity:j={j}",
        ))

    for i, j in busy:
        _check_nonnegative_int(i, "busy staff index")
        _check_nonnegative_int(j, "busy session index")
        if i >= invigilator_count or j >= task_count:
            raise ValueError(f"busy pair {(i, j)} is outside the instance")
        constraints.append(fix_false(var(i, j), f"busy:i={i},j={j}"))

    for j, k in overlaps:
        _check_nonnegative_int(j, "overlap task index")
        _check_nonnegative_int(k, "overlap task index")
        if j >= task_count or k >= task_count or j == k:
            raise ValueError(f"overlap pair {(j, k)} must refer to two distinct tasks")
        for i in range(invigilator_count):
            constraints.append(at_most(
                [var(i, j), var(i, k)], 1, f"overlap:i={i},j={j},k={k}",
            ))

    return LinearModel(invigilator_count, task_count, tuple(constraints))

# Checking the bridge on truth assignments

def clause_is_true(clause, assignment):
    return any(value_of(assignment, abs(literal)) == (1 if literal > 0 else 0)
               for literal in clause)


def check_bridge(predicate, constraint, variables):
    ordered = _distinct_variables(variables)
    if len(ordered) > MAX_ENUMERATED_VARIABLES:
        raise ValueError(
            f"refusing to enumerate 2**{len(ordered)} assignments; "
            f"the limit is {MAX_ENUMERATED_VARIABLES} variables"
        )
    mismatches = []
    for flags in product((0, 1), repeat=len(ordered)):
        assignment = dict(zip(ordered, flags))
        expected = bool(predicate(assignment))
        actual = constraint.holds(assignment)
        if expected != actual:
            mismatches.append((assignment, expected, actual))
    return mismatches


def check_clause_bridge(clause):
    variables = sorted({abs(literal) for literal in clause})
    return check_bridge(
        lambda assignment: clause_is_true(clause, assignment),
        clause_to_linear(clause),
        variables,
    )


def _count_true(assignment, variables):
    return sum(value_of(assignment, variable) for variable in variables)

_A, _B, _C = 1, 2, 3
PATTERNS = (
    (
        "a v b",
        "at least one of a, b",
        lambda m: bool(m[_A] or m[_B]),
        clause_to_linear([_A, _B], "pattern"),
    ),
    (
        "-a v b",
        "a -> b (implication)",
        lambda m: (not m[_A]) or bool(m[_B]),
        clause_to_linear([-_A, _B], "pattern"),
    ),
    (
        "-a v -b",
        "not (a and b); this is hard rule H2 for one staff member",
        lambda m: not (m[_A] and m[_B]),
        clause_to_linear([-_A, -_B], "pattern"),
    ),
    (
        "-a",
        "a is forbidden; this is hard rule H1 (availability)",
        lambda m: not m[_A],
        clause_to_linear([-_A], "pattern"),
    ),
    (
        "a v b v -c",
        "mixed clause, three literals",
        lambda m: bool(m[_A] or m[_B] or not m[_C]),
        clause_to_linear([_A, _B, -_C], "pattern"),
    ),
    (
        "exactly-one(a,b,c)",
        "exactly one of a, b, c",
        lambda m: _count_true(m, (_A, _B, _C)) == 1,
        exactly_one([_A, _B, _C], "pattern"),
    ),
    (
        "at-most-k(a,b,c), k=2",
        "at most two of a, b, c",
        lambda m: _count_true(m, (_A, _B, _C)) <= 2,
        at_most([_A, _B, _C], 2, "pattern"),
    ),
    (
        "at-least-k(a,b,c), k=2",
        "at least two of a, b, c",
        lambda m: _count_true(m, (_A, _B, _C)) >= 2,
        at_least([_A, _B, _C], 2, "pattern"),
    ),
    (
        "exactly-k(a,b,c), k=2",
        "exactly two of a, b, c; this is hard rule H3 for one task",
        lambda m: _count_true(m, (_A, _B, _C)) == 2,
        exactly([_A, _B, _C], 2, "pattern"),
    ),
)


def verify_patterns():
    return {label: check_bridge(predicate, constraint, sorted(constraint.variables))
            for label, _meaning, predicate, constraint in PATTERNS}


WRONG_MAPPINGS = (
    (
        "a v b  ->  x_a + x_b == 1",
        "Reading 'or' as 'exactly one' forbids the perfectly legal case a = b = 1.",
        lambda m: bool(m[_A] or m[_B]),
        LinearConstraint({_A: 1, _B: 1}, "==", 1, "wrong:or-as-exactly-one"),
        {_A: 1, _B: 1},
    ),
    (
        "-a v b  ->  x_a + x_b >= 1",
        "Forgetting to flip the negated literal: the row accepts a = 1, b = 0, "
        "which falsifies a -> b.",
        lambda m: (not m[_A]) or bool(m[_B]),
        LinearConstraint({_A: 1, _B: 1}, ">=", 1, "wrong:missing-negation"),
        {_A: 1, _B: 0},
    ),
    (
        "-a v -b  ->  x_a + x_b >= 1",
        "Using the positive clause form for a negative clause inverts hard rule "
        "H2: it allows the double booking a = b = 1 and bans the idle a = b = 0.",
        lambda m: not (m[_A] and m[_B]),
        LinearConstraint({_A: 1, _B: 1}, ">=", 1, "wrong:overlap-sense"),
        {_A: 1, _B: 1},
    ),
    (
        "exactly-k  ->  sum x <= k",
        "Keeping only the at-most half of hard rule H3 lets a task go unstaffed; "
        "the empty schedule becomes feasible.",
        lambda m: _count_true(m, (_A, _B, _C)) == 2,
        at_most([_A, _B, _C], 2, "wrong:capacity-at-most"),
        {_A: 0, _B: 0, _C: 0},
    ),
    (
        "exactly-k  ->  sum x >= k",
        "Keeping only the at-least half of hard rule H3 lets a task be "
        "overstaffed, which M2 would then exploit to balance its workload.",
        lambda m: _count_true(m, (_A, _B, _C)) == 2,
        at_least([_A, _B, _C], 2, "wrong:capacity-at-least"),
        {_A: 1, _B: 1, _C: 1},
    ),
)


def wrong_mapping_counterexamples():
    report = []
    for label, reason, predicate, constraint, witness in WRONG_MAPPINGS:
        mismatches = check_bridge(predicate, constraint, sorted(constraint.variables))
        report.append((
            label, reason, constraint, witness,
            bool(predicate(witness)), constraint.holds(witness), len(mismatches),
        ))
    return report

# Notation and conversion table, handed over to M2 and the report

NOTATION = (
    ("I, i", "Set of staff and its index; i = 0..N-1, ordered as staff_ids"),
    ("J, j, k", "Set of sessions (shift code, campus); j = 0..M-1, as session_ids"),
    ("d_j", "Demand of task j: shift_demands[j], the exact number of staff"),
    ("Assign(i,j)", "Predicate: staff i works task j"),
    ("x_ij", "0/1 variable for Assign(i,j); variable ID i*M+j+1"),
    ("Busy(i,j)", "Data: staff i is unavailable for session j; seeded scenario field busy"),
    ("Overlap(j,k)", "Data: tasks j and k share time; loader field overlaps"),
)

CONVERSION_ROWS = (
    ("H1 Availability",
     "forall i,j: Busy(i,j) -> not Assign(i,j)",
     "-Assign(i,j)",
     "[-v]",
     "x_ij == 0"),
    ("H2 No double-booking",
     "forall i,j,k: Overlap(j,k) & Assign(i,j) -> not Assign(i,k)",
     "-Assign(i,j) v -Assign(i,k)",
     "[-v1, -v2]",
     "x_ij + x_ik <= 1"),
    ("H3 Exact capacity",
     "forall j: exactly d_j staff i satisfy Assign(i,j)",
     "exactly-k over Assign(.,j)",
     "sequential counter, aux IDs > N*M",
     "sum_i x_ij == d_j"),
    ("Generic clause",
     "disjunction over literals",
     "(v_p for p in P) v (-v_n for n in N)",
     "[p.., -n..]",
     "sum_P x_p - sum_N x_n >= 1 - |N|"),
    ("Clause a v b", "a or b", "a v b", "[a, b]", "x_a + x_b >= 1"),
    ("Clause -a v b", "a -> b", "-a v b", "[-a, b]", "x_b - x_a >= 0"),
    ("Clause -a v -b", "not (a and b)", "-a v -b", "[-a, -b]", "x_a + x_b <= 1"),
    ("Exactly-one", "exactly one of S", "exactly-one(S)", "pairwise or counter",
     "sum_S x == 1"),
    ("At-most-k", "at most k of S", "at-most-k(S)", "counter encoding",
     "sum_S x <= k"),
    ("Exactly-k", "exactly k of S", "exactly-k(S)", "counter encoding",
     "sum_S x == k"),
    ("Empty clause", "contradiction", "[]", "[]", "0 >= 1 (infeasible row)"),
)


def _md_cell(text):
    """Escape pipes so a cell never splits the row, backticks included.

    GitHub resolves `\\|` before inline parsing, so `|N|` inside a code span
    would otherwise turn one row into seven columns instead of five.
    """
    return text.replace("|", "\\|")


def bridge_table_markdown():
    """Render the notation and conversion tables for DECISIONS.md and the report."""
    lines = ["### Notation (M1 -> M2)", "", "| Symbol | Meaning |", "|---|---|"]
    lines += [f"| `{_md_cell(symbol)}` | {_md_cell(meaning)} |"
              for symbol, meaning in NOTATION]
    lines += [
        "",
        "### Conversion table: logic -> 0/1 linear",
        "",
        "| Rule / pattern | FOL | Grounded clause | CNF (DIMACS) | Linear 0/1 |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {_md_cell(rule)} | `{_md_cell(fol)}` | `{_md_cell(clause)}` | "
              f"`{_md_cell(dimacs)}` | `{_md_cell(linear)}` |"
              for rule, fol, clause, dimacs, linear in CONVERSION_ROWS]

    lines += [
        "",
        "Every x is a 0/1 variable: these rows are equivalences over integers, "
        "not over the LP relaxation.",
        "`clause_to_linear` always emits the canonical `>=` form, so a clause of "
        "negative literals arrives as `-x_a - x_b >= -1`; `LinearConstraint.flip()` "
        "multiplies it by -1 into the `x_a + x_b <= 1` shown above.",
        "M2 should build on `encode_invigilator_assignment_linear`, whose "
        "capacity equality has no auxiliary variables and a tighter relaxation "
        "than a clause-by-clause translation of the sequential counter.",
    ]
    return "\n".join(lines)


def main():
    print(bridge_table_markdown())

    print("\n=== PATTERN CHECK (every truth assignment) ===")
    results = verify_patterns()
    failures = 0
    for label, meaning, _predicate, constraint in PATTERNS:
        mismatches = results[label]
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        failures += len(mismatches)
        print(f"  {label:<26} -> {constraint.text():<22} {status}   ({meaning})")
    print(f"  {len(PATTERNS)} patterns checked, {failures} mismatches.")

    print("\n=== COUNTEREXAMPLES FOR WRONG MAPPINGS ===")
    for entry in wrong_mapping_counterexamples():
        label, reason, constraint, witness, expected, actual, total = entry
        print(f"\n  {label}")
        print(f"    Why it is wrong: {reason}")
        if expected == actual:
            print("    The witness no longer disagrees: this entry is stale.")
            continue
        values = ", ".join(f"x{v}={b}" for v, b in sorted(witness.items()))
        print(f"    Counterexample: {values} -> logic says {expected}, "
              f"the row {constraint.text()} says {actual}")
        print(f"    ({total} of the truth assignments disagree in total)")

    print("\n=== SEEDED REAL-DATA SCENARIOS ===")
    import sys
    from pathlib import Path

    if not __package__:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from m1_logic.data_loader import PROJECT_FOLDER
    from m1_logic.prepare_instances import prepare_instances

    seed = int((PROJECT_FOLDER / "data/seed.txt").read_text(encoding="utf-8-sig").strip())
    cases = prepare_instances(seed)
    for name in ("sat", "unsat"):
        data = cases[name]
        model = encode_invigilator_assignment_linear(
            len(data["staff_ids"]), data["shift_demands"], data["busy"], data["overlaps"],
        )
        print(f"  {name}: {model.staff_count} staff x {model.task_count} sessions = "
              f"{len(model.assignment_variables())} binary variables, no auxiliaries")
        print(f"  Constraint counts: {model.summary()}")
        baseline = {model.var(i, j): 1 for i, j in data["baseline"]}
        print(f"  Baseline violations under this seeded Busy scenario: "
              f"{len(model.violated(baseline))} (baseline availability is not preserved)")


if __name__ == "__main__":
    main()
