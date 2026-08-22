# Model Depth Rules

Use this reference before the modeling plan and before revising a shallow paper.
It converts algorithm examples into contest-paper modeling depth. Do not use an
algorithm only because a local example exists.

## Algorithm Selection Order

Choose the method by the problem structure:

1. Define decision variables, state variables, parameters, units, objective, and
   hard constraints.
2. Treat historical topic-method mappings as routing hints only; confirm the
   current task's objective, constraints, data, and evaluation metric before
   selecting a method.
3. Check whether the model is linear, integer, network, dynamic, stochastic,
   evaluation/ranking, forecasting, fitting, or simulation.
4. Prefer exact or structured methods when tractable: LP/MILP, transportation
   problem, dynamic programming, shortest path, network flow, matching,
   regression, or closed-form estimators.
5. Use heuristics such as SA, GA, PSO, immune algorithm, or ant colony only when
   exact methods are infeasible, the search space is large, or the objective is
   nonconvex/non-smooth.
6. Use neural networks only when data size, train/validation split, feature
   engineering, and comparison baseline are defensible.
7. Record why simpler baselines are insufficient.
8. If a PoC or prototype produced objective values, evaluate it with `poc-evaluation.md` before locking the method. A runnable PoC is only smoke-test evidence; method-selection evidence requires comparison against a baseline or alternative on the same case.

## Budget-Bounded Candidate Screening

Record at least two structurally different candidates for each substantive model
choice unless proof or dominance establishes a unique route. This is a reasoning
requirement, not a requirement to run two full solvers or produce two papers.

Use the lowest-cost evidence that can change the route, in this order:

1. reject a route analytically when it conflicts with hard constraints,
   observability, units, data volume, or required outputs;
2. compare tractability, identifiability, complexity, and solver availability;
3. use a hand-check, a tiny exact case, downsampled data, or an existing baseline;
4. run a bounded PoC only when the earlier checks do not separate the routes;
5. run a full-scale comparison only when the model choice materially changes the
   conclusion and the remaining contest budget supports it.

Every discriminating test states a time, case, sample, or run cap before it runs.
Stop once the decision rule is met. An approved `time_budget`, `compute_budget`,
or `contest_time` waiver may skip a specific expensive comparison test; scope it
to that test ID and record the retained route, reason, and failure condition. It
does not waive feasibility, hard-constraint audits, result recomputation, or
validation of the selected final model.

## Per-Method Depth Contract

