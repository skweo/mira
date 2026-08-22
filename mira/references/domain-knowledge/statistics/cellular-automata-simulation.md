# Knowledge Card: statistics/cellular-automata-simulation

## Tags
- cellular automata
- CA
- grid simulation
- lattice grid
- discrete spatial simulation
- local rule
- synchronous update
- neighborhood
- Moore neighborhood
- Von Neumann neighborhood
- Margolus neighborhood
- boundary condition
- periodic boundary
- stochastic cellular automata
- Game of Life
- forest fire
- percolation
- diffusion-limited aggregation
- lattice gas
- sand pile
- 元胞自动机
- 细胞自动机
- 点格自动机
- 网格仿真
- 格点
- 离散空间
- 局部规则
- 同步更新
- 邻域
- Moore邻域
- Von Neumann邻域
- Margolus邻域
- 边界条件
- 周期边界
- 生命游戏
- 森林火灾
- 渗流
- 扩散限制聚集
- 格子气
- 砂堆

## Problem Patterns
- A contest problem involves spatial spread, local interaction, congestion propagation, fire/epidemic/rumor spread, land-use transition, traffic cells, crowd movement, diffusion-like growth, particle motion, or pattern formation on a grid.
- The mechanism depends on neighboring cells more than on global equations.
- State is naturally discrete, such as empty/occupied/burning/tree, susceptible/infected/recovered, road cell speed state, alive/dead, or particle/wall/empty.
- The output is a spatiotemporal pattern, front speed, affected area, density evolution, cluster shape, stabilization time, or scenario comparison.
- A simple ODE or aggregate model cannot capture local barriers, boundaries, heterogeneity, or spatial feedback.

## Applicability Conditions
- A defensible grid resolution, coordinate mapping, and cell meaning can be defined.
- The state set is finite and each state has domain meaning.
- Neighborhood, boundary condition, update schedule, and local transition rule can be stated explicitly.
- Parameters such as spread probability, ignition rate, growth probability, or threshold can be estimated, calibrated, or stress-tested.
- The paper can provide quantitative metrics and validation beyond visual snapshots.

## Contraindications
- Do not use CA only to create attractive figures when an aggregate equation, graph model, or regression answers the task.
- Do not use arbitrary grid size, state rules, or probabilities without sensitivity.
- Do not claim physical realism from visual resemblance alone.
- Do not use deterministic CA when the mechanism is stochastic unless randomness is intentionally excluded and justified.
- Do not use stochastic CA for final recommendations without repeated seeds and uncertainty.

## Algorithm Core
- CA contract route:
  1. define grid/domain, cell size, time step, and boundary condition;
  2. define state set and state variables with units or meanings;
  3. define neighborhood such as Von Neumann, Moore, Margolus, or a task-specific set;
  4. define local update rule or rule table;
  5. initialize grid and parameters;
  6. update synchronously using the previous grid to produce the next grid;
  7. compute pattern metrics and validate with baselines/sensitivity.
- Deterministic rule example:
  - `next_cell = f(current_cell, neighbor_count_or_pattern)`.
- Stochastic rule example:
  - `next_cell = f(current_cell, neighbors, random_draw, parameters)`, with seed, probability parameters, and repeated runs.
- Margolus/block route:
  - alternate 2x2 block partitions by timestep parity;
  - use when particle-like movement, collisions, or conservation are central.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| cell-state matrix | Stores grid states | Keep state codes and meanings in a table |
