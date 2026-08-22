# Figure And Table Rules

Use this reference when planning, drafting, or revising figures and tables for a
`contest_final` Chinese mathematical modeling contest paper.

Also read `visual-expression-rules.md` when creating final figures or diagrams.
This file decides what evidence is needed; `visual-expression-rules.md` controls
readability, style, image assets, and final visual polish.
Read `figure-diversity-portfolio-rules.md` when the paper has several figures,
when figures feel repetitive, or when a high-award target needs richer visual
reasoning.
Read `visual-expression-rules.md` and `chart-gallery-index.md` when result
tables may support richer chart grammar such as radar charts, heatmaps,
surfaces, distribution plots, polar plots, or tool-specific evidence.
Read `system-flowchart-diagram-rules.md` and `visual-backend-rules.md` when a
paper needs workflow, idea, architecture, approval, or model-route diagrams.
Read `image-generation-visual-rules.md` when a mechanism, scene, equipment, or
conceptual legend may benefit from AI image generation.

## Evidence Ladder

Before implementation selects final paper figures for a `contest_final`, run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plan_presentation_budget.py --root <project-root>
```

Then run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_opportunity_audit.py `
  --root <project-root> `
  --output-level contest_final `
  --write-report checks\visual_opportunity_report.md `
  --write-json checks\visual_opportunity_report.json
```

Then run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\figure_storyboard.py `
  --root <project-root> `
  --write-report planning\figure_storyboard.md `
  --write-json planning\figure_storyboard.json
```

Use `planning/presentation_budget.md` as the figure/table/reference budget for
implementation and paper. The budget prevents `standard` lane from silently
compressing the figure set below the level needed for high-award comparison.
Use `planning/figure_storyboard.md` as the visual reasoning plan: it should say
which figures define, derive, operate, show results, validate, zoom, or compare.
Use `checks/visual_opportunity_report.md` before final figure generation to
catch missed chart grammars. A warning does not mean "add the chart blindly";
it means either generate the recommended visual from evidence or write a
visible waiver explaining why the chart would not improve the claim.
Use `checks/figure_portfolio_report.md` to check whether the actual figure set
has a reasonable mix of visual roles and chart grammars.

Plan figures and tables as an evidence ladder:

1. Data structure evidence: matrix view, heatmap when useful, distribution,
   trend, network view, missing/abnormal summary, or grouped comparison.
2. Model logic evidence: technical route, subquestion flowchart, variable
   structure, constraint structure, or indicator system.
3. Result evidence: final route, schedule, ranking, parameter, allocation, or
   policy table, plus claim-critical plots.
4. Validation evidence: baseline comparison, error/residual analysis,
   constraint audit, sensitivity curve, multi-seed stability, or solver gap.
5. Supporting result files: complete routes/schedules, long parameter tables,
   code map, run settings, and reproducibility commands kept outside the PDF.

Do not add a layer if the source data or result artifact does not exist.
AI-generated illustrations may fill an explanation layer only when they clarify
a scene, object, mechanism, or conceptual legend. They do not count as source
data, result evidence, validation evidence, or solver proof.

For geometry, kinematics, collision, path, or algorithm-heavy papers, the body
should also expose a visual reasoning chain:

1. Definition visual: coordinate system, object geometry, variables, or state.
2. Derivation visual when helpful: local geometry, relation, or constraint that
   explains why the formula has its form.
3. Operation visual: theorem check, recurrence, search procedure, or solver
   update flow.
4. Result visual/table: final state, threshold, route, speed, ranking, or policy.
5. Detail/validation visual: local zoom, paired boundary states, residual,
   feasibility audit, or sensitivity.

This chain is not a fixed quota. It is a checklist for whether the reader can
see how the model moves from object definition to final claim.

For high-award comparison targets, the evidence ladder should be visible in the PDF, not only in saved artifacts. A reviewer should see the data structure, model idea, result evidence, and validation evidence while reading the body. If the paper has only result tables and audit prose, return to implementation and build better visuals.

## Table Style

For final-paper tables, prefer three-line style. In LaTeX, use `booktabs` with
`\toprule`, `\midrule`, and `\bottomrule`; avoid vertical rules and repeated
`\hline`. In Typst or Markdown, render an equivalent restrained table rather
than a dense full-grid table.

