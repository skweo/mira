# Mira 0.5.6

Mira 0.5.6 upgrades high-award writing with theoretical-threshold and
proof-scope discipline.

## Added Capability

**Theoretical threshold support**

When a paper claims an optimal strategy, dominance relation, monotonic trend,
or strategy-switch threshold, Mira should try to provide a compact mathematical
reason instead of relying only on result tables.

Preferred artifacts:

- `planning/theory_proof_plan.md`
- `results/tables/theoretical_thresholds.csv`
- `results/tables/dominance_conditions.csv`
- `results/tables/monotonicity_check.csv`

Preferred paper behavior:

- state the claim scope before using words such as `最优`, `总是`, or `必然`;
- derive a marginal cost-benefit inequality when two actions differ by one
  decision;
- state dominance or monotonicity conditions when a policy family is pruned;
- explain strategy-switch boundaries with the condition that changes sign;
- use an explicit waiver when the evidence is only exhaustive enumeration,
  solver gap, simulation stability, or benchmark agreement.

## New Gate Behavior

The award gate checks whether strong optimality/threshold language is backed by
proof terms, threshold artifacts, or a theory proof plan. Papers that repeatedly
claim `最优` or strategy switches without proof-scope evidence receive a
high-award warning.
