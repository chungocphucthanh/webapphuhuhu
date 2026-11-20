# Design decisions

Record, per module, WHY you chose each objective, constraint, DFA, and dynamical direction, and what you rejected.

## M1 - Data and modeling decisions (revised 2026-09-20)

- Capacity: Following the latest clarification, a session is (shift code, campus); count all staff roles together and remove history-based eligibility.
  Busy: Baseline absence does not prove unavailability. The raw loader leaves Busy unknown; test scenarios generate it from Random(seed) per person/shift, shared across campuses.
  Overlap: Use actual time intersections; touching endpoints are allowed and travel belongs to M2.
  Cases: Keep three complete, non-overlapping shift codes with total demand at most six, including one multi-campus code. Seeded available sets cover each shift's demand for SAT; one seeded shift retains only demand minus one available staff for UNSAT. These are controlled test choices; capacity never changes.
  Handoff: TV5 exports data/m1_cases/real_slice.csv and returns SAT/UNSAT/toy input dictionaries from prepare_instances(seed), without writing JSON. TV4 owns instance tests, solver verification, result JSON and run_all.py integration.

## M1 - CNF encoding decisions (2026-09-15; revised 2026-09-20)

- Scope: The encoder converts loader data into CNF without changing data or generating Busy again. Solving and UNSAT core extraction are separate work.
  Variables: Assign(i,j) means staff i works session j, identified by (shift code, campus). Use zero-based indices and ID i*M+j+1, with N staff and M sessions. Pass scenario busy, not busy_by_shift; the encoder now takes four arguments, with no ineligible argument.
  Capacity: Encode each task's exact demand using a sequential counter, rather than hardcoding two staff or listing all forbidden combinations. A shared IDPool keeps auxiliary IDs above N*M and avoids collisions; these IDs are not staff assignments.
  Rules: Require exact capacity, forbid Busy assignments and prevent double-booking. All staff can serve any role; baseline assignments are not fixed.
  Input handling: Invalid counts or indices raise ValueError. Demand greater than the staff count produces an empty clause (UNSAT), since the input is valid but impossible to satisfy.
  Checks: Existing encoder tests check small schedules and baseline capacity/overlap without Busy. Unknown Busy is rejected rather than treated as an empty list. TV4 handles the separate toy and seeded instance tests.

## M1 - Logic-to-linear bridge decisions (2026-09-19; revised 2026-09-20)

- **Scope:** Requirement 1.3 turns the M1 rules into 0/1 linear constraints and checks that
  translation. It does not encode CNF (that is `m1_logic/cnf.py`) and does not solve, so
  `m1_logic/linear_bridge.py` imports nothing outside the standard library and M2 can use it
  without a SAT solver.
- **Variables:** Keep the CNF encoder's numbering unchanged: `Assign(i,j)` is variable ID
  `i*M+j+1`, and `x_ij` is the 0/1 variable with that ID. M1 and M2 then exchange schedules and
  counterexamples with no translation layer. IDs above `N*M` only ever come from CNF auxiliaries.
- **Two translations, kept separate:** `clause_to_linear` / `cnf_to_linear` map one clause to one
  row and stay exact for any CNF, auxiliaries included; this is the version that justifies the
  mapping in the report. `encode_invigilator_assignment_linear` instead states capacity as one
  equality per task, which creates no auxiliary variable and gives a tighter LP relaxation.
  **M2 builds on the second**; the first is evidence, not a model to solve.
- **Normal form:** Clause rows are always emitted as `>=`, so a negative clause arrives as
  `-x_a - x_b >= -1` and `LinearConstraint.flip()` multiplies it by -1 into the `x_a + x_b <= 1`
  shown in the table. Repeated literals collapse, a tautology becomes `0 >= 0`, and the empty
  clause becomes `0 >= 1`, matching the empty clause `cnf.py` appends for an impossible demand.
