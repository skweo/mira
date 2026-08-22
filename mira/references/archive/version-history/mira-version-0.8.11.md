# Mira 0.8.11

## Scope

Mira 0.8.11 adds AI image-generation routing for illustrative visuals in
Chinese mathematical modeling contest papers.

Use this only when a generated image helps the reader understand a mechanism,
scene, equipment layout, physical setup, structure, or conceptual legend that
would be hard to express with a simple chart or editable PPT/vector diagram.

## Allowed Uses

- mechanism or physical-process illustration;
- problem scene or equipment schematic background;
- conceptual legend explaining force, flow, layer, state, or interaction;
- realistic-looking but clearly illustrative object/scene image;
- cover-like or section-leading visual when the contest format allows it.

## Forbidden Uses

- data charts, result curves, heatmaps, sensitivity plots, route maps, or solver
  evidence that should be generated from data or code;
- fake experiment photos, fake measured equipment, fake maps, fake datasets, or
  fake literature figures;
- precise geometry, formula, coordinate, constraint, or algorithm diagrams that
  should remain editable and traceable;
- generated text inside the image when Chinese labels must be exact. Add labels
  later with PPT, matplotlib, SVG, LaTeX, or another editable layer.

## Required Records

For every AI-generated visual, record:

- tool name, version/model, developer, and use date;
- stage and purpose, such as `implementation 图示生成`;
- summarized prompt and reply/result;
- generated asset path and final edited asset path;
- human modification and adoption decision;
- paper location and caption/claim supported.

These records belong in `planning/ai_usage_ledger.json`,
`planning/ai_usage_ledger.md`, and `figures/figure_index.md` or
`diagrams/diagram_index.md`. For CUMCM-style output, they must also appear in
the AI-use detail PDF generated from the ledger.

## Prompt Rule

Prompt for visual structure, object relations, style, and blank label space.
Avoid asking the model to render exact Chinese text, formulas, numbers, tables,
or final answer labels. Add exact labels and arrows in an editable post-process.

## Paper Rule

The caption must make the figure's status clear when needed, for example:
`图 X 由 AI 辅助生成并经人工修改，用于说明系统结构，不作为数值计算证据。`
Use this wording only when contest rules and paper style make an explicit body
marker appropriate; otherwise keep the full disclosure in the AI-use detail
material and references.
