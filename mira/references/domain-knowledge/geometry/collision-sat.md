# Knowledge Card: geometry/collision-sat

## Tags
- collision detection
- separating axis theorem
- SAT
- oriented rectangle
- OBB
- segment width
- overlap
- clearance
- 碰撞检测
- 分离轴定理
- 有向矩形
- 最小间隙

## Problem Patterns
- A model must decide whether two non-axis-aligned rectangles, vehicles, bars, or rigid bodies overlap.
- Centerline paths are known, but body width or rectangular footprint determines feasibility.
- The problem asks for the first collision, minimum safe spacing, turning feasibility, or clearance.
- A chain or vehicle layout has many pairwise non-neighbor interactions that cannot be judged from centerline distance alone.

## Applicability Conditions
- Each body can be represented as an oriented rectangle or convex polygon at each tested time/design point.
- Rectangle vertices or center, length, width, and heading are available.
- Adjacent connected bodies can be excluded or treated with special rules if their intended contact is not a collision.
- The search has a candidate set of body pairs; all relevant non-neighbor pairs can be checked within runtime.

## Contraindications
- Do not use only center-to-center or centerline distance when rectangular width can cause overlap.
- Do not use axis-aligned bounding boxes for rotated bodies unless they are only a conservative prefilter.
- Do not rely on a plotted figure to prove no collision.
- Do not test only integer seconds or coarse pitch values when the reported boundary is continuous.

## Algorithm Core
- For two convex polygons A and B, SAT says they do not overlap if there exists an axis where their projections are disjoint.
- For oriented rectangles, candidate axes are the two edge normals/directions of rectangle A and the two of rectangle B.
- For each axis `u`, project all vertices: `[min(v·u), max(v·u)]`.
- If any interval pair is disjoint by more than tolerance, the rectangles are separated; otherwise they overlap.
- Minimum clearance can be approximated from projection gaps or computed with segment distance after a non-overlap decision.
- First-collision or limiting-pitch tasks need an outer continuous search over time/design variables, not only SAT at sampled points.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| oriented rectangle construction | Builds footprint from two handles or center/heading | Must use actual length and width |
| candidate-pair pruning | Reduces O(n^2) pair checks | Exclude adjacent intended links; use distance/AABB only as prefilter |
| SAT projection | Exact overlap test for convex rectangles under floating-point tolerance | Test all four unique axes |
| tolerance policy | Handles near-touch numerical noise | Report whether touching counts as collision |
| local boundary search | Finds first time or minimum pitch | Combine SAT Boolean with bisection/golden/ternary refinement |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Collision tolerance | Use a small geometric tolerance tied to coordinate precision | Sensitivity near the reported boundary |
| Candidate pairs | Exclude directly connected neighbors only with a written rule | Log pair count and closest checked pair |
| Time/design step | Coarse scan is only a candidate generator | Refine around first overlap or minimum clearance |
| Rectangle width/length | Use problem-given body dimensions, not handle spacing alone | Vertex audit for representative segments |

## Validation Requirements
- Vertex-construction audit for several representative bodies.
- Pair-screening rule: which pairs are checked, excluded, and why.
- SAT unit tests or toy cases: separated, touching, overlapping, rotated-overlapping.
- Boundary refinement for first collision, limiting design parameter, or safe clearance.
- Minimum-clearance or nearest-pair table near the reported critical result.

## Failure Signs
- Collision is judged from a plot or from centerline distance only.
- The code checks only neighboring bodies or only one hand-picked pair.
- Rotated rectangles are checked as axis-aligned boxes without justification.
- The reported boundary changes when the time or design grid is halved.
- The paper says "no collision" but provides no nearest-pair or clearance evidence.

## Repair Moves
- Convert every relevant body to oriented rectangle vertices and add SAT overlap tests.
- Add a candidate-pair log and nearest-pair table.
- Refine the boundary with bisection or local continuous search after coarse scan.
- If rectangles are insufficient, generalize SAT to convex polygons or use segment-distance clearance as an additional check.

## Paper Usage
- Explain SAT briefly through projection intervals; avoid long computational-geometry exposition.
- Include a schematic/table for rectangle construction and a result table with critical pair, time/design value, and clearance.
- State the tolerance and whether touching is treated as collision.

## Source Materials
- General computational geometry: separating axis theorem for convex polygons.

## Confidence
- high for oriented-rectangle overlap detection.
- medium for clearance magnitude unless paired with explicit distance computation and tolerance sensitivity.
