# Validation Patterns

Use this reference before result analysis, final writing, and compliance checks.
Validation is the boundary between a runnable answer and a contest-final paper.

## Optimization Validation

| Solver type | Required evidence | Wording rule |
|---|---|---|
| Exact dynamic programming | state recurrence, scale, exact objective, route or schedule audit | may call exact only inside the stated subproblem |
| MILP/exact solver | solver name, gap/tolerance, feasibility audit, bound or objective certificate | may call global optimum only when gap/proof supports it |
| Heuristic/local search | baseline comparison, fixed seed, multi-start or multi-seed stability, constraint audit | call best-found or current experimental solution, not global optimum |
| Decomposition | subproblem definition, merge/repair logic, lost-global-optimality warning, full feasibility audit | avoid global-optimal claims unless proved |
| Simulation/search | scenario design, seed/settings, repeatability, sanity checks, metric uncertainty | describe estimated or simulated performance |

## Data And Model Validation

- Anti-paper-tiger gate: validate problem contract, assumption risk, data audit,
  result reproducibility, and constraint audit before treating a draft as
  contest-final. Any key result without provenance, objective recomputation, or
  feasibility audit is unverified, even if the paper prose looks complete.
- Problem-specific adaptation: verify that the chosen method handles the current
  task's special geometry, workflow, field semantics, coordinate system,
  intervention mechanism, or output format. A generic method without this check
  is unvalidated.
- Data extraction: for video, image, survey, sensor, spreadsheet, or
  high-dimensional attachments, validate the extracted table before modeling
  with spot checks, range checks, missing/error handling, or threshold
  sensitivity. Do not validate only the later model.
- Forecasting: use a time-respecting split or defensible error estimate,
  prediction-vs-actual evidence, residual/error metrics, and plausibility bounds.
- Parameter fitting: show residuals, convergence/tolerance, identifiability or
  sensitivity, and at least one independent or limiting-case check when possible.
- Parameter identification/inverse problem: verify the forward model, fitted
  target semantics, residual/loss function, parameter bounds, fitted data
  segment, validation segment or limiting-case check, parameter sensitivity, and
  every requested calibration/result table.
- Evaluation/ranking: state indicator direction, normalization, weight source,
  ranking robustness, sensitivity to weights, and the score/ranking table used
  for the final decision. For AHP, save judgment matrices, eigenvalue weights,
  CI/RI/CR records, and the alternative or object scores.
- Routing/network: verify edge definition, route continuity, visit uniqueness,
  capacity, time windows, and final route table.
- Genetic algorithms and other population heuristics: besides the final best
  value, verify ordinary baseline performance, multi-seed best/mean/std,
  convergence trend, feasibility or repair audit, and a diversity signal when
  early convergence is a known risk. If using layered population, adaptive
  crossover/mutation, or SA-GA, add an ablation comparison to show the extra
  mechanism is useful for the current task.
- Network flow: verify capacity, flow conservation, source/sink or supply/demand
  balance, and recomputed total cost from the edge-flow table.
- Multi-objective optimization: compare against single-objective baselines,
  report objective tradeoffs, and test weight/priority sensitivity.
- Scheduling/capacity: verify coverage, inventory/state nonnegativity, resource
  capacity, lower bound/gap when available, and representative schedule.
- Workflow scheduling/dispatch: verify event-time continuity, movement/setup
  time, loading/unloading/cleaning time, no-overlap constraints, failure
  start/end effects when relevant, and downstream impact after recovery.
- Transportation/supply-demand allocation: verify allocation row sums, column
  sums, supply/demand balance, dummy or shortage handling, integrality when
  resources are indivisible, and total cost recomputed from the allocation and
  cost matrix.
- Dynamic programming: verify the recurrence, boundary condition, reconstructed
  policy, state transition feasibility, and total objective recomputed from the
  recovered path or schedule.
- Forecast-then-optimize: validate the forecast before optimization; do not use
  unvalidated predictions as if they were measured facts.
- Interpolation/spatial reconstruction: verify coordinate units, grid regularity,
  target-domain coverage, and boundary/extrapolation handling; compare against
  nearest-neighbor or linear baselines when useful; validate with holdout points,
  synthetic ground truth, residual/error maps, sampling-orientation sensitivity,
  or threshold sensitivity for edge-aware methods.
