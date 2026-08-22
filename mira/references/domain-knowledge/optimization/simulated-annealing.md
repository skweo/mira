# Knowledge Card: optimization/simulated-annealing

## Tags
- simulated annealing
- SA
- Metropolis
- stochastic local search
- combinatorial optimization
- neighborhood search
- cooling schedule
- reheating
- multi-start
- TSP
- routing
- scheduling
- assignment
- heuristic optimization
- 模拟退火
- 组合优化
- 邻域搜索
- 温度控制
- 路线排列
- 距离矩阵
- 两交换
- 三交换
- 候选解
- 当前解
- 最优解

## Problem Patterns
- A contest subproblem is a discrete or mixed discrete-continuous optimization problem with a large search space and many local optima.
- Exact DP, MILP, or enumeration is available only for small instances, but the full instance is too large for exact search within contest time.
- A candidate solution can be encoded as a route, order, assignment vector, selected subset, schedule, or parameter vector.
- Chinese routing/permutation signals include 路线, 路径, 排列, 城市顺序, 距离矩阵, 两交换, 三交换, 当前解, 候选解, and 最优解.
- Good solutions require occasional acceptance of worse moves to escape local optima, plateaus, or greedy traps.
- The paper needs a credible heuristic with visible convergence, sensitivity, and baseline evidence.

## Applicability Conditions
- The solution encoding maps cleanly to feasible or repairable problem solutions.
- At least one meaningful neighborhood operator can be defined and implemented.
- The objective value can be evaluated repeatedly and cheaply enough for many iterations.
- Hard constraints are checked directly or repaired before objective comparison; penalties are reserved for soft violations or documented relaxations.
- A small-instance exact certificate, greedy baseline, or previously validated heuristic baseline can be produced.

## Contraindications
- Do not use SA when a full exact solver, DP, or graph shortest-path formulation can solve the actual instance quickly and transparently.
- Do not use SA as the main method when the solution encoding cannot preserve or repair feasibility.
- Do not claim global optimality unless exhaustive search, an exact bound, or solver certificate supports it.
- Do not hide scale errors behind a penalty objective; component ratios must be reported when penalties dominate.
- Do not use a single run, single seed, and single parameter setting for contest-final claims.

## Algorithm Core
- Treat SA as a stochastic local-search framework controlled by temperature:
  1. generate an initial solution `x0`, set `x_best = x0`, and evaluate `E(x0)`;
  2. set initial temperature `T0`, minimum temperature `T_min`, inner-loop length `k`, and cooling rule;
  3. at each temperature, sample neighbors by one or more operators;
  4. compute `Delta E = E(x_new) - E(x_current)` for minimization;
  5. accept all improving moves and accept worse moves with Metropolis probability `exp(-Delta E / T)`;
  6. always preserve `best_so_far` separately from the probabilistic current state;
  7. stop only after a temperature threshold, iteration limit, no-improvement rule, or stability test is met.
- The paper must distinguish `current solution`, `best solution`, and `candidate solution`; mixing these states causes incorrect SA descriptions and code.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| swap | Exchange two positions, assignments, or selected elements | Good first operator for permutations and assignments; check capacity/time constraints after swap |
| insert / relocate | Remove one item and insert it elsewhere | Useful for routing and scheduling order adjustment |
| 2-opt / reverse segment | Reverse a route or sequence segment | Strong baseline operator for TSP-like routes |
| three-breakpoint segment reorder | Select three route positions and move or reorder the middle segment | Useful as a larger TSP/routing neighborhood; forbid adjacent breakpoints when the move would be empty |
| block move | Move a contiguous block of tasks/customers/items | Helps when single-item moves improve too slowly |
| add/delete/replace | Change selected resources, tasks, or links | Use when solution size is variable |
| repair-after-move | Convert an infeasible candidate back to feasible form | Record repair rules; do not silently change the objective definition |
| reheating | Temporarily raise temperature after stagnation | Use only when convergence trace shows premature freezing |
| best-so-far memory | Preserve the best solution ever seen | Required because Metropolis acceptance can move away from the best state |
| post-SA local polish | Run greedy or local search from `best_so_far` | Useful final intensification; report it as a separate polish step |
| multi-start / multi-seed | Repeat SA from several initial states or random seeds | Required for stochastic robustness claims |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Objective scale | Normalize or report objective components before setting temperature | Component table; penalty/travel or penalty/main-objective ratio |
| Initial temperature `T0` | Calibrate from sampled objective differences; choose `T0` to give a high initial worsening-move acceptance rate rather than guessing | Sample 50-200 random neighboring deltas and report initial acceptance estimate |
| Acceptance probability | Use `p = exp(-Delta E / T)` for worse moves in minimization | Log accepted worse-move rate by temperature band |
| Cooling schedule | Use a monotone rule such as geometric cooling for contest code; slower schedules trade runtime for quality | Sensitivity over at least 2-3 cooling rates |
| Inner-loop length `k` | Scale with problem size and number of operators; too small means each temperature is not sampled | Convergence table and runtime table |
| Minimum temperature / stop | Combine `T_min` with max iterations and no-improvement patience | Record stopping reason, not only final objective |
| Random seed count | Run multiple seeds for stochastic methods in contest-final mode | Report best/mean/std or at least best/worst/mean |
| Penalty coefficients | Calibrate using objective-component scale; do not let penalties swamp the real objective without explanation | Trigger repair if penalty ratio exceeds card/auditor threshold |
| Distance/cost matrix | Precompute pairwise costs for TSP/VRP-style repeated evaluation | Include matrix construction and unit check in code outputs |