| Method family | Must specify | Must validate | Do not overclaim |
|---|---|---|---|
| LP/MILP/integer programming | variables, objective coefficients, equality/inequality constraints, bounds, integrality, solver/gap | feasibility, binding constraints, objective value, sensitivity or gap | do not round LP relaxation as an integer solution |
| Transportation/supply-demand allocation | supply points, demand points, cost matrix, balance policy, divisibility/integrality, shortage or dummy-node handling | row/column supply-demand audit, recomputed total cost, unit consistency, sensitivity to key supply/demand/cost | do not report only total cost without allocation matrix; do not ignore unbalanced supply and demand |
| Dynamic programming | stages, state variables, decisions, transition rule, boundary condition, recurrence, state-space size | reconstructed policy/schedule, transition audit, objective recomputation, baseline comparison | do not call a staged narrative dynamic programming without an explicit state recurrence |
| Goal/multi-objective programming | each objective, unit normalization, hard-vs-soft constraints, weights/priorities/target values | single-objective baselines, tradeoff table, weight sensitivity | do not hide hard constraints as soft penalties |
| Graph shortest path/network flow | nodes, directed/undirected edges, edge weights, connectivity, source/sink, path constraints | route continuity, edge direction, all requested nodes/flows, baseline path | do not use Dijkstra for negative or non-additive weights |
| Network/min-cost flow | source/sink/supply/demand, capacity, cost, conservation constraints | capacity audit, flow conservation, recomputed total cost | do not report total flow without edge flow table |
| TSP/VRP/routing heuristic | encoding, decoder, objective terms, hard constraints, neighborhood/crossover/mutation, seed, stopping rule | coverage, uniqueness, capacity/time-window audit, decoded route table, baseline, multi-seed stability | do not call global optimum without proof |
| Simulated annealing | initial solution, neighborhood operator, temperature schedule, chain length, acceptance rule, best-vs-current tracking | baseline, convergence curve, repeated seeds, feasibility audit | do not treat one run as proof |
| Genetic algorithm | chromosome encoding/decoder, objective-to-fitness mapping, feasible initialization, selection, crossover, mutation, elitism or best-so-far memory, repair operator, generations and no-improvement stopping rule, seed count, adaptive-operator or hybrid-SA parameters when used | baseline or exact small case, multi-run best/mean/std and feasibility rate, decoded final solution table, constraint repair/audit, convergence with first-best generation, parameter sensitivity, ablation when adding GA improvements | do not use unsuitable crossover that breaks feasibility; do not hide objective direction through inverse fitness; do not present improved or hybrid GA as better without a comparable baseline; do not report only an adaptation curve without decoded decisions |
| Particle swarm | particle dimension, encoding/decoder, objective direction, per-dimension position and velocity bounds, inertia/social/cognitive parameters, seed count, stopping or restart rule, constraint repair | baseline or exact small case, numeric convergence trace, diversity/stagnation trace when adaptive mutation is used, bound/constraint audit, repeated-run best/mean/std, parameter sensitivity, ablation for mutation/hybrid variants | do not use PSO for discrete/permutation constraints without encoding and repair; do not report plot-only results; do not hide maximization/minimization through reciprocal fitness; do not call a PSO result global optimum without proof |
| Forecasting/time series | time index, target, predictors, train/validation split, leakage prevention, metric | MAE/RMSE/MAPE/residuals, scenario or uncertainty | do not optimize downstream on unvalidated forecasts |
| Grey prediction | level-ratio check, accumulated sequence, background value, parameter estimate, inverse accumulation | residuals, relative error, posterior or small-error probability when used | do not use GM(1,1) blindly on long/noisy/non-monotone data |
| Regression/PCA | variable meaning, normalization, collinearity/dimension reduction, coefficient interpretation | residuals, holdout/CV when possible, explained variance, sensitivity | do not present correlation as causation |
| Parameter identification/inverse problem | forward model, observed field semantics, unknown parameters and bounds, observation equation, residual/loss definition, fitting data segment | residuals, validation segment or limiting case, parameter sensitivity/identifiability, final requested calibration/result table | do not fit displayed/legacy/model-derived values as if they were true observations; do not write "least squares gives" without a loss function |
| AHP/evaluation | hierarchy, judgment matrix, weights, consistency ratio, indicator directions | CR check, weight sensitivity, ranking robustness | do not hide subjective weights |
| Interpolation/spatial reconstruction | coordinate system, units, sample locations, grid spacing, anisotropy, interpolation kernel, target points/plane, boundary/extrapolation policy | holdout or synthetic ground truth, baseline comparison, residual/error map when useful, sampling/orientation/threshold sensitivity, runtime for large grids | do not call interpolated values exact measurements; do not ignore discontinuities or extrapolation |
| Engineering algorithm simulation/resource tradeoff | system or signal chain, performance metric, resource metric, discrete design variables, fixed-point/implementation assumptions, throughput/timing constraints, operation-cost table | baseline/floating-point comparison, parameter grid, seed/sample settings, feasible-region audit, resource recomputation, performance-resource sensitivity | do not optimize resources before proving performance constraints; do not treat floating-point simulation as fixed-point implementation |
| Wavelet analysis / wavelet neural network | sampling rule, signal/image preprocessing, wavelet basis, decomposition level, threshold or feature rule, boundary handling, WNN architecture when used | reconstruction/denoising error, baseline filter or raw-feature comparison, basis/level sensitivity, downstream validation, train-vs-validation loss for WNN | do not use wavelet methods only because a demo script exists; do not treat training fit as generalization |
| Monte Carlo/simulation | random variables, distributions, sampling method, seed, run count, scenario design | convergence/uncertainty interval, sanity check, repeated seeds | do not report simulation output as deterministic fact |
| Erlang C / queueing capacity | arrival interval and rate, AHT/service time, offered load, server count, occupancy, target answer time, service-level target, queue assumptions | unit audit, stability `m>u`, occupancy audit, wait probability/ASA/service-level recomputation, staffing sensitivity, observed or simulation comparison when assumptions are weak | do not use with abandonment, time-varying arrivals, priorities, finite queues, or multi-skill servers without adjustment or simulation |
| Cellular automata / grid simulation | grid/domain and cell size, finite state set, neighborhood, boundary condition, local rule or rule table, synchronous update policy, initialization, timestep, stopping rule, output metrics | rule-table audit, old/new grid synchronization test, hand-updated toy pattern, metric curves, grid/boundary/neighborhood sensitivity, multi-seed and parameter-grid checks for stochastic CA, conservation audit when claimed | do not use snapshots as proof; do not hide periodic boundaries in indexing; do not claim prediction from uncalibrated local rules |
| Markov chain / state-transition model | state table, discrete time step, initial distribution, transition-probability source, transition matrix convention, chain type, prediction horizon, requested metric | row/column stochastic audit, transition-source audit, Markov/no-memory check, `a(n)=a(0)P^n` recomputation, steady-state convergence or absorbing-chain `Q/M` audit, sensitivity to transition probabilities and state partition | do not report steady state for absorbing/reducible chains; do not invent transition probabilities; do not ignore trend/seasonality/history dependence |
| Neural network | task type, learning paradigm, dataset size, features, split, architecture, activation, loss or internal criterion, initialization, training algorithm, learning-rate/line-search or damping settings, stopping rule | train/validation/test metrics, baseline comparison, overfitting check, convergence trace, repeated seeds/initializations when unstable, task-specific metric such as confusion matrix or RMSE | do not use advanced models without data sufficiency; do not use biological analogies as evidence; do not treat a demo script's parameters as contest evidence; do not present LM/CG/Newton training as proof of global or generalized performance |

