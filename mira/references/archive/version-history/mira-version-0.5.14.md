# Mira 0.5.14

Mira 0.5.14 adds system-flowchart diagram grammar on top of Mira 0.5.13.

This upgrade refines the previous journal-grade visual work. It does not create
a large communication-device icon library. Instead, it learns the transferable
structure of strong system diagrams: main chain, branches, merge points, domain
lanes, compact module labels, disciplined arrows, and abbreviation explanations.

## New Standard

For `contest_final`, if a problem has a process, state, decision, recursion, or
multi-stage solver chain, Mira should try to include at least one clean
flowchart or system-link diagram. The diagram must correspond to actual model
logic and should be referenced in nearby text.

## New Gate

Run:

```bash
python scripts/flowchart_diagram_gate.py --root <project-root> --write-report checks/flowchart_diagram_report.md --write-json checks/flowchart_diagram_report.json
```

Unresolved findings usually return to implementation for diagram generation or paper
for caption, abbreviation, and text-loop repair.

## Non-goals

- Do not build a communication icon library yet.
- Do not draw equipment diagrams that do not support a model or conclusion.
- Do not replace formulas with diagrams; use diagrams to expose the formula
  chain and stage logic.