Use `references/three-line-table-rules.md` before final paper writing or
revision. Before final delivery, run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\table_style_audit.py --root <project-root> --write-report checks\table_style_report.md --write-json checks\table_style_report.json
```

Table-style findings return to paper. They may change table formatting,
captions, units, and placement, but not numeric values.

## Required By Problem Type

| Problem type | Main-text evidence | Supporting result files |
|---|---|---|
| Routing/VRP/VRPTW | distance/travel-time matrix view or edge-cost summary, route map, route/load/time table, coverage audit, capacity/time-window audit, vehicle-count sensitivity | complete route schedule, edge table, solver settings |
| Scheduling/MILP | demand/load distribution, heatmap when the data are naturally two-dimensional, resource or coverage diagram, summary schedule table, gap or bound table, representative schedule | complete schedule, solver log/gap, code map |
| Forecasting | raw trend, train/validation split, prediction-vs-actual curve, residual/error table, scenario or sensitivity plot | full forecast table, parameter table |
| Parameter fitting | raw data, preprocessing diagnostic, fitted curve, residual/error plot, parameter sensitivity or uncertainty table | solver tolerance, convergence log, full parameter estimates |
| Evaluation/ranking | indicator-source table, indicator system when useful, weight table, normalized indicator table, score/ranking table, weight sensitivity | full normalized matrix, full judgment matrices, CR records |
| Mechanism/simulation | mechanism diagram, scenario table, simulation result curve/table, plausibility or limiting-case check | full parameter/scenario settings |
| Interpolation/spatial reconstruction | coordinate/grid schema, target geometry when needed, reconstructed field/slice/surface, compact method comparison or error table, residual/error map only when it supports a local-error claim | full grid metadata, interpolation settings, holdout/residual tables, sensitivity runs |
| Engineering algorithm/resource tradeoff | system/simulation platform diagram, baseline metric curve/table, parameter-scan curve/surface, operation-level resource table, timing/pipeline diagram when throughput matters, performance-resource tradeoff table/curve | full parameter grid, seed/sample settings, fixed-point settings, complete operation counts, code map |

## Placement Rules

- Put each figure or table in the section that makes the claim.
- Before a figure/table, state what question it answers.
- After a figure/table, interpret the change, comparison, or decision value.
- Use captions to state what the figure/table proves, not just what it depicts.
- Use reviewer-readable labels. Axis labels, legends, and important annotations must remain legible after PDF compilation. Avoid tiny English method labels when a concise Chinese label would make the figure clearer.
- For Chinese papers, figure captions, table captions, axis labels, legends,
  colorbar labels, subplot titles, and in-figure annotations must be Chinese
  except for accepted acronyms, variable symbols, and units. Matplotlib strings
  such as `tilt angle`, `case`, `force allocation`, `pulse duration`,
  `probability`, or `residual angle` are final-delivery FAIL items in Mira 0.8.
- A figure should usually carry one claim. If it needs multiple subplots, each subplot must have a clear caption or annotation and the surrounding text must interpret the comparison.
- If a figure uses arrows, colored intervals, highlighted objects, or local
  detail panels, the paragraph after the figure should explicitly say what
  those marks mean. Do not assume the reader will infer the legend's role.
- For critical values found by traversal, bisection, local search, PSO, SA, or
  any other search, prefer a coarse-to-fine visual pair: broad search trend plus
  local refined view or boundary-state comparison.
- For theorem-based constraints, match text steps to visual labels. A step named
  `STEP1`/`STEP2`/`STEP3` should correspond to visible objects, arrows,
  intervals, states, or matrices in the figure or flowchart.
- Choose the simplest visual form that supports the claim. Use heatmaps only for
  dense matrices, spatial grids, time-resource grids, correlation matrices, or
  other genuinely two-dimensional relationships. Prefer tables, line charts,
  bar charts, network diagrams, or concise summaries when they communicate the
  evidence more directly.
- For small scheme-by-indicator comparisons, evaluate radar charts before
  defaulting to plain tables or grouped bars. Use radar only after metric
  normalization and direction alignment; otherwise use parallel coordinates or
  a normalized score table.
- For two-parameter sensitivity or response tables, evaluate heatmap, contour,
  or surface figures. Use MATLAB/Octave-style surfaces only when the response
  grid or interpolation contract is recorded.
- For mechanism, signal-chain, rigid-body, control-loop, model-route, or
  algorithm-loop explanations, evaluate PPT-editable reasoning diagrams or
  pseudo-3D schematics when the diagram exposes real variables, states,
  modules, or feedback.
- For mechanism scenes, equipment appearances, physical-process intuition, or
  conceptual legends that cannot be cleanly expressed as a data chart or
  editable vector/PPT diagram, AI image generation is allowed. Record prompt,
  model/tool, generated asset, edits, and paper location in the visual index;
  add exact Chinese labels in post-processing.
- For workflow, idea, architecture, and decision diagrams, choose the diagram
  grammar before drawing: compact route, platform architecture map,
  decision/process swimlane, or complex technical swimlane. A final diagram
  should expose stage containers or lanes, main flow, branches, feedback, and
  legend/callout text whenever those structures exist in the model.
- Keep main-text tables compact. Save long schedules, route lists, and full
  matrices as structured result files.
- Avoid decorative charts and oversized flowcharts that do not support a claim.
- Do not reuse a fixed visual package across all papers. AHP/evaluation papers need an indicator hierarchy only when it clarifies real criteria; heatmaps only when the normalized matrix is large enough to reveal structure; flowcharts only when the model chain is nontrivial.
- For interpolation tasks, use heatmaps, contour maps, surfaces, slices, or residual maps only when the data are genuinely spatial/grid-like and the visual supports a reconstruction or error claim.
- For engineering implementation tasks, use timing or pipeline diagrams only when timing, throughput, delay, or parallelism is part of the model. Use resource tables as evidence, not decoration; every resource total should be traceable to operation counts or problem-provided unit costs.
- Store every paper figure's source data, generation script, supported claim,
  and intended paper location in `figures/figure_index.md`.
- When the figure storyboard has `callout` text, either convert it into nearby
  prose or use it as a compact explanatory side note. Do not leave callout text
  only in planning files.
- For high-award multi-question papers, use the presentation budget as an
  evidence-coverage guide, not a figure quota. Add a visual only when it defines
  a mechanism, supports a result, validates a claim, or explains a decision
  better than nearby text or a compact table.
- Before final delivery, verify that figure/table numbering is sequential and
  matches every in-text reference. Manual numbering mistakes are treated as a
  format defect even when the model is correct.
- Before final delivery, run `scripts/check_presentation_strength.py --root <project-root> --write-report checks/presentation_strength_report.md` for `contest_final` outputs. If it reports weak visual evidence, do not fix by adding decorative plots; add claim-bearing figures or tables from data, result, or validation artifacts.
- Before final delivery, run `scripts/visual_asset_audit.py --root <project-root> --write-report checks/visual_asset_audit_report.md --write-json checks/visual_asset_audit_report.json` to catch low-resolution, unindexed, placeholder, or oversized visual assets.
- Before final delivery, run `scripts/visual_reasoning_audit.py --root <project-root> --write-report checks/visual_reasoning_audit_report.md --write-json checks/visual_reasoning_audit_report.json` to catch missing figure references, weak abstract/result emphasis, unhighlighted final formulas, missing zoom/detail evidence, unjustified heatmaps/3D views, and weak multi-case visual evidence.
- Before final delivery, run `scripts/final_polish_language_gate.py --root <project-root> --write-report checks/final_polish_language_report.md --write-json checks/final_polish_language_report.json` to catch English figure/table prose and matplotlib labels embedded in final Chinese figures.
- Before final delivery, run `scripts/visual_opportunity_audit.py --root <project-root> --output-level contest_final --write-report checks/visual_opportunity_report.md --write-json checks/visual_opportunity_report.json` to catch missed radar, heatmap/surface, distribution, polar, PPT reasoning, and toolchain-provenance opportunities.
- Before final delivery, run `scripts/flowchart_diagram_gate.py --root <project-root> --write-report checks/flowchart_diagram_report.md --write-json checks/flowchart_diagram_report.json` to catch missing or weak workflow/idea/architecture diagram grammar.
- Before final delivery, run `scripts/figure_portfolio_gate.py --root <project-root> --write-report checks/figure_portfolio_report.md --write-json checks/figure_portfolio_report.json` to catch repetitive chart grammar, missing validation/operation/definition visuals, or advanced visuals without a clear evidence role.

## MathorCup A Routing Upgrade Checklist

For the current MathorCup A route/scheduling paper family, a stronger final
revision should include these artifacts when data support them:

- travel-time matrix view, heatmap when useful, or edge-cost summary;
- node demand and/or time-window distribution;
- time-window violation bar chart or schedule timeline for the selected Q2/Q3/Q4 plans when penalties drive the objective;
- algorithm comparison table: baseline, local search, seeded heuristic, and
  multi-start or multi-seed variant;
- route continuity, visit uniqueness, and coverage audit;
- vehicle-count sensitivity for the relevant range, such as 5-9 vehicles;
- load rate or vehicle utilization table/plot;
- route or route-family visualization when it helps compare vehicle grouping or time-window pressure;
- separate result files with complete route schedule, run settings, seed, and
  solver parameters.