## Official-Judging Adaptation Gate

Official CUMCM judging points repeatedly penalize copied generic methods. Before
locking a model, state the task-specific adaptation:

1. What special geometry, workflow, physical mechanism, platform rule, coordinate
   system, data-collection mode, or output format changes the generic method?
2. Which variables, constraints, parameters, objective terms, or validation
   checks were added because of those special conditions?
3. Which official subquestion deliverables are produced by this model?
4. Which generic assumptions are unsafe for this task and were avoided?

If this adaptation cannot be stated, the model is a draft-only route.

## Evaluation And AHP Depth

For AHP, TOPSIS, fuzzy evaluation, entropy-weight scoring, or composite-index models, require a full evaluation pipeline:

1. Explain why the task is an evaluation/ranking/selection problem.
2. Define the evaluated objects or candidate alternatives.
3. Derive criteria or indicators from the problem mechanism, data fields, stakeholder goals, or credible sources.
4. State each indicator's direction, units, data source, and normalization or scoring method.
5. State the weight source: AHP judgment matrix, entropy weight, expert rule, literature, objective data, or hybrid weight.
6. Compute the final score/index/ranking and place the result table near the claim.
7. Validate with weight sensitivity, scenario reweighting, comparison to known ranking, or case sanity check.
8. If the evaluation feeds a later model, state the handoff explicitly, such as weights to index, index to classification, or index to optimization.

AHP should not be the entire model unless the official task is purely qualitative decision selection with limited data. In stronger papers, AHP usually appears after indicator construction or mechanism modeling and before classification, policy choice, or optimization.

## Data-Rich Optimization Depth

For resource allocation, production planning, scheduling, routing, book-number allocation, or capacity-allocation problems:

