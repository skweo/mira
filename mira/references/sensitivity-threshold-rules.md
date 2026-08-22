# Sensitivity And Threshold Rules

Use this reference when a contest-final paper makes a recommendation that may
change under parameter uncertainty, cost changes, sampling error, or modeling
assumptions. The goal is to move from qualitative "sensitive/not sensitive"
language to quantitative switch boundaries and robustness evidence.

## Required Sensitivity Types

For high-award `contest_final` papers, include at least one quantitative
sensitivity artifact unless the problem is purely deterministic with no
meaningful parameters.

Prefer these in order:

1. **One-at-a-time parameter scan**: vary one important parameter over a stated
   range and record objective and decision changes.
2. **Strategy switch threshold**: solve for the critical value where policy A
   and policy B have equal objective value.
3. **Two-parameter boundary**: when two costs/probabilities jointly drive a
   decision, show a grid or contour of the winning strategy.
4. **Sample-size or confidence sensitivity**: for posterior/robust models,
   compare choices under multiple sample sizes or confidence levels.
5. **Elasticity table**: report relative objective change when each key
   parameter changes by a fixed percent.

## Parameter Selection

Choose parameters that affect the final recommendation, not every symbol.
Common high-value parameters:

- defect rate or failure probability;
- inspection/detection cost;
- replacement/exchange loss;
- dismantling/rework cost;
- purchase cost of a high-impact component;
- capacity, time, or queue service rate;
- posterior sample size or confidence level.

If a parameter is assumed rather than measured, it is a stronger candidate for
sensitivity.

## Output Artifacts

Save one or more of:

- `results/tables/sensitivity_scan.csv`
- `results/tables/threshold_analysis.csv`
- `results/tables/sample_size_sensitivity.csv`
- `figures/sensitivity_*.png`
- `figures/strategy_switch_*.png`

Recommended CSV columns:

| column | meaning |
|---|---|
| `case` or `qid` | question/case identifier |
| `parameter` | varied parameter name |
| `value` | tested value |
| `objective` / `cost` / `profit` | resulting metric |
| `best_policy` | selected policy at that value |
| `baseline_policy` | reference policy, if applicable |
| `switch_from` / `switch_to` | policy transition for threshold rows |
| `threshold_value` | critical value when available |
| `note` | interpretation or range limits |

## Paper Requirements

Include a subsection named one of:

- `定量灵敏度分析`
- `策略切换边界`
- `参数临界值分析`
- `样本量敏感性分析`

The text should answer:

1. Which parameter is varied and why?
2. Over what range is it varied, and what is the source or rationale?
3. Does the final policy change?
4. If it changes, what is the threshold and economic/mechanistic reason?

Good phrasing:

> 当调换损失 \(\ell\) 低于 ... 时，成品检测收益不足以覆盖检测费；
> 当 \(\ell\) 超过 ... 时，市场退回风险占主导，策略切换为成品检测。

Avoid weak phrasing:

> 调换损失对结果比较敏感。

## Gate Rules

For high-award `contest_final` output:

- A recommendation with no sensitivity evidence is a warning.
- Qualitative sensitivity prose without a saved scan, threshold, or elasticity
  table is still a warning.
- If a sensitivity scan shows the final recommendation changes inside the
  plausible parameter range, the paper must state the execution condition or
  risk, not present a single unconditional strategy.

