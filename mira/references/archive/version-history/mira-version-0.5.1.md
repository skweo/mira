# Mira 0.5.1

Mira 0.5.1 is the first high-award critique-response upgrade after the 0.4.x
paper-quality chain.

## Added Capability

**Baseline comparison / information-value evidence**

High-award contest-final papers should not only claim that a model is innovative.
They should compare against a simplified, common-sense, point-estimate, or
algorithmic baseline whenever the problem allows it.

Required artifacts when feasible:

- `results/tables/baseline_comparison.csv`
- A paper subsection such as `基准模型对比`, `信息价值对比`, or `与简化模型的对照`
- A short explanation of what model feature was removed and what profit/cost
  was lost

## New Gate Behavior

`award_review_gate.py` now checks:

- whether `baseline_comparison.csv` exists and contains rows;
- whether the paper contains baseline, ablation, simplified-model, or
  information-value language;
- whether innovation claims appear without comparison evidence.

Missing comparison evidence is a high-award warning, not merely a wording issue.