| double-buffer update | Enforces synchronous update | Use `old_grid` and `new_grid`; avoid in-place leakage |
| Von Neumann neighborhood | Four orthogonal neighbors | Good for cardinal contact/flow or road-grid interactions |
| Moore neighborhood | Eight surrounding neighbors | Good for diagonal spread/contact |
| Margolus neighborhood | Alternating 2x2 block neighborhood | Useful for lattice gas, sand, particle motion, conservation |
| periodic boundary | Wraps edges | Useful for artificial infinite/torus domains; must be justified |
| fixed/reflecting boundary | Models walls, borders, or obstacles | Needed when domain edges are physical |
| stochastic transition | Adds probabilistic ignition/growth/spread/sticking | Requires seed, parameter source, sensitivity |
| pattern metric extraction | Converts snapshots into evidence | Use affected area, density, cluster count, front speed, stabilization time |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Grid size and cell size | Match data resolution or mechanism scale | Grid-refinement or aggregation sensitivity |
| Time step | Match event/process timescale | Sensitivity and stability of metrics |
| State coding | Use finite states with clear meanings | State-count and impossible-state audit |
| Neighborhood | Match physical/social contact path | Compare 4-neighbor vs 8-neighbor when ambiguous |
| Boundary condition | Reflects domain edge behavior | Boundary sensitivity or domain-extension check |
| Random seed | Fix for reproducibility, vary for robustness | Multi-seed spread |
| Probability parameters | Estimate, calibrate, or use scenario bands | Parameter grid and threshold/sensitivity table |
| Initial condition | Use observed map, data-derived density, or justified scenario | Initial-density/pattern sensitivity |
| Stopping rule | Fixed horizon, steady state, extinction, threshold area, or convergence | Report reason and horizon sensitivity |

## Validation Requirements
- CA contract table: cell meaning, state set, grid size/resolution, neighborhood, boundary, rule, parameters, initial condition, timestep, and stopping rule.
- Rule-table audit: local rules are complete, mutually consistent, and map all states to legal states.
- Synchronization audit: verify the implementation uses the previous grid for all simultaneous updates.
- Small-pattern test: hand-update or known-pattern test for at least one toy grid.
- Metric extraction: pair snapshots with quantitative curves/tables such as density, area, spread speed, cluster count, extinction time, or conserved quantity.
- Sensitivity: grid size, boundary condition, initial density/pattern, neighborhood choice, and key probabilities.
- Multi-seed: required for stochastic CA; report mean/spread or confidence interval.
- Baseline: compare with ODE/difference equation, graph diffusion, percolation threshold, simple random spread, or observed pattern when available.

## Failure Signs
- The model section names CA but never states state set, neighborhood, boundary condition, or update rule.
- The code updates cells in place and changes the intended synchronous rule.
- The result is only a sequence of images with no metrics.
- Periodic boundary is used only because indexing is convenient.
- A stochastic CA uses one seed and one parameter setting to make a final recommendation.
- The selected neighborhood changes conclusions and no sensitivity is reported.
- The rule can generate impossible states, lose/gain particles unexpectedly, or violate conservation where conservation is claimed.

## Repair Moves
- Add a CA contract table and rule table before results.
- Rewrite implementation with old/new grids and add a synchronization test.
- Add a hand-computed 5x5 or 10x10 toy-grid trace.
- Extract quantitative metrics from every simulation run and plot metric curves.
- Run grid-size, boundary, neighborhood, initial-condition, and probability sensitivity.
- For stochastic CA, run repeated seeds and report spread; use common initial maps when comparing policies.
- If CA adds little explanatory value, replace it with an aggregate dynamic model, graph spread model, queue/discrete-event simulation, or spatial interpolation model.

## Paper Usage
- Present CA as "discrete spatial state + local rule + synchronous evolution + validation", not as a generic simulation label.
- Use snapshots only when they support a named spatial claim; pair them with numeric metrics.
- Include a compact rule table and a process diagram showing grid -> neighbor summary -> state update -> metric extraction.
- Phrase results as scenario/model-based evolution under the stated local rules.
- Avoid claiming real-world prediction unless rules and parameters are calibrated or validated against observed data.

## Source Materials
- Useful sections: CA definition, Wolfram behavior classes, elementary CA, Game of Life, Moore/Von Neumann/Margolus neighborhoods, forest-fire stochastic CA, lattice-gas conservation example, DLA and sand-pile examples, MATLAB matrix update pattern.
- Reliability: medium for CA modeling discipline and implementation obligations; demo code is not benchmark evidence.

## Confidence
- medium: useful for contest-level CA model construction, implementation audits, and validation requirements; domain-specific CA rules still require calibration or external evidence.

