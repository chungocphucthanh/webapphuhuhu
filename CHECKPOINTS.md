
# Weekly checkpoints (one dated entry per week)

## week-01 (7-13 Sep)

Progress: Set up the repository (Git workflow, branch protection, .gitignore, dependencies aligned to python-sat==1.8.dev16), preprocessed the Excel dataset and wrote the loader, recorded the modeling decisions in DECISIONS.md, and drafted the Module 1 report.
Per member:
<2551931 Dinh Hoang Quang Vinh> scaffolded the M1 module, implemented the Excel data loader (data_loader.py), wrote preprocessing edge-case and verification tests, and documented the data modeling decisions.
<2551896 Nguyen Quoc Hung> set up the Git workflow and branch protection, maintained MEETINGS.md, and merged pull requests into main.
<2551919 Dang Nguyen Thien Phuc> configured .gitignore, aligned the dependencies with python-sat==1.8.dev16, and coordinated task assignment and meeting schedules.
<2551922 Chu Ngoc Phuc Thanh> drafted the First-Order Logic specification and the formal modeling section of the M1 report.
<2551913 Vo Nguyen Vi Nguyen> checked the Git workflow with every member, reviewed and polished teammates' work, and helped reach the team decisions.

## week-02 (14-20 Sep)

Progress: Finished Module 1: CNF encoding (req 1.2), SAT solving with UNSAT core extraction, the logic-to-linear bridge (req 1.3), the revised Busy/availability rules, the switch from Excel to seeded CSV instances, an M1 stage in run_all.py, and the first M1 report PDF (tag m1).
Per member:
<2551931 Dinh Hoang Quang Vinh> revised the Busy rules, moved the loader to CSV, added prepare_instances.py with seeded SAT/UNSAT cases, and refined the UNSAT core extraction and solver output.
<2551896 Nguyen Quoc Hung> implemented linear_bridge.py with tests (req 1.3), renamed sat_solve.py to sat_check.py and added the minimal UNSAT core slice, wired M1 into run_all.py, and merged the pull requests.
<2551919 Dang Nguyen Thien Phuc> implemented the variable mapping and CNF encoding in cnf.py with tests (req 1.2) and documented it in DECISIONS.md, README.md and CONTRIBUTIONS.md.
<2551913 Vo Nguyen Vi Nguyen> implemented the SAT solver and model extraction (req 1.2), added UNSAT handling in unsat_core.py, and fixed the missing openpyxl dependency.
<2551922 Chu Ngoc Phuc Thanh> compiled and added the first Module 1 report PDF under report/.

## week-03 (21-27 Sep)

Progress: Split the Module 2 (LP/ILP) work among the five members and recorded it in MEETINGS.md (22 Sep). Delivered the M2 data and variables handoff (req 2.1, 2.2, 2.6): the Instance built from the M1 loader, seeded availability (baseline prior, flip rate 0.30), seeded preferences and soft weights, sparse x_ij variables and w_i expressions, with the availability decision recorded in DECISIONS.md. The Lead re-verified the instance statistics (73 staff, 83 sessions, baseline max_load 19) and fixed a Python 3.9/macOS import failure.
Per member:
<2551931 Dinh Hoang Quang Vinh> implemented instance.py and variables.py (req 2.1, 2.2, 2.6) with 8 passing tests.
<2551896 Nguyen Quoc Hung> reviewed the data-and-variables handoff, verified its statistics and tests, and added `from __future__ import annotations` so M2 runs on macOS/Python 3.9.

## week-04 (28 Sep-4 Oct)

Progress: Started the M2 formulation and documentation. Wrote the mathematical formulation (hard constraints, soft constraints, objective) and documented the data and decision variables. The meetings on 1 and 4 Oct revised how the module sections are divided and planned the solver, tuning and soft-constraint work (tag week-04).
Per member:
<2551922 Chu Ngoc Phuc Thanh> wrote the M2 mathematical formulation: hard and soft constraints and the objective.
<2551931 Dinh Hoang Quang Vinh> documented the M2 data and decision variables (req 2.1, 2.2, 2.6) and fixed the module .md files.
<2551896 Nguyen Quoc Hung> kept MEETINGS.md up to date and merged the pull requests.

## week-05 (5-11 Oct)

Progress: Finished Module 2: the objective and performance analysis (req 2.3, 2.9), the soft penalties with K fitted from the baseline and the infeasibility diagnosis with sensitivity analysis (req 2.5, 2.8), the hard constraints with the independent validator and the counterexamples (req 2.4, 2.10), and the model assembly, two-stage solve and run_all integration (req 2.7). The team reviewed and unified all M2 files on 11 Oct (tags Week-05 and m2).
Per member:
<2551919 Dang Nguyen Thien Phuc> added the fairness objective and the performance analysis (req 2.3, 2.9).
<2551913 Vo Nguyen Vi Nguyen> implemented the soft penalties LOC/FAT/TRV, evaluate_soft and K fitted from the baseline (req 2.5), and the elastic infeasibility diagnosis with weight and K sensitivity (req 2.8).
<2551922 Chu Ngoc Phuc Thanh> added the hard constraints H1-H3, the independent validator and the two counterexamples (req 2.4, 2.10).
<2551896 Nguyen Quoc Hung> finished the model assembly and interfaces (req 2.7), then merged and reconciled all M2 parts in one update (11 Oct).

## week-06 (12-18 Oct)

