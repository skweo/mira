# Mira 0.6.8

Mira 0.6.8 adds reproducible 3D bar/bar3D visualization support for small
two-way matrices, scenario-indicator comparisons, and parameter-grid cell
comparisons.

## New Standard

- Route `references/3d-bar-visualization-rules.md` when a figure, result
  analysis, or revision mentions 3D bar, bar3D, two-category matrix bars,
  scenario-by-indicator bars, or parameter-grid bar charts.
- Use `scripts/plot_3d_bar.py` for CSV/XLSX long tables with `x`, `y`, `value`
  columns or matrix-form input.
- Save static PNG/PDF figures, cleaned bar-cell data, matrix data, plotting
  parameters, camera view, and a caption/caveat index.
- Treat 3D bars as structural matrix evidence. Use heatmaps, three-line tables,
  or ranking tables when exact value comparison matters.

## Non-goals

- Do not use 3D bars for ordinary one-dimensional rankings.
- Do not use 3D bars for dense matrices where occlusion hides values.
- Do not weaken the 0.6.1-0.6.7 layout, derivation, control-plane, t-SNE,
  distribution, flow, or 3D-scatter rules.
