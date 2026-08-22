# Mira 0.7.3

## Scope

Mira 0.7.3 adds figure-portfolio control for contest-final papers.

## Problem Fixed

Earlier Mira versions planned visual evidence roles, but they did not audit the
overall chart grammar. This allowed two weak patterns:

- repeated line/bar/heatmap figures that made the paper look visually flat;
- decorative advanced plots that looked diverse but did not support claims.

## Active Rule

Visual diversity must follow evidence roles.

- Use mechanism or geometry diagrams when the objects and variables need to be
  seen before equations.
- Use process or operation diagrams when the algorithm, DP, heuristic, theorem,
  or solver route matters.
- Use result curves/tables/maps for final answers.
- Use validation, residual, baseline, sensitivity, or audit visuals for result
  credibility.
- Use zoom/detail panels only when full-scale plots hide critical local evidence.
- Use advanced charts only when their data structure justifies them.

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\figure_portfolio_gate.py `
  --root <project-root> `
  --write-report checks\figure_portfolio_report.md `
  --write-json checks\figure_portfolio_report.json
```

Findings return to implementation and should be repaired through the figure
storyboard, figure/diagram indexes, visual generation, captions, and nearby
interpretation.
