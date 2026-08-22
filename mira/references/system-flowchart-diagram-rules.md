# System Flowchart Diagram Rules

Use these rules when Mira needs to draw or audit process diagrams, system-link
diagrams, decision flows, state-transition diagrams, or mechanism pipelines.
This rule set is inspired by clean communication-system figures, but it is not
a communication-component icon library.

## Core Principle

A good flowchart is a reasoning object. It shows how information, material,
state, probability, cost, or decisions move through a system. Do not draw a
decorative equipment picture when a clean module-chain diagram would explain
the model better.

## What To Learn From The Laser-THz Paper

- **Main chain first**: place the dominant signal/process path on one horizontal
  or vertical axis.
- **Branches are meaningful**: use split/merge points only for real switching,
  coupling, recycling, state transition, or alternative decisions.
- **Module labels are compact**: short labels inside boxes; long definitions go
  below the figure or in the caption.
- **Domains are visible**: distinguish optical/electrical/wireless, upstream/
  downstream, input/model/output, or data/model/decision domains with subtle
  bands, braces, or labels.
- **Arrows are disciplined**: one arrow style for main flow, thinner/dashed
  arrows for feedback, uncertainty, or optional paths.
- **Caption explains abbreviations**: if a box uses short names, the caption or
  footnote decodes them.

## Contest Modeling Translation

Use the same grammar for:

- production/quality-control process chains;
- dynamic programming or recursion state transition;
- sampling -> estimation -> optimization -> robustness workflow;
- traffic, queueing, routing, scheduling, or supply-chain systems;
- neural/regression/SVM feature-to-result pipelines;
- multi-stage simulation and scenario experiments.

## Mermaid Sequence Diagrams

Use `sequenceDiagram` when the diagram's main job is interaction order rather
than module structure:

- data/model interaction: input validation -> solver call -> result check ->
  frozen output;
- solver/data call chain: code -> solver -> data file -> audit -> paper;
- feedback control: controller -> system -> observation -> correction;
- multi-role workflow where the actor sequence matters.

Use the template at `assets/templates/mermaid_sequence_diagram.mmd`. Keep the
Mermaid source in `diagrams/` when it is used for a paper figure. For
contest-final delivery, export to SVG/PDF/PNG or redraw in PPT/TikZ if the
Mermaid rendering is not polished enough.

Do not use `sequenceDiagram` for a static variable relation, a formula chain,
or a simple one-line algorithm. Use a structure diagram, flowchart, or table.

## Design Rules

1. Keep one visual reading direction unless the real process is cyclic.
2. Align modules on a grid; avoid floating, uneven boxes.
3. Use 2-4 colors max: main flow, secondary flow, uncertainty/feedback, neutral
   modules.
4. Put units or domain names on lanes instead of repeating them in every box.
5. Use small pictograms only when they reduce text. Do not build a large icon
   library before the diagram grammar is stable.
6. If a process has more than 12 modules, group them into stages or split into
   multi-panel diagrams.
7. Pair a flowchart with a paragraph saying what modeling assumption or formula
   each stage corresponds to.

## Recommended Artifacts

- `diagrams/model_solution_flow.png` or `.svg`: whole-paper solve chain.
- `diagrams/<question>_process_flow.png`: one problem-specific process diagram.
- `diagrams/<question>_state_transition.png`: recursion, DP, Markov, or
  feedback structure.
- `diagrams/<question>_sequence.mmd`: Mermaid source for interaction order,
  with an exported `.svg`/`.png` when inserted into the paper.
- `planning/figure_storyboard.md`: record diagram role as `process`,
  `state-transition`, `system-link`, `decision-flow`, `sequence`, or
  `mechanism`.
- `checks/flowchart_diagram_report.md`: output of
  `scripts/flowchart_diagram_gate.py`.

## Waivers

Record a waiver when:

- the problem has no process/system structure;
- a table or equation communicates the logic more clearly;
- the output is only a quick draft;
- a strict page limit prevents a support diagram.