- **Checks:** Each clause and cardinality pattern is compared with its Boolean meaning over _all_
  of its truth assignments rather than sampled ones: 9 patterns, 0 mismatches. The instance model
  is compared with an independent rule checker over every 0/1 assignment of small instances, and
  with the CNF encoder through Minisat assumptions. Tests now use capacity, Busy and overlap
  only; the baseline check explicitly uses empty Busy to check historical capacity/overlap.
- **Counterexamples kept in the module:** five plausible but wrong mappings, each with the witness
  that refutes it. Two that matter here: reading `a v b` as `x_a + x_b == 1` rejects the legal
  `a = b = 1`, and writing hard rule H2 as `x_a + x_b >= 1` inverts it, allowing the double
  booking `a = b = 1` while banning the idle `a = b = 0`. Keeping only half of `exactly-k` leaves
  a task unstaffed (`<= k`) or overstaffed (`>= k`), which M2's objective would then exploit.
- **Instance size:** The full CSV has 73 staff and 83 sessions, giving 6,059 assignment
  variables. Raw Busy remains unknown. Executable examples use the smaller real-data slice
  and availability from `prepare_instances(seed)`; absence from baseline does not imply Busy.
  Both the linear encoder and selector encoder take the same four arguments as the CNF
  encoder and reject unknown Busy. There are no role or eligibility constraints.
- **Handoff:** M2 consumes `LinearModel.constraints` directly (`coefficients`, `sense`, `rhs`,
  `origin`); there is no objective here, since fairness weights and soft rules belong to M2. The
  two tables below are generated by `bridge_table_markdown()` - regenerate and repaste them after
  any change to the module; the generator escapes `|`, so a cell such as `1 - |N|` cannot split
  the row. `python -m m1_logic.linear_bridge` prints the same table separately.

### Notation (M1 -> M2)

| Symbol           | Meaning                                                                |
| ---------------- | ---------------------------------------------------------------------- |
| `I, i`         | Set of staff and its index; i = 0..N-1, ordered as staff_ids           |
| `J, j, k`      | Set of sessions (shift code, campus); j = 0..M-1, as session_ids       |
| `d_j`          | Demand of task j: shift_demands[j], the exact number of staff          |
| `Assign(i,j)`  | Predicate: staff i works task j                                        |
| `x_ij`         | 0/1 variable for Assign(i,j); variable ID i*M+j+1                      |
| `Busy(i,j)`    | Data: staff i is unavailable for session j; seeded scenario field busy |
| `Overlap(j,k)` | Data: tasks j and k share time; loader field overlaps                  |

### Conversion table: logic -> 0/1 linear

| Rule / pattern       | FOL                                                             | Grounded clause                          | CNF (DIMACS)                          | Linear 0/1                           |
| -------------------- | --------------------------------------------------------------- | ---------------------------------------- | ------------------------------------- | ------------------------------------ |
| H1 Availability      | `forall i,j: Busy(i,j) -> not Assign(i,j)`                    | `-Assign(i,j)`                         | `[-v]`                              | `x_ij == 0`                        |
| H2 No double-booking | `forall i,j,k: Overlap(j,k) & Assign(i,j) -> not Assign(i,k)` | `-Assign(i,j) v -Assign(i,k)`          | `[-v1, -v2]`                        | `x_ij + x_ik <= 1`                 |
| H3 Exact capacity    | `forall j: exactly d_j staff i satisfy Assign(i,j)`           | `exactly-k over Assign(.,j)`           | `sequential counter, aux IDs > N*M` | `sum_i x_ij == d_j`                |
| Generic clause       | `disjunction over literals`                                   | `(v_p for p in P) v (-v_n for n in N)` | `[p.., -n..]`                       | `sum_P x_p - sum_N x_n >= 1 - \|N\|` |
| Clause a v b         | `a or b`                                                      | `a v b`                                | `[a, b]`                            | `x_a + x_b >= 1`                   |
| Clause -a v b        | `a -> b`                                                      | `-a v b`                               | `[-a, b]`                           | `x_b - x_a >= 0`                   |
| Clause -a v -b       | `not (a and b)`                                               | `-a v -b`                              | `[-a, -b]`                          | `x_a + x_b <= 1`                   |
| Exactly-one          | `exactly one of S`                                            | `exactly-one(S)`                       | `pairwise or counter`               | `sum_S x == 1`                     |
| At-most-k            | `at most k of S`                                              | `at-most-k(S)`                         | `counter encoding`                  | `sum_S x <= k`                     |
| Exactly-k            | `exactly k of S`                                              | `exactly-k(S)`                         | `counter encoding`                  | `sum_S x == k`                     |
| Empty clause         | `contradiction`                                               | `[]`                                   | `[]`                                | `0 >= 1 (infeasible row)`          |