## Implementation Notes
- For permutation routing/TSP code, use a route vector as the state and precompute a distance or cost matrix before the SA loop.
- Keep `candidate`, `current`, and `best_so_far` as separate states. Revert only the candidate when a worse move is rejected.
- Log at least: seed, temperature, best objective, current objective, accepted worse moves, rejected moves, and stopping reason.
- Do not copy demo constants such as `cooling = 0.99`, `T0 = 97`, `T_min = 3`, or `Markov_length = 10000` as universal defaults; record how they were calibrated or tested.
- When a code example contains an empty constraint-check placeholder, treat it as a warning: constrained contest problems need a real feasibility filter or repair layer.

## Validation Requirements
- Baseline comparison: compare against greedy, local search without annealing, and exact/DP/MILP result on a small instance when feasible.
- Multi-seed stability: run several random seeds and report best, mean, and variation.
- Convergence/history: save best objective by iteration or temperature and include a curve or table.
- Parameter sensitivity: vary initial temperature, cooling rate, and inner-loop length; show objective-runtime tradeoff.
- Feasibility audit: report final hard-constraint violations as zero or list repaired/relaxed constraints explicitly.
- Component audit: decompose the objective into travel/cost/penalty/service terms so abnormal domination is visible.
- Stopping audit: state whether termination came from temperature threshold, iteration cap, no-improvement patience, or stability.

## Failure Signs
- The first feasible result is accepted as final without baseline, multi-seed, or convergence evidence.
- Best objective changes little after early iterations and worse-move acceptance quickly drops to zero.
- Results vary widely across seeds but the paper reports only the single best run.
- Penalty or one objective component dominates by orders of magnitude.
- Candidate moves are mostly infeasible and no rejection/repair statistics are recorded.
- Parameters are described as "chosen by experience" with no sampled deltas, acceptance behavior, or sensitivity table.
- SA is used where an exact graph, DP, or MILP solution was available at the same scale.
- The paper uses "global optimum" wording for a heuristic best-found solution.

## Repair Moves
- Recalibrate `T0` from sampled positive `Delta E` values and target initial acceptance rather than using a guessed temperature.
- Add or replace neighborhood operators: for routing use 2-opt, relocate, swap, and block moves; for assignment use swap and replace; for scheduling use insert and block moves.
- Add hard feasibility filters or repair functions before objective evaluation.
- Add reheating only after documented stagnation, and compare with plain SA.
- Add multi-start runs and report distribution if seed instability appears.
- Add post-SA local polish from `best_so_far` when convergence stalls near a good solution.
- If a penalty explosion appears, return to the model: rescale objective terms, hard-filter true constraints, or change decomposition before re-running SA.
- If SA underperforms a simple baseline, downgrade it to a comparison method or switch to exact/decomposition methods.

## Paper Usage
- Present SA as a heuristic or metaheuristic unless an external certificate is provided.
- Include an algorithm table with encoding, operators, temperature rule, acceptance rule, stopping rule, and seed count.
- Put claim-critical convergence and sensitivity near the result section; keep exhaustive runs as separate result files.
- Use wording such as "best-found solution under the tested settings" when no bound is available.
- When combining SA with exact solvers, clearly name which layer is heuristic and which layer is exact/feasibility checking.

## Source Materials
- Source type: algorithm course/teaching material.
- Useful sections: Metropolis acceptance rule, SA flow, state/neighborhood generation, cooling schedule, initial temperature calibration, inner/outer stopping rules, improvement methods, TSP example.
- Useful code patterns: permutation encoding, vectorized distance matrix, two-exchange and three-segment neighborhoods, separate candidate/current/best states.
- Reliability: medium. The source is stable for SA fundamentals; contest parameters and operator choices must still be calibrated on the current data.

## Confidence
- medium: strong for enforcing SA implementation discipline, validation, and paper-claim boundaries; not sufficient by itself to select domain-specific neighborhoods for every routing/scheduling variant.
