# Innovation And Contribution Rules

Use this reference when a contest-final paper has a nontrivial model design,
state definition, solver route, robustness layer, visual evidence chain, or
engineering decision procedure. The goal is to make the paper's contribution
easy for a reviewer to find and verify.

## When Required

For high-award `contest_final` papers, add an innovation/contribution summary
when the paper claims any of:

- a new state definition or information structure;
- a better solver, exact enumeration, DP, MILP, or certified method;
- robust/posterior/uncertainty-aware decision making;
- a visualization or evidence chain that changes the decision;
- an engineering execution process beyond raw numerical answers.

## Contribution Ledger

Create a short internal ledger before writing:

| field | content |
|---|---|
| `contribution` | what is new or unusually strong |
| `problem_solved` | what weakness in an ordinary model it fixes |
| `evidence` | table, figure, equation, baseline, or sensitivity result |
| `benefit` | profit/cost/accuracy/robustness/interpretability improvement |
| `scope` | where the claim is valid |

Save it as `planning/innovation_ledger.md` when feasible. If a table is useful,
save `results/tables/contribution_ledger.csv`.

## Paper Placement

Use one of these section titles:

- `本文创新与贡献`
- `模型创新点`
- `主要贡献`
- `方法优势与证据`

Place the section after the overall modeling idea or before model evaluation.
Keep it short: usually 3--4 contributions.

Each item should follow this structure:

1. **Innovation**: name the feature.
2. **Why it matters**: state the ordinary-model weakness.
3. **Evidence**: cite the equation/table/figure/baseline/sensitivity result.
4. **Scope**: say when the contribution applies.

Good phrasing:

> 三态信息保持模型解决了拆解后已知合格信息被重置的问题；
> 表 ... 的基准对比显示，该信息保存带来 ... 元/件收益。

Avoid weak phrasing:

> 本文模型具有创新性，结果较好。

## Abstract And Conclusion

The abstract may mention the main contribution, but it must still prioritize
final answers. The conclusion should not only repeat numbers; it should state
what reusable decision principle the paper contributes.

## Gate Rules

For high-award `contest_final` output:

- Innovation claims without a named contribution section are a warning.
- A contribution without nearby evidence is a warning.
- Overclaiming is a warning: do not call an exact enumeration "new algorithm"
  unless there is a genuinely new algorithmic idea.
- If the contribution depends on a baseline, sensitivity, or assumption
  extension, cite that evidence in the contribution item.

