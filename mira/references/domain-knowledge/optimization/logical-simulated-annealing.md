# Knowledge Card: optimization/logical-simulated-annealing

## Tags
- simulated annealing
- logical simulated annealing
- CLP
- MILP
- LP
- scheduling
- hybrid heuristic
- constraint filtering
- inventory scheduling
- mixed integer programming
- 启发式优化
- 逻辑约束
- 调度优化

## Problem Patterns
- A scheduling, routing, assignment, or production-planning problem has many discrete decisions plus continuous balance/flow/capacity variables.
- Candidate moves easily violate logical constraints, resource limits, or material-balance constraints.
- Pure MILP is accurate but slows sharply as periods, tasks, tanks, machines, vehicles, or resources increase.
- Pure SA/GA/local search produces many infeasible candidates or relies on large penalty terms to hide infeasibility.
- The problem can be split into a discrete search layer and a fast feasibility/evaluation layer.

## Applicability Conditions
- A candidate discrete plan can be encoded compactly, such as event-time choices, assignment lists, connection decisions, or operation lists.
- Given a candidate discrete plan, remaining continuous or linear subproblem constraints can be checked by LP/MILP/CP/CLP, forward simulation, or deterministic feasibility audit.
- Logical constraints can reject invalid candidates before expensive objective evaluation.
- A baseline exact or MILP/LP model is available for small instances or reduced windows.

## Contraindications
- Do not use this card when all constraints are already easy enough for exact MILP/DP within contest time.
- Do not use SA as a substitute for writing constraints; the feasibility checker must still encode the real logical/resource rules.
- Do not accept candidates only through a penalty objective when infeasible states can be filtered deterministically.
- Do not claim global optimality from the hybrid heuristic unless a bound, solver gap, or exhaustive comparison supports it.

## Algorithm Core
- Use SA as the outer search engine for discrete decisions.
- For every candidate move, run a feasibility filter before final acceptance:
  1. generate a neighboring discrete plan;
  2. check logical constraints with CLP/CP-style rules or direct deterministic logic;
  3. solve/check the continuous or linear subproblem when needed;
  4. compute objective change only for candidates that pass or have a recorded relaxation;
  5. accept improvements directly and accept worse feasible candidates with a temperature probability.
- Treat temperature as search-radius control: high temperature explores a wider candidate region; lower temperature narrows the accepted worsening moves.
- Use the deterministic checker to shrink the search space early, not merely to audit final output.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| add operation | Insert a task/resource connection/event into a period | Use only if capacity and compatibility rules allow it |
| delete operation | Remove an existing operation from a period | Check downstream demand, balance, or service feasibility |
| replace operation | Swap one discrete connection/resource/task for another | Useful when the number of active operations is bounded |
| stage-wise move | Choose one decision stage first, then update the affected list | Good for problems whose stages affect later feasibility |
| CLP/CP filter | Reject candidates that violate logical rules | Run before objective evaluation whenever possible |
| LP/MILP subproblem | Complete or evaluate continuous variables under fixed discrete choices | Use as a repair/evaluation layer, not necessarily full global solve |
| small-instance exact benchmark | Compare hybrid SA with MILP/DP on reduced instances | Calibrates claim strength and parameter settings |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Initial temperature | Set high enough to avoid early entrapment but record acceptance behavior | Sensitivity over at least 2-3 starting temperatures when feasible |
| Cooling rate | Larger cooling factor increases runtime and may improve objective only mildly after a point | Report runtime-objective tradeoff instead of one magic value |
| Iterations per temperature | Scale with number of move types and active discrete variables | Save convergence/history table |
| Feasibility filter strictness | Prefer hard rejection for true logical/resource constraints | Count rejected candidates by reason |
| Penalty terms | Use only for soft constraints or relaxations | Report component ratios and compare with hard-filtered results |

## Validation Requirements
- Feasibility audit: list each logical/resource/balance constraint family and the number of candidate/final violations.
- Rejection diagnostics: report candidate counts, rejected-by-logic counts, rejected-by-linear-subproblem counts, and accepted moves.
- Baseline comparison: MILP/DP/LP on a small instance or reduced horizon, plus a simple greedy/local baseline when possible.
- Parameter sensitivity: initial temperature, cooling rate, and iteration count versus objective and runtime.
- Convergence/history: best objective by iteration or temperature.
- Claim boundary: state whether the final result is exact, bounded, or best-found.

## Failure Signs
- Most generated candidates are infeasible and the paper reports only the final objective.
- Feasibility is handled only by a huge penalty coefficient without hard constraint checks.
- SA parameters are chosen by "many experiments" with no sensitivity table.
- Hybrid heuristic is faster than MILP but no small-instance comparison is provided.
- The same local modification is repeatedly revisited, causing slow improvement or duplicate search paths.
- Continuous variables or balance constraints are recomputed only after the final route/schedule is chosen.

## Repair Moves
- Add a deterministic feasibility filter before accepting/evaluating SA moves.
- Split the model into discrete search variables and continuous/linear completion variables.
- Log rejection reasons and use them to redesign neighborhood operators.
- Add replace/delete/add operators instead of only random permutation swaps.
- Run a small-window MILP/DP benchmark to calibrate objective quality.
- If infeasible candidates dominate, narrow the move set to feasibility-preserving operators or stage-wise moves.
- If runtime grows too fast, reduce full MILP calls by caching subproblem results or using cheap logical screening before linear solves.

## Paper Usage
- Describe the method as a hybrid heuristic or mixed SA-constraint-programming route unless exact optimality is certified.
- Put the feasibility-filter flowchart near the algorithm description.
- Report runtime and objective together; speed improvement alone is not enough.
- Use a table comparing hybrid SA with exact/MILP on small cases and with heuristic baselines on larger cases.
- Explain which constraints are hard-filtered and which are soft-penalized.

## Source Materials
- Tian Wende, Sun Suli. "Optimization of Crude Inventory Scheduling in Refinery Based on Logical Simulated Annealing Method." Petroleum Refinery Engineering, 2005, 35(3): 52-56.
- Reliability: medium. It is a domain method paper with case comparison and parameter plots; use as operational guidance, not as universal proof.

## Confidence
- medium: strong for hybrid SA plus constraint filtering in scheduling problems; parameter values and operator sets must be calibrated to the current contest data.
