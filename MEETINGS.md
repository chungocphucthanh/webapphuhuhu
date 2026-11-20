# Weekly meeting minutes

## 2026-09-09 (week-01)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:
  - Team ID decides: CO2011-261-A01-2551896; seed = 1358677812; soft_weights = [0.84, 1.9, 1.97]
- Task split for the coming week (who does what across all four modules):
  - Module leads: M1 <Đinh Hoàng Quang Vinh>, M2 <Nguyễn Quốc Hùng>, M3 <Đặng Nguyễn Thiên Phúc>, M4 <Võ Nguyễn Vĩ Nguyên>, M5/report <Chu Ngọc Phúc Thành>
  - Each member commit at all 4 modules (>= 1 commit for each module)
  - Meeting for 30 minutes

## 2026-09-10 (week-01)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:
  - Task split in M1:
    1.1: Chu Ngọc Phúc Thành (REQ: 1.1 — Fix the notation, domains, predicates and hard rules; coordinate integration)
    1.2: Võ Nguyễn Vĩ Nguyên (REQ: 1.2 — SAT solver, model and UNSAT/core)
    1.3: Nguyễn Quốc Hùng (REQ: 1.3 — Logic → linear bridge)
    1.4: Đặng Nguyễn Thiên Phúc (REQ: 1.2 — Variable mapping and CNF encoding)
    1.5: Đinh Hoàng Quang Vinh (REQ: 1.2 — Real data, preprocessing and independent verification)
  - Module leads: M1 <Đinh Hoàng Quang Vinh>, M2 <Nguyễn Quốc Hùng>, M3 <Đặng Nguyễn Thiên Phúc>, M4 <Võ Nguyễn Vĩ Nguyên>, M5/report <Chu Ngọc Phúc Thành>
  - Meeting for 60 minutes

## 2026-09-16 (week-02)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:
  - Decisions:

1. Revise Busy generation: baseline assignment implies availability. “Not assigned” does not mean “busy”.
2. Define Observed from baseline assignments and Busy = Drawn \ Observed. Require Busy ∩ Observed = ∅.
3. Replace implicit 50/50 probability with busy_rate (default: [0.2 or 0.3]). Test 0.2, 0.3, and 0.5.
4. Keep seed 1358677812 and sorted ordering. Generate all random draws before removing Observed. Data slices inherit Busy instead of regenerating it.
5. Keep history-based role eligibility: Eligible(i,r) if staff i performed role r in the baseline. Document this as a conservative assumption.
6. Compare baseline and new schedules under identical data and constraints. Validate both for capacity, Busy, eligibility, and overlap.
7. Use one workload definition [proposed: number of assignments]. Evaluate fairness using max load and L1 deviation. Claim improvement only when experimentally verified.
8. Add reproducibility, Busy-invariant, slicing, baseline-SAT, and independent-validator tests.
9. run_all.py must report seed, busy_rate, Busy statistics, baseline violations, and SAT result. Conclusions must specify the availability scenario.
10. Discuss the design and next tasks for Hùng and Nguyên.

## 2026-09-19 (week-02)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

1. Revise the m1_logic code.
2. Discuss the file structure of run_all.py.
3. Discuss Module 2.

## 2026-09-20 (week-02)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

1. Wrap up M1 and verify all cases end to end.
2. Plan the work for M2.
3. Write the checkpoint and the contributions record.
4. Tag the week-02 commit.
5. Run the rubric YAML file to score the work.

## 2026-09-22 (week-03)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:
  - Task split in M2 (LP/ILP):
    TV1: Đinh Hoàng Quang Vinh (REQ 2.1, 2.2, 2.6 — Instance from M1 data, availability set A, toy/slice instances, decision variables, seeded simulated data)
    TV2: Chu Ngọc Phúc Thành (REQ 2.4, 2.10 — hard constraints H1-H3, independent validator, cross-check against M1 rules, counterexamples)
    TV3: Nguyễn Quốc Hùng — Lead (REQ 2.7 — MODEL.md and interfaces, build_model, two-stage solve with PuLP/CBC, autograder outputs, integration)
    TV4: Đặng Nguyễn Thiên Phúc (REQ 2.3, 2.9 — metrics and baseline figures, objective function, performance and baseline comparison)
    TV5: Võ Nguyễn Vĩ Nguyên (REQ 2.5, 2.8 — soft penalties LOC/FAT/TRV, fitting K from data, infeasible handling and sensitivity tuning)
  - D1 availability: ask the instructor how availability should be defined for M2; if no answer by 2026-09-24, use "day" mode and record it in DECISIONS.md.
  - D2 objective: lexicographic — stage 1 minimises max_load t, stage 2 keeps t <= t* and minimises L1 plus the weighted soft penalties.
  - Lead publishes MODEL.md first as the shared contract; any interface change goes through a PR.
  - run_all.py writes m2_ilp/schedule.csv and m2_ilp/metrics.json only after the independent validator reports no violation.
  - Tag week-03 and self-score with rubric.yaml before the tag.

## 2026-10-01 (week-04)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

