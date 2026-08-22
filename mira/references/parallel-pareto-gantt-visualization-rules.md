# Parallel, Pareto, And Gantt Visualization Rules

Use this reference when a contest-final paper needs a parallel-coordinate plot,
Pareto-front plot, Gantt chart, or implementation timeline.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| Parallel coordinates | Compare many schemes across multiple normalized indicators. | There are only two indicators, or directions/units are not normalized. |
| Pareto front | Explain two-objective tradeoffs such as cost-quality, time-risk, or accuracy-complexity. | A single weighted score is already the only decision rule, or objective directions are unclear. |
| Gantt/timeline | Show scheduling, execution workflow, project stages, production plan, or emergency-response sequence. | The chart is not based on model output, engineering assumptions, or a real execution plan. |

These figures strengthen decision explanation and engineering implementation.
They should not replace formulas, objective functions, constraints, or solver
evidence.

## Data Contract

- Parallel coordinates require one item/scheme column and at least two numeric
  metric columns. Record normalization and lower-is-better metrics.
- Pareto plots require two numeric objective columns and explicit objective
  directions (`min` or `max`).
- Gantt charts require task, start, and either end or duration columns; optional
  resource/stage and milestone columns clarify implementation.
- Save cleaned plot data, summary table, parameters, PNG/PDF figures, and a
  caption/caveat index.

## Figure Standards

- Parallel coordinates should use normalized, same-direction indicators when
  the plot supports ranking or screening. If many lines overlap, filter to
  candidate schemes or group by category.
- Pareto plots should visually separate dominated and nondominated points and
  state the interpretation of each objective axis.
- Gantt charts should align task order with the actual execution sequence and
  use color for stages/resources, not decoration.
- Captions should state the decision role: screening, tradeoff, execution plan,
  or validation workflow.

## Interpretation Discipline

Good wording:

> 平行坐标图显示方案 D 在成本和时间上占优，但准确性与鲁棒性偏低，因此本文将其作为低成本候选，而非最终推荐方案。

> Pareto 前沿说明成本继续下降会牺牲质量收益，最终选择位于前沿中部的方案 B，是因为其满足预算约束且边际质量损失较小。

> 甘特图将模型输出转化为三阶段执行计划，展示数据准备、求解复核和提交材料之间的时间约束与里程碑。

Avoid:

> 本文加入平行坐标图、Pareto 图和甘特图，使论文更高级。

## Script

Use the reusable script:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py `
  --root <project-root> --kind parallel --input results\tables\scheme_metrics.csv `
  --item-col 方案 --metrics 成本,时间,准确性,鲁棒性 `
  --lower-is-better 成本,时间 --group-col 类型 --prefix q4_parallel
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py `
  --root <project-root> --kind pareto --input results\tables\candidates.csv `
  --x 成本 --y 质量收益 --x-direction min --y-direction max `
  --label-col 方案 --prefix q3_pareto
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py `
  --root <project-root> --kind gantt --input results\tables\schedule.csv `
  --task-col 任务 --start-col 开始 --end-col 结束 --resource-col 阶段 `
  --prefix implementation_gantt
```

Built-in demos:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py --root <project-root> --kind parallel --demo
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py --root <project-root> --kind pareto --demo --x 成本 --y 质量收益 --x-direction min --y-direction max
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_parallel_pareto_gantt.py --root <project-root> --kind gantt --demo
```

The script writes PNG/PDF figures, cleaned plot data, summary statistics,
parameters, and a caption/caveat index.
