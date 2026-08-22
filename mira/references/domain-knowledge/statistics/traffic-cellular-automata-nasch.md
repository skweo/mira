# Knowledge Card: statistics/traffic-cellular-automata-nasch

## Tags
- traffic cellular automata
- NaSch model
- Nagel-Schreckenberg
- multi-lane traffic
- lane changing
- keep-right rule
- random slowdown
- traffic density
- flow-density relation
- periodic boundary
- 元胞自动机交通流
- 交通流
- 换道
- 随机慢化
- 车流密度

## Problem Patterns
- A contest problem asks for congestion evolution, lane policy, road-capacity effect, traffic density-flow relation, or microscopic vehicle movement.
- The road can be discretized into cells and vehicles advance by integer cell speeds.
- Local rules such as acceleration, safe-distance braking, random slowdown, and lane changing drive the macroscopic pattern.
- The paper needs a simulation model for traffic states rather than only an aggregate regression or ODE.

## Applicability Conditions
- Cell length, time step, lane count, road length, speed levels, vehicle density, and boundary condition can be justified.
- Vehicle update rules are explicitly stated and use synchronous update or an equivalent conflict-free mechanism.
- Random slowdown and initial vehicle generation have fixed seeds or repeated-run evidence.
- Output metrics include flow, average speed, density, queue/congestion length, throughput, or lane-changing count.

## Contraindications
- Do not use NaSch only for animation; snapshots without traffic metrics are not contest-final evidence.
- Do not use periodic boundaries when the real task has inflow/outflow ramps, intersections, or bottlenecks unless the simplification is stated.
- Do not update vehicles in-place if the intended CA rule is synchronous.
- Do not compare lane policies from one random seed only.

## Algorithm Core
1. Define road grid: lanes, cells, boundary condition, occupied/empty state, speed state.
2. Initialize vehicles from density and max-speed distribution.
3. For each time step, compute gaps and lane-changing feasibility from the previous state.
4. Apply lane-changing rules with safety distance and conflict handling.
5. Apply NaSch movement: acceleration, braking by gap, random slowdown, position update.
6. Accumulate traffic metrics and validate by seed/grid sensitivity.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| gap calculation | Computes headway to the next vehicle | Must handle periodic or open boundary correctly |
| acceleration/braking | NaSch speed update | Speed cannot exceed `vmax` or safe gap |
| random slowdown | Models human/traffic noise | Requires seed and repeated runs |
| lane-change safety | Prevents unsafe target-lane moves | Check front and rear gaps before moving |
| synchronous update | Avoids update-order artifacts | Use old/new grid or staged move lists |
| metric accumulator | Converts simulation to evidence | Flow/speed/density curves, not only images |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Cell length/time step | Match vehicle length and speed units | Unit audit and sensitivity |
| Density `p` | Sweep across plausible range | Fundamental diagram or density-flow table |
| Random slowdown probability | Scenario or calibrated parameter | Multi-seed and sensitivity |
| Safety distance | Tie to speed/cell convention | Collision/no-overlap audit |
| Lane-change rule | State keep-right, incentive, and safety rules | Compare no-lane-change or single-lane baseline |
| Boundary condition | Periodic for ring-road/fundamental diagram; open for inflow/outflow | Boundary sensitivity |

## Validation Requirements
- CA contract table: cell size, time step, lane count, road length, states, speed levels, boundary, update order.
- Rule table for acceleration, braking, random slowdown, lane changing, and conflict resolution.
- Conservation audit: vehicle count is preserved for periodic boundary unless inflow/outflow is modeled.
- Collision audit: no two vehicles occupy the same cell after update.
- Metrics: average speed, flow, density, queue/congestion length, lane-changing count or throughput.
- Multi-seed and parameter sensitivity for random slowdown, density, max-speed mix, and lane-changing rule.
- Baseline: single-lane NaSch, no-lane-change scenario, deterministic no-random-slow case, or observed traffic data if available.

## Failure Signs
- The result is an animation or grid plot only.
- Vehicle count changes unexpectedly under periodic boundary.
- Cars pass through each other because updates are in-place.
- Lane changes check only the target cell but not rear safety.
- The paper reports one density and one seed as a general traffic conclusion.
- Flow/speed units are not converted from cells/step.

## Repair Moves
- Rewrite the update as staged old-state to new-state transitions.
- Add vehicle-count, collision, and speed-bound assertions.
- Add density sweep and multi-seed table.
- Add fundamental diagram or policy-comparison curve.
- If intersections or queues dominate, switch or hybridize with discrete-event/queueing simulation.

## Paper Usage
- Present as "microscopic traffic CA with NaSch movement and lane-change rules".
- Pair snapshots with quantitative traffic curves.
- State that results are scenario simulations under stated cell/time scaling, not direct field prediction unless calibrated.

## Source Materials
- `$PROJECT_ROOT\Math_Model\cellular_automata_traffic`
- Files inspected: `cellular.m`, `switch_lane.m`, `move_forward.m`, `new_cars.m`, `para_count.m`, `README_import.md`.
- Reference noted in source: Nagel and Schreckenberg cellular automaton freeway traffic model.

## Confidence
- medium: strong for contest-level traffic CA discipline; calibration and real-road boundary modeling remain task-specific.
