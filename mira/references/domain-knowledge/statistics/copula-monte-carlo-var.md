# Knowledge Card: statistics/copula-monte-carlo-var

## Tags
- Copula
- Monte Carlo
- Value at Risk
- VaR
- risk quantile
- tail dependence
- dependence modeling
- marginal distribution
- joint distribution
- probability integral transform
- Kendall tau
- Spearman rho
- Gaussian Copula
- Student-t Copula
- Gumbel Copula
- Clayton Copula
- Frank Copula
- 蒙特卡洛
- 风险价值
- 相依结构
- 边际分布
- 联合分布
- 厚尾
- 尾部相关
- 分位数
- 置信水平
- 事后检验

## Problem Patterns
- A contest problem asks for risk, reliability, loss, shortage, overload, extreme event probability, or quantile-based safety threshold.
- Several random variables are correlated, but their marginal distributions differ or show skewness, heavy tails, or nonlinear dependence.
- Linear correlation and multivariate normal assumptions look too weak for tail events.
- The target result is a distribution, quantile, exceedance probability, or scenario-based risk metric rather than a single deterministic forecast.
- Available historical or simulated data can be converted into empirical marginal distributions and rank dependence.

## Applicability Conditions
- Each variable has enough observations, empirical samples, or defensible parametric distributions to estimate a marginal CDF.
- The dependence structure materially affects the aggregate risk or decision.
- The model can sample joint scenarios and map them back through inverse marginal distributions.
- A baseline such as independence, Gaussian/linear correlation, empirical bootstrap, or direct historical quantile is available.
- The paper can report seed, sample count, confidence level, tail direction, and coverage/backtest logic.

## Contraindications
- Do not use Copula only as decoration when variables are nearly independent or the final result is insensitive to dependence.
- Do not use VaR when the problem needs expected tail loss, maximum loss, or constraint feasibility across all scenarios unless VaR is explicitly justified.
- Do not fit a complex Copula when sample size is too small to estimate tail dependence credibly.
- Do not claim that one Copula family is universally best; choose by fit, tail behavior, and validation.
- Do not use normal marginals by habit when empirical data show heavy tails or skewness.

## Algorithm Core
- Build the stochastic risk model in four layers:
  1. define loss/risk variables, aggregation formula, weights, units, and tail direction;
  2. fit or estimate each marginal distribution `F_i`;
  3. transform observations to `u_i = F_i(x_i)` and fit/select a Copula `C(u_1, ..., u_n)`;
  4. sample joint uniform scenarios from `C`, transform by inverse marginals `x_i = F_i^{-1}(u_i)`, aggregate losses, and compute quantiles.
- For bivariate conditional simulation, sample `u` and `w` from uniform variables, solve a conditional Copula inverse for `v`, then map `u, v` through inverse marginals.
- Treat VaR as a quantile estimate: for loss `L`, `VaR_alpha` is the threshold whose empirical exceedance probability is near the target tail probability.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| marginal fitting | Estimate each variable's CDF separately | Compare candidate distributions or empirical CDF before choosing |
| probability integral transform | Map observations to uniform scores | Requires continuous or tie-handled marginals |
| rank dependence | Estimate monotone dependence with Kendall tau or Spearman rho | More robust than Pearson for nonlinear monotone dependence |
| Gaussian Copula baseline | Linear-correlation dependence benchmark | Weak for tail dependence; useful as a baseline |
| Student-t Copula | Captures symmetric tail dependence better than Gaussian | Needs degrees-of-freedom choice or estimation |
| Gumbel Copula | Captures upper-tail dependence | Use only when the relevant tail direction matches the problem |
| Clayton Copula | Captures lower-tail dependence | Use when lower-tail co-movement matters |
| Frank Copula | Captures symmetric dependence with weak tail emphasis | Not ideal for strong tail dependence |
| Monte Carlo sampling | Generate joint scenarios and aggregate risk | Requires seed, run count, convergence, and uncertainty checks |
| coverage/backtest | Compare target alpha with empirical exceedance rate | Required when historical outcomes are available |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Marginal family | Fit candidates such as empirical, normal, t, lognormal, gamma, or problem-specific distributions | Histogram/QQ/KS or likelihood/AIC evidence |
| Copula family | Match tail direction and compare against Gaussian/independence baseline | Log-likelihood/AIC/BIC, visual transformed scatter, coverage error |
| Dependence parameter | Estimate with Kendall tau, Pearson correlation, or MLE as appropriate | Record estimator and parameter value |
| Simulation count `N` | Use enough samples for stable tail quantiles; increase `N` for smaller alpha | Convergence table across at least 2-3 sample sizes |
| Confidence/tail level | State whether alpha is confidence or tail probability and whether lower or upper tail is used | Coverage/exceedance table |
| Random seed | Fix and record seed for reproducibility | Re-run or multi-seed check |
| Aggregation formula | Define weights, signs, and units before simulation | Component contribution or scenario sanity check |

