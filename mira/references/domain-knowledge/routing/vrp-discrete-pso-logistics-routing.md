# Knowledge Card: routing/vrp-discrete-pso-logistics-routing

## Tags
- VRP
- vehicle routing
- logistics distribution
- distribution routing
- discrete PSO
- particle swarm optimization
- adaptive mutation PSO
- premature convergence
- fitness variance
- particle encoding
- vehicle assignment
- route order
- multi-depot routing
- multi-vehicle routing
- 物流配送
- 配送路径
- 车辆路径
- 离散粒子群
- 自适应变异
- 粒子编码

## Problem Patterns
- A logistics, delivery, distribution, VRP, or multi-vehicle route problem is being solved with PSO.
- Each customer must be assigned to a vehicle/route and ordered inside that vehicle's route.
- The model has capacity, depot, vehicle-count, path-length, service-time, or other route-feasibility constraints.
- Plain continuous PSO has been proposed for a discrete routing/permutation problem.
- A stochastic routing heuristic reports one best route but lacks repeat-run evidence.

## Applicability Conditions
- Every customer can be decoded from a particle into exactly one route and one service position.
- A complete route table can be reconstructed from the particle, including depot/vehicle assignment and customer order.
- Route feasibility can be audited after decoding: visit uniqueness, missing/duplicate customers, depot continuity, capacity, time/service constraints, and objective recomputation.
- The instance is too large or too nonlinear for a clean exact method, or PSO is used as a comparison/hybrid solver with baseline evidence.
- Repeated runs and parameter sensitivity are affordable.

## Contraindications
- Do not use this card when a small VRP/TSP instance can be solved exactly or bounded well by DP, MILP, branch-and-bound, or enumeration.
- Do not use raw real-valued PSO positions directly as routes without an explicit decoder and repair rule.
- Do not treat adaptive mutation PSO as automatically superior to SA, GA, MILP, insertion heuristics, or local search.
- Do not report "global optimum" from PSO unless an independent certificate, exact small-case comparison, or valid lower bound supports it.

## Algorithm Core
- Represent each particle as a route-decoding object, not only a real vector. A useful pattern for N customers is a 2N component encoding:
  - `Xv`: vehicle or route assignment for each customer;
  - `Xr`: within-route ordering key or rank for each customer.
- Decode by grouping customers by `Xv`, then sorting customers in each vehicle group by `Xr`; repair or reject duplicate, missing, overload, depot, or time-window violations.
- Maintain `pbest` and `gbest`, but judge route quality by the original route objective after decoding.
- Split particles by fitness quality at each iteration. Better particles receive smaller inertia for local exploitation; poorer particles receive larger inertia for exploration; middle particles keep the base setting.
- Monitor population diversity, such as fitness variance. If variance is too small and the best value stalls, treat the swarm as prematurely converged and trigger mutation/restart.
- Mutation should perturb the decoded route or the assignment/order components while preserving or repairing feasibility.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| `Xv` assignment decoder | Map customers to vehicle/depot/route | Must ensure each customer appears once and vehicle capacity/resource limits hold |
| `Xr` order decoder | Sort customers within each route | Must recompute route length/time after sorting |
| fitness grouping | Separate high, middle, and low quality particles | Grouping threshold must be recorded; do not silently tune after seeing results |
| adaptive inertia | Let good particles exploit locally and poor particles explore globally | Validate with a plain PSO ablation |
| fitness-variance stagnation check | Detect over-clustering or early convergence | Save diversity or variance trace, not only final best value |
| adaptive mutation | Escape local best when stagnation appears | Mutated route must be decoded and audited for feasibility |
| partial restart | Restore diversity when mutation is insufficient | Preserve best-so-far and report restart count |
| route-local polish | Improve decoded route by swap, relocate, 2-opt, or Or-opt | Report as hybrid PSO plus local search, with ablation |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Particle count | Compare several sizes, such as small/medium/large budgets, rather than copying one value | Table with best, mean, success count, average iteration, and runtime |
| Iteration limit | Use convergence or no-improvement stopping, not only a fixed generation count | Save first-best iteration and convergence trace |
| Inertia | Use adaptive or decreasing inertia only with a reason: exploration early or poor-particle exploration, exploitation for good particles | Ablation against constant-inertia PSO |
| `omega_min`, grouping constants | Treat source values such as `omega_min=0.4`, `k1=1.5`, `k2=0.3` as starting points | Sensitivity or waiver |
| Mutation probability | Keep mutation small and tie it to diversity/stagnation; source examples use low probabilities such as roughly 0.05-0.10 | Report mutation count and compare with no-mutation PSO |
| Fitness variance threshold | Scale it to the current objective and population; do not reuse an absolute threshold blindly | Plot or table of variance/stagnation trigger |
| Objective components | Report route distance/cost, violation penalty, vehicle count, and any soft penalties separately | Component ratio and hard-constraint audit |

## Validation Requirements
- Baseline comparison against at least one of: plain PSO, greedy insertion, nearest-neighbor plus repair, SA/GA/local search, exact small instance, or MILP relaxation.
- Repeated-run statistics over multiple seeds: best, mean, worst/std, success count or feasible-rate, first-best/average iteration, and runtime.
- Particle-count or iteration-budget sensitivity when PSO is a main solver.
- Ablation for adaptive inertia, mutation, restart, local polish, or any hybrid mechanism.
- Decoded final route table with vehicle/depot assignment, customer order, route distance/time, capacity/resource use, and constraint violations.
- Route diagram or route map generated from the decoded result.
- Convergence and diversity/stagnation evidence saved as numeric data and a figure.

## Failure Signs
- PSO is used for VRP/TSP/routing but the paper does not state the route encoding and decoder.
- The final output is a route picture without a decoded route table and constraint audit.
- Only one random run is reported, or only the best seed is shown.
- Mutation/adaptive inertia is claimed to improve results without a plain-PSO ablation.
- Population diversity collapses early, but the run continues and the paper calls the result optimal.
- Route feasibility is repaired after the fact but the objective is not recomputed from the repaired route.
- Increasing particle count or iteration count changes the result materially, but no sensitivity is reported.

## Repair Moves
- Add a route decoder with visit-uniqueness, vehicle-capacity, depot-continuity, and objective recomputation checks.
- Replace raw continuous coordinates with assignment/order encoding or switch to GA/SA/local-search operators better suited to permutations.
- Add diversity trace, no-improvement patience, and adaptive mutation/restart when stagnation is detected.
- Add route-local operators such as swap, relocate, 2-opt, 2-opt*, or Or-opt to improve decoded routes.
- If a baseline dominates, downgrade PSO to a comparison method and select the stronger method.
- If results are unstable, increase seed count and report distribution before writing a strong claim.

## Paper Usage
- Write "adaptive/discrete PSO best-found routing scheme" unless an exact certificate exists.
- Include a method table with particle encoding, decoder, repair rule, inertia/mutation settings, particle count, iteration limit, seed count, and stopping rule.
- Place route map, route table, convergence/diversity figure, and baseline/sensitivity table near the result claim.
- Explain adaptive mutation as a repair against premature convergence, not as a guaranteed improvement.

## Source Materials
- Reading method: CAJ/HN converted to image-based PDF; key algorithm and experiment pages were visually inspected.
- Reliability: medium. Useful for operational PSO routing design and validation discipline; not proof that PSO is the best solver for every logistics routing contest problem.

## Confidence
- medium for encoding, stagnation diagnosis, adaptive-mutation obligations, and validation requirements.
- low for selecting PSO as the main solver without current-instance baselines.
