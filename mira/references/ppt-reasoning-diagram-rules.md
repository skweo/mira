# PPT Reasoning Diagram Rules

Use this reference when Mira needs PowerPoint-shaped reasoning diagrams for a
Chinese mathematical modeling contest paper. This is for paper figures, not
presentation decks.

## Purpose

PPT is useful when a reasoning diagram needs editable shape layout, lanes,
arrows, callout boxes, and polished alignment that are awkward in plain
matplotlib. The final paper should include exported PNG/PDF; the PPTX is the
editable source artifact.

## When To Use

| Diagram | Good use | Avoid when |
|---|---|---|
| Complex technical swimlane | Repeated tasks, split/merge stages, memory/disk/output transfer, route groups, or multi-agent/multi-vehicle cross-stage exchange | The process is a single chain with no repeated instances or cross-lane dependencies |
| Platform architecture map | Data layer, modeling/design layer, deployment/execution layer, management/support layer, and user/application layer must be shown together | The paper only needs one modeling route and no system layers |
| Decision/process swimlane | Actors, yes/no decisions, rejection loops, records, work orders, or review steps matter | The process has no real branch or return loop |
| Whole-paper idea map | Shows how subquestions, models, results, and final advice connect | Each question is independent and a table is clearer |
| Showcase work map | Summarizes the whole modeling work with a title bar, nested dashed containers, side input chain, module stacks, sensitivity branches, and bottom objective split | The map copies an example paper's content or adds boxes without a real reasoning relation |
| Multi-branch feature-fusion architecture | Shows multi-source inputs, parallel encoders, latent feature bars, fusion/attention, and final prediction or decision | The paper has only one feature family or no validation/ablation for the fusion layer |
| CNN architecture | Shows input tensor, convolution/pooling blocks, Flatten/GAP, dense head, and prediction/classification output | The model does not actually use convolution or lacks training/validation evidence |
| Pseudo-3D schematic | Shows semantic layer depth, tensor/channel stacks, spatial/module topology, or scenario cards with editable PPT blocks | Depth has no stated meaning, labels become smaller, or exact numeric comparison is inferred from perspective |
| Model reasoning diagram | Maps variables, formulas, modules, and validation checks | The diagram repeats section headings without mathematical objects |
| Algorithm/process flow | Shows branch, loop, feedback, or stage ownership | The algorithm is a simple one-line formula |
| Enterprise execution diagram | Converts model outputs into owner, trigger, action, KPI, and review cycle | It is only a management slogan with no model link |
| Mermaid sequence diagram | Shows interaction order, call chain, solver/data exchange, or feedback timing | The relation is static, spatial, or mainly a formula chain |

## Data Contract

- Keep a JSON spec with `nodes`, `edges`, optional `groups`, and optional
  `callouts`.
- Each node should correspond to a real data object, variable set, formula,
  model module, algorithm step, result, decision, or execution action.
- Each edge should state what moves along it: data, parameter, constraint,
  state, objective value, risk signal, policy, or feedback.
- Save PPTX, normalized spec, node/edge CSV files, parameters, and diagram index.
- Export PNG/PDF for the final paper when PowerPoint or LibreOffice is
  available; otherwise record the export blocker and do not pretend the image
  was generated.

## Style Rules

- Use one main reading direction and align nodes on a grid.
- Use subtle domain/stage lanes for data/model/result/execution layers.
- For complex technical swimlanes, use large stage containers, repeated
  instance rows, cross-lane arrows, and labels for split, merge, shuffle,
  fetch, handoff, or exchange. Keep repeated rows visually consistent.
- For platform architecture maps, use dashed containers for major domains,
  thick arrows for the main business/model chain, smaller arrows for support
  links, side rails for input/output/application, and a bottom band for common
  support functions.
- For decision/approval swimlanes, use role lanes, vertical sequence, diamond
  decision nodes, explicit yes/no labels, return loops, and terminal record or
  output nodes.
- For interaction-order diagrams, first draft with Mermaid `sequenceDiagram`
  and `assets/templates/mermaid_sequence_diagram.mmd`; redraw as PPT only when
  final-paper polish, lanes, callouts, or layout control require it.
- For showcase work maps, use nested dashed containers to distinguish modeling
  stages, keep a clear top goal bar, and reserve the bottom row for objective
  decomposition or final decision output.
- For pseudo-3D schematics, use a stable oblique offset and make depth mean
  layer, channel, case, scenario, or module capacity; keep text on front faces.
- Keep node labels short; put long explanation in the caption or nearby text.
- Use dashed arrows only for feedback, uncertainty, optional paths, or
  assumption relaxation.
- Use callouts to explain a key mechanism, threshold, exception, or formula
  connection; do not use callouts as decoration.
- Prefer 2-4 colors and keep text readable after PDF compilation.
- Do not use icons as decoration. An icon must identify a real data object,
  model module, actor, platform component, solver step, record, or output.

## Script

Use the reusable script:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py `
  --root <project-root> `
  --spec diagrams\q2_reasoning_spec.json `
  --prefix q2_reasoning `
  --export auto
```

Built-in demos:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo model_flow --prefix model_flow --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo decision_loop --prefix decision_loop --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo paper_logic --prefix paper_logic --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo showcase_work --prefix showcase_work --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo multimodal_fusion --prefix multimodal_fusion --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo cnn_architecture --prefix cnn_architecture --export auto
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py --root <project-root> --demo pseudo_3d_architecture --prefix pseudo_3d_architecture --export auto
```

For Mira 0.8.3 reference grammars, use custom JSON specs based on one of:

- `showcase_work` for architecture/idea maps;
- `decision_loop` for decision or approval swimlanes;
- `model_flow` or a custom grouped spec for compact route diagrams;
- a custom repeated-row spec for complex technical swimlanes.

If Office export is unavailable, run with `--export none` to produce the PPTX
source and index, then export manually from PowerPoint before final insertion.

## Paper Integration

- Put the exported figure near the formula, algorithm, or management workflow it
  explains.
- The caption should state the reasoning role, not merely "flowchart".
- Nearby text should map important visual labels to symbols, constraints,
  solver steps, or execution actions.
- Do not count a PPT diagram as numerical evidence. Pair it with formulas,
  result tables, solver logs, or validation figures when the claim is numeric.
- The diagram index should record the selected grammar, stage/lane meaning,
  main-flow arrows, feedback/auxiliary arrows, repeated instances if any, and
  legend/callout text.
- For multi-source feature fusion, also read
  `references/multimodal-fusion-architecture-rules.md`; every branch, vector,
  fusion block, and feedback path must correspond to real features, modules,
  formulas, losses, or validation evidence.
- For CNN architecture figures, also read
  `references/cnn-architecture-diagram-rules.md`; input sizes, convolution
  kernels/channels, pooling, vectorization, output head, and validation evidence
  must be visible in the diagram or nearby table.
- For pseudo-3D PPT figures, also read
  `references/pseudo-3d-ppt-diagram-rules.md`; the depth dimension must be
  named in the caption and paired with a module/layer/scenario/variable table
  or other concrete evidence.