## Validation Requirements
- Marginal fit audit: distribution choice, parameter values, and goodness-of-fit or empirical justification.
- Dependence audit: scatter of transformed uniform variables or rank-correlation table.
- Copula comparison: at least one simple baseline, usually independence or Gaussian/linear-correlation simulation.
- Monte Carlo convergence: risk quantile under multiple sample counts or repeated seeds.
- Backtest/coverage: compare target tail probability with empirical exceedance rate when historical data exist.
- Sensitivity: vary marginal family, Copula family, confidence level, and key weights/parameters.
- Paper claim boundary: state that results are scenario/model-based estimates under selected marginals and dependence structure.

## Failure Signs
- The paper assumes multivariate normality despite heavy-tail or extreme co-movement evidence.
- Marginal distributions are never fitted or justified before Copula simulation.
- Pearson correlation is treated as a complete dependence model for tail-risk claims.
- VaR values are reported without confidence level, tail direction, sample count, or seed.
- Only one Copula family is used and no baseline or backtest is shown.
- The simulated VaR's realized percentile is far from target alpha and no repair is attempted.
- The paper uses a risk quantile as a hard worst-case guarantee.
- Monte Carlo output changes materially with sample count or random seed.

## Repair Moves
- Replace normal marginals with empirical or heavy-tailed marginals when fit diagnostics show skewness or thick tails.
- Add independence/Gaussian baseline and at least one tail-sensitive Copula comparison.
- Use rank dependence and transformed-uniform scatter to diagnose nonlinear dependence.
- Increase simulation count or use repeated seeds until quantile estimates stabilize.
- If VaR underestimates tail loss, test expected shortfall/CVaR or a more conservative confidence level.
- If sample size is weak, downgrade claims and use scenario sensitivity instead of precise tail-dependence conclusions.
- If tail direction is mismatched, switch among Gumbel/Clayton/t-Copula or explain why the selected family matches the domain.

## Paper Usage
- Explain Copula in contest terms as "separate each variable's marginal distribution from their dependence structure."
- Present the workflow as a small flowchart: marginal fit -> uniform transform -> Copula fit -> Monte Carlo scenarios -> quantile/backtest.
- Include a table of marginal parameters, Copula parameters, simulation settings, VaR/quantile results, and coverage error.
- Avoid finance-only wording when the contest problem is nonfinancial; translate VaR to risk threshold, shortage quantile, overload quantile, or reliability bound.
- Do not write "true risk" or "worst loss"; write "estimated quantile under the fitted joint distribution."

## Source Materials
- Useful sections: Sklar theorem, Copula families, Kendall tau, marginal distribution fitting, Copula Monte Carlo sampling, VaR result table, post-hoc coverage comparison.
- Reliability: medium. The source is a finance method paper; use its workflow and validation ideas, not its case-specific conclusion.

## Confidence
- medium: strong for correlated-risk Monte Carlo modeling and contest-paper validation structure; Copula family choice must be revalidated for each dataset and domain.