Every x is a 0/1 variable: these rows are equivalences over integers, not over the LP relaxation.
`clause_to_linear` always emits the canonical `>=` form, so a clause of negative literals arrives as `-x_a - x_b >= -1`; `LinearConstraint.flip()` multiplies it by -1 into the `x_a + x_b <= 1` shown above.
M2 should build on `encode_invigilator_assignment_linear`, whose capacity equality has no auxiliary variables and a tighter relaxation than a clause-by-clause translation of the sequential counter.

## M1 - Solver integration (2026-09-20)

- `run_all.py --seed <seed> --stage m1` uses the prepared SAT/UNSAT slice and toy inputs.
  The solver consumes their Busy pairs unchanged. UNSAT runs first, then SAT; each writes
  `m1_logic/sat_result.json`, so the final file holds the SAT schedule. No second JSON is written.
  Output has only `satisfiable`, `model` (false for UNSAT), and `unsat_core` (null for SAT).
  Core descriptions use staff IDs and session labels (shift code plus campus), not indices.

## M2 - Vinh: data and variables v1 (2026-09-25; req 2.1, 2.2, 2.6)

- Reuse the M1 loader: 73 staff, 83 (shift, campus) sessions, 769 assignments; keep demand and time overlap unchanged, with no eligibility rule.
- The supplied M2 forum reply allows seeded availability using baseline as a prior, replacing the temporary `day` default. V1 keeps observed person/shift pairs available and flips each unobserved pair to available with probability 0.30, using Random(seed), sorted staff IDs then shift codes, one draw per unobserved pair. Availability is shared across campuses of a shift; overlap still prevents simultaneous work. This one-way flip preserves baseline feasibility without fixing assignments. The 30% rate and grouping are our v1 choices, not teacher-set values; generate on full data before slicing.
- Simulate preferences with a separate Random(seed): P(BAL)=1/3; split the remaining 2/3 by baseline campus frequencies (uniform without history). These are synthetic, not residence data. Import all three weights from tools.make_seed.soft_weights; v1 maps w1 to location, w2 to fatigue and w3 to travel. All three must enter the downstream objective. The preference probabilities and weight mapping are v1 choices permitted by the supplied guidance.
- Create only x[i,j] for pairs in A, Binary by default or Continuous [0,1] for relaxation; w[i] is a sum expression. Slices retain all available candidates and remap existing availability, overlap, baseline and preferences without resampling.
- The supplied forum clarification fixes beats_baseline to max_load < baseline_max_load; keep the full-data baseline value 19, computed from unchanged assignments. Baseline daily loads reach 4; K=3 is the v1 soft-fatigue handoff choice (7 of 472 active person-days exceed it), not a hard limit. Lead and the other owners still implement MODEL.md, penalties, solver, output and run_all integration.

## M2 - Nguyen: soft terms and the fatigue threshold (2026-10-02; req 2.5; D7)

- LOC = sum c_ij x_ij with c_ij = 1 when a CS1/CS2 person works the other campus; BAL costs nothing. Preferences are simulated (req 2.6), so LOC is a modelling choice, not a residence fact.
- FAT: s_id >= (sessions of i on day d) - K. TRV: z_idc >= x_ij for the sessions of day d at campus c, v_id >= z_id1 + z_id2 - 1 (forum d=33630: travel between campuses is a soft cost). s, z, v are continuous: with positive weights the minimisation pushes them to max(0, .), and an integer x forces z to 1.
- Variables are created only where the term can be positive: s when i has more than K available sessions that day (207), z and v when i can reach both campuses that day (1,002 and 501). The others would always be 0.
- D7 K = 3, fitted: the smallest K such that at least 95% of the baseline's 472 working person-days have at most K sessions (1: 246, 2: 162, 3: 57, 4: 7; share <= 3 is 98.5%). K is a penalty threshold, not a hard limit. Rejected: K = 2 (an 85% rule) would penalise 64 person-days of the human schedule, i.e. treat ordinary practice as fatigue; and any K not derived from the data.
- `evaluate_soft` measures any fixed schedule with the same definitions; tests check it equals the model's three expressions at the solver's schedule.

