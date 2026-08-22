# Knowledge Card: optimization/genetic-algorithm

## Tags
- genetic algorithm
- GA
- chromosome
- gene
- population
- fitness
- selection
- roulette selection
- crossover
- one-point crossover
- mutation
- elitism
- binary encoding
- real-valued encoding
- permutation encoding
- repair operator
- best-so-far
- multi-seed
- ablation
- 遗传算法
- 染色体
- 染色体编码
- 种群
- 适应度
- 选择
- 轮盘赌
- 交叉
- 单点交叉
- 变异
- 精英保留
- 二进制编码
- 可行性修复

## Problem Patterns
- A subproblem is a large discrete, mixed discrete-continuous, nonlinear, nonconvex, or black-box optimization problem.
- Candidate solutions can be represented as chromosomes: binary strings, real vectors, permutations, assignments, schedules, routes, selected subsets, or mixed encodings.
- Exact LP/MILP, DP, network flow, shortest path, or enumeration is unavailable at the actual scale, but small-instance or simplified baselines can still be produced.
- The task needs a good feasible solution with robustness evidence, not a certified global optimum.
- Local optimum or premature convergence risk is visible, making diversity, mutation, restart, or hybrid local search relevant.

## Applicability Conditions
- The chromosome encoding and decoder match the actual decision structure.
- Crossover and mutation preserve feasibility or have an explicit repair operator.
- The fitness function is a traceable transformation of the original objective and constraints.
- Objective evaluation is affordable for many individuals and generations.
- A baseline, small exact case, or simpler heuristic can be run for comparison.
- Multiple random seeds are affordable enough for stability reporting.

## Contraindications
- Do not use GA when the current instance has a clean exact formulation that can be solved transparently within contest time.
- Do not use generic one-point crossover for permutation, route, schedule, or assignment encodings if it creates duplicates, missing tasks, or infeasible resource states.
- Do not hide hard constraints only inside a large penalty when feasible encoding or repair is available.
- Do not present improved GA, adaptive GA, layered GA, or SA-GA as better without an ablation or baseline.
- Do not use a function-optimization demo as evidence that GA fits a contest-specific constrained problem.

## Algorithm Core
- Contest-final GA must state:
  1. chromosome encoding and decoder;
  2. initialization method and feasibility policy;
  3. original objective, fitness transform, penalty terms, and objective direction;
  4. selection mechanism, such as roulette, tournament, rank, or elitist selection;
  5. crossover operator suited to the encoding;
  6. mutation operator and mutation probability;
  7. elitism or best-so-far memory;
  8. repair operator and constraint audit;
  9. stopping rule and seed count.
- Keep `current population`, `offspring`, and `best_so_far` conceptually separate. Selection and mutation may worsen a generation, so the best historical feasible chromosome must be preserved.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| binary encoding | Function or 0-1 selection problems | Needs bit-length, variable-range mapping, and resolution audit |
| real-valued encoding | Continuous parameter calibration | Use bound repair and dimension-wise mutation |
| permutation encoding | TSP/VRP/order/scheduling | Use order crossover, PMX, swap, insert, or inversion, not naive one-point crossover |
| roulette selection | Selects by fitness proportion | Requires nonnegative comparable fitness; unstable when fitness scales badly |
| tournament/rank selection | More robust selection pressure | Record tournament size or rank rule |
| one-point crossover | Binary strings and simple fixed-length encodings | Unsafe for permutations unless followed by repair |
| mutation | Maintains diversity and escape ability | Rate must be tuned; too high becomes random search |
| elitism / best-so-far | Prevents best solution loss | Required when operators can destroy good chromosomes |
| repair operator | Converts offspring to feasible solutions | Required for hard constraints, routes, schedules, and assignments |
| adaptive operators | Adjust crossover/mutation by stagnation or diversity | Needs trigger and ablation |
| hybrid SA/local search | Adds local improvement or worse-solution acceptance | Must not accept hard-constraint violations |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Population size | Choose by dimension/search space and runtime; small teaching values such as 20 are only smoke-test settings | Sensitivity over at least 2-3 sizes when GA is central |
| Generation limit | Combine max generation with no-improvement patience or target tolerance | Report first-best generation and stopping reason |
| Crossover probability | Must match encoding and feasibility repair; demo values are not universal | Sensitivity or baseline comparison |
| Mutation probability | Use to maintain diversity; too low can cause premature convergence, too high randomizes search | Diversity/stagnation metric and multi-seed distribution |
| Fitness transform | Preserve objective ordering and make direction explicit | Recompute original objective for final decoded solution |
| Penalty coefficients | Scale from objective components or constraint violation impact | Component ratio and zero hard-violation audit |
| Runtime | Fitness evaluation often dominates | Save runtime by generation and vectorize/cached objective where possible |

## Validation Requirements
- Baseline comparison: random/greedy/local search, ordinary GA, exact small case, or structured solver.
- Multi-seed statistics: best, mean, worst or standard deviation, plus feasibility rate.
- Convergence log: best objective, mean objective, feasible count, diversity proxy, and first-best generation.
- Constraint audit after decoding the final chromosome.
- Parameter sensitivity for population size, generations, crossover/mutation probabilities, and penalty scale.
- Ablation when using elitism, layered population, adaptive operators, SA-GA, local polish, restart, or repair-heavy variants.
- Objective/fitness ledger showing original objective, transformed fitness, penalty terms, and final recomputation.

## Failure Signs
- The paper names GA before defining variables, encoding, decoder, and objective.
- A route, assignment, or schedule GA uses one-point binary-style crossover and creates infeasible offspring.
- Only the single best run is reported.
- The best solution appears early but the algorithm runs many more generations without gain and no stopping audit.
- Penalty terms dominate or hard-constraint violations remain in the final decoded solution.
- Improved or hybrid GA has no ordinary-GA and simple-baseline comparison.
- Fitness is inverted, shifted, or penalized but the original objective is not recomputed in the result table.
- The final output is an adaptation curve rather than a decoded route/allocation/schedule/parameter table.

## Repair Moves
- Redesign encoding to match the solution structure: binary for 0-1 decisions, real-valued for continuous parameters, permutation for routes/order, mixed encoding for mixed decisions.
- Replace unsafe crossover with encoding-aware operators and add repair.
- Add elitism or explicit best-so-far memory.
- Add no-improvement stopping and report first-best generation.
- Add multi-seed runs, baseline comparison, and ablation for added operators.
- Replace penalty-only hard constraints with feasible initialization, repair, or deterministic feasibility checks.
- If a structured solver or simpler heuristic dominates, downgrade GA to a comparison method and select the stronger approach.

## Paper Usage
- Present GA as a heuristic best-found method unless a bound or exact comparison certifies optimality.
- Include a compact algorithm table: encoding, fitness, selection, crossover, mutation, repair, elitism, seed count, stopping rule.
- Put decoded final solution and constraint audit near the main result.
- Put claim-critical convergence, multi-seed statistics, and parameter sensitivity near the result section; keep exhaustive runs as separate result files.
- Use "best-found feasible solution under the tested settings" rather than "global optimum" without proof.

## Source Materials
- Source type: MATLAB teaching note plus prior GA method papers.
- Reliability: medium for programming discipline and validation obligations; low as evidence that GA is best for any specific contest task.

## Confidence
- medium: strong for enforcing GA encoding/operator/validation discipline.
- low for selecting GA over exact or structured methods without project-specific baseline evidence.
