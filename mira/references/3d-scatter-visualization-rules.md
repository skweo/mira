# 3D Scatter Visualization Rules

Use this reference when a contest-final paper needs a 3D scatter plot, point
cloud, spatial sample distribution, three-variable relationship, 3D feature
space, parameter-response point cloud, or colored 3D clustering companion.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| 3D scatter | Spatial coordinates, 3D point clouds, three-variable coupling, clustered feature space, simulation samples in three dimensions. | Only one or two variables matter, exact comparison is the main claim, or points are too dense to read. |
| 3D scatter + projections | The 3D view shows structure but occlusion may hide local density, separation, or thresholds. | The projection panels repeat the same information without supporting a nearby claim. |

Use a table for exact coordinates, a 2D scatter for two variables, a heatmap or
contour for dense gridded surfaces, and a 3D scatter when the spatial or
three-variable structure itself supports the reasoning.

## Data Contract

- Use a point table with three numeric columns for `x`, `y`, and `z`.
- Use optional `color` for class, cluster, scenario, or numeric response; use
  optional `size` only when it encodes a real fourth variable.
- Save cleaned plot data, summary statistics, axis ranges, view angle, and
  parameters.
- Downsample only for readability and record the seed and sample size.
- Do not mix units without labeling axes and explaining the scale.

## Figure Standards

- Record the camera view (`elev`, `azim`) so the figure is reproducible.
- Use equal or range-aware axis aspect when possible; do not let one long axis
  visually flatten the other two.
- Keep marker alpha below 1 for dense point clouds.
- Use a legend for categorical color and a colorbar for numeric color.
- Add XY/XZ/YZ projection panels when occlusion affects the claim.
- Captions should state what the three axes, color, and marker size mean.

## Interpretation Discipline

Good wording:

> 三维散点图显示样本在特征1、特征2、特征3构成的空间中形成四个相对分离的点簇，其中簇2与簇4在特征3方向距离最大；结合投影图可见二者在XY平面存在局部重叠，因此本文只将该图作为分群可视化证据，而不直接据此判定分类准确率。

Avoid:

> 三维图很高级，因此本文加入三维散点图。

Do not claim global separation, thresholds, or dominance only from one static
view. Pair the figure with projection panels, distance statistics, clustering
metrics, or a result table when the conclusion depends on exact comparison.

## Script

Use the reusable script for CSV/XLSX point tables:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_3d_scatter.py `
  --root <project-root> `
  --input results\tables\points.csv `
  --x 特征1 `
  --y 特征2 `
  --z 特征3 `
  --color 类别 `
  --projections `
  --prefix q2_feature_space
```

The script writes PNG/PDF figures, cleaned point data, summary statistics,
parameters, and a caption/caveat index.
