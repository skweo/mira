# Mira 0.8.3

## Scope

Mira 0.8.3 strengthens workflow, idea, structure, and process-diagram design
for Chinese mathematical modeling contest papers.

The upgrade learns three reusable diagram grammars:

| Reference grammar | Use when | Required structure |
|---|---|---|
| Complex technical swimlane | A system has repeated tasks, partitions, memory/disk/result exchange, or cross-stage transfer | stage containers, repeated instances, cross-lane arrows, merge/split labels, boundary annotations |
| Platform architecture map | A model or system has data, design/modeling, deployment, management, and application layers | dashed containers, icon/module nodes, thick main arrows, side/bottom support layers, output/user layer |
| Decision/approval swimlane | A process has actors, decisions, rejection loops, records, or work orders | role lanes, vertical sequence, diamond decisions, yes/no branches, return loop, terminal records |

This is not a decorative-flowchart target. Use these grammars only when they
make the model route, solver process, physical mechanism, or decision workflow
easier to understand than prose alone.

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\flowchart_diagram_gate.py `
  --root <project-root> `
  --write-report checks\flowchart_diagram_report.md `
  --write-json checks\flowchart_diagram_report.json
```

The gate checks whether process-heavy papers have diagrams and whether existing
diagrams expose:

- flowchart or route-map assets included in the paper;
- `diagrams/diagram_index.md` rows;
- stage containers, lanes, or grouped regions;
- branch, merge, feedback, or loop labels;
- decision nodes when decisions, approval, thresholds, or acceptance/rejection
  appear in the text;
- main-flow versus feedback/auxiliary-flow distinction;
- repeated instances when the text describes batch, split, vehicle, sample,
  task, scenario, particle, or route families;
- callouts, notes, legend, or abbreviation explanations;
- source toolchain such as PPTX, SVG, Python, or Mermaid.

## Drawing Rule

Before drawing, choose one diagram grammar:

1. Use a compact route diagram when the paper only needs
   `input -> transformation -> model -> solver -> validation -> output`.
2. Use a platform architecture map when the model has data/model/deployment or
   data/model/result/decision layers.
3. Use a decision/approval swimlane when there are actors, thresholds,
   yes/no branches, return loops, and records.
4. Use a complex technical swimlane when there are repeated instances and
   cross-stage exchange, such as map/reduce tasks, multi-vehicle routing,
   multi-agent control, split-merge heuristics, or staged simulation.

Record the selected grammar in the diagram index. If a high-value grammar is
not used, record a waiver explaining why a table, formula, or simpler diagram
is clearer.

## Repair Behavior

`checks/flowchart_diagram_report.md` feeds `iteration_loop.py`.

Typical repairs:

- missing process diagram returns to implementation;
- weak lanes/containers returns to implementation to redraw with grouped stages;
- weak branch/feedback logic returns to implementation to add decision/loop labels;
- missing repeated-instance grammar returns to implementation when batch or parallel
  instances are central to the model;
- missing legend or abbreviation explanation returns to implementation to add
  callouts and nearby interpretation.

Do not repair by adding decorative icons without model meaning.
