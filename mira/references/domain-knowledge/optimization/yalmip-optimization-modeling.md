# Knowledge Card: optimization/yalmip-optimization-modeling

## Tags
- YALMIP
- sdpvar
- optimize
- sdpsettings
- MATLAB optimization modeling
- LP
- MILP
- QP
- SDP
- SOCP
- Gurobi
- CPLEX
- MOSEK
- solver status
- 优化建模
- 线性规划
- 整数规划
- 二次规划

## Problem Patterns
- The contest model is a constrained optimization problem and MATLAB is the preferred implementation environment.
- Variables, constraints, and objective can be written declaratively.
- The model may be LP, MILP, QP, SOCP, SDP, or a convex/mixed-integer variant supported by external solvers.
- A readable model implementation is more valuable than hand-coded matrix assembly.

## Applicability Conditions
- A compatible solver is installed or a fallback solver is acceptable for the problem class.
- Decision variables, bounds, integrality, constraints, and objective are mathematically defined before coding.
- The problem scale is within solver capability.
- Solver status, objective value, and primal variables can be saved as artifacts.

## Contraindications
- Do not claim Gurobi/CPLEX/MOSEK results unless that solver actually ran and logs/status support it.
- Do not use YALMIP as a black box before checking feasibility, units, and constraint construction.
- Do not solve nonconvex or nonlinear models with a convex solver without reformulation or explicit limitation.
- Do not report `value(x)` when `sol.problem` indicates failure, infeasibility, or numerical issues.

## Algorithm Core
1. Define decision variables using `sdpvar`, `binvar`, or `intvar`.
2. Build constraints as an explicit list with bounds, equalities, inequalities, and integrality.
3. Define objective and direction.
4. Set solver options with `sdpsettings`.
5. Run `sol = optimize(Constraints, Objective, options)`.
6. Check `sol.problem`, `sol.info`, and `yalmiperror(sol.problem)`.
7. Extract `value(...)`, recompute objective/constraints, and save logs/results.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| `sdpvar` | Continuous variables | Dimension and shape audit required |
| `binvar`/`intvar` | Binary/integer decisions | Check solver supports integrality |
| constraint list | Declarative model constraints | Name/group constraints for audits |
| `sdpsettings` | Solver and verbosity control | Record solver and options |
| solver status check | Prevents using failed output | Mandatory before `value` enters paper |
| recomputation audit | Verifies objective and constraints from values | Required for final numbers |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Big-M constants | Derive tight values from data bounds | Sensitivity and infeasibility check |
| Solver tolerance/gap | Match paper precision | Report gap/status for MILP |
| Variable bounds | Always specify meaningful bounds | Bound audit and unit check |
| Objective scaling | Avoid coefficients differing by extreme orders | Component ratio and scaling audit |
| Solver choice | Match LP/MILP/QP/SDP/SOCP class | Status/log evidence |

## Validation Requirements
- Model table: variables, dimensions, domains, bounds, units.
- Constraint inventory with count and meaning.
- Solver lineage: YALMIP version if known, solver name, options, status code, gap/tolerance, runtime.
- Feasibility audit from extracted solution, not only solver status.
- Objective recomputation from primitive variables.
- Baseline or small-instance check when the model is complex.
- Infeasibility handling: if solver fails, record status and do not write numerical conclusions.

## Failure Signs
- The code extracts `value(x)` without checking `sol.problem`.
- The paper says "Gurobi solved" but logs show fallback or no solver execution.
- Big-M values are arbitrary and dominate numerics.
- Variable dimensions do not match the mathematical model.
- A nonconvex expression silently changes the intended problem class.
- The solver returns infeasible/unbounded but the paper still reports a solution.

## Repair Moves
- Add solver-status gate and save solver log.
- Add bounds and tighten Big-M constants.
- Recompute objective and every hard constraint from `value(...)`.
- Run a small hand-checkable instance.
- If solver unavailable, downgrade to model formulation plus alternative executable solver, and state lineage honestly.

## Paper Usage
- Describe YALMIP as an implementation/modeling layer, not as the mathematical method itself.
- Name the actual optimization class and solver that produced results.
- Include solver status/gap only as much as needed; keep detailed logs as separate result files.

## Source Materials
- `$PROJECT_ROOT\Math_Model\YALMIP_example`
- Files inspected: `yalmip_learning.m`, `README_import.md`.

## Confidence
- medium-high for YALMIP workflow and audit requirements.
- solver-specific capability depends on the installed MATLAB/YALMIP/solver environment.
