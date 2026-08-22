# Mira 0.8.2

## Scope

Mira 0.8.2 strengthens visual-opportunity selection for Chinese mathematical
modeling contest papers.

The upgrade addresses papers that already have figures, but still miss the
most expressive chart grammar for the evidence. A table with several schemes
and several indicators should trigger a radar or parallel-coordinate decision;
a two-parameter sensitivity table should trigger heatmap/surface consideration;
a mechanism-heavy route should trigger PPT-editable reasoning diagrams when a
diagram would clarify the model.

This is not a figure-count target. The gate asks whether Mira noticed and
handled high-value visual opportunities.

## New Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_opportunity_audit.py `
  --root <project-root> `
  --output-level contest_final `
  --write-report checks\visual_opportunity_report.md `
  --write-json checks\visual_opportunity_report.json
```

The gate scans `results/tables`, `figures/figure_index.md`,
`diagrams/diagram_index.md`, `planning/figure_storyboard.md`, and paper text.

It checks for:

- multi-scheme, multi-indicator tables that should consider radar charts or
  parallel coordinates after normalization and direction alignment;
- metric-value tables that should consider compact radar/normalized indicator
  profiles;
- two-parameter response or sensitivity tables that should consider heatmaps,
  contour maps, or MATLAB/Octave-style surface figures;
- large sample or Monte Carlo tables that should expose distribution, tail, or
  quantile evidence;
- circular angle/direction data that should consider polar plots;
- mechanism, route, control, algorithm, or pseudo-3D structure text that should
  consider PPT-editable reasoning diagrams;
- missing figure/diagram indexes and missing visual toolchain provenance.

## Toolchain Rule

Mira should choose tools by visual role:

| Evidence need | Preferred toolchain |
|---|---|
| Reproducible data plot | Python/matplotlib with saved data, parameters, PNG/PDF |
| Small normalized scheme comparison | Python radar plot or Excel-compatible normalized table/chart |
| Two-parameter response surface | Python surface/contour or MATLAB/Octave-style surface when available |
| Editable route/mechanism diagram | PPT/PowerPoint source plus exported PNG/PDF |
| Exact values or audit ledger | Excel-compatible CSV/XLSX table plus compact paper table |

Record the actual toolchain in `figures/figure_index.md` or
`diagrams/diagram_index.md`. Do not claim PPT, Excel, MATLAB, or any tool was
used unless the artifact or command proves it.

## Repair Behavior

`checks/visual_opportunity_report.md` feeds `iteration_loop.py`.

Typical repairs:

- missed radar opportunity returns to implementation to normalize indicators and
  generate radar, parallel coordinates, or a normalized score table;
- missed heatmap/surface opportunity returns to implementation to build a response
  map or explicitly waive it if the table is too sparse;
- missing toolchain provenance returns to implementation to update figure/diagram
  indexes;
- missing PPT/mechanism opportunity returns to implementation only when the diagram
  explains a real model route, variable relation, solver loop, or physical
  mechanism.

Do not repair by adding decorative advanced charts.
