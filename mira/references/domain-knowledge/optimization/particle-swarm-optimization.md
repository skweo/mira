# Knowledge Card: optimization/particle-swarm-optimization

## Tags
- particle swarm optimization
- PSO
- swarm intelligence
- bounded continuous optimization
- black-box optimization
- hyperparameter tuning
- parameter calibration
- inertia weight
- cognitive coefficient
- social coefficient
- velocity clamp
- position repair
- personal best
- global best
- pbest
- gbest
- local best
- lbest
- neighborhood topology
- constriction factor
- online performance
- offline performance
- ParSwarm
- OptSwarm
- multi-seed
- 粒子群
- 粒子群算法
- 粒子群优化
- 惯性权重
- 学习因子
- 个体最优
- 全局最优
- 速度限制
- 速度边界
- 位置边界
- 参数寻优
- 局部版本
- 邻域拓扑
- 环形拓扑
- 轮形拓扑
- 约束因子
- 在线性能
- 离线性能

## Problem Patterns
- A subproblem is a bounded continuous or mixed continuous parameter-search task with a nonlinear, nonconvex, noisy, or derivative-free objective.
- Typical contest uses include model-parameter calibration, threshold/weight search, SVM or neural-network hyperparameters, PID/control parameters, continuous resource allocation, and black-box simulation tuning.
- The objective can be evaluated many times within contest runtime.
- A vector of decision variables has clear lower and upper bounds.
- The paper needs a heuristic search route with convergence and robustness evidence, not an exact optimality certificate.
- For logistics distribution, VRP, TSP, assignment, or other discrete routing tasks, also retrieve `routing/vrp-discrete-pso-logistics-routing`; this general PSO card is not enough by itself.

## Applicability Conditions
- The decision vector can be represented as a real-valued particle position or has a validated discrete encoding and repair rule.
- Every dimension has a bound, unit, and interpretation.
- The fitness/objective direction is explicit: minimization, maximization, or a documented transformation.
- Hard constraints can be checked or repaired after each position update.
- The information-exchange topology is named: global-best, local-neighborhood, ring, fully connected, or another explicit neighborhood rule.
- If MATLAB/demo code is reused, the implementation ledger names the particle matrix, personal/global best storage, objective direction, bound logic, and random source.
- At least one baseline exists, such as random search, grid search, local optimizer, exact small case, or a simpler feasible rule.
- Repeated runs with different seeds are affordable.

## Contraindications
- Do not use PSO when LP/MILP, convex optimization, DP, network flow, shortest path, closed-form estimation, or enumeration solves the actual instance clearly.
- Do not use continuous PSO directly for permutation, routing, assignment, integer, or combinatorial problems without an encoding, decoder, and feasibility repair.
- Do not rely on a penalty objective for hard constraints when deterministic repair or filtering is available.
- Do not use PSO for a very expensive simulation objective unless the evaluation budget, early-stop rule, and uncertainty are explicit.
- Do not claim global optimum without a bound, exact comparison, or exhaustive certificate.

## Algorithm Core
- Maintain for each particle `i`: position `x_i`, velocity `v_i`, personal best `p_i`, and global best `g`.
- Standard minimization skeleton:
  1. initialize particles within per-dimension bounds and initialize velocities with a scale tied to those bounds;
  2. evaluate objective `F(x_i)` and set personal/global bests;
  3. update velocity by `v_i <- w v_i + c1 r1 (p_i - x_i) + c2 r2 (g - x_i)`;
  4. clamp velocity per dimension;
  5. update position by `x_i <- x_i + v_i`;
  6. clip or repair position and audit hard constraints;
  7. reevaluate, update personal/global bests, and log the best-so-far value;
  8. stop by iteration budget, no-improvement patience, target tolerance, runtime, or convergence rule.
