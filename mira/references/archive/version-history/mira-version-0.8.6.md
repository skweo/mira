# Mira 0.8.6

## Scope

Mira 0.8.6 adds Hexbin joint-distribution plots with marginal histograms.

Use this grammar when a result table has many paired numeric samples and an
ordinary scatter plot would hide density because points overlap.

## When To Use

- Two continuous numeric variables with at least about 120 complete samples.
- Monte Carlo, simulation, residual, paired observation/prediction, parameter
  sample, or feature-response data.
- The paper needs to show bivariate density, correlation direction, dense
  regions, tail behavior, or marginal distribution shape.

## When Not To Use

- Small samples where individual points should be inspected.
- Few discrete categories where grouped bars, box plots, or tables are clearer.
- Matrix-like parameter grids where heatmaps or contour plots are more direct.
- Claims that require causality, optimality, or exact thresholds without
  supporting statistics.

## Output Contract

`scripts/plot_hexbin_joint.py` writes:

- hexbin joint figure as PNG/PDF;
- cleaned paired sample data;
- summary statistics including Pearson and Spearman correlation;
- parameter JSON with `gridsize`, bins, and source;
- figure index with caption, interpretation, and caveats.

The figure must follow Mira 0.8.5 style: white background, no chart grid
backdrop, Chinese labels, and a clear colorbar saying that hex color means
sample count.
