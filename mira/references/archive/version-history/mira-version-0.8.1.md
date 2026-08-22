# Mira 0.8.1

## Scope

Mira 0.8.1 strengthens modeling-route clarity for Chinese mathematical
modeling contest papers.

The upgrade addresses papers that have formulas, figures, and results but do
not clearly explain how each official question is transformed into a model and
solved. This is a writing-and-control upgrade, not a page-count target.

## New Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\modeling_route_audit.py --root <project-root> --output-level contest_final --write-report checks\modeling_route_report.md --write-json checks\modeling_route_report.json
```

The gate checks:

- visible overall route section such as `建模思路`, `技术路线`, `建模路线`, or `求解流程`;
- route roles: input, output, target, constraints, model, solver, validation,
  and evidence;
- per-question route coverage for multi-question papers;
- formula blocks that appear before any route explanation;
- route diagram/table need for complex multi-question papers;
- planning artifacts that should carry route cards before paper writing.

## Writing Requirement

For `contest_final`, the reader should see this route before dense formulas or
large result tables:

```text
official task -> input/output -> modeling transformation -> variables/objective/constraints -> solver route -> result evidence -> validation/interpretation
```

For each official subquestion, include a concise route card or paragraph:

| Item | Requirement |
|---|---|
| Input/output | What enters the model and what answer must be produced |
| Transformation | How the story problem becomes a mathematical object |
| Model | Variables, objective, constraints, mechanism, or state system |
| Solver | Exact, heuristic, simulation, regression, DP, or numerical route |
| Evidence | Which table/figure/result supports the answer |
| Validation | Feasibility, baseline, sensitivity, residual, convergence, or audit |

## Route Visual Policy

A technical route diagram is useful when the paper has several questions,
model families, or feedback loops. A concise route table is acceptable when it
communicates the route more directly. Do not add decorative flowcharts just to
satisfy a visual quota.

## Iteration Behavior

`checks/modeling_route_report.md` feeds `iteration_loop.py`.

Typical repairs:

- missing overall route returns to analysis;
- missing per-question route cards return to analysis;
- formula-before-route warnings return to modeling;
- route diagram/table gaps return to implementation only when they improve reader
  comprehension.

