# Showcase Scenario Rules

Use these rules when Mira targets a high-award Chinese mathematical modeling
contest paper, especially after comparing against official showcased papers.
The goal is not to add decorative pages. The goal is to turn a compact model
solution into a visible evidence chain that a reviewer can follow quickly.

## Core Rule

Keep the strongest valid model as the spine. If exact enumeration, DP,
closed-form recursion, or solver-backed proof is feasible, do not replace it
with simulated annealing, genetic algorithms, or Monte Carlo just to look rich.
Add simulation and scenario experiments as validation, stress tests, or
engineering interpretation.

## Required Layers

For `contest_final` outputs, try to build all four layers unless the problem is
too small or the contest page limit forbids it.

1. **Stage/process storyboard**: show how data, state, decision, solver, and
   result move through the problem. Prefer one overall flow plus one local
   process diagram for the most complex subquestion.
2. **Scenario experiment layer**: add at least one batch case, scenario matrix,
   Monte Carlo/posterior perturbation, parameter stress test, or representative
   enterprise example that validates or interprets the analytic result.
3. **Search/process evidence**: for enumeration, DP, heuristic search, or
   Monte Carlo, show the search scale, convergence/iteration trace, top-candidate
   gap, running profile, or state-space reduction. This complements the
   algorithm-complexity gate.
4. **Reviewer-facing visuals**: each main figure should have a role
   (`define`, `derive`, `compare`, `validate`, `explain`, `decide`) and nearby
   text that states the decision consequence. Use 3D surfaces or heatmaps only
   for real two-parameter interactions, threshold surfaces, or spatial/temporal
   mechanisms.

## Writing Moves

- Convert per-unit values into a representative batch-scale statement when the
  problem is operational: e.g. "per unit profit" plus "10,000-unit batch impact".
- Add one paragraph after each scenario or convergence figure: what changed,
  why it changed, and whether the recommended decision changes.
- When a simulation agrees with an exact solution, say it validates execution
  behavior, not optimality. When it disagrees, return to assumptions, random
  error, or objective mismatch.
- For official-showcase feel, prefer evidence density over page count: a short
  paper with weak experiments is not fixed by adding prose.

## Recommended Artifacts

- `planning/showcase_storyboard.md`: planned process, scenario, and supporting
  evidence.
- `results/tables/scenario_experiments.csv`: scenario matrix, batch cases, or
  stress tests.
- `results/tables/search_process_evidence.csv`: convergence, top-candidate gap,
  runtime trace, or state-space reduction.
- `checks/showcase_presentation_report.md` and `.json`: output of
  `scripts/scenario_showcase_gate.py`.

## Waivers

Record a visible waiver in the paper or check report when:

- the problem is purely deterministic and a simulation would be fake evidence;
- the official contest page limit blocks useful visual expansion;
- result data are not available yet and the paper is intentionally a draft;
- a figure would duplicate an existing stronger table or proof.
