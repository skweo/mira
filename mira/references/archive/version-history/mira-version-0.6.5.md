# Mira 0.6.5

Mira 0.6.5 adds reproducible distribution-visualization support for violin
plots, box plots, and JoyPlot/ridgeline plots.

## New Standard

- Route `references/distribution-visualization-rules.md` when a figure, result
  analysis, or revision mentions violin plot, box plot, JoyPlot, ridgeline,
  group distribution, outliers, IQR, or multi-scenario density comparison.
- Use `scripts/plot_distribution.py` for CSV/XLSX result tables when these
  distribution plots are needed.
- Save figure files, reshaped plot data, summary statistics, parameters, and a
  caption/caveat index.
- Treat distribution figures as evidence for spread, stability, tail risk,
  multimodality, and outliers. Do not claim statistical significance from the
  figure alone.

## Non-goals

- Do not replace exact result tables with decorative distribution plots.
- Do not use kernel-density shapes when each group has too few observations.
- Do not weaken the 0.6.1-0.6.4 layout, derivation, control-plane, or t-SNE
  rules.
