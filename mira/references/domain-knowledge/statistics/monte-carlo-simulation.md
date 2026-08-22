# Knowledge Card: statistics/monte-carlo-simulation

## Tags
- Monte Carlo
- random simulation
- stochastic simulation
- random sampling
- probability model
- estimator
- hit-or-miss
- sample mean
- numerical integration
- area estimation
- convergence
- standard error
- confidence interval
- random seed
- 蒙特卡洛
- 随机模拟
- 随机抽样
- 随机投点
- 概率模型
- 估计量
- 平均值估计
- 数值积分
- 样本量
- 收敛检验
- 误差估计

## Problem Patterns
- The target quantity is a probability, expectation, integral, area, reliability, risk, success rate, service rate, or scenario outcome that is hard to compute deterministically.
- The problem can be expressed as repeated random experiments with a clearly defined sampling distribution and estimator.
- A deterministic formula exists but is costly, or the system has random inputs that naturally require simulation.
- The paper needs to validate a complicated mechanism model by random scenarios or stress cases.

## Applicability Conditions
- Mira can define the random variables, their distributions, sampling domain, and independence/dependence assumptions.
- The estimator maps simulated samples to the target quantity with the correct scale and units.
- Runtime permits enough samples or repeated seeds to show convergence.
- A sanity baseline is available: analytic special case, grid/quadrature estimate, historical frequency, deterministic simplification, or known bound.
- The final paper can report seed, sample size, estimator, uncertainty, and convergence evidence.

## Contraindications
- Do not use Monte Carlo as a decorative validation when a simple exact calculation is available and sufficient.
- Do not use a stochastic estimate as a hard feasibility proof unless every sampled constraint has a deterministic audit or conservative bound.
- Do not use one random seed and one `N` as contest-final evidence for a decision-sensitive result.
- Do not sample from arbitrary distributions without data, mechanism, or sensitivity support.
- Do not mix hit-or-miss and sample-mean integration formulas; they estimate the same integral through different estimators.

## Algorithm Core
- Probability-model-first route:
  1. define target quantity `theta` as a probability, expectation, integral, or statistic;
  2. define random variables, sampling domain, and distribution;
  3. define the estimator `theta_hat = g(X_1, ..., X_N)`;
  4. run simulation with recorded seed and sample count;
  5. report convergence, uncertainty, and baseline sanity checks.
- Event-frequency estimator: for success count `m` in `N` independent trials, estimate `p = m / N`.
- Hit-or-miss area/integral estimator: sample `(x_i, y_i)` uniformly in a bounding rectangle, count hits under the curve or inside the target region, and multiply hit ratio by rectangle area.
- Mean-value integration estimator: sample `x_i ~ U(a,b)` and estimate `Integral_a^b f(x) dx = (b-a) * mean(f(x_i))`.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| random experiment definition | Connects the contest target to probability or expectation | Required before code or results |
| uniform sampling | Area, simple integral, geometric probability, scenario baseline | Must state interval/rectangle and scale factor |
| success indicator | Converts samples into event probability | Hit condition must match target exactly |
| sample-mean estimator | Estimates expectations or integrals | Usually lower variance than hit-or-miss for smooth nonnegative functions |
| hit-or-miss estimator | Estimates irregular areas or feasibility region volume | Needs bounded sampling region and many samples |
| repeated seeds | Measures stochastic stability | Use when result drives ranking or recommendation |
| convergence ladder | Shows how result changes as `N` increases | At least 3 sample sizes for contest-final stochastic estimates |
| baseline comparison | Prevents plausible but wrong simulation | Use exact/simplified/grid/historical checks |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Sample count `N` | Treat as a modeling parameter, not a coding detail | Convergence table and runtime record |
| Random seed | Fix for reproducibility; vary for robustness | Report seed and repeated-seed spread |
| Success count `m` | Only estimates a probability before scaling | Check target unit: probability vs area vs cost |
| Bounding area | Use the smallest defensible rectangle/domain that contains target region | Verify no target mass is outside domain |
| Estimator formula | Write the estimator before results | Unit check and baseline comparison |
| Standard error | For sample mean, use sample standard deviation divided by `sqrt(N)` when applicable | Confidence interval or repeated-run spread |
| Distribution assumptions | Use empirical/mechanistic distributions when available | Sensitivity to distribution parameters |

## Validation Requirements
- Estimator traceability: target quantity -> random variables -> estimator -> code output -> paper result.
- Reproducibility: seed, software/runtime, sample count, and aggregation formula are recorded.
- Convergence: report at least 3 sample sizes or an equivalent stopping criterion.
- Uncertainty: report standard error, confidence interval, or repeated-seed spread.
- Baseline: compare with analytic, deterministic, historical, grid, or simplified-case result when possible.
- Constraint audit: for simulation used inside optimization, separately check hard constraints and invalid samples.
- Sensitivity: vary sample count and key distribution/parameter assumptions if the result affects ranking or policy.

## Failure Signs
- The model says "Monte Carlo simulation" but never defines the probability model or estimator.
- A single random number is used as a final result with no `N`, seed, convergence, or error estimate.
- Penalty/risk/cost results are dominated by simulation noise or change under repeated seeds.
- The estimator's unit does not match the target quantity.
- Invalid samples are silently dropped or repaired without reporting the rule.
- The simulation cannot reproduce a known special case.
- Monte Carlo is used to hide an unresolved deterministic modeling error.

## Repair Moves
- Write the estimator equation and unit check before touching parameters.
- Add an analytic or grid baseline for a simplified case.
- Increase `N`, add repeated seeds, and report convergence until decision order stabilizes.
- Replace arbitrary distributions with empirical sampling, fitted distributions, or sensitivity bands.
- Switch from hit-or-miss to sample-mean integration for smooth integrals when variance is too high.
- Use stratified/Latin-hypercube/quasi-Monte Carlo only after the plain estimator and validation are clear.
- If simulation is embedded in optimization, cache scenarios or use common random numbers for fair comparison.

## Paper Usage
- Present Monte Carlo as a reproducible estimator, not as a black-box algorithm.
- Include a compact "simulation settings" table: target, random variables, distribution, estimator, `N`, seed, baseline, and uncertainty metric.
- For final decisions, pair stochastic estimates with convergence or confidence intervals.
- Phrase results as "estimated under the stated random model" unless validated against real data.
- Use a flowchart only when it shows random-input generation, evaluation, aggregation, and validation, not generic method decoration.

## Source Materials
- Useful sections: probability-model-first explanation, Buffon needle event-frequency example, random-point area estimate, sample-mean integral estimate.
- Reliability: medium teaching source; promotes fundamentals and validation obligations, not advanced sampling performance claims.

## Confidence
- medium: reliable for Monte Carlo basics and contest-final evidence requirements; advanced variance reduction and domain-specific distribution fitting require additional cards.
