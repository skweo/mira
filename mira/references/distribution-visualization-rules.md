# Distribution Visualization Rules

Use this reference when a contest-final paper needs violin plots, box plots,
JoyPlot/ridgeline plots, distribution comparison, group spread, outlier, or
multi-scenario density figures.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| Violin plot | Compare distribution shape, skewness, multimodality, and quartiles across groups. | Each group has very few samples or exact values are the only claim. |
| Box plot | Compare median, IQR, range, and outliers compactly. | Shape or multimodality is important. |
| JoyPlot / ridgeline | Compare many ordered groups, time windows, scenarios, or policy distributions. | Groups are unordered and too few to justify a layered density view. |

Use tables for exact values, bar charts for a single aggregate, violin/box plots
for distribution comparison, and JoyPlot when many distributions must be scanned
as a visual sequence.

## Data Contract

- Use real saved result data, not manually typed chart values.
- Record the value column, group column, and optional hue/secondary category.
- Save the reshaped plotting data and summary statistics table.
- For wide result tables, melt numeric columns into long format before plotting.
- Do not draw a density figure for fewer than 5 complete numeric observations;
  for weak per-group sample sizes, prefer box/strip plots or a table.

## Figure Standards

- Violin plots should show quartiles or medians and may overlay light jittered
  points when sample size is moderate.
- Box plots should preserve outliers; do not hide fliers unless the text explains
  a robust-summary reason.
- JoyPlot groups should have a meaningful order: time, scenario severity,
  parameter level, median value, or explicit paper order.
- Use readable group labels. Rotate or switch to horizontal layout when labels
  are long.
- Captions must state what the distribution feature supports: stability,
  risk tail, outlier presence, scenario difference, or policy robustness.

## Interpretation Discipline

Good distribution wording:

> 图中方案 B 的中位数较高且四分位距较窄，说明其典型表现和稳定性同时优于其他方案；方案 D 虽均值较高，但右尾过长，需结合风险约束判断是否可接受。

Avoid:

> 小提琴图更好看，所以本文使用小提琴图。

Do not infer statistical significance from a figure alone. If the claim is
"significantly different", support it with a test, confidence interval, bootstrap
interval, or a problem-specific threshold.

## Script

Use the reusable script for CSV/XLSX result tables:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_distribution.py `
  --root <project-root> `
  --input results\tables\scenario_metrics.csv `
  --kind all `
  --value 指标值 `
  --group 方案 `
  --prefix q3_policy_distribution
```

For wide-format indicator columns:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_distribution.py `
  --root <project-root> `
  --input results\tables\feature_matrix.csv `
  --features 指标1,指标2,指标3 `
  --prefix q2_indicator_distribution
```

The script writes PNG/PDF figures, plot data, summary statistics, parameters,
and a caption/caveat index.
