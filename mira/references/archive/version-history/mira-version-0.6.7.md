# Mira 0.6.7

Mira 0.6.7 adds reproducible 3D scatter visualization support for spatial point
clouds, three-variable relationships, and 3D feature-space figures.

## New Standard

- Route `references/3d-scatter-visualization-rules.md` when a figure, result
  analysis, or revision mentions 3D scatter, point cloud, spatial samples,
  three-variable relationship, feature-space scatter, or parameter-response
  point cloud.
- Use `scripts/plot_3d_scatter.py` for CSV/XLSX point tables with three numeric
  axis columns and optional color, size, and label columns.
- Save static PNG/PDF figures, cleaned point data, summary statistics, plotting
  parameters, camera view, and a caption/caveat index.
- Treat 3D scatter as structural or spatial evidence. Use projections, tables,
  clustering metrics, or contour/heatmap views when exact comparison matters.

## Non-goals

- Do not use 3D scatter to make ordinary two-variable plots look more complex.
- Do not infer precise thresholds or global cluster separation from one static
  camera angle.
- Do not weaken the 0.6.1-0.6.6 layout, derivation, control-plane, t-SNE,
  distribution, or flow-visualization rules.
