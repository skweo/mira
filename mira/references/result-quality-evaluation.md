# Result Quality Evaluation

Use this reference after executable results exist, before implementation result freeze,
and before final delivery. Result-quality evaluation is the numeric layer under
semantic audit: it computes whether the result itself looks strong enough to
trust, not only whether the paper explains it.

## Difference From Semantic Audit

| Layer | Main question | Typical evidence |
|---|---|---|
| Semantic audit | Is the result plausibly argued and honestly claimed? | result report, paper text, parameter explanations, claim wording |
| Result-quality evaluation | Do the actual numbers pass objective, baseline, convergence, and sensitivity tests? | frozen numbers, history tables, baseline tables, sensitivity tables |

Both layers are required for `contest_final`. A result can pass semantic audit
prose checks and still fail result quality if the objective is dominated by an
unexplained penalty, the heuristic is still improving, or a recommendation
changes under a small parameter perturbation.

## Required Checks

### Objective Component Ratios

For each subquestion with transport/routing cost and penalty components:

- compute `penalty / max(|travel|, 1)`;
- warn above `100`;
- fail above `1000` unless exact/certificate evidence makes the scale
  explainable;
- fail severe heuristic cases where the ratio is above `10000`;
- also record `objective / travel` when the objective is dominated by non-travel
  terms.

A high ratio is not automatically wrong, but it cannot be silently accepted.
The repair must add a bound, pressure analysis, penalty normalization,
lexicographic objective, sensitivity check, or a better model.

### Baseline Improvement

For each case in `results/tables/baseline_comparison.csv`:

- compare the frozen result against the best available baseline/alternative;
- fail if the frozen result is worse than the best comparable row;
- warn if the best improvement margin is too small for a heuristic claim;
- record the improvement ratio when the result is clearly better than simple
  baselines.

PoC and baseline tables must be comparable: same case, same minimization metric,
same major constraints.

### Convergence And Stability

For history tables such as `q3_history.csv`:

- compute overall best-objective improvement;
- compute tail improvement over the last 20 percent of logged iterations;
- mark convergence as weak if the tail still improves materially;
- warn when history is too sparse to support a convergence claim;
- when multiple runs exist, compute spread across final best values and warn if
  the solution is unstable.

Heuristic results should be reported as best-found unless exact optimality is
proved by a bound, gap, or recurrence.

### Recommendation Sensitivity

For recommendation variables such as Q4 vehicle count:

- recompute the selected option under the recorded fixed cost;
- test whether the selected option changes under +/-10%, +/-25%, and +/-50%
  perturbations;
- compute breakpoints where another option becomes better;
- fail if a recommendation changes within +/-10%;
- warn if it changes within +/-25% or has no sensitivity table;
- record the nearest breakpoint and valid parameter interval.

Example: if `combined = routing_objective + K * M_fixed`, then the breakpoint
between selected `K_s` and alternative `K_i` is
`M = (R_i - R_s) / (K_s - K_i)`. A selected `K=8` with `M_fixed=200` and nearest
breakpoint `323` is robust to moderate increases, but the paper must state that
the recommendation changes when fixed cost exceeds that breakpoint.

### Parameter Criticality

If a dominant objective component depends on a penalty coefficient, fixed cost,
weight, threshold, capacity, or solver parameter, the result-quality report must
warn when no sensitivity or calibration evidence exists.

## Executable Gate

Recommended command:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\result_quality.py --root . --write-report checks\result_quality_report.md --write-json checks\result_quality_report.json
```

For `contest_final`, only an unresolved `FAIL` in
`checks/result_quality_report.md` blocks implementation and final delivery. A
`WARN` remains visible diagnostic evidence but does not block the workflow;
record material limitations in the result report and paper when they affect the
interpretation or recommendation.

## Repair Routing

| Finding pattern | Return to | Required repair |
|---|---|---|
| penalty/travel explosion | implementation, possibly implementation | component ratio, bound, pressure analysis, penalty scaling, lexicographic objective, or model repair |
| frozen result worse than baseline | implementation | rerun, fix implementation, or select stronger method |
| weak convergence or high multi-seed spread | implementation | more iterations, better operators, parameter tuning, decomposition, or multi-seed stability report |
| fragile recommendation under fixed cost | modeling | revise objective, add scenario recommendation, or state valid parameter interval |
| missing sensitivity for dominant weight | implementation | run perturbation table or justify/calibrate parameter |

Do not clear result-quality findings by editing prose alone. The owning numeric
artifact must change, or the limitation must be explicit and waived.
