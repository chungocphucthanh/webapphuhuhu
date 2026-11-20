# M4 — Vector fatigue and fairness (direction B)

This module implements **exactly direction B** of the assignment brief, pp. 6
and 16: derive a team fatigue recurrence from the real workload, compute and
verify its fixed points and stability, relate the spread to fairness, and add a
soft fatigue threshold. B makes the fairness argument explicit and needs no
unobserved available/busy/on-leave labels or rolling-horizon feedback policy.

## Reproduce

Use Python 3.12 with the pinned dependencies in the repository's
`requirements.txt` (the pinned OR-Tools release does not support Python 3.14).
From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_all.py --seed "$(cat data/seed.txt)" --stage m4
.venv/bin/python -m pytest m4_dynamics/tests -q
```

M4 reads the completed `m2_ilp/schedule.csv`. If that file is absent, run stage
`m2` first. It validates the dense CSV, availability, overlap and exact demand
before using the schedule. It writes its artifacts in `m4_dynamics/`; it does
not overwrite the previous modules' outputs. `run_all.py --stage all` also
executes M4 after M3.

For another output folder or a different valid M2-format schedule:

```sh
.venv/bin/python -m m4_dynamics.run --out-dir /tmp/m4-results
.venv/bin/python -m m4_dynamics.run --schedule m2_ilp/schedule.csv --weeks 52
```

The team seed is checked by the existing M2 instance builder. M4 makes no new
random draws. Solver settings reuse M2's single-thread CBC configuration.

## Workload and parameter calibration

`workload.py` reuses the M1/M2 instance and counts actual assignments, including
every staff member and every calendar day. The 73 staff have 769 assignments in
83 sessions from 2026-05-18 through 2026-06-13: 27 calendar days. Consecutive
seven-day blocks starting at the first date have durations `d = [7,7,7,6]` and
total counts `[15,103,339,312]`. Empty blocks are retained. Multiple sessions on
one day each count as an assignment, as in M2.

For staff `i` and block `k`, let `c[k,i]` be the actual count and
`L[k,i] = 7*c[k,i]/d[k]` its weekly rate. The term-average weekly load is
`ell[i] = 7*sum_k c[k,i]/27`. This uses the calendar exposure rather than
treating the last six days as a full week. The running total
`w[k,i] = sum_{h<k} c[h,i]` is exported for inspection. It is a descriptive
accumulator and is not assigned a fixed point.

There are no fatigue measurements in the dataset. We therefore define fatigue
as a **workload proxy in weekly-load equivalents**, with explicit assumptions:

1. Fit retention `a` by unconstrained pooled lag-one ordinary least squares:
   `L[k+1,i] = intercept + a*L[k,i] + residual`, over 219 staff/block pairs.
   Specifically, `a = sum((X-Xbar)*(Y-Ybar))/sum((X-Xbar)^2)`.
   Workload persistence stands in for fatigue retention; it is not a measured
   physiological recovery coefficient. A constant predictor or an estimate
   outside `[0,1)` raises an error; the implementation does not clip it.
2. Set `r=0`, since a separate rest effect cannot be identified from these
   assignment records. This follows the brief's allowed zero-rest example.
   No assignment on a day is not evidence of leave or measured recovery.
3. Calibrate `b` so the equilibrium at the observed mean weekly load `mu`
   equals `mu`: `(b*mu-r*rho)/(1-a)=mu`, giving `b=1-a` for `r=0`.
   This defines the proxy's scale; it is not a second statistical estimate.
4. For the observed trajectory use `F[0]=0` as a reference state. Fatigue before
   the observation window is unknown.

On the supplied data, `a=0.27063439282332274`, `b=0.7293656071766772`, and
`r=0`. The workload regression intercept is `3.115617`, RMSE is `2.529817`,
and R-squared is `0.061930`. The weak fit and the short, demand-varying window
limit predictive use. The intercept is reported as a regression diagnostic;
the fatigue recurrence's forcing is the calibrated `b*ell`.

## Recurrence, equilibrium and fairness

For a fixed weekly load vector `ell` and rest vector `rho`, the model is

```text
F[n+1] = a F[n] + b ell - r rho
F*     = (b ell - r rho)/(1-a)                         (a != 1)
F[n]   = F* + a^n (F[0]-F*)
```

The Jacobian is `a I`; all eigenvalues equal `a`. Thus the fixed point is
globally asymptotically stable if `|a|<1`, neutral if `|a|=1` and it exists,
and unstable if `|a|>1`. At `a=1` nonzero forcing has no fixed point, while
zero forcing has a continuum of neutral fixed points. At `a=-1` trajectories
oscillate without decay. These regimes are checked numerically, including
growth at `a=1.05`; stability is not assumed by the analysis functions.

With equal load `ell[i]=mu` and equal rest `rho[i]=rho_bar`, all components have
the same equilibrium `(b*mu-r*rho_bar)/(1-a)`. Differences satisfy
`F[n,i]-F[n,j] = a^n*(F[0,i]-F[0,j])`, so

```text
spread(F[n])   = |a|^n * spread(F[0])
variance(F[n]) = a^(2n) * variance(F[0])
```

Fairness in this sense is an attracting fixed point. Under unequal constant
loads, the stable equilibrium generally has nonzero spread. With our
calibration, `F*[i]=ell[i]`, so equilibrium spread directly measures weekly
load imbalance.

The long-run experiment uses constant **term-average** load vectors from the
baseline, M2 schedule, and M4 fatigue-aware schedule. An equal-load reference
uses the same total weekly demand, divided by 73. It is an ideal average-load
comparison, not a claim that identical fractional weekly loads can be realized
by an integer schedule under individual availability constraints. All four
experiments start from the same nonuniform terminal baseline fatigue, so zero
spread is reached by convergence rather than imposed as the initial condition.
No cyclic roster is claimed to converge to a constant fixed point.

The separate historical simulation applies each block's observed weekly rate.
For a block of `d` days and `r=0`, set

```text
alpha_d = a^(d/7)
beta_d  = b*(1-alpha_d)/(1-a)
F[k+1]  = alpha_d F[k] + beta_d L[k]
```

This agrees with the full-week map and preserves its equilibrium. The six-day
block therefore has six days of decay and exposure. It assumes constant mean
load within each block and does not claim to model the order of shifts inside
that block.

## Soft threshold in the ILP

Fit `H` as the nearest-rank 95th percentile of all 292 baseline block-end
fatigue values, including idle staff: `H=5.660327617142248`. Coverage 95% is a
policy choice. H is a proxy threshold, not a clinical safety limit.

`planning.add_fatigue_soft_constraints` adds linear fatigue states and rows
for every staff member and block boundary, including the initial state:

```text
L[k,i]       = (7/d[k]) * sum_{j in block k} x[i,j]
F[k+1,i]     = alpha_d F[k,i] + beta_d L[k,i]
F[k,i]       <= H + s[k,i]
s[k,i]       >= 0
new objective = M2 stage-2 objective + lambda_FAT * sum_{k,i} s[k,i]
```

The weight `lambda_FAT=1.9` comes from the existing seed-derived fatigue weight.
The old M2 soft terms also remain in the objective. An exceedance costs a
penalty instead of making assignments infeasible. Initial excess is included
even though future assignments cannot change it. Under the constant-rate
interpolation, fatigue is monotone within a block, so its maximum occurs at a
boundary.

The M4 run performs one finite-horizon refinement using M2's model and its
existing maximum-load cap of 11. It independently validates the solution and
checks every solver fatigue state and total excess against the numerical
simulator (tolerance `1e-5` for CBC's printed values). This remains direction B;
there is no rolling-horizon re-solving or state-dependent allocation feedback.
The produced variant enforces M2's hard rules. The helper also composes with
M3's `add_rules_to_m2` on the same model; this run does not assert M3 temporal
acceptance of its new schedule.

## Reproduced results

All fixed points have mean `2.731100964`, equal to `769*7/(73*27)`.
The 52-week simulations reach them within `1e-8` (observed maximum error
`4.45e-16`). The equal-load spread and variance formulas are checked at every
step, as is return after a one-person initial perturbation.

| Schedule / reference | Equilibrium spread | Equilibrium variance | Observed threshold excess |
| --- | ---: | ---: | ---: |
| Baseline | 4.148148 | 0.327941 | 16.312130 |
| Completed M2 | 0.259259 | 0.016725 | 3.287398 |
| M4 fatigue-aware | 0.259259 | 0.016725 | 0.000000 |
| Equal-load reference | 0.000000 | 0.000000 | Not an observed roster |

The refined schedule has all 769 assignments, max/min total loads 11/10,
L1 deviation `36.328767`, location penalty 28, and zero old daily-fatigue and
travel penalties. It improves within-term threshold exposure while preserving
M2's workload fairness. Its equilibrium spread equals M2's because both have
the same distribution of total loads.

## Files and executable checks

| File | Purpose |
| --- | --- |
| `workload.py` | Strict schedule reader, calendar blocks, rates and real running totals |
| `fatigue.py` | Calibration, recurrence, equilibrium, stability, threshold and simulation |
| `planning.py` | Soft ILP rows and fatigue-aware finite-horizon refinement |
| `run.py` | Reproducible pipeline with numerical assertions |
| `plots.py` | Headless report figures |
| `results.json` | Input hashes, parameters, assumptions, all checks and per-person equilibria |
| `observed_weekly.csv` | Actual counts, rates, cumulative counts and block-end fatigue |
| `trajectories.csv` | All 52-week autonomous trajectories, including time zero |
| `fatigue_aware_schedule.csv` | Dense M2-format schedule from the M4 refinement |
| `observed_fatigue.png` | Maximum historical fatigue and soft threshold |
| `fatigue_equilibrium.png` | Staff ranges, means and equilibria in all four scenarios |
| `fairness.png` | Spread and variance trajectories |

Tests cover the brief's worked example, nonzero rest, analytical solutions,
stable/neutral/unstable cases, equal and unequal loads, known regression data,
unsupported calibration, calendar gaps, partial weeks, count conservation,
malformed inputs, a genuinely soft infeasible-as-hard threshold, and agreement
between solver states and independent simulation. Two complete M4 runs must
produce byte-identical JSON, CSV and PNG outputs without changing the M2 input.

`tests/test_direction_b.py` adapts the third-party Direction A cases in the
root `test.py` to the Direction B API and the brief's requirements. It retains
the example assignments, documents partial-week normalization, and checks equal
and unequal loads, stability boundaries, real-data calibration, and soft ILP
thresholds. Run it alone with:

```sh
.venv/bin/python -m pytest m4_dynamics/tests/test_direction_b.py -q
```
