# Mira 0.6.9

Mira 0.6.9 adds reproducible structure-schematic support for model
relationships, system/object structures, topology, geometry sketches, and local
detail diagrams.

## New Standard

- Route `references/structure-schematic-rules.md` when a figure, diagram,
  result explanation, or revision mentions structure schematic, model relation,
  object structure, geometry schematic, topology, module architecture, or local
  detail schematic.
- Use `scripts/plot_structure_diagram.py` for JSON specs or nodes/edges tables.
- Save static PNG/PDF diagrams, normalized spec, node/edge/group/callout tables,
  parameters, and a caption/caveat index.
- Treat structure schematics as modeling-logic evidence. They explain how the
  model is constructed; they do not replace formulas, result tables, or
  validation figures.

## Non-goals

- Do not draw decorative structure diagrams with no nearby reasoning role.
- Do not use a schematic as evidence for exact numerical claims.
- Do not weaken the 0.6.1-0.6.8 layout, derivation, control-plane, statistical
  visualization, flow, 3D scatter, or 3D bar rules.
