# Mira 0.5.9

Mira 0.5.9 adds algorithm-complexity and solver-efficiency discipline on top
of Mira 0.5.8.

## Added Capability

**Algorithm Complexity and Solver Efficiency**

Mira should no longer treat algorithm descriptions as complete when they only
name DP, enumeration, heuristic search, or a solver. For contest-final papers,
nontrivial algorithms must explain their instance scale, complexity, runtime or
solver evidence, and why the chosen route is feasible.

Preferred artifacts:

- `planning/algorithm_complexity.md`
- `planning/solver_efficiency.md`
- `results/tables/solver_efficiency.csv`
- `results/tables/algorithm_complexity.csv`

## New Gate Behavior

The final-paper chain now includes `scripts/solver_efficiency_gate.py`. This
gate checks whether DP, exhaustive enumeration, heuristics, Monte Carlo,
grid-search, and solver-backed optimization claims have:

- time/space complexity or an explicit operation count;
- realized state, strategy, variable, constraint, sample, or grid scale;
- runtime, memory, solver-status, gap, or feasibility evidence;
- pruning, decomposition, layered DP, memoization, or a waiver when the search
  space would otherwise look arbitrary;
- correct claim strength, especially for heuristic and sampled methods.

For examples such as `2^16=65536` enumeration, Mira should state the strategy
count, per-strategy evaluation cost, observed runtime, and why full enumeration
is acceptable or why a pruning/layered-DP alternative is unnecessary.