1. Identify decision granularity first, such as course-level vs discipline-level, customer-level vs region-level, or route-level vs vehicle-level.
2. Build the objective from primitive terms, and avoid double-counting the same demand, sales, score, or competitiveness information in multiple factors.
3. Separate hard constraints from preference factors: capacity, total quota, minimum service level, inventory, time, and resource limits belong in constraints unless the problem says otherwise.
4. Record which attachment supplies each objective term, constraint, parameter, and adjustment factor.
5. If multiple decision granularities are defensible, compare or at least state how the choice may change results.
6. After solving, recompute objective value and all hard constraints from the final decision table.
7. If the task has supply, demand, and a cost matrix, check the transportation-problem or min-cost-flow formulation before using a heuristic.
8. If the task has stages and state transitions, check the dynamic-programming formulation before collapsing it into an arbitrary weighted score.
9. If the task requires a schedule, route table, assignment table, or support
   spreadsheet, define the table schema before solving and audit feasibility from
   that table after solving.

## Parameter Identification And Inverse Problems

For calibration, correction, deformation identification, fault-parameter
estimation, or inverse modeling:

1. Split the work into the forward model and the inverse identification task.
2. Audit the raw fields before fitting. Record whether each field is measured,
   displayed, cumulative, interval-change, model-derived, or legacy-calibration.
3. Define the observation equation that connects raw data to the forward model.
4. Fit the quantity the problem actually observes. If the observation is a
   change, fit model-predicted changes, not absolute displayed values.
5. State parameter bounds and physical meaning before running search or least
   squares.
6. Validate on a separate segment, limiting case, synthetic known-answer case, or
   residual/sensitivity analysis.
7. Produce every requested deliverable such as calibration table, corrected
   table, parameter values, and model-reliability comparison.

For video, image, sensor, survey, or other raw-media/data-extraction problems:

1. Treat extraction as a model step, not clerical preprocessing.
2. Define the target observable, extraction rule, sampling interval or frame
   rule, coordinate transform, missing/error handling, and uncertainty source.
3. Save the extracted table before fitting, optimization, or plotting.
4. Prefer actual extracted data over design standards when the task asks for
   observed behavior.
5. Validate extraction with spot checks, duplicate extraction on a subset,
   comparison to known bounds, or sensitivity to extraction thresholds.

For differential-equation, heat-transfer, mechanics, or control problems:

1. Define the coordinate system and state variables before equations.
2. State all required initial, boundary, interface, continuity, or terminal
   conditions; equations without definite conditions are incomplete.
3. For discretized control or PDE models, state mesh/step size, stability or
   convergence consideration, and solver route.
4. Separate performance/safety constraints from objectives such as thickness,
   cost, mass, or time.
5. Validate by limiting cases, dimensional/unit checks, parameter sensitivity, or
   comparison to known/reference conditions.

For scheduling and workflow dispatch problems:

1. Model the actual workflow sequence, including movement, setup, loading,
   unloading, cleaning, queueing, waiting, failure, and recovery when relevant.
2. Define event-time variables and resource states, not only aggregate counts.
3. Audit the final schedule for time continuity, resource capacity, task
   coverage, no-overlap, waiting logic, and failure propagation.
4. Report both detailed schedule/assignment tables and aggregate efficiency
   metrics.

For staged planning problems such as lodging-venue-transport, staffing-routing, or inventory-dispatch:

1. State the dependency order and which upstream result is passed downstream.
2. Keep upstream alternatives when the first-stage optimum is nonunique; choose among them using downstream cost, feasibility, distance, or convenience.
3. Do not combine all stages into one weighted objective unless the variables, constraints, and weights are all defensible.
4. Interpret costs by stakeholder. A cost paid by participants or customers may be a preference constraint, not the organizer's direct objective.
5. For capacity forecasts, include shortage penalty, service-level target, or safety margin when under-supply has high practical cost.

## Code Example Use

Local MATLAB/Python examples are implementation hints only.

