# Mira 0.6.6

Mira 0.6.6 adds reproducible flow-relationship visualization support for Sankey
diagrams and circular Sankey/chord diagrams.

## New Standard

- Route `references/flow-visualization-rules.md` when a figure, result analysis,
  or revision mentions Sankey, circular Sankey, chord diagram, source-target
  flow, OD flow, material flow, energy flow, information flow, or transfer
  structure.
- Use `scripts/plot_flow.py` for CSV/XLSX edge tables with source, target, and
  positive value columns.
- Save static PNG/PDF figures, cleaned edge data, node summaries, parameters,
  and a caption/caveat index.
- Treat Sankey/chord figures as structural evidence. Keep exact flow values in
  nearby tables or saved edge data.

## Non-goals

- Do not use flow diagrams for simple one-dimensional compositions that a table
  or stacked bar can show more clearly.
- Do not mix incompatible units in one width scale.
- Do not weaken the 0.6.1-0.6.5 layout, derivation, control-plane, t-SNE, or
  distribution-visualization rules.
