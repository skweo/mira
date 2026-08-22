# Mira 0.6.11

Mira 0.6.11 adds reproducible radar charts, Taylor diagrams, and 3D
surface/response-surface figures.

## New Standard

- Route `references/radar-taylor-surface-visualization-rules.md` when a figure,
  paper section, result analysis, or revision mentions radar chart, spider
  chart, Taylor diagram, model prediction comparison, 3D surface, response
  surface, parameter surface, contour companion, or two-parameter sensitivity.
- Use `scripts/plot_radar_taylor_surface.py` with `--kind radar`,
  `--kind taylor`, or `--kind surface`.
- Save PNG/PDF figures, cleaned plot data, summary table, parameters, and a
  caption/caveat index.
- Treat these figures as claim-bearing evidence only when the data contract is
  satisfied: comparable indicators for radar, paired observations/predictions
  for Taylor, and meaningful continuous grids or interpolation records for 3D
  surfaces.

## Non-goals

- Do not use radar charts as a substitute for explicit weighted scoring.
- Do not use Taylor diagrams as a substitute for bias or residual analysis.
- Do not read exact optima from a 3D surface without numerical refinement.
- Do not weaken the 0.6.1-0.6.10 layout, derivation, control-plane, and visual
  reproducibility rules.
