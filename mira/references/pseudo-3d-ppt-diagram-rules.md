# Pseudo-3D PPT Diagram Rules

Use this reference when Mira needs PPT-editable pseudo-3D or 2.5D schematic
figures for a Chinese mathematical modeling contest paper. This is for
structure, architecture, layer, spatial, and mechanism diagrams; it is not a
replacement for numerical 3D plots.

## Trigger

Use pseudo-3D PPT diagrams when at least one visible depth dimension has real
meaning:

- layer depth: data layer, model layer, solver layer, decision layer;
- channel depth: CNN feature maps, tensor channels, stacked samples;
- spatial depth: physical layout, geometry relation, module topology;
- pipeline depth: foreground input, middle transformation, rear validation;
- scenario depth: multiple plans or cases stacked as comparable cards.

Avoid pseudo-3D when a flat table, 2D curve, heatmap, or ordinary flowchart
would be clearer.

## Visual Grammar

- Use a stable oblique offset, normally right-up or right-down, across the whole
  figure.
- Depth must mean something stated in the caption: layer, channel, time, case,
  scenario, or module stack.
- Use stacked translucent faces for repeated feature maps or cases; use one
  thick block for a single module with capacity or representation depth.
- Keep labels on the front face only. Do not place text on side faces.
- Use at most 3 depth levels unless the diagram is specifically a CNN feature
  map or stacked scenario figure.
- Keep colors muted; depth should come from offset and layering, not heavy
  gradients.

## Paper Evidence Contract

For contest-final papers, a pseudo-3D diagram must be paired with evidence:

- architecture or module diagram -> nearby module/layer/variable table;
- CNN/tensor block -> input size, kernel/channel/downsampling table;
- spatial mechanism -> coordinate definition, geometry constraint, or formula;
- scenario stack -> scenario table or result comparison;
- workflow stack -> owner/trigger/output table or algorithm steps.

Do not treat the 3D look itself as evidence. It is only a reading aid.

## PPT Command

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py `
  --root <project-root> --demo pseudo_3d_architecture `
  --prefix pseudo_3d_architecture --export auto
```

If Office export is unavailable, use `--export none` and keep the generated
PPTX as the editable source.

## Failure Signs

- The caption cannot say what depth represents.
- Important text becomes smaller because the 3D effect consumes space.
- Arrows cross behind blocks and become ambiguous.
- The diagram looks like a cover graphic but cannot be mapped to variables,
  formulas, modules, cases, or results.
- Exact numeric comparison is made from perspective depth rather than a table,
  heatmap, contour plot, or ordinary chart.
