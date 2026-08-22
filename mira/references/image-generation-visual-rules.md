# AI Image-Generation Visual Rules

Use these rules when a mathematical modeling paper needs an illustration that is
not a data chart and not a precise editable model diagram.

## Decision Rule

Use AI image generation only for illustrative visuals:

| Need | Prefer |
|---|---|
| Numeric result, sensitivity, distribution, matrix, route, forecast, error | Python, MATLAB/Octave, Excel, ECharts, or table from data |
| Exact flowchart, coordinate system, algorithm, formula relation, architecture | Python/matplotlib/networkx, MATLAB, TikZ, or scoped Mermaid/PPT |
| Physical scene, equipment, mechanism intuition, conceptual legend, background illustration | AI image generation plus editable labels |

If a visual supports a numeric claim, it must be generated from data or code.
If it explains a mechanism or scene, AI generation is allowed when traceable.

## Required Workflow

1. Add the planned visual to `planning/figure_storyboard.md/json` with role
   `define`, `derive`, `operate`, or `explain`.
2. Record why AI generation is better than a data chart or editable diagram.
3. Generate the image with the model's image tool.
4. Post-process exact Chinese labels, arrows, formulas, and callouts in an
   editable layer when needed.
5. Save source prompt/response summary and asset path in
   `planning/generated_image_route.json`.
6. Add the asset to `figures/figure_index.md` or `diagrams/diagram_index.md`
   with source tool, prompt summary, human edits, supported claim, and paper
   location.
7. Run visual-asset and AI-compliance checks before final delivery.

## Prompt Pattern

Use concise prompt fields:

```text
Subject:
Paper role:
Objects and relations:
Viewpoint/composition:
Style:
Blank label space:
Do not include:
```

Prefer clean, high-resolution, label-ready output. Avoid embedded text,
watermarks, fake data panels, fake UI, fake charts, and fake measurement values.

## Disclosure

For contest-final papers, AI-generated images count as AI-assisted content.
They must be included in the generated-image route record. Do not
claim the team used no AI tools if image generation was used.