- Translate or adapt examples into the current project's `code/` folder.
- Replace hardcoded demo data with current-task data.
- Save run logs, parameters, seeds, outputs, and audit tables.
- Do not execute `.exe`, `.bat`, archives, shortcuts, or unknown binaries.
- If an example uses random search, add fixed seeds and repeated runs.
- If an example produces only a plot, also save the numeric table behind it.
- If a PoC compares candidate methods, save `results/tables/poc_results.csv` or `method_screening.csv` and run `scripts/poc_evaluate.py`. A candidate that is much worse than a comparable baseline should be downgraded or rejected before modeling.

## Engineering Implementation Depth

For DSP, ASIC/FPGA, embedded, control-system, communication, or industrial-simulation problems, require an implementation-aware modeling chain:

1. Build a shared simulation platform before subquestion-specific optimization.
2. Validate a baseline such as no compensation, simple method, floating-point method, or official reference.
3. Scan bounded discrete design variables such as bit width, Pilot count, window length, lookup-table size, delay, and parallelism.
4. Save raw parameter-grid outputs before fitting curves or surfaces.
5. Separate performance constraints from resource objectives. Performance must pass before resource minimization is meaningful.
6. Build resource totals from problem-specified primitive operations such as add, multiply, lookup, buffer, delay, memory, or pipeline stage.
7. For fixed-point designs, discuss bit-width range, overflow risk, quantization noise, and convergence to the floating-point baseline.
8. If replacing an expensive operation with an approximation such as lookup, CORDIC, Taylor expansion, or piecewise linearization, report accuracy range and resource saving.
9. For automatic design schemes, define input metric, adjustment direction, threshold/stop rule, and fallback for infeasible or low marginal-gain cases.

## Paper Evidence Required

For each substantial model section, include:

1. Why the method fits the task and why the baseline is insufficient.
2. Formal variables, parameters, objective, and constraints.
3. Algorithm steps or solver route specific to the current data scale.
4. Result table with units and provenance.
5. Validation evidence chosen from `validation-patterns.md`.
6. Limitations that follow from the actual model, not generic praise/criticism.
7. The requested scoring artifact produced by the model, such as a parameter
   table, route table, schedule table, ranking, strategy rule, or policy
   recommendation.

## Shallow Model Failure Signs

- The paper names an algorithm before defining variables and objective.
- A formula is generic and no parameter source is given.
- A heuristic has no encoding, neighborhood/operator, seed, or stopping rule.
- A multi-objective model gives one "comprehensive optimum" without objective tradeoff or weight sensitivity.
- A network-flow result gives only total cost/flow and no edge-flow table or conservation audit.
- A result table exists but no constraint audit exists.
- A neural network appears without dataset size, train/test split, features, and
  baseline.
- A perceptron/BP section appears without checking whether the task is linear
  classification, nonlinear classification, or nonlinear regression.
- A BP result reports only training fit, with no holdout/CV metric, baseline, or
  repeated-initialization stability check.
- A BP section names LM, conjugate-gradient, Newton, or line-search training but
  omits training parameters, convergence/stop reason, and validation metrics.
- A literature model, software command, or common algorithm appears without
  task-specific adaptation to the current data, geometry, workflow, or
  constraints.
- A data-rich problem jumps to fitting or optimization before saving an extracted
  data table and field-to-model-use ledger.
- A PDE, heat-transfer, mechanics, or control model has equations but no initial,
  boundary, interface, terminal, or constraint conditions.
- A schedule or dispatch result reports only throughput or count without the
  detailed schedule table and time-feasibility audit.
- A ranking appears without indicator direction, weight source, and sensitivity.
- A route/path result appears without edge definition and route continuity.
- A PoC/prototype objective is reported but not compared against a baseline or alternative, or a clearly worse PoC method remains the selected route.
- AHP appears as a generic tree and weight table but no alternative scores, normalized indicator matrix, or downstream decision uses the weights.
- AHP or subjective ranking replaces a hard-constrained allocation problem with known capacities, demands, and integer decisions.
- A staged planning problem collapses forecast, allocation, and transport/facility decisions into one arbitrary weighted score without dependency or feasibility checks.
- An interpolation result appears without coordinate units, sample spacing, target-domain definition, boundary policy, baseline/error check, or caveat about extrapolation and discontinuities.
