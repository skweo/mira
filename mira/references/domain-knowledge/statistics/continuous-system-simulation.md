# Knowledge Card: statistics/continuous-system-simulation

## Tags
- continuous system
- dynamic simulation
- computer simulation
- mathematical simulation
- differential equation
- ODE
- numerical integration
- Euler method
- time discretization
- step size
- state variable
- initial condition
- trajectory validation
- balance equation
- threshold time
- stock-flow simulation
- 连续系统
- 动态模拟
- 计算机模拟
- 数学模拟
- 微分方程
- 常微分方程
- 数值积分
- 欧拉法
- 时间离散化
- 步长
- 步距
- 状态变量
- 初始条件
- 守恒关系
- 平衡方程
- 阈值时间

## Problem Patterns
- A contest problem asks for a process that evolves over time: population, traffic flow, resource stock, heat/contaminant spread, epidemic dynamics, mechanical motion, or system response.
- The system state changes continuously with time and can be described by rates of change.
- The model uses equations such as `dy/dt = f(t,y)` or a system of ODEs.
- The output is a trajectory, time to threshold, final state after a horizon, equilibrium, or sensitivity to control/parameters.
- A simulation section shows time curves or dynamic scenarios and needs numerical evidence.
- The system is a stock-flow process where volume, mass, inventory, concentration, heat, or another conserved quantity changes through inflow and outflow.

## Applicability Conditions
- State variables, units, initial conditions, parameters, and time horizon can be defined.
- The rate equation `f(t,y)` is derived from mechanism, data fitting, conservation, balance, or stated assumptions.
- The process is continuous enough that a time-discretized ODE model is meaningful.
- The solver step size and method can be selected and validated within contest runtime.
- There is some validation surface: observed data, analytic special case, conservation law, equilibrium, monotonicity, or step-refinement behavior.

## Contraindications
- Do not use continuous-system simulation when the process is event-driven with jumps; retrieve/use discrete-event simulation instead.
- Do not use a differential equation merely to look sophisticated when a static algebraic or regression model answers the task.
- Do not treat Euler's method as sufficient for high-precision, stiff, oscillatory, chaotic, or long-horizon systems without stronger validation.
- Do not ignore hard bounds such as nonnegative populations, capacity limits, or conservation constraints.
- Do not claim exact trajectories from numerical integration.

## Algorithm Core
- Continuous-system route:
  1. define state vector `y(t)`, units, initial condition `y(t0) = y0`, and time horizon;
  2. define dynamic law `dy/dt = f(t, y, theta)` and parameter sources;
  3. discretize time as `t_k`, step `h_k = t_{k+1} - t_k`;
  4. choose solver/update rule;
  5. simulate trajectory and validate numerical/physical behavior.
- Euler baseline update:
  - `y_{k+1} = y_k + h_k f(t_k, y_k)`;
  - use as an explainable baseline or quick sanity check, with step-size sensitivity.
- Balance-equation route:
  - update conserved stock by `stock_{k+1} = stock_k + inflow_k - outflow_k`;
  - compute derived state, such as concentration or ratio, after updating the stock denominator;
  - stop at the first threshold crossing and refine step size if threshold time is decision-sensitive.
- Stronger contest-final route:
  - compare Euler with RK4 or a trusted ODE solver when the result is accuracy-sensitive;
  - report step-size/tolerance and convergence of final state or key metrics.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| state-variable definition | Identifies what evolves over time | Must include units and initial values |
