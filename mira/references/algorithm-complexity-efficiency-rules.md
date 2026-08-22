# Algorithm Complexity and Solver Efficiency Rules

Use this reference when a contest-final paper uses dynamic programming,
exhaustive enumeration, branch-and-bound, heuristic search, Monte Carlo,
MILP/MINLP, solver-backed optimization, grid search, or any algorithm whose
feasibility is not obvious from the problem size.

## Core Principle

An algorithm section is incomplete if it only says what was computed. It must
also show why the computation is feasible at the contest scale and how the
claimed optimality or best-found status follows from the solver route.

## Required Explanation

For every nontrivial algorithm, provide:

| item | required content |
|---|---|
| algorithm class | DP, enumeration, MILP, heuristic, Monte Carlo, solver-backed optimization, etc. |
| input scale | state count, strategy count, variable count, constraint count, sample count, or grid size |
| complexity | time complexity, space complexity, or explicit operation count |
| feasibility | runtime, memory, solver status, or bounded scale argument |
| efficiency design | pruning, memoization, decomposition, vectorization, batching, or a waiver explaining why it is unnecessary |
| claim strength | exact optimum, complete enumeration, bounded solution, or best-found heuristic result |

Preferred artifacts:

- `planning/algorithm_complexity.md`
- `planning/solver_efficiency.md`
- `results/tables/solver_efficiency.csv`
- `results/tables/algorithm_complexity.csv`

Suggested `solver_efficiency.csv` columns:

```csv
question,algorithm,scale_symbol,scale_value,time_complexity,space_complexity,runtime_seconds,solver_status,efficiency_note,claim_strength
```

## Enumeration Pattern

For exhaustive enumeration, state the search-space formula and the realized
scale. A phrase like "we enumerate all strategies" is not enough.

Minimum pattern:

1. Define the number of binary decisions or candidate states.
2. Derive the strategy count, e.g. `2^16=65536`.
3. State the per-strategy evaluation cost.
4. Explain why full enumeration is feasible.
5. Mention whether pruning, symmetry reduction, or layered DP is unnecessary,
   used, or rejected.

## Dynamic Programming Pattern

For DP, state:

- state variables and state count;
- action count or transition count per state;
- recurrence evaluation order;
- boundary and traceback cost;
- time and memory complexity;
- whether rolling arrays, memoization, pruning, or state compression are used.

## Heuristic Pattern

For simulated annealing, genetic algorithms, local search, particle swarm,
ant colony, or other heuristics, state:

- solution encoding and neighborhood/operator cost;
- iteration count, population size, temperature schedule, or stopping rule;
- per-run and total runtime;
- multi-seed stability or convergence evidence;
- that results are best-found/current experimental solutions unless a bound or
  exhaustive check proves exact optimality.

## Solver-Backed Pattern

For YALMIP, Gurobi, CPLEX, SciPy, MATLAB toolboxes, or other solvers, state:

- decision variable count and constraint count;
- solver name/version when material;
- status, gap/tolerance, runtime, and infeasibility handling;
- whether the problem scale is within solver capability;
- fallback route if the solver fails.

## Bad Patterns

- Saying "the enumeration is small" without a strategy count or runtime.
- Reporting 65536 strategies but not explaining per-strategy cost.
- Calling a heuristic result globally optimal without a proof, bound, or full enumeration.
- Naming a solver but omitting status, gap, or scale.
- Giving Big-O notation without connecting it to the actual contest instance.
