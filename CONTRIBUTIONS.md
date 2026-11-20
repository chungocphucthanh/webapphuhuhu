# Contribution ledger (who did what) + signed % table

| Requirement                         | Primary owner (StudentID)      | Reviewers        |
| ----------------------------------- | ------------------------------ | ---------------- |
| 1.1 Predicate specification         | 2551922 Chu Ngoc Phuc Thanh    | ...              |
| 1.2 CNF variable mapping & encoding | 2551919 Dang Nguyen Thien Phuc | 2551913, 2551931 |
| 1.2 SAT solver & UNSAT core         | 2551913 Vo Nguyen Vi Nguyen    | 2551919          |
| 1.2 Dataset preprocessing           | 2551931 Dinh Hoang Quang Vinh  | 2551919          |
| 1.3 Logic-to-LP bridge              | 2551896 Nguyen Quoc Hung       | 2551919          |

| Member (StudentID Name)        | Contribution % | Signature |
| ------------------------------ | -------------- | --------- |
| 2551922 Chu Ngoc Phuc Thanh    | 100%           | Thanh     |
| 2551919 Dang Nguyen Thien Phuc | 100%           | Phuc      |
| 2551913 Vo Nguyen Vi Nguyen    | 100%           | Nguyen    |
| 2551931 Dinh Hoang Quang Vinh  | 100%           | Vinh      |
| 2551896 Nguyen Quoc Hung       | 100%           | Hung      |

## Module 2 (LP/ILP): contribution ledger + signed % table

| Requirement                                                                            | Primary owner (StudentID)      | Reviewers |
| -------------------------------------------------------------------------------------- | ------------------------------ | --------- |
| 2.1 Instance from M1 data & availability set A                                         | 2551931 Dinh Hoang Quang Vinh  | ...       |
| 2.2 Decision variables                                                                 | 2551931 Dinh Hoang Quang Vinh  | ...       |
| 2.3 Objective function                                                                 | 2551919 Dang Nguyen Thien Phuc | ...       |
| 2.4 Hard constraints H1-H3 & independent validator                                     | 2551922 Chu Ngoc Phuc Thanh    | ...       |
| 2.5 Soft penalties LOC/FAT/TRV                                                         | 2551913 Vo Nguyen Vi Nguyen    | ...       |
| 2.6 Toy/slice instances & seeded simulated data                                        | 2551931 Dinh Hoang Quang Vinh  | ...       |
| 2.7 MODEL.md, build_model, two-stage solve (PuLP/CBC), autograder outputs, integration | 2551896 Nguyen Quoc Hung       | ...       |
| 2.8 Infeasible handling & sensitivity tuning (fit K from data)                         | 2551913 Vo Nguyen Vi Nguyen    | ...       |
| 2.9 Metrics, baseline figures, performance & baseline comparison                       | 2551919 Dang Nguyen Thien Phuc | ...       |
| 2.10 Counterexamples & cross-check against M1 rules                                    | 2551922 Chu Ngoc Phuc Thanh    | ...       |

| Member (StudentID Name)        | Contribution % | Signature |
| ------------------------------ | -------------- | --------- |
| 2551922 Chu Ngoc Phuc Thanh    | 100%           | Thanh     |
| 2551919 Dang Nguyen Thien Phuc | 100%           | Phuc      |
| 2551913 Vo Nguyen Vi Nguyen    | 100%           | Nguyen    |
| 2551931 Dinh Hoang Quang Vinh  | 100%           | Vinh      |
| 2551896 Nguyen Quoc Hung       | 100%           | Hung      |

## Module 3 (Automata): contribution ledger + signed % table

| Requirement                                                                                          | Primary owner (StudentID)      | Reviewers |
| ---------------------------------------------------------------------------------------------------- | ------------------------------ | --------- |
| 3.1 Strings from CSV (encode_strings.py), DFA class & JSON export (dfa.py)                           | 2551919 Dang Nguyen Thien Phuc | 2551931   |
| 3.1 Rules R1-R3 (rules.py), submitted JSON files & DFA tests against plain Python                    | 2551931 Dinh Hoang Quang Vinh  | 2551922   |
| 3.2 Product automaton, minimisation & state-count table (product_min.py)                             | 2551913 Vo Nguyen Vi Nguyen    | 2551931   |
| 3.3 Regular-to-ILP flow model & linking to M2 variables, re-solve and comparison (regular_to_ilp.py) | 2551896 Nguyen Quoc Hung       | 2551919   |
| 3.4 R4 bounded-counter DFA, pumping-lemma proof (pumping.md) & M3 report part                        | 2551922 Chu Ngoc Phuc Thanh    | 2551913   |
| M3 decisions (two-shift days, JSON format) in DECISIONS.md                                           | 2551919 Dang Nguyen Thien Phuc | 2551896   |
| M3 integration: run_all.py --stage m3, "valid" flag in the app, tag m3                               | 2551919 Dang Nguyen Thien Phuc | 2551896   |

| Member (StudentID Name)        | Contribution % | Signature |
| ------------------------------ | -------------- | --------- |
| 2551922 Chu Ngoc Phuc Thanh    | 100            | Thanh     |
| 2551919 Dang Nguyen Thien Phuc | 100            | Phuc      |
| 2551913 Vo Nguyen Vi Nguyen    | 100            | Nguyen    |
| 2551931 Dinh Hoang Quang Vinh  | 100            | Vinh      |
| 2551896 Nguyen Quoc Hung       | 100            | Hung      |

## Module 4 (Discrete dynamical systems, direction B): contribution ledger + signed % table

| Requirement / work unit | Primary owner (StudentID Name) | Reviewers |
| --- | --- | --- |
| Real-data workload extraction (`workload.py`) | 2551896 Nguyen Quoc Hung | 2551913 |
| Vector fatigue model (`fatigue.py`, `tests/test_fatigue.py`) | 2551922 Chu Ngoc Phuc Thanh | 2551913 |
| Soft fatigue threshold (`planning.py`, `tests/test_planning.py`) | 2551919 Dang Nguyen Thien Phuc | 2551913 |
| Integration and reproducibility (`run.py`, `plots.py`, `tests/test_run.py`, `run_all.py`) | 2551931 Dinh Hoang Quang Vinh | 2551913 |
| Documentation (`m4_dynamics/README.md`, `README.md`, `DECISIONS.md`) | 2551913 Vo Nguyen Vi Nguyen | 2551913 |

| Member (StudentID Name) | Contribution % | Signature |
| --- | --- | --- |
| 2551922 Chu Ngoc Phuc Thanh | 100 | Thanh |
| 2551919 Dang Nguyen Thien Phuc | 100 | Phuc |
| 2551913 Vo Nguyen Vi Nguyen | 100 | Nguyen |
| 2551931 Dinh Hoang Quang Vinh | 100 | Vinh |
| 2551896 Nguyen Quoc Hung | 100 | Hung |
