# Figure Diversity Portfolio Rules

Use this reference when a Mira contest paper needs stronger and more varied
visual evidence.

## Core Rule

Diversify by evidence role, not by decoration.

A strong paper visual portfolio usually combines several of these roles:

| Role | Good visual forms | Use when |
|---|---|---|
| define | mechanism diagram, geometry schematic, state/network diagram | readers need objects, coordinates, variables, or states before equations |
| derive | local relation diagram, constraint sketch, formula-linked annotation | a formula or constraint is hard to see from text alone |
| operate | flowchart, recurrence/update diagram, search process, pipeline | algorithm, DP, heuristic, theorem, or solver logic matters |
| result | curve, route map, schedule, ranking, final-state plot, compact table | the visual carries a final decision or answer |
| validate | residual plot, baseline comparison, sensitivity, audit map, feasibility table | claims need robustness, constraints, or error evidence |
| zoom | local inset, boundary-state pair, critical-detail panel | full-scale plots hide a collision, peak, threshold, crossing, or local failure |
| compare | grouped subplots, before/after panels, scenario matrix, Pareto/frontier view | multiple policies, candidates, or scenarios must be contrasted |

## Avoid

- Do not add 3D, Sankey, radar, t-SNE, violin, or heatmap figures merely to
  look diverse.
- Do not use the same line chart grammar for every claim when the paper contains
  mechanisms, algorithms, validations, and comparisons.
- Do not use heatmaps unless the data are naturally matrix/grid-like.
- Do not use 3D surfaces unless the claim depends on a two-parameter response or
  spatial surface; pair with a 2D projection when exact comparison matters.
- Do not leave figure roles only in the storyboard. The paper text and captions
  should reveal why each visual exists.

## Portfolio Check

Before final contest delivery, run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\figure_portfolio_gate.py `
  --root <project-root> `
  --write-report checks\figure_portfolio_report.md `
  --write-json checks\figure_portfolio_report.json
```

Warnings should return to implementation. Repair by changing the figure storyboard,
figure index, diagrams, captions, or nearby interpretation. Add new visuals only
when a different visual grammar supports a missing evidence role.

## Practical Pattern

For a multi-question contest-final paper, aim for a visible mix like:

- one definition or mechanism diagram when the object system is nontrivial;
- one operation/process visual when the solver route is nontrivial;
- per-question result visuals or compact result tables;
- at least one validation/sensitivity/baseline visual when final conclusions
  depend on numerical experiments;
- zoom or comparison panels only when the claim requires them.

This is a portfolio pattern, not a quota.
