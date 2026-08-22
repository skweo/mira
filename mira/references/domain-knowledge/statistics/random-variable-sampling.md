# Knowledge Card: statistics/random-variable-sampling

## Tags
- random variable
- random sampling
- pseudo-random number
- inverse transform
- inverse CDF
- quantile function
- Box-Muller
- normal sampling
- frequency table sampling
- cumulative probability mapping
- uniform distribution
- exponential distribution
- binomial distribution
- Poisson distribution
- distribution parameterization
- RNG seed
- 随机变量
- 抽样
- 随机抽样
- 伪随机数
- 逆变换
- 反函数
- 分布函数
- 均匀分布
- 正态分布
- 指数分布
- 二项分布
- 泊松分布
- 统计检验
- 频率表
- 累计概率

## Problem Patterns
- A Monte Carlo, stochastic simulation, queueing, reliability, risk, demand, arrival, service-time, or scenario model needs samples from specified distributions.
- The problem statement or data imply a non-uniform distribution, but the code can only directly generate uniform pseudo-random numbers.
- Mira needs to justify how random inputs were generated before reporting simulation results.
- A custom distribution, fitted distribution, or truncated/domain-limited distribution is used.
- Simulation results depend on tails, rare events, or distribution parameters.
- The source data provide empirical frequencies or a probability table that must be converted into random-number intervals.

## Applicability Conditions
- The distribution family, parameters, support, and units are known, fitted, or defensibly assumed.
- The chosen sampler is compatible with the distribution: built-in library, inverse CDF, transformation, or another validated method.
- Random variables' independence or dependence assumptions are explicit.
- The sample count is large enough for the downstream Monte Carlo estimator and validation checks.
- Reproducibility is possible through seed, software, and parameter records.

## Contraindications
- Do not sample from an arbitrary distribution because it is convenient; tie it to data, mechanism, or sensitivity analysis.
- Do not use independent samplers for correlated variables unless independence is justified or sensitivity shows little effect.
- Do not use a rough CLT/12-uniform normal approximation for tail probability, VaR, reliability, or small-probability decisions.
- Do not trust built-in random functions without checking parameter conventions and output shape.
- Do not use random sampling as a substitute for a deterministic constraint feasibility proof.

## Algorithm Core
- Uniform base route:
  1. generate `r_i ~ U(0,1)` with a recorded pseudo-random generator and seed;
  2. map `r_i` into the target distribution through a validated transformation or library sampler;
  3. check empirical support, moments, and quantiles before using samples in the model.
- Inverse-transform route: for CDF `F`, sample `X = F^{-1}(r)` where `r ~ U(0,1)` when the inverse CDF or numerical quantile function is available.
- Frequency-table route: sort outcomes, compute cumulative probabilities, map each `r ~ U(0,1)` into exactly one interval, and audit that intervals cover `[0,1]` without gaps or overlaps.
- Normal route:
  - use a tested `Normal(mu, sigma)` sampler when available; or
  - use Box-Muller with independent `r1, r2 ~ U(0,1)`, `r1 > 0`, then transform standard normal samples to `mu + sigma*z`.