- For maximization, use a consistent reversed comparison or transform the objective and then report the original objective value.
- Log `first_best_iteration` or `first_target_hit_iteration` when the best value appears before the final iteration; fixed long runs need marginal-gain evidence.
- A MATLAB-style ledger may store `[position, velocity, fitness]` in `ParSwarm` and per-particle `pbest` plus final-row `gbest` in `OptSwarm`; if this structure is used, audit the `max`/`min` convention and recompute the original objective.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| global-best PSO | Fast convergence on continuous search | Can converge prematurely; use multi-seed and sensitivity |
| local-neighborhood PSO | Slower but sometimes more stable exploration | State neighbor rule; do not let code topology contradict the paper wording |
| ring/wheel neighborhood | Simple local-best topology for preserving exploration | State ring, random ring, wheel, or random wheel; topology is part of the method, not decoration |
| distance-based neighborhood | Neighbor set follows current spatial distance between particles | Expensive because it needs pairwise distances; justify runtime and memory |
| expanding neighborhood | Starts local and expands toward global-best PSO | Record expansion schedule and compare against fixed global/local topology when material |
| inertia-weight PSO | Balance exploration and exploitation | Record `w`; use constant or decreasing schedule with sensitivity |
| constriction-factor PSO | Damp position update and improve stability | Treat `0.729` as a candidate setting, not a proof of global convergence |
| global-local hybrid velocity | Combines fast global guidance and stable local exploration | Report mixing coefficient and ablation against plain global/local PSO |
| velocity clamp | Prevent particles from jumping outside meaningful ranges | Set per dimension as a fraction of variable range, not a copied scalar |
| position clipping | Enforce simple box bounds after movement | Good for bound constraints; not enough for coupled constraints |
| repair/decoder | Convert a particle into a feasible constrained solution | Required for integer, assignment, routing, or coupled-capacity tasks |
| mutation/restart | Escape stagnation or boundary trapping | Treat as hybrid PSO; compare against plain PSO |
| local polish | Improve the best particle by local search or exact small solve | Report as a separate intensification step |
| multi-seed run | Measure stochastic stability | Required for contest-final PSO claims |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Swarm size | Use a size appropriate to dimension and runtime; teaching examples with 20-30 particles are starting points only | Sensitivity table over at least 2-3 sizes when PSO is a main solver |
| Iteration limit | Choose from convergence/runtime tradeoff, not a copied `100` or `200` | Convergence trace and stopping reason |
| Topology/neighborhood | Global-best is faster but may stagnate; local-neighborhood may preserve exploration | Compare or justify when topology materially affects the result |
| Inertia `w` | Common practical range is roughly `0.4-0.9`; decreasing schedules may help stagnation | Compare at least two settings or justify from prior calibration |
| Inertia schedule | Linear or nonlinear decreasing schedules are tuning devices | Show convergence/quality difference; do not cite a schedule as proof |
| Learning factors `c1,c2` | Typical examples use values near `1.5-2.0`; balance self and social learning | Sensitivity or robustness check |
| Adaptive `c1,c2` | Can decrease cognitive weight and increase social weight over time | Compare with fixed `c1=c2=2` or record why not affordable |
| Constriction factor | Teaching code often uses `a=0.729` | Ablation or convergence comparison if used in a main result |
| Velocity cap | Scale by each variable's range, such as a bounded fraction of `upper-lower` | Bound-hit rate and convergence behavior |
| Variable scaling | Normalize heterogeneous units before PSO or use dimension-wise velocity caps | Unit table and post-run inverse transform |
| Objective transform | Avoid hidden reciprocal/negative fitness unless the original objective is recomputed | Final table reports both transformed fitness and original objective if transformed |
| Constraint penalties | Use only for soft constraints or documented relaxations | Penalty/component ratio and zero-violation audit for hard constraints |
| Fitness evaluation | Vectorize or cache expensive objective components when possible | Runtime table and identical-result check against scalar evaluation |
| Online/offline performance | Use as diagnostic trace of average/best historical fitness | Secondary evidence only; still require original-objective, multi-seed, baseline, and constraint audit |

