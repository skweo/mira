# Mira 0.8.5

## Scope

Mira 0.8.5 adds clean figure-background discipline for contest-final figures.

## Rules

- Use white plotting areas by default.
- Do not enable default grid backdrops in ordinary matplotlib charts.
- Avoid seaborn `whitegrid` or `darkgrid` styles for final-paper figures.
- Use threshold lines, bracket annotations, shaded intervals, or callouts when
  the reader needs a reference cue.
- Radar and Taylor diagrams may keep necessary polar/radial structural guides,
  because those lines are part of the chart grammar rather than decoration.
- Heatmaps, contour maps, surface plots, and maps may show real data grids or
  contour structure when the grid itself carries meaning.

## Implementation

`scripts/visual_style.py` defaults to `axes.grid=False`, white figure/axes
backgrounds, and no inset/3D grid. Visual helpers should not call
`ax.grid(True)` unless a chart-specific exception is documented.

`scripts/visual_asset_audit.py` scans project plotting code for accidental grid
backdrops so visual-style regressions return to implementation before final delivery.