Progress: Midterm week; no new commits on main. Module 2 was already merged and tagged (m2) on 11 Oct.
Per member: no commits this week.

## week-07 (19-25 Oct)

Progress: Started Module 3. The meeting on 21 Oct split M3 among the five members, adopted the instructor's answers on the DFA JSON format and on two-shift days (priority N > A > M), and fixed the timeline to 8 Nov. Delivered the DFA class and CSV-to-string encoder (req 3.1), the R1-R3 DFAs with the three submitted JSON files and their explanation (req 3.1), and the regular-constraint ILP with the before/after comparison (req 3.3). Corrected the prototype counts in DECISIONS.md to what the code produces (R2 5, 32 rejected, 41 accepted). Opened issues #50-#53 for the text fixes, the file layout, and the open tasks for 3.2 and 3.4.
Per member:
<2551919 Dang Nguyen Thien Phuc> added dfa.py and encode_strings.py (req 3.1), the M3 decisions and AI-use note, the corrected prototype counts, reviewed the pull requests, and opened issues #50-#53.
<2551931 Dinh Hoang Quang Vinh> implemented rules.py with R1-R3, the three DFA JSON files and 3.1.md (req 3.1), and revised the text after review.
<2551896 Nguyen Quoc Hung> implemented regular_to_ilp.py (flow model on the layered graph, link to the M2 variables, re-solve and comparison) and 3.3.md (req 3.3), and merged the pull requests.
<2551913 Vo Nguyen Vi Nguyen> rewrote the Module 2 reports in English; product_min.py (req 3.2) is planned for week-08 (issue #52).
<2551922 Chu Ngoc Phuc Thanh> R4 and the pumping proof (req 3.4) are planned for week-08 (issue #53); no M3 commit yet.

## week-08 (26 Oct-1 Nov)

Progress: Merged the revised 3.1 theory file (PR #54, 27 Oct) and the move of 3.3 into m3_automata/ with its rewrite (PR #56, 1 Nov), which closed issues #50 and #51. Module 3 on main now holds the DFA class, the string encoder, R1-R3 with the three submitted JSON files, and the regular-constraint ILP with its before/after comparison. 3.2 (product_min.py, issue #52) has no commit and 3.4 (R4, issue #53) is not on main yet; both block run_all.py --stage m3 and the tag m3.
Per member:
<2551931 Dinh Hoang Quang Vinh> revised 3.1.md after review (PR #54): formal definitions, correctness arguments and a neutral README link (issue #50).
<2551896 Nguyen Quoc Hung> moved regular_to_ilp.py, 3.3.md and the JSON into m3_automata/, merged main and resolved the 3.3 conflicts, and rewrote 3.3.md to the module style (PR #56, issue #51).
<2551919 Dang Nguyen Thien Phuc> reviewed and merged PRs #54 and #56, tracked the open issues #52 and #53, and checked the R4 branch against the data.
<2551913 Vo Nguyen Vi Nguyen> no M3 commit on main this week; product_min.py and 3.2.md (req 3.2) are due before 8 Nov.
<2551922 Chu Ngoc Phuc Thanh> R4 DFA, dfa_R4.json, pumping.md and 3.4.md (req 3.4) are on branch m3_thanh (1 Nov) and not merged yet.

## week-09 (2-8 Nov)

Progress: Closed Module 3. Merged R4 with the pumping proof and 3.4.md (PR #58, 3 Nov), the export of R4 in rules.main with the README order (PR #59, 3 Nov), product_min.py with 3.2.md (PR #60, 4 Nov), and the grader file layout with run_all.py --stage m3 (PR #61, 5 Nov). All four requirements 3.1-3.4 are now on main: the three submitted DFA files and minimization.json sit in m3_automata/, R4 and the ILP results in m3_automata/extra/. `python run_all.py --seed $(cat data/seed.txt) --stage m3` rebuilds the files and prints the violations (R1 28, R2 5, R3 3; 32 rejected and 41 accepted), R4 (20 of 73 by prefix, 19 at the end of the term), the state counts (R1xR2xR3 259 to 15, with R4 2072 to 99) and the ILP re-solve (objective 59.849 to 66.569, all 73 strings accepted). DECISIONS.md now gives R4 as 20. Tag m3 is created on 8 Nov after this checkpoint is merged. Not done: the "valid" flag in the app (app/ holds only a README) and replacing the stand-in product in regular_to_ilp.py by product_min.py (same counts, no effect on results).
Per member:
<2551922 Chu Ngoc Phuc Thanh> added r4() and r4_counts() in rules.py, dfa_R4.json, pumping.md, 3.4.md and test_r4.py (PR #58, req 3.4).
<2551913 Vo Nguyen Vi Nguyen> added product_min.py (product, partition refinement, counts table), 3.2.md and test_product_min.py (PR #60, req 3.2).
<2551919 Dang Nguyen Thien Phuc> fixed rules.main and the README order (PR #59), renamed the DFA files and states to the grader format, added minimization.json, moved R4 and the ILP results to extra/, wired run_all.py --stage m3, corrected R4 in DECISIONS.md (PR #61), reviewed and merged PRs #58-#61.
<2551896 Nguyen Quoc Hung> no M3 commit this week; regular_to_ilp.py and 3.3.md from week-08 are unchanged and pass their tests.
<2551931 Dinh Hoang Quang Vinh> no M3 commit this week; 3.1.md was updated for the new state names in PR #61.