## Validation Requirements
- Baseline comparison against random/grid search, local optimizer, exact small instance, or a structured model.
- Multi-seed stability with best, mean, worst or standard deviation of the original objective.
- Convergence evidence saved as numeric table and figure.
- Bound and hard-constraint audit for the final solution.
- Parameter sensitivity for swarm size, iteration count, inertia, learning factors, and velocity cap.
- Topology audit: global-best, local-best, ring/wheel, distance-neighborhood, or global-local hybrid must match code and paper wording.
- Ablation when using mutation, restart, constriction, local polish, or any hybrid PSO variant.
- Objective-transform audit for maximization/minimization conversions.
- Runtime-quality tradeoff: report whether larger swarm or more iterations materially improve the original objective.
- Position-bound audit, especially when code clips velocity but not position.
- For reused teaching code, audit random source (`rand`/`unifrnd`), objective direction, velocity-cap formula, and final result in original units.

## Failure Signs
- A single PSO run is treated as proof of optimality.
- The result is only a convergence plot without a final variable table, seed, or constraint audit.
- The final point repeatedly hits upper/lower bounds without explanation.
- Seed variance is large, or early stagnation appears, but the paper reports only the best seed.
- PSO is used for TSP/VRP/assignment/integer allocation with no encoding or repair.
- PSO is used for logistics routing but the method lacks a decoded vehicle/customer route table.
- Mutation or random reset changes coordinates outside the intended scale.
- A reciprocal or negative fitness transform causes confusion about whether the original problem is being minimized or maximized.
- A simpler baseline is equal or better, but PSO remains the selected method.
- The paper says global topology but the code uses local-neighborhood update, or vice versa.
- The paper reports online/offline performance curves but omits original-objective convergence, seed distribution, or baseline comparison.
- Velocity lower bound is coded as `-upper_bound` or another asymmetric-bound shortcut instead of a dimension-wise range cap.
- Demo parameters such as 20 particles, 4000 iterations, `c1=c2=2`, or constriction `0.729` appear without sensitivity or runtime justification.
- Position leaves the declared bound because only velocity is clipped.
- Increasing swarm size or iteration count adds large runtime with negligible objective gain, but the largest setting is still reported as if it were justified.

## Repair Moves
- Normalize variables and rederive per-dimension velocity caps.
- Add or tune inertia schedule, constriction factor, restart, or mutation only after documenting stagnation.
- If global-best stagnates, test local-best ring/wheel topology or a documented global-local hybrid before only increasing iterations.
- Replace asymmetric velocity clamps with `vmax_j = rho * (upper_j - lower_j)` and clamp to `[-vmax_j, vmax_j]`.
- Replace toolbox-specific random calls such as `unifrnd` with seeded `rand` or document the runtime environment.
- Add feasibility repair or switch to a discrete method such as GA, SA, DP, MILP, or local search for combinatorial structure.
- For logistics distribution or VRP tasks, apply the discrete PSO routing card: assignment/order encoding, decoded route audit, stagnation detection, and adaptive-mutation ablation.
- Increase seeds and report distribution; do not select one lucky run silently.
- Replace penalty-only handling of hard constraints with repair/filtering.
- If a baseline dominates, downgrade PSO to a comparison method and select the baseline or structured solver.
- For boundary-heavy results, recheck bounds, units, objective scaling, and constraint formulation before writing the result.
- Add no-improvement stopping, record first-best iteration, and compare runtime-quality tradeoffs.
- Vectorize or cache objective evaluation, then verify it matches scalar evaluation on a small sample.

## Paper Usage
- Describe PSO as a heuristic or metaheuristic best-found search unless an independent certificate exists.
- Include an algorithm table with encoding, bounds, velocity rule, `w/c1/c2`, swarm size, iterations, seed count, and stopping rule.
- Put convergence, sensitivity, multi-seed summary, and final constraint audit near the result section.
- Online/offline curves may appear as diagnostics, but the main result table must use the original objective and feasible decision variables.
- If mutation/restart/local polish is used, call the method hybrid/adaptive PSO and include an ablation table.
- Use wording such as "PSO best-found solution under tested settings" rather than "global optimum" when no proof exists.

## Source Materials
- Local sources:
- Source type: MATLAB teaching/code examples.
- Reliability: medium-low. The files teach PSO skeletons and common pitfalls; they do not prove performance on contest-scale constrained problems.

## Confidence
- medium for enforcing PSO implementation discipline, validation, and paper-claim boundaries.
- low for selecting PSO over structured solvers in a new contest task without baseline evidence.
