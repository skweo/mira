# Knowledge Card: statistics/risk-decision-monte-carlo

## Tags
- Monte Carlo
- risk decision
- stochastic decision
- investment decision
- project evaluation
- NPV
- net present value
- cash flow simulation
- discount rate
- information value
- imperfect information
- threshold policy
- waiting option
- real option
- policy comparison
- common random numbers
- 风险决策
- 风险投资
- 项目投资
- 净现值
- 现金流
- 折现率
- 购买情报
- 信息价值
- 等待策略
- 技术改造
- 阈值策略
- 策略比较

## Problem Patterns
- A contest problem asks for a recommendation under uncertain market demand, cost, loss, capacity, price, service level, policy effect, or risk event.
- Candidate decisions include invest/not invest, wait, buy information, expand capacity, upgrade technology, choose a threshold, or combine mutually compatible actions.
- The objective is expected profit, NPV, cost, risk-adjusted benefit, shortage loss, or another scenario-dependent value.
- Several random inputs interact through a computable recurrence, but closed-form decision-tree or Bayesian integration is too complex.
- The recommendation may change under risk preference, discount rate, threshold choice, or distribution assumptions.

## Applicability Conditions
- Random variables, distributions, support, units, and dependence assumptions can be stated or stress-tested.
- Every candidate policy can be evaluated on the same scenario table or paired random stream.
- The payoff/cost/cash-flow recurrence is explicit enough to audit on individual scenarios.
- Mutually exclusive and combinable actions are known before running simulation.
- The paper can report sample count, seed, policy thresholds, risk metrics, and sensitivity results.

## Contraindications
- Do not use Monte Carlo decision simulation when deterministic calculation or exact dynamic programming gives the required answer at contest scale.
- Do not rank policies from independent random samples when objective differences are small.
- Do not make a final risk recommendation from mean value alone when downside probability or risk preference matters.
- Do not use arbitrary subjective distributions without sensitivity or scenario justification.
- Do not call a coarse threshold scan "global optimization" unless a stronger search or certificate supports it.

## Algorithm Core
- Scenario-policy route:
  1. define decision set, mutually exclusive actions, and allowed combinations;
  2. define random inputs and generate a common scenario table with recorded seed;
  3. compute state/cash-flow/payoff recurrence for each policy under each scenario;
  4. scan policy parameters such as information threshold, waiting threshold, capacity level, or discount rate;
  5. aggregate mean objective plus risk metrics and choose the policy only after convergence and sensitivity checks.
- Information-purchase route:
  - model the signal as imperfect information with cost and correlation/accuracy;
  - choose an action by a threshold rule on the signal;
  - compare net value after information cost with no-information and perfect-information baselines when feasible.
- Waiting-option route:
  - shift timeline, investment timing, market share/capacity state, terminal value, and discounting consistently;
  - compare immediate action vs waiting under the same underlying market scenarios.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| common scenario table | Fair policy comparison | Required when ranking stochastic policies |
| cash-flow recurrence | Converts random states into objective values | Must include timing, units, and terminal terms |
| threshold scan | Optimizes information, waiting, or capacity trigger | Check grid resolution and edge optima |
| discount-rate grid | Tests risk/financing sensitivity | Report switching points when recommendation changes |
| imperfect signal model | Represents paid forecasts or tests | Needs accuracy, correlation, or confusion matrix |
| combined-policy enumerator | Tests feasible action combinations | Must respect mutual exclusivity |
| downside-risk summary | Shows more than expected value | Use probability of loss, quantile, CVaR, or spread |
| paired difference analysis | Reduces ranking noise | Compare policy value differences scenario by scenario |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Sample count `N` | Choose by convergence of policy ranking and risk metrics, not habit | `N` ladder and multi-seed spread |
| Random seed | Fix for reproducibility and vary for robustness | Same seed reproduces tables; repeated seeds keep ranking |
| Discount rate | Treat as a sensitivity parameter unless prescribed | Grid or switching-point analysis |
| Threshold grid | Include enough resolution around the maximum or decision boundary | Neighboring-threshold audit |
| Information cost | Subtract before comparison; report gross and net value if useful | No-information and optional perfect-information baseline |
| Signal accuracy/correlation | Tie to data, mechanism, expert assumption, or sensitivity band | Sensitivity and calibration check |
| Cash-flow timing | Cash flow at start/end of period changes NPV | One-scenario ledger audit |
| Risk metric | Match stakeholder risk preference | Downside probability/quantile table |

## Validation Requirements
- Policy contract: candidate actions, allowed combinations, threshold variables, and objective definition.
- Random-input contract: distributions, parameter sources, dependence assumptions, seed, and sample count.
- Common-random-number comparison for policy ranking, or a documented reason why it is not possible.
- Cash-flow/payoff audit on representative scenarios, including timing and units.
- Convergence and repeated-seed checks for final policy ranking and selected thresholds.
- Sensitivity to discount rate, threshold grid, distribution parameters, and information accuracy.
- Risk profile beyond the mean when the recommendation concerns investment, safety, shortage, or loss.
- Baseline comparison: no-action/no-information, deterministic expected-value case, analytic toy case, or perfect-information upper bound when feasible.

## Failure Signs
- The paper reports one expected NPV/cost table and never shows uncertainty, convergence, or downside risk.
- Policies are simulated with different random streams and small differences decide the winner.
- Information purchase is modeled as free, perfect, or uncalibrated.
- Waiting ignores delayed cash-flow timing, opportunity cost, market-share loss, or horizon shift.
- Thresholds appear only as table headers with no explanation of how they were chosen.
- A combined strategy is evaluated without listing incompatible action pairs.
- Discount-rate or distribution sensitivity flips the recommendation and no switching explanation is given.
- The final wording says "optimal" although only a stochastic grid search was performed.

## Repair Moves
- Re-run all policies on a shared scenario table and compare paired differences.
- Add mean, standard error or seed spread, downside probability, and key quantiles to the result table.
- Add threshold refinement around the current best policy and report edge cases.
- Add no-information, no-action, and perfect-information or deterministic baselines.
- Add discount-rate and distribution sensitivity; if the winner changes, state policy regions instead of one universal recommendation.
- Build a one-scenario ledger table to catch cash-flow timing and unit mistakes.
- If threshold policy is complex, switch to dynamic programming, stochastic programming, or simulation optimization when scale allows.

## Paper Usage
- Present the method as "scenario simulation plus policy comparison", not as a black-box Monte Carlo label.
- Use one concise workflow figure: random input generation -> scenario table -> policy recurrence -> threshold scan -> risk/sensitivity audit.
- Include a result table with policy, threshold, mean objective, risk metric, sensitivity, and recommendation.
- Phrase claims as "best among tested policies under stated assumptions" unless a stronger optimizer or proof is provided.
- Keep detailed simulation code and large scenario tables as separate result files; keep the main text focused on policy logic and validation.

## Source Materials
- Useful sections: risk-variable setup, NPV cash-flow recurrence, technology-upgrade decision, information-purchase threshold scan, waiting decision, combined strategies, discount-rate table.
- Reliability: medium. The source is an older Chinese case paper; use its scenario-policy workflow and validation warnings, not its case-specific numeric conclusions.

## Confidence
- medium: strong for contest-level stochastic decision simulation structure; advanced finance valuation, formal real-options pricing, and stochastic programming need additional specialized cards.