## M2 - Nguyen: infeasibility handling and sensitivity (2026-10-02; req 2.8)

- Relax: when stage 1 is infeasible, `solve` calls `tuning.diagnose`: H3 becomes sum x + u_j = r_j, u_j >= 0, with objective t + 1000 sum u_j. 1000 exceeds any gain in t, so the solver first minimises the total shortage. Sessions with u_j > 0 play the role of M1's unsat core. On M1's UNSAT slice (prepare_instances(seed)) both name 20260610_2_CS2: M1's core gives the reason (capacity + 5 Busy facts), u_j gives the size (1 person missing). No weight or LP relaxation can fix that; the data or the rule must change.
- Re-weight: each weight scaled by 0.5, 1, 2 and K in {2, 3, 4}, on the prefixes of 1, 2, 3 weeks and the full data. The horizons are fixed by the calendar before looking at results.
- Findings: max load never changes (stage 1 is separate). On 3 weeks, doubling lambda_LOC trades L1 28.11 -> 48.82 for LOC 17 -> 3; the two schedules tie at lambda_LOC ~ 1.48, above our 0.84, so fairness wins with the team's weights. FAT and TRV are 0 in every run: availability is wide enough to avoid them at no fairness cost. K = 2 costs location (LOC 28 -> 50 on full data); K = 4 equals K = 3.
- Decision: keep the generated weights and K = 3. Changing weights until the table looks nicer would break the seed rule.

## M3 - Two-shift days, JSON format and rules (2026-10-21; req 3.1)

- Alphabet is fixed to {M, A, N, -}, one symbol per day (brief, confirmed by the instructor on the forum, 2026-10-21). Sessions map to symbols by start time: 07g00 and 09g30 are M, 13g00 and 15g30 are A, 18g15 is N, no session is "-".
- Assumption: the 18g15 session is treated as the night shift N. The brief only allows stating assumptions about night shifts; if 18g15 were an evening shift the data would contain no night shift and R2 would never apply. Not covered by the instructor's reply.
- Two-shift days: 169 of 472 (person, day) pairs have two sessions of different class (168 morning + afternoon, 1 afternoon + night). The kept symbol follows the priority N > A > M (morning + afternoon -> A, afternoon + night -> N, morning + night -> N). Rejected: a fifth symbol D (breaks the fixed alphabet) and forbidding two-shift days in M2 (the baseline violates 169 pairs and the ILP may become infeasible). Consequence: R4 counts the kept symbol, so it leans towards A.
- JSON: nested dict, `transitions[state][symbol] -> state`, complete DFA with all 4 symbols for every state and an explicit trap state `dead`. The format lives in one `to_json` method of dfa.py so it can be changed in one place. One file per rule in `m3_automata/`.
- Rules: R1 no more than 2 consecutive working days (4 states, trap included); R2 a night shift must be followed by a rest day (3 states); R3 at most 4 working days in any 7-day window (58 reachable states, 36 after minimisation); R4 |#M - #A| <= 3 at every prefix, i.e. "at all times" (8 states), following the brief's wording "never differ" and bounded counter -c..c plus a trap. Working day means M, A or N.
- Prototype numbers to reproduce in run_all.py --stage m3: R1xR2 11 -> 4, R1xR2xR3 259 -> 15, R1..R4 2072 -> 99 states. On the 73 baseline strings the violations are R1 28, R2 5, R3 3, R4 20 (19 if only the end of the term is checked); R1 and R2 and R3 together reject 32 and accept 41.
- One file per rule in `m3_automata/`: dfa_max2_consecutive.json (R1), dfa_night_then_rest.json (R2), dfa_max4_in_7days.json (R3) and minimization.json with the R1xR2xR3 counts, named and spelled as in the instructor's test (states run0-run2, free/after_night, w+six bits; 2026-11-05). R4 and the ILP results are in `m3_automata/extra/` so that only these four JSON files are in `m3_automata/`.