| rate equation | Encodes mechanism or fitted dynamics | Must match signs, units, and assumptions |
| time grid | Converts continuous time to computable steps | Step size controls accuracy and runtime |
| Euler method | Simple first-order numerical integration | Baseline only for many contest-final uses |
| Runge-Kutta comparison | Stronger integration evidence | Use RK4 or library ODE solver when feasible |
| step refinement | Numerical convergence check | Compare `h`, `h/2`, `h/4` or equivalent |
| physical invariant check | Prevents plausible but impossible curves | Check nonnegativity, conservation, capacity, equilibrium |
| trajectory validation | Compares simulated path to data or expected behavior | Use residuals, endpoint error, or qualitative phase behavior |
| balance ledger | Audits stock-flow or conservation dynamics | Compare inflow, outflow, stock, and derived ratios per step |
| threshold crossing check | Finds time to a target level | Refine near the crossing instead of reporting a coarse grid artifact |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Step size `h` | Choose small enough for stable trajectory and accurate final metrics | Step-size sensitivity table |
| Time horizon | Match problem decision horizon and data range | Avoid extrapolating beyond justified range |
| Initial condition | Use measured/provided value or calibrated estimate | Initial-value audit and sensitivity |
| Parameters `theta` | Estimate, cite source, or justify assumptions | Parameter sensitivity or fit residual |
| State units | Keep derivative units consistent with state/time | Dimensional/unit check |
| Solver | Euler for baseline; RK/library solver for final accuracy-sensitive results | Cross-solver comparison |
| Output metric | Define whether decision uses whole trajectory, final state, maximum, threshold time, or integral over time | Recompute metric under refined step |
| Balance terms | Inflow/outflow/source/sink terms must match state units | Step-level ledger and conservation residual |
| Threshold time | Report whether the crossing time is interpolated or grid-based | Compare smaller step sizes near threshold |

## Validation Requirements
- State contract table: state variable, unit, initial value, parameter source, dynamic equation, time horizon.
- Numerical method disclosure: solver, update formula or library, step size/tolerance, and stopping rule.
- Step-size sensitivity for any final numeric claim based on a trajectory.
- Physical consistency: nonnegativity, boundedness, conservation/balance, equilibrium, or monotonicity as applicable.
- Balance ledger for stock-flow models: update primary conserved quantities before derived ratios and show residuals or a representative trace.
- Baseline/cross-solver check: analytic special case, RK4/library comparison, or observed time-series fit when available.
- Parameter sensitivity if the dynamic law contains fitted or assumed rates.
- Plot trajectory with labeled axes and units; pair plot with table of key numeric outputs.

## Failure Signs
- The paper shows a dynamic curve without state equation, initial condition, or step size.
- The method says "simulation" but does not distinguish static, continuous dynamic, and discrete-event simulation.
- Euler method is used as final evidence without step-size or cross-solver check.
- Numerical trajectory violates known physical constraints.
- Stock-flow update changes a derived ratio without updating numerator and denominator consistently.
- Reported threshold time changes materially when the step size or print interval changes.
- The final recommendation changes when step size is halved.
- The derivative equation has inconsistent units or signs.
- Long-horizon extrapolation is made without stability or parameter-sensitivity discussion.

## Repair Moves
- Add a state contract table before simulation results.
- Derive or restate `f(t,y)` from balance law, mechanism, or fitted relation; audit units and signs.
- Run step refinement and report final metric changes.
- Add a balance ledger for one representative trajectory and refine the grid around any decision threshold.
- Compare Euler against RK4 or a trusted ODE solver for the same initial condition.
- Add invariant/constraint checks and clip/repair only with explicit justification.
- If data exist, calibrate parameters and show residual/trajectory comparison.
- If the process has jumps or queues, switch to a discrete-event or hybrid simulation card instead of forcing continuous ODEs.

## Paper Usage
- Present continuous-system simulation as "state equation + numerical integration + validation", not as a generic simulation label.
- Use Euler method for transparent explanation, but state limitations and validation if it supports final results.
- Include a small table of step-size sensitivity and a trajectory figure with units.
- Separate model assumptions from numerical solver settings.
- Write results as approximate simulated trajectories under the stated model and discretization.

## Source Materials
- Useful sections: static/dynamic simulation distinction, continuous-system definition, ODE form `dy/dt = f(t,y)`, time discretization, Euler update.
- Reliability: medium teaching source; promotes foundational obligations, not advanced ODE solver theory.

## Confidence
- medium: strong for basic continuous dynamic-system modeling discipline; high-precision, stiff, PDE, or control problems need additional specialized cards.