1. Revise the logic for how the sections of the Module are divided
2. Prepare the remaining parts of the Module for next week

##2026-10-04 (week-04)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

1. Discuss how to implement the logic of the solver, fine-tuning, and soft constraints.
2. Draft the team's Module 2 section of the report.
3. Write the end-of-week checkpoint.

## 2026-10-11 (week-05)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

1. Review and revise the whole Module together and fix the errors found
2. Update MEETINGS.md and CHECKPOINTS.md
3. Discuss Module 3 and the midterm material

## 2026-10-21 (week-07)

- Attendance: 2551896 Nguyễn Quốc Hùng, <2551931 Đinh Hoàng Quang Vinh>, <2551896 Nguyễn Quốc Hùng>, <2551919 Đặng Nguyễn Thiên Phúc>, <2551913 Võ Nguyễn Vĩ Nguyên> <2551922 Chu Ngọc Phúc Thành>
- Decisions:

  - Instructor reply on the forum (Mai Xuân Toàn, 2026-10-21 08:08):
    Q1 JSON: the brief does not fix the structure inside `transitions`; nested dict {"q0": {"M": "q1", "-": "q0", ...}} is accepted, but every state must have a transition for all 4 symbols.
    Q2 two-shift days: Σ = {M, A, N, -} is fixed with one symbol per day, no extra symbol; our priority N > A > M is accepted. Record the convention in DECISIONS.md and the report.
  - Task split in M3 (Automata), Phúc is M3 lead:
    1: Đinh Hoàng Quang Vinh (REQ 3.1 — rules.py with R1, R2, R3, the JSON files to submit, DFA tests against plain Python predicates)
    2: Chu Ngọc Phúc Thành (REQ 3.4, R4 — bounded-counter DFA for |#M-#A| <= c, pumping.md, M3 part of the report)
    3: Nguyễn Quốc Hùng (REQ 3.3 — regular_to_ilp.py, layered-graph flow model, linking to the M2 variables x[i,j], re-solve and before/after comparison)
    4: Đặng Nguyễn Thiên Phúc — Lead (REQ 3.1 — encode_strings.py, dfa.py, DECISIONS.md; run_all.py --stage m3, "valid" flag in the app, integration, tag m3)
    5: Võ Nguyễn Vĩ Nguyên (REQ 3.2 — product_min.py, state-count table, independent recomputation with a second algorithm)
  - Timeline: week-07 (19-25 Oct) dfa.py, strings, R1-R3 and JSON; week-08 (26 Oct-1 Nov) product and minimisation, flow model and M2 linking; week-09 (2-8 Nov) pumping and report, run_all, cross-review, tag m3. Deadline 8 Nov (one 48h grace token only if declared in CHECKPOINTS.md before the deadline).
  - Every member needs at least one non-trivial commit in each module; commit messages carry the requirement id, e.g. "m3: R1,R2 DFA JSON (req 3.1)".
  - Cross-review: Vinh reads 3.2, Nguyên reads 3.4, Thành reads 3.1, Phúc reads 3.3.

  ## 2026-10-25 (week-08)


  - Attendance: 2551931 Đinh Hoàng Quang Vinh, 2551896 Nguyễn Quốc Hùng, 2551919 Đặng Nguyễn Thiên Phúc, 2551913 Võ Nguyễn Vĩ Nguyên, 2551922 Chu Ngọc Phúc Thành
  - Decisions:

    - Status of M3 (checked on `main` after PR #49): 3.1 code and JSON (R1-R3), the DFA class, the string encoder and 3.3 (flow model, M2 linking, before/after table) are merged. 3.2 (product_min.py) and 3.4 (R4, pumping.md) have no commits yet.
    - Corrected baseline numbers for the 73 strings: 9 staff with a night shift, R1 28, R2 5, R3 3 violations, 32 rejected and 41 accepted by R1, R2 and R3 together (DECISIONS.md updated in PR #44). The R4 numbers in the slide do not reproduce with the current encoder (direct check, c = 3: 20 of 73 for "at all times", 19 for "end of term only"); Thành confirms them with his own code before DECISIONS.md is changed.
    - Writing standard: every theory file (3.1-3.4) follows the way m2_ilp/2.3.md is written: title "# 3.x Short title", first sentence links the code, definition, argument, small hand example, "Functions in the code", limits; no slide, leader or instructor references; every statement checkable from the repo.
    - Layout: all M3 files sit directly in m3_automata/ (as in the module layout). regular_to_ilp.py and 3.3.md move out of m3_automata/3.3/, which currently breaks the import and 4 links.
    - Issues opened and assigned: #50 Vinh (rewrite 3.1.md), #51 Hùng (move files, fix 3.3.md), #52 Nguyên (product_min.py, 3.2.md), #53 Thành (r4(), dfa_R4.json, pumping.md, 3.4.md).
    - Week-08 targets: product_min.py and the state-count table merged by 1 Nov; r4() and pumping.md merged by 1 Nov; once product_min.py is merged, regular_to_ilp.py uses it instead of its own product and minimisation.
    - Cross-review as agreed in week-07: Vinh reads 3.2, Nguyên reads 3.4, Thành reads 3.1, Phúc reads 3.3. Reviews are posted on the PR before merging.

  ## 2026-11-01 (week-09)

- Attendance: 2551931 Đinh Hoàng Quang Vinh, 2551896 Nguyễn Quốc Hùng, 2551919 Đặng Nguyễn Thiên Phúc, 2551913 Võ Nguyễn Vĩ Nguyên, 2551922 Chu Ngọc Phúc Thành
- Decisions:
  - Status of M3 on main (after PR #56): 3.1 (R1-R3, JSON, 3.1.md), the DFA class, the encoder and 3.3 (regular_to_ilp.py, 3.3.md) are merged. 3.2 has no commit. 3.4 exists only on branch m3_thanh.
  - Thành opens the PR for m3_thanh after two fixes in 3.4.md: main() in rules.py exports only R1-R3 although the text says it writes dfa_R4.json (either add R4 to main() or change the text), and the CB003 example is wrong (CB003 never leaves |d| <= 3 at any prefix and ends at d = -1). r4(c) itself matches the direct predicate on all words of length 0-7 and gives 20 of 73 (prefix reading) and 19 of 73 (end-of-term reading).
  - DECISIONS.md line on the prototype counts is corrected for R4: 20, not 28, once the m3_thanh PR is merged.
  - Nguyên merges product_min.py and 3.2.md by 4 Nov (issue #52), with the state counts R1 4/4, R2 3/3, R3 58/36, R1xR2 11/4, R1xR2xR3 259/15 and a second algorithm as cross-check. Hùng then replaces the stand-in product in regular_to_ilp.py by product_min.py.
  - Phúc adds run_all.py --stage m3 and the "valid" flag in the app after product_min.py is merged, and tags m3.
  - Each member updates the AI-tool declaration in README.md for the part they wrote.
  - Cross-review before the tag: Vinh reads 3.2, Nguyên reads 3.4, Thành reads 3.1, Phúc reads 3.3.
  - Deadline for M3 is 8 Nov; a grace token is declared in CHECKPOINTS.md before that date or not at all.

  ## 2026-11-08 (week-10)

- Attendance: 2551931 Đinh Hoàng Quang Vinh, 2551896 Nguyễn Quốc Hùng, 2551919 Đặng Nguyễn Thiên Phúc, 2551913 Võ Nguyễn Vĩ Nguyên, 2551922 Chu Ngọc Phúc Thành
- Decisions:
  - Status of M3 on main (after PR #61): 3.1-3.4 are merged with their theory files. run_all.py --stage m3 runs from a clean checkout and reproduces the table of numbers in CHECKPOINTS.md. M3 is closed and tagged m3 on 8 Nov.
  - File layout follows the instructor's test: the three DFA files (dfa_max2_consecutive.json, dfa_night_then_rest.json, dfa_max4_in_7days.json) and minimization.json are the only JSON files in m3_automata/; R4 (extra/dfa_R4.json) and the ILP results (extra/regular_to_ilp.json) are not graded rules and live in extra/. State names follow the same test (run0-run2, free/after_night, w+six bits).
  - R4 count in DECISIONS.md is corrected to 20 of 73 (19 if only the end of the term is checked).
  - Not done and moved to the report phase: the "valid" flag in the app (the app folder is empty), and the switch of regular_to_ilp.py to product_min.py.
  - Next: Module 4 split and timeline at the next meeting.

## 2026-11-15 (week-10)

- Attendance: 2551931 Đinh Hoàng Quang Vinh, 2551896 Nguyễn Quốc Hùng, 2551919 Đặng Nguyễn Thiên Phúc, 2551913 Võ Nguyễn Vĩ Nguyên, 2551922 Chu Ngọc Phúc Thành
- Decisions:
  - Task split in M4 (direction B, vector fatigue and fairness), Nguyên is M4 lead and made the split this week:
    1: Nguyễn Quốc Hùng (workload.py — real-data weekly workload extraction from the M2 schedule)
    2: Chu Ngọc Phúc Thành (fatigue.py, tests/test_fatigue.py — vector fatigue recurrence, calibration, fixed points and stability)
    3: Đặng Nguyễn Thiên Phúc (planning.py, tests/test_planning.py — soft fatigue threshold in the ILP)
    4: Đinh Hoàng Quang Vinh (run.py, plots.py, tests/test_run.py, run_all.py --stage m4 — integration and reproducible outputs)
    5: Võ Nguyễn Vĩ Nguyên — Lead (m4_dynamics/README.md, README.md, DECISIONS.md — documentation of direction B and the calibration assumptions, CONTRIBUTIONS.md)
  - Status of M4 on main: every member finished the assigned part, pushed it to a branch and merged it into main (PRs #63, #64, #65 and #67). The documentation and the M4 section of CONTRIBUTIONS.md are on main as well.
  - Next: prepare Module 5 and the final steps of the course. The report video (recorded presentation of the project) and the written report are the two remaining deliverables. Each member checks their own part of the report against the code on main before it is submitted.
