# Structure Schematic Rules

Use this reference when a contest-final paper needs a structure schematic,
model-relationship diagram, object structure, geometry schematic, variable
relationship map, module architecture, topology, local-detail schematic, or
problem-object diagram.

## When To Use

| Diagram | Best use | Avoid when |
|---|---|---|
| Object/system structure | Show the real system, components, states, modules, or topology before modeling. | The figure only repeats prose and has no variables, constraints, or reasoning role. |
| Model relationship schematic | Connect input data, variables, assumptions, equations, solver, validation, and output. | A formal derivation or result table is needed instead of a diagram. |
| Geometry/local-detail schematic | Explain coordinate system, angle, distance, boundary, collision, zoom region, or physical layout. | Scale, threshold, or exact value is important but not backed by a quantitative figure/table. |

Use a structure schematic to explain how the model is constructed. Use result
figures to prove numerical conclusions.

## Data Contract

- Prefer a JSON spec with `nodes`, `edges`, optional `groups`, and optional
  `callouts`; or use nodes/edges CSV tables.
- Each node must correspond to a real object, variable, state, equation, module,
  data source, constraint, or output.
- Each edge must have a meaning: data flow, state transition, dependency,
  constraint link, feedback, local refinement, or result handoff.
- Save normalized spec, node table, edge table, parameters, and a caption/caveat
  index.
- Do not invent structural elements only to make a figure look full.

## Diagram Standards

- Keep labels short and use nearby prose for explanation.
- Use groups or lanes only when they clarify levels such as data layer, model
  layer, decision layer, or validation layer.
- Use dashed arrows for optional, feedback, or local-refinement links; explain
  the meaning in the caption or nearby text.
- Use callouts for key insight, not long paragraphs.
- For geometry schematics, show coordinate, variable, boundary, and local zoom
  roles; pair with quantitative plots when scale matters.
- Captions should state what the diagram explains and how it connects to the
  following formula, model, or result.

## Interpretation Discipline

Good wording:

> 图中将来料批次、抽样判定、零配件状态、装配树递推和策略输出放在同一结构中。虚线表示拆解回收后的状态反馈，说明后续递推不能把回收件重新视为完全未知件，这正是三态信息保持模型的结构来源。

Avoid:

> 本文加入结构图，使论文更美观。

Do not use a structure schematic as evidence for numerical optimality. It should
explain modeling logic; exact values still need formulas, tables, code outputs,
or validation figures.

## Script

Use the reusable script for JSON specs:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_structure_diagram.py `
  --root <project-root> `
  --spec diagrams\q2_structure_spec.json `
  --prefix q2_model_structure
```

Or use nodes/edges tables:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_structure_diagram.py `
  --root <project-root> `
  --nodes diagrams\structure_nodes.csv `
  --edges diagrams\structure_edges.csv `
  --prefix q2_model_structure
```

The script writes PNG/PDF figures, normalized spec, node/edge/group/callout
tables, parameters, and a caption/caveat index.
