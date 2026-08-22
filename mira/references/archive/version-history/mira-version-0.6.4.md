# Mira 0.6.4

Mira 0.6.4 adds a reusable t-SNE visualization capability without expanding the
startup control plane.

## New Standard

- Route `references/tsne-visualization-rules.md` when a figure, model plan, or
  revision mentions t-SNE, TSNE, embedding, manifold learning, high-dimensional
  visualization, or clustering visualization.
- Use `scripts/plot_tsne.py` for CSV/XLSX feature matrices when a reproducible
  t-SNE plot is needed.
- Save figure files, coordinates, parameters, and a caption/caveat index instead
  of inserting a screenshot-only t-SNE image.
- Treat t-SNE as visual evidence only. Pair it with quantitative metrics,
  tables, confusion matrices, cluster scores, or robustness checks when the
  paper makes a classification or clustering claim.

## Non-goals

- Do not turn every high-dimensional problem into a t-SNE figure.
- Do not use t-SNE as proof of global distance, true cluster count, or model
  accuracy.
- Do not weaken the 0.6.1 abstract layout, 0.6.2 derivation-density, or 0.6.3
  control-plane cleanup rules.