- Engineering algorithm implementation: validate the shared simulation platform
  before optimizing design variables; compare against a baseline or floating-point
  reference; freeze parameter-grid outputs, random seed, sample count, and metric
  tables; audit all hard constraints such as performance threshold, throughput,
  delay alignment, and resource budget; recompute resource totals from primitive
  operations rather than copying a final total.
- Wavelet analysis: validate the sampling rule, boundary handling, wavelet
  basis, decomposition level, threshold or feature extraction rule, and
  reconstruction/denoising error. When wavelet features feed prediction or
  classification, compare against raw-feature and simple-filter baselines. For a
  wavelet neural network, require the same train/validation/test, baseline, and
  overfitting checks as other neural networks.
- Differential-equation/PDE/control models: check coordinate/state definitions,
  initial conditions, boundary conditions, interface/continuity or terminal
  conditions, unit consistency, numerical discretization route, and
  stability/convergence or limiting-case behavior.
- Recommendation outputs: verify each policy, management, or design
  recommendation against the computed indicator, scenario result, optimization
  result, or simulation result that supports it.
- Neural networks: first identify the learning paradigm and task type. For
  supervised models require train/validation/test or cross-validation, baseline
  comparison, task-specific metrics, and overfitting checks before they can be a
  main model. For unsupervised models require an internal criterion, stability,
  and interpretation check. For reinforcement learning require a defined
  environment, state/action/reward, baseline policy, reward curve, and
  safety/constraint audit.
- Perceptron/BP validation: for single-layer perceptrons, verify the linear
  separability assumption or compare against a linear classifier. For BP/MLP,
  record architecture, activation, loss, initialization, training algorithm,
  stopping rule, and random seed; use validation/test metrics rather than
  training fit only, and repeat initialization when local minima or instability
  affects the reported result.
- BP optimizer validation: when using line search, conjugate-gradient,
  Newton/Gauss-Newton, or Levenberg-Marquardt training, save the optimizer name,
  learning-rate/line-search or damping settings, iteration limit, stopping
  reason, convergence trace, and any failed retry. Treat these as training
  evidence only; generalization still requires validation/test metrics and a
  baseline comparison.

## Failure Signs

Treat these as major issues or blockers in `contest_final`:

- A final result appears with no baseline, audit, or sensitivity.
- The paper has polished prose, figures, or references but lacks problem
  contracts, data audit, result provenance, or constraint audit.
- A heuristic result is called optimal.
- An exact-optimal claim has no proof, lower bound, or solver gap.
- A long route or schedule is summarized without a complete supporting result file.
- A flow or allocation model has no edge/assignment table and no conservation or
  coverage audit.
- A transportation solution reports only a total objective without an allocation
  matrix, row/column audit, or unit-checked cost matrix.
- A dynamic-programming solution gives a final value without states, recurrence,
  boundary condition, and recovered decisions.
- A neural network is used on small data with no baseline or validation split.
- A perceptron is used for nonlinear or XOR-like classification without feature
  mapping or hidden layers.
- A BP network copies demo settings such as fixed hidden-node count, training
  goal, or epoch limit without tuning, validation, and baseline comparison.
- A BP paper claims better performance because it used LM, conjugate gradient, or
  line search, but reports no validation-set improvement, convergence trace, or
  baseline comparison.
- A table reports precise numbers without units, source artifact, or run settings.
- A known algorithm, software command, or literature model is used without
  checking the task's special geometry, mechanism, workflow, or output contract.
- Raw media or large attachments are referenced but no extracted data table,
  extraction rule, or extraction validation exists.
- A parameter-identification result uses the wrong field as target, lacks the
  residual definition, or has no validation/sensitivity evidence.
- A calibration or inverse-problem paper estimates parameters but omits the
  requested calibration table, corrected table, or reliability comparison.
- A minimum value, optimum route, ranking, parameter choice, or feasible scheme
  cannot be recomputed from saved result files.
- A practical recommendation appears without a supporting computed scenario,
  indicator, or optimization result.
- A differential-equation model has no definite conditions or numerical method
  audit.
- A schedule or dispatch paper gives totals without a detailed time/resource
  feasibility audit.
- The conclusion introduces a result that is not supported in the body.
- Interpolated values are treated as measured facts, or a reconstructed surface
  is shown without domain, boundary, baseline/error, or sampling-limit evidence.
- An engineering/resource result reports the "lowest resource" design without a
  baseline comparison, fixed-point check, throughput audit, or operation-level
  resource table.
