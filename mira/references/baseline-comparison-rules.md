# Baseline Comparison Rules

Use this reference when a contest-final paper claims a model, state definition,
solver, robustness layer, or visualization is better than an ordinary approach.
The goal is to quantify the value of the new modeling choice instead of only
describing it as an innovation.

## Required Baseline Types

For `contest_final` papers, add at least one baseline unless the problem is a
pure proof, pure fitting, or the official question has no meaningful alternative.

Prefer baselines in this order:

1. **Simplified structural baseline**: remove the paper's key modeling
   innovation while keeping the same data and objective.
   - Examples: no information-memory state, no dismantling credit, no queue
     priority class, no time-window repair, no interaction term.
2. **Common-sense policy baseline**: all-check, no-check, greedy, nearest,
   equal allocation, average-rate, or first-fit.
3. **Point-estimate baseline**: solve with fixed parameters and compare with
   robust/posterior/re-sampled decisions.
4. **Algorithm baseline**: compare an exact/DP/MILP/enumeration solution with a
   heuristic, or compare a heuristic against a lower bound/certified result.

## Output Artifact

Save baseline results to `results/tables/baseline_comparison.csv` when possible.
Use these columns where applicable:

| column | meaning |
|---|---|
| `case` or `qid` | question/case identifier such as `Q2`, `Q3`, `case_5` |
| `method` | `final_model`, `memoryless_baseline`, `greedy`, `point_estimate`, etc. |
| `objective` / `cost` / `profit` | the metric used by the final model |
| `delta_vs_final` | baseline minus final for cost, or final minus baseline for profit |
| `relative_delta` | normalized improvement when meaningful |
| `changed_decision` | short description of policy changes |
| `note` | why this baseline matters |

If objectives are maximized, make the sign convention explicit in `note`.

## Paper Requirements

In the final paper, include a short subsection named one of:

- `基准模型对比`
- `信息价值对比`
- `与简化模型的对照`
- `稳健策略收益对比`

The subsection should answer three questions:

1. What assumption or modeling feature is removed in the baseline?
2. How much profit/cost/accuracy/robustness is lost?
3. Which final-paper claim does this support?

Good phrasing:

> 与不保存拆解后已知合格信息的无记忆模型相比，三态模型在情形 1--3
> 分别提高利润 ... 元/件，说明信息保持不是形式化状态扩展，而是可量化的
> 成本节约来源。

Avoid weak phrasing:

> 本文模型比传统模型更好。

## Gate Rules

For high-award `contest_final` output:

- Missing all baselines is a warning unless a waiver says why no meaningful
  baseline exists.
- A claimed innovation without a baseline or ablation comparison is a high-risk
  warning.
- A baseline that repeats the final method under another name does not count.
- If a baseline beats the final method, return to modeling/code/results; do not
  hide or omit it.