## M3 - Linking the DFA to the M2 model (2026-10-21; req 3.3)

- Own flow model on the layered graph, written with PuLP/CBC like M2; OR-Tools AddAutomaton is only an optional cross-check.
- Link to M2: u[i,t,a] = 1 if staff i has at least one session of class a on day t (u >= x[i,j] and u <= sum of x[i,j] over those sessions); day symbol z[i,t,.] chosen with priority N > A > M (z_N = u_N, z_A >= u_A - u_N, z_A <= u_A, z_A <= 1 - u_N, z_M likewise, z_- = 1 - sum z); flow y[i,t,q,a] with sum over q of y = z[i,t,a] and the usual flow conservation per staff. y can stay continuous in [0,1] because z is binary.
- Only R1xR2xR3 (15 states) is added to M2; R4 is handled at DFA level and in the proof (3.4), because R1..R4 (99 states) reached the 150 s limit in the prototype.
- Prototype on the real M2 instance (seed 1358677812): max_load t* = 11 in all variants (baseline 19); stage-2 objective 59.85 (M2 alone, 0.4 s), 66.57 with R1xR2xR3 (16.8 s), 69.93 with R1..R4 (148 s, time limit). These must be re-measured by the team's own code.
- The reference code used for the prototype is not in the repo; the team rewrites it in its own structure so DECISIONS.md and the explanations are the team's own.

## M4 - Vector fatigue and fairness (2026-11-15)

- Choose exactly direction B. It exposes the relationship between load imbalance
  and fatigue spread and can use the existing baseline and M2 schedule directly.
  A would need a feedback allocation policy; C would need availability states
  which cannot be observed from absence in the baseline.
- Count actual assignments in consecutive calendar weeks from the first session,
  retaining idle days and staff. Convert the final six-day block to a weekly
  rate for calibration and account for its duration in simulation. Export running
  workload as descriptive data; it has no claimed equilibrium.
- Define fatigue in weekly-load-equivalent units. Fit a lag-one workload
  regression with an intercept as a transparent proxy for retention; do not
  describe it as observed fatigue. On this dataset a=0.270634, with weak
  R-squared 0.061930. Set r=0 because separate recovery cannot be identified.
  Calibrate b=1-a so mean equilibrium equals mean observed weekly load. Report
  these limitations; do not invent fatigue measurements or clip an unsupported
  retention estimate into the stable interval.
- Analyze the autonomous constant-average-load vector map separately from the
  finite observed trajectory. Equal weekly average load has one attracting
  common equilibrium; unequal load leaves a nonzero equilibrium spread. Use
  nonuniform initial fatigue, check both spread and variance contraction, and
  verify stable, neutral and unstable parameter regimes with perturbations.
- Fit the soft threshold from the baseline's block-end proxy fatigue at 95%
  coverage. Add exact recurrence rows and nonnegative exceedance slacks to M2
  stage 2, preserving the completed schedule's max-load cap. Penalize excess
  with the existing seed-derived fatigue weight. A one-shot M2-based refinement
  gives zero excess without changing max load 11 or L1 fairness. M3 temporal
  acceptance is not asserted for this variant; the helper can be added to the
  same model as M3's regular constraints.
- Keep M4 output in its own directory and make `run_all.py --stage m4`
  reproduce all results and figures. Mathematical checks, independent schedule
  validation and solver/simulator agreement must pass before results are saved.
  See `m4_dynamics/README.md` for the full derivation and assumptions.

## Repo & Git policy

- Turned on Branch protection rule for `main` (require PR, no force-push, no deletion).
- The team commited to manual compliance: no one uses `git push --force` up to main.
