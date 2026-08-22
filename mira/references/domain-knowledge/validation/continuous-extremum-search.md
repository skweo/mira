# Knowledge Card: validation/continuous-extremum-search

## Tags
- continuous extremum
- peak search
- maximum
- minimum
- grid search
- coarse scan
- discrete scan
- integer second scan
- local refinement
- ternary search
- golden section
- Brent method
- threshold crossing
- 峰值
- 极值
- 离散扫描
- 整数秒
- 连续加密
- 局部加密

## Problem Patterns
- A result asks for the maximum/minimum of a continuous-time or continuous-parameter quantity.
- The code first scans integer seconds, fixed grid points, threshold values, or design parameters.
- The final answer is sensitive to the exact peak time, first crossing, limiting parameter, minimum clearance, or maximum response.
- A sampled result is used to set a scale factor, safety bound, feasibility boundary, or final recommendation.

## Applicability Conditions
- The objective or constraint can be evaluated at arbitrary real values, or interpolation is physically justified.
- A coarse grid has already found one or more candidate intervals containing a local extremum or boundary.
- Function evaluations are deterministic enough that local refinement is meaningful.
- The quantity is locally unimodal, bracketable, or can be refined by subdivision/root finding.

## Contraindications
- Do not treat the best sampled grid point as the final continuous optimum unless the variable is truly discrete.
- Do not use ternary/golden search blindly across a multimodal interval; bracket candidate neighborhoods from the scan.
- Do not refine a noisy simulation peak without replication or smoothing.
- Do not report excessive decimal places when the refinement tolerance, interpolation model, or solver tolerance is weaker.

## Algorithm Core
1. Run a coarse scan only to identify candidate neighborhoods and edge cases.
2. For each candidate index `k`, bracket the local interval, e.g. `[x_{k-1}, x_{k+1}]`.
3. Refine with a suitable method:
   - maximum/minimum of a smooth unimodal function: bounded Brent, golden-section, or ternary search;
   - threshold/first crossing: bisection or `root_scalar`;
   - nonsmooth feasible boundary: interval halving with constraint audit.
4. Re-evaluate all hard constraints and derived metrics at the refined point.
5. Compare coarse and refined values; freeze the refined value and record tolerance.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| coarse scan | Finds candidate intervals | Not final evidence for continuous variables |
| neighbor bracket | Uses points around the best sampled point | Include boundary candidates separately |
| bounded scalar optimize | Refines local max/min | Use sign flip for maximization if needed |
| root/bisection search | Refines first crossing or feasibility boundary | Requires sign/feasibility change bracket |
| step-halving check | Tests grid artifact risk | Report if refined result changes materially |
| freeze ledger | Records coarse value, refined value, tolerance, and source file | Prevents paper from citing stale sampled output |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Coarse step | Choose for coverage and candidate discovery | Halve once to ensure the same neighborhood is found |
| Refinement tolerance | Tie to requested output precision | Do not report more digits than tolerance supports |
| Candidate interval | Use neighboring scan points or physical event bracket | Check boundaries and multiple candidates |
| Objective evaluation | Must recompute from the full model, not from rounded table output | Save refined evaluation row |
| Noisy simulation | Use repeated seeds or smoothing before local search | Report uncertainty band |

## Validation Requirements
- Coarse scan table with step size and candidate interval.
- Refined local search log: method, bracket, tolerance, refined argument, refined value.
- Boundary check: endpoints and nearby competing candidates.
- Constraint audit at the refined point.
- Difference table: coarse best vs refined best; if the difference affects conclusions, update paper numbers and frozen results.
- For maxima that scale a final recommendation, recompute the final scale factor from the refined value.

## Failure Signs
- The final answer is at an integer second or grid point with no refinement evidence.
- The report says "maximum", "minimum", "critical", or "optimal" after only a loop over sampled points.
- A scale factor or safety margin is computed from a sampled peak.
- The best point is adjacent to the scan boundary, but the search interval was not extended.
- Re-running with half the step changes the answer beyond reported precision.

## Repair Moves
- Add bounded local search around every candidate peak.
- Add bisection/root search for first crossing or feasibility boundary.
- Extend the scan range if the best point lies at the edge.
- If the variable is genuinely discrete, state the discreteness and audit all neighboring values.
- If the function is noisy, add replications and report confidence intervals instead of a single refined peak.

## Paper Usage
- Phrase the workflow as "coarse scan locates the candidate interval; continuous local refinement gives the reported value".
- Include the refined time/parameter and value in the main result table, with tolerance.
- Do not cite the integer-grid candidate as the final number unless it is only a diagnostic.
- This card is mandatory whenever a continuous final claim is derived from a discrete or coarse scan.

## Related Cards
- Related cards: `geometry/rigid-chain-kinematics`, `geometry/collision-sat`, `statistics/continuous-system-simulation`.

## Confidence
- high for smooth deterministic one-dimensional extrema and threshold boundaries.
- medium for nonsmooth or noisy simulations, which need additional uncertainty handling.
