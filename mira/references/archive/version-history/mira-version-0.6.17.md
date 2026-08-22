# Mira 0.6.17

## Scope

Mira 0.6.17 adds PPT-editable pseudo-3D schematic figures for contest-paper
structure, architecture, layer, tensor/channel, spatial, and scenario-stack
visuals.

## Added Capability

- Route pseudo-3D, 2.5D, layered-block, stacked-card, tensor-block, and spatial
  schematic requests to `references/pseudo-3d-ppt-diagram-rules.md`.
- Generate an editable PowerPoint demo with pseudo-3D blocks through
  `plot_ppt_reasoning_diagram.py --demo pseudo_3d_architecture`.
- Support per-node pseudo-3D depth in the PPT diagram spec through
  `pseudo_3d`, `depth_layers`, `depth_dx`, and `depth_dy`.

## Guardrail

Pseudo-3D depth must carry semantic meaning. It may show layer, channel, case,
scenario, module capacity, or spatial relation, but it must not replace
formulas, exact numeric tables, solver evidence, or validation figures.
