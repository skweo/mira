# Radar, Taylor, And 3D Surface Visualization Rules

Use this reference when a contest-final paper needs a radar chart, Taylor
diagram, or 3D surface/response-surface figure.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| Radar chart | Compare a small number of schemes across normalized indicators, such as accuracy, stability, cost, efficiency, and robustness. | Indicators have incompatible directions or units and no normalization; there are too many schemes or indicators. |
| Taylor diagram | Compare prediction or simulation models against observations using correlation, standard deviation, and centered RMSE. | There is no paired observed-predicted data, or the main issue is bias/extreme error rather than pattern agreement. |
| 3D surface | Show continuous response surface, two-parameter sensitivity, geometry surface, or objective-function shape. | Data are a tiny discrete scheme matrix, or exact ranking is clearer as a table/heatmap. |

These figures are high-information visuals only when they answer a nearby
modeling question. Do not add them as decorative advanced charts.

## Data Contract

- Radar: use one item/scheme column and numeric metric columns. Record whether
  indicators were normalized, scaled, or direction-adjusted.
- Taylor: use paired observation and prediction columns, or a precomputed table
  containing model, correlation, standard deviation, and centered RMSE.
- 3D surface: use numeric `x`, `y`, and `z` columns. If the table is scattered
  rather than a complete grid, record interpolation settings.
- Save cleaned plot data, summary table, parameters, PNG/PDF figures, and a
  caption/caveat index.

## Figure Standards

- Radar charts should usually contain no more than 5-6 schemes. Pair final
  rankings with an explicit weighted score or table.
- Radar axes must have the same interpretation direction. If lower cost is
  better, transform it into a benefit indicator before plotting.
- Taylor diagrams require paired samples and should state whether standard
  deviation is raw or normalized by the observed standard deviation.
- Taylor diagrams do not show mean bias; add residual/error statistics when
  bias matters.
- 3D surface figures should record camera view and color scale. Add a 2D contour
  or heatmap companion when thresholds, maxima, minima, or boundaries matter.
- Interpolated surfaces are visual approximations; do not use them as proof of
  an optimum unless a numerical optimizer or grid/refinement result supports it.

## Interpretation Discipline

Good wording:

> 雷达图显示方案 C 在准确性与鲁棒性上占优，但成本优势较弱，因此本文仅将其作为候选方案；最终排序仍由式(12)的加权综合得分和权重敏感性检验确定。

> 泰勒图表明模型 A 同时具有最高相关系数和最接近观测的标准差，且中心化 RMSE 最小；但其平均偏差仍需由表 6 的误差统计进一步检验。

> 三维曲面揭示目标函数在参数 \(a\) 与 \(b\) 的耦合方向上存在局部谷值，随后使用局部细化搜索确定最优参数，而不直接从曲面目测读数。

Avoid:

> 本文加入雷达图、泰勒图和三维曲面图，使论文更美观。

## Script

Use the reusable script:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py `
  --root <project-root> --kind radar --input results\tables\scheme_metrics.csv `
  --item-col 方案 --metrics 准确性,稳定性,效率,成本优势 --normalize minmax `
  --prefix q4_scheme_radar
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py `
  --root <project-root> --kind taylor --input results\tables\predictions.csv `
  --obs 观测值 --pred-cols 模型A,模型B,模型C --normalize-std `
  --prefix q2_prediction_taylor
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py `
  --root <project-root> --kind surface --input results\tables\response_grid.csv `
  --x 参数x --y 参数y --z 目标值 --contour `
  --prefix q3_response_surface
```

Built-in demos:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py --root <project-root> --kind radar --demo
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py --root <project-root> --kind taylor --demo --normalize-std
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_radar_taylor_surface.py --root <project-root> --kind surface --demo --contour
```

The script writes PNG/PDF figures, cleaned plot data, summary statistics,
parameters, and a caption/caveat index.
