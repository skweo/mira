# Knowledge Card: routing/time-window-routing

## Tags
- routing
- TSPTW
- VRPTW
- time window
- no-wait
- simulated annealing
- local search
- clustering
- 二次惩罚
- 时间窗
- 路径优化

## Problem Patterns
- A route, vehicle, worker, order, customer, or task sequence must satisfy arrival/departure time windows.
- The objective mixes travel time or cost with lateness, waiting, service-time, overtime, or penalty terms.
- The first heuristic solution has huge penalty/travel ratios or many time-window violations.
- The task scale makes exact enumeration impractical, but the paper still needs feasibility audits and baseline comparison.

## Applicability Conditions
- Travel/service times and time-window bounds can be computed or estimated in consistent units.
- A candidate sequence can be checked by forward simulation from primitive data.
- Time-window violation has a clear sign: early, late, waiting, overtime, unserved, or infeasible transfer.
- For no-wait variants, waiting is forbidden or heavily penalized and must be handled during move evaluation.

## Contraindications
- Do not use a generic permutation heuristic when feasibility depends on resources or synchronization not represented in the encoding.
- Do not use a single fixed penalty coefficient without scale inspection when travel and violation terms use different units.
- Do not claim optimality from SA/GA/local search unless an exact bound, solver gap, or exhaustive check supports it.

## Algorithm Core
- Encode each route as an ordered list of visits, plus route/vehicle assignment when multiple routes exist.
- Evaluate a sequence by forward time propagation: arrival, service start, departure, waiting/violation, accumulated cost.
- Prefer feasible or near-feasible initialization: nearest insertion, earliest-deadline insertion, regret insertion, or clustered route construction.
- Use local search or SA on top of a feasible/near-feasible initializer. Moves must recompute time-window feasibility, not just distance.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| relocate / insertion | Move one customer/task to another position or route | Best first repair for late-window violations and route balance |
| swap | Exchange two visits | Useful for local ordering conflicts; reject or penalize infeasible forward schedule |
| 2-opt / 2-opt* | Reverse a segment or exchange route tails | Good for travel reduction; for strict time windows, delta must include propagated arrival changes |
| Or-opt | Move a short consecutive block | Keeps locally compatible service clusters together |
| destroy-repair | Remove high-violation visits, reinsert by least added violation/cost | Use when SA gets trapped in a high-penalty region |
| time-window-aware clustering | Cluster by spatial proximity and compatible time-window centers/widths | Use before search when a direct 50+ node permutation is unstable |
| lexicographic repair | Minimize hard violations first, then travel inside feasible or low-violation region | Use when penalty coefficient tuning dominates the objective |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Linear lateness penalty | Start with coefficient making one typical violation comparable to one medium travel leg | Report component ratio and coefficient sensitivity |
| Quadratic lateness penalty | Normalize time violation by a reference scale before squaring, such as average service interval or window width | Check that penalty/travel ratio is not orders of magnitude larger unless the task requires it |
| SA initial temperature | Choose so early acceptance rate for worsening moves is roughly 0.6-0.9 on sampled moves | Save initial sampling or convergence log |
| Cooling rate | Use a grid such as 0.90, 0.95, 0.98, 0.995 when runtime allows | Compare best objective, violations, and runtime |
| Iterations per temperature | Scale with node count and operator count; record stopping rule instead of a magic number | Convergence/history table |
| Multi-start seeds | Use at least 5 seeds for contest-final stochastic heuristic evidence when runtime permits | Report best/mean/std and best route audit |

## Validation Requirements
- Feasibility audit table: route continuity, visit uniqueness, capacity/resource if any, arrival/service/departure times, and time-window violation by visit.
- Baseline comparison: greedy insertion, earliest-deadline route, exact/DP on a small subset, relaxed MILP, or nearest-neighbor plus repair.
- Objective decomposition: travel cost/time, waiting, lateness, overtime, unserved penalty, and total objective.
- Multi-seed or multi-parameter stability for SA/GA/local search.
- Convergence/history plot or table for stochastic optimization.
- Sensitivity of penalty coefficients when violation penalties dominate the objective.

## Failure Signs
- Penalty/travel ratio is larger than about 10x without a task-driven explanation, or larger than 100x without a hard-constraint interpretation.
- Most objective improvement comes from penalty coefficient changes rather than route feasibility improvement.
- A route has duplicated/missing visits, negative times, impossible service order, or time-window violations hidden inside aggregate totals.
- Different seeds produce qualitatively different route structures with no explanation.
- The paper says "optimal route" while only a heuristic best-found solution was produced.

## Repair Moves
- First audit the time propagation and objective decomposition from primitive route data.
- If penalties dominate, normalize violation terms and run a coefficient grid or switch to lexicographic violation-first optimization.
- If SA/local search is stuck, add time-window-aware relocate, swap, Or-opt, and destroy-repair moves before only changing cooling parameters.
- If direct permutation search is unstable, decompose by spatial and time-window clusters, solve subroutes, then repair cross-cluster boundary visits.
- If the scale is small enough, run an exact or relaxed subset benchmark to calibrate the heuristic.

## Paper Usage
- Write "启发式搜索得到的当前最优/较优方案" unless optimality is certified.
- Put objective decomposition and feasibility audit near the route result table.
- Explain penalty coefficients by scale normalization or sensitivity, not by "经过多次实验取值" alone.
- When using clustering decomposition, explain why the decomposition preserves the task's spatial/time-window structure and include boundary-repair logic.

## Source Materials
- Seeded from Mira MathorCup A 2026 failure analysis and general routing heuristic practice.
- Reliability: operational heuristic, not a theorem. Promote or refine after validated project runs and user-fed algorithm sources.

## Confidence
- medium: the rules are standard contest-friendly routing heuristics, but exact parameter ranges must be calibrated to each dataset and objective definition.
