# M2: ILP assignment model

M2 uses binary assignment variables to assign staff to sessions. The sections below describe the data, variables, and schedule evaluation.

- [M2 requirement 2.1: Sets, parameters, and availability](2.1.md): dataset sets, demand for each session, and permitted staff–session pairs.
- [M2 requirement 2.2: Decision variables](2.2.md): sparse assignment variables and workload expressions for each staff member.
- [M2 requirement 2.3: Objective function](2.3.md): minimize the maximum load first, then minimize L1 load deviation and soft penalties.
- [M2 requirement 2.6: Dataset input, synthetic preferences, and weights](2.6.md): data loading, preference generation, and seed-derived weights.
- [M2 requirement 2.7: Model assembly, solver, and outputs](2.7.md): assemble the ILP, solve it in two stages with PuLP and CBC, validate the schedule, and write `schedule.csv` and `metrics.json`.
- [M2 requirement 2.9: Evaluation metrics and performance](2.9.md): workload metrics, baseline comparison, model size, and LP bounds.
