# 3D Bar Visualization Rules

Use this reference when a contest-final paper needs 3D bars, bar3D, a
two-category comparison matrix, scenario-by-indicator bars, or a parameter-grid
bar chart.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| 3D bar / bar3D | A small two-way matrix: scheme x metric, scenario x indicator, parameter A x parameter B. | One-dimensional ranking, dense grids, many categories, or exact comparison as the main claim. |
| 3D bar + heatmap/table | The 3D bars show overall shape, while exact cell comparison still matters. | The heatmap/table repeats the same point without improving readability. |

Use ordinary bars for one-dimensional rankings, grouped bars for a few
side-by-side categories, heatmaps for dense matrices, and 3D bars only when the
two-way structure itself helps the reasoning.

## Data Contract

- Use either a long table with `x`, `y`, `value` columns or a matrix table.
- Aggregate duplicate `x-y` cells before plotting and record the aggregation
  method.
- Save cleaned long cells, matrix data, plotting parameters, and camera view.
- Keep the unit consistent across all bars.
- Keep the number of bars small enough to read; if bars crowd together, switch
  to heatmap/table.

## Figure Standards

- Bar height must encode the numeric value.
- Color may encode height, x category, or y category, but only one of them.
- Record `elev` and `azim` because camera angle changes perceived height.
- Keep category labels readable after PDF compilation.
- Add a heatmap or three-line table when exact value comparison matters.
- Captions should state the two category axes, the height variable, the unit,
  and the main highlighted cell or pattern.

## Interpretation Discipline

Good wording:

> 三维柱状图以方案为纵向类别、指标为横向类别，柱高表示评分。可以看到方案D在公平性和稳定性上形成局部高峰，但收益指标并非最高；因此本文后续推荐不能只依据单一收益，而应结合多指标加权结果。具体数值见相邻矩阵表。

Avoid:

> 三维柱状图更好看，因此本文采用3D柱状图。

Do not use one static 3D view to claim small differences. Pair close
comparisons with a saved matrix table, heatmap, ranking table, or sensitivity
scan.

## Script

Use the reusable script for long tables:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_3d_bar.py `
  --root <project-root> `
  --input results\tables\scenario_metric.csv `
  --x 指标 `
  --y 方案 `
  --value 评分 `
  --heatmap `
  --prefix q3_scenario_metric
```

For matrix tables, add `--matrix` and optionally `--index-col`.

The script writes PNG/PDF figures, cleaned bar cells, matrix data, parameters,
and a caption/caveat index.