- CLT approximation route: sum independent uniforms and standardize only for rough normal sampling, not final tail-sensitive claims.
- Library route: use functions such as uniform, normal, exponential, binomial, and Poisson samplers only after a parameterization audit.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| pseudo-random generator | Produces reproducible base randomness | Must record seed and software |
| cumulative probability table | Samples empirical discrete outcomes | Probabilities must sum to 1 after rounding |
| inverse CDF | Samples continuous or discrete variables from a known CDF | Needs inverse formula or numerical quantile |
| Box-Muller transform | Generates normal samples from two uniforms | Requires `r1 > 0`; validate mean/variance |
| CLT uniform-sum approximation | Rough normal-like sampler | Weak in tails; avoid for risk/reliability |
| built-in sampler | Reduces implementation burden | Must audit parameter convention |
| empirical sampler/bootstrap | Samples from observed data | Requires representative historical data |
| distribution diagnostic | Checks generated samples match intended law | Use moments, histogram/QQ, KS/chi-square, or quantile checks |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Seed | Fix for reproducibility; vary for robustness | Same seed reproduces results; multi-seed spread recorded |
| Support/domain | Generated samples must obey physical and mathematical bounds | Min/max and invalid-sample count |
| Distribution parameters | Record meaning and units, such as `mu`, `sigma`, rate, scale, trials, probability | Compare empirical moments/quantiles to intended values |
| Exponential parameter | Check whether software uses mean/scale or rate `lambda` | Verify theoretical mean and variance from generated samples |
| Normal parameter | Check whether the second parameter is standard deviation or variance | Empirical standard deviation check |
| Matrix/output shape | Sampling dimensions must match scenario design | Shape assertion and row/column meaning |
| Dependence | Independent sampling is a model assumption | Correlation/rank check or Copula/joint sampler |
| Frequency table | Convert frequencies to cumulative intervals and record boundary convention | Sum-to-one check and generated-frequency audit |

## Validation Requirements
- Sampling contract table: variable, distribution, parameter source, support, sampler, seed, and sample count.
- Parameterization audit for every built-in sampler used in code.
- Empirical distribution check: mean, variance, support, and at least one quantile or goodness-of-fit check for important variables.
- Cumulative-table audit for empirical discrete samplers: intervals cover `[0,1]`, no outcome is unreachable, and boundary rules are deterministic.
- Tail check for rare-event, reliability, shortage, or risk problems.
- Independence/dependence check for multi-variable simulation.
- Reproducibility check: rerun with same seed and compare outputs; repeated seeds when the decision ranking is sensitive.
- Integration with the Monte Carlo card: downstream estimator still needs convergence and uncertainty evidence.

## Failure Signs
- Simulation code calls `rand`, `normrnd`, `exprnd`, `binornd`, or `poissrnd` with unexplained parameters.
- Generated samples violate domain constraints, such as negative demand, impossible probability, or impossible count.
- Cumulative-probability intervals have gaps, overlaps, rounding loss, or a missing final interval.
- Paper claims a distribution but generated moments or quantiles do not match it.
- Exponential rate/scale, normal variance/standard deviation, or binomial trial/probability parameters are confused.
- Tail results are based on small samples or rough normal approximations.
- Correlated scenario variables are sampled independently and produce unrealistic combinations.

## Repair Moves
- Add a sampling contract table before the simulation section.
- Replace rough normal approximation with a tested library sampler or Box-Muller transform, then validate samples.
- Use inverse CDF or empirical quantile sampling for custom one-dimensional distributions.
- Rebuild frequency-table sampling with cumulative probabilities and test generated frequencies against the input table.
- Add parameterization unit tests for built-in sampler calls.
- For correlated variables, retrieve a dependence-model card such as Copula Monte Carlo or use joint empirical resampling.
- If samples violate constraints, switch to a truncated distribution, rejection/repair rule with reported rejection rate, or deterministic bound.
- Increase sample count and add multi-seed checks if distribution diagnostics are unstable.

## Paper Usage
- Explain random-variable generation as a short sampling contract, not a long programming tutorial.
- Put formulas only for nontrivial transformations such as inverse CDF or Box-Muller; for built-ins, report parameter meanings and validation.
- Do not write that pseudo-random numbers are "true random"; write that they are reproducible pseudo-random samples validated for the simulation.
- When using software functions, cite the distribution and parameter convention in prose/table, not only code.
- Keep random-sampling validation separate from final Monte Carlo estimator validation.

## Source Materials
- Useful sections: pseudo-random number explanation, inverse-transform method, CLT normal approximation, Box-Muller transform, common distribution sampler examples.
- Reliability: medium teaching source; promotes sampling discipline and validation requirements, not advanced RNG theory.

## Confidence
- medium: solid for contest-level sampling obligations and common failure signs; advanced random-number testing, variance reduction, and high-dimensional dependence require additional cards.
