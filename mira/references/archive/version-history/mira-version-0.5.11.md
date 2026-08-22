# Mira 0.5.11

Mira 0.5.11 adds the official-showcase scenario and visual-storyboard layer on
top of Mira 0.5.10.

This upgrade comes from comparing Mira's compact 2024 CUMCM B solution with an
official showcased B paper. Mira's exact modeling chain can be stronger than a
showcase paper's heuristic simulation, but the showcased paper often wins in
visible evidence density: process diagrams, scenario simulations, convergence
figures, batch-scale interpretation, and appendix code/evidence.

## New Standard

For `contest_final`, Mira should not stop at "formula, result, conclusion".
It should also try to produce:

- stage/process diagrams for the model and the hardest subquestion;
- scenario, simulation, perturbation, or batch-case validation;
- convergence, enumeration, top-candidate, or search-process evidence;
- clear figure roles and nearby decision interpretation;
- a compact appendix evidence package.

## New Gate

Run:

```bash
python scripts/scenario_showcase_gate.py --root <project-root> --write-report checks/showcase_presentation_report.md --write-json checks/showcase_presentation_report.json
```

Unresolved findings return to implementation, 5, 6, or 7 depending on whether the
missing item is result data, a figure, a diagram, or paper interpretation.

## Non-goals

- Do not add simulated annealing, GA, or Monte Carlo when exact enumeration or
  DP already proves the result and no validation role exists.
- Do not force 3D plots or heatmaps unless they explain a genuine interaction,
  threshold, spatial pattern, or temporal evolution.
- Do not bloat the paper with raw code in the main body; use appendix and
  artifact manifests.

