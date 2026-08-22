# Knowledge Card: statistics/markov-chain-model

## Tags
- Markov chain
- Markov process
- stochastic process
- discrete-time state transition
- transition matrix
- transition probability
- state probability vector
- row-stochastic matrix
- steady state
- stationary distribution
- regular chain
- ergodic chain
- absorbing chain
- absorbing state
- fundamental matrix
- matrix power prediction
- inventory state
- lost sales
- grade structure
- population structure
- inflow
- outflow
- 马尔科夫链
- 马氏链
- 马尔可夫链
- 马尔科夫过程
- 随机动态系统
- 状态转移
- 转移概率
- 转移矩阵
- 状态概率
- 初始分布
- 无后效性
- 齐次马尔科夫链
- 正则链
- 遍历链
- 平稳分布
- 稳态概率
- 吸收链
- 吸收状态
- 基本矩阵
- 库存状态
- 失销概率
- 等级结构
- 调入比例
- 退出比例

## Problem Patterns
- A contest problem asks how a population, customer, product, disease state, credit grade, inventory level, traffic state, membership level, land category, or organizational grade evolves across discrete periods.
- The current state is a plausible sufficient summary for next-period probabilities.
- The output is an `n`-step state distribution, long-run structure, loss probability, absorption probability/time, or a policy that changes transition or inflow proportions.
- Data are available as transition counts/proportions, or the transition probabilities can be derived from a domain distribution or rule.
- A simpler deterministic trend cannot represent random state switching, while a continuous ODE is too aggregate for the discrete state structure.

## Applicability Conditions
- Time is naturally discrete or can be defensibly discretized.
- States are mutually exclusive, collectively exhaustive, and meaningful for the decision.
- A transition matrix can be estimated, derived, or scenario-tested.
- The Markov/no-memory assumption is plausible or can be checked against data.
- Initial distribution and prediction horizon are known.
- The required result matches the chain type: regular-chain steady state, absorbing-chain absorption behavior, or finite-horizon prediction.

## Contraindications
- Do not use a Markov chain when state duration, trend, seasonality, covariates, or hidden variables dominate and are not represented in the state.
- Do not force continuous measurements into arbitrary states without threshold sensitivity.
- Do not report a steady state for an absorbing or reducible chain as if it were a regular-chain equilibrium.
- Do not invent transition probabilities without counts, mechanism, distribution, expert scenario, or sensitivity.
- Do not hide entry/exit, births/deaths, recruitment/retirement, or replenishment rules inside an unexplained matrix.
- Do not use Markov wording for a deterministic recurrence unless transition proportions and probability interpretation are clearly stated.

## Algorithm Core
- Basic finite-state route:
  1. define discrete time step and states `1..k`;
  2. define state probability vector `a(n)`;
  3. estimate or derive transition matrix `P = {p_ij}`;
  4. audit `p_ij >= 0` and row sums equal 1 under row-vector convention;
  5. predict with `a(n+1)=a(n)P` and `a(n)=a(0)P^n`;
  6. compute requested metrics from the predicted distribution.
- Regular-chain route:
  - check that the chain is irreducible/aperiodic or that some finite power of `P` is positive;
  - solve `wP=w`, `sum(w)=1`;
  - verify convergence from different initial distributions before using `w`.
- Absorbing-chain route:
  - reorder states into absorbing and transient groups;
  - write `P` in canonical form with transient block `Q`;
  - compute fundamental matrix `M=(I-Q)^-1`;
  - use `M` for expected time spent in transient states and expected absorption time.
- Derived-transition route:
  - for inventory, queue-state, disease, or genetic examples, derive `p_ij` from the demand, service, survival, birth, or pairing distribution;
  - show at least one row derivation in the paper and audit the full matrix in code.
- Open-structure route:
  - for grade/population systems with exits and inflows, define internal transition matrix `Q`, exit vector `w`, inflow vector `r`, and total change `M(t)`;
  - use `n(t+1)=n(t)Q + R(t)r - exit` or an equivalent audited form before reducing to a stochastic matrix.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| state table | Defines each discrete state and unit | Required before any matrix |
| time-step selection | Sets transition interval | Must match data or decision period |
| transition count table | Estimates `P` from observed moves | Add smoothing or explain zero transitions |
| transition matrix audit | Checks nonnegative probabilities and row sums | Prevents silent algebra errors |
| matrix-power prediction | Computes `n`-step distribution | Keep row/column convention consistent |
| stationary solve | Finds long-run distribution | Only for appropriate chain type |
| absorbing-state split | Separates absorbing and transient states | Required before `M=(I-Q)^-1` |
| fundamental matrix | Computes transient visits and absorption time | Valid only when absorption conditions hold |
| derived probability row | Builds a matrix row from a probability law | Useful for inventory/demand models |
| inflow-outflow ledger | Handles open population or grade structure | Do not bury exits in `P` without explanation |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| State partition | Choose states with domain meaning and enough data per state | Threshold/state-merge sensitivity |
| Time step | Use observed transition interval or contest decision period | Compare alternative aggregation when ambiguous |
| Transition probabilities | Estimate from counts, derive from distribution/rule, or define scenarios | Row-sum, uncertainty, holdout/backtest |
| Zero counts | Smooth only when justified; record rule | Sensitivity to smoothing |
| Initial distribution | Use known initial state, observed proportions, or scenario vector | Normalize and test initial-condition effect |
| Prediction horizon | Match requested years/weeks/generations/periods | Horizon sensitivity and convergence check |
| Steady state | Solve `wP=w`, `sum(w)=1` only after chain-type check | Convergence from multiple initial distributions |
| Absorption metrics | Use `Q` and `M=(I-Q)^-1` for transient behavior | Compare with simulation or finite powers |
| Open-structure inflow `r` | Sum to 1 and connect to recruitment/replenishment policy | Feasibility and target-structure sensitivity |
| Derived demand parameter | Example: Poisson `lambda` for inventory transition rows | Parameter grid and metric sensitivity |

## Validation Requirements
- State contract: states are mutually exclusive, collectively exhaustive, and tied to the contest deliverable.
- Time-step contract: the transition interval is explicit and consistent with data.
- Matrix audit: all entries are nonnegative and each row/column sums to 1 under the stated convention.
- Transition-source audit: include transition count table, fitted distribution, mechanism derivation, or scenario source.
- Markov-assumption audit: justify no-memory; when data allow, compare one-step predictions across history/duration groups.
- Prediction audit: recompute `a(n+1)=a(n)P`; probabilities stay normalized at every horizon.
- Steady-state audit: check chain type, solve `wP=w`, and verify convergence from at least two initial distributions.
- Absorbing-chain audit: identify absorbing states, transient block `Q`, fundamental matrix `M`, expected absorption time, and absorption probabilities when relevant.
- Sensitivity: transition probability perturbation, initial distribution, state thresholds, demand parameter, or inflow ratio.
- Baseline: compare against persistence/no-change baseline, empirical marginal distribution, deterministic flow model, queue/inventory formula, or observed holdout.

## Failure Signs
- "Markov chain" appears but no state table, time step, initial distribution, or transition matrix is given.
- The transition matrix does not sum to 1 by rows/columns, or the convention changes mid-paper.
- Transition probabilities are arbitrary and no sensitivity is shown.
- The chain has absorbing states, but the paper reports a regular-chain steady state.
- The predicted distribution contains negative probabilities or sums not equal to 1.
- The result changes under a small transition-probability perturbation, but the paper reports one vector as certain.
- The process has strong trend/seasonality/history dependence, but the model uses a time-homogeneous first-order chain without testing.
- Entry/exit terms are present in the real system but absent from the model.
- A continuous or high-dimensional state is discretized with unexplained thresholds.

## Repair Moves
- Add a state/time/transition contract table before formulas.
- Re-estimate `P` from transition counts and add a row-sum audit table.
- Add one worked row derivation from data or a probability law.
- If the chain is absorbing, switch from steady-state wording to absorption probability/time analysis.
- If the chain is reducible or periodic, report finite-horizon predictions or class-specific limits instead of one global steady state.
- Add history/dependence checks or expand the state to include duration, season, previous state, or covariates.
- Add transition-parameter and state-threshold sensitivity.
- For open grade/population systems, add explicit inflow and exit vectors and verify total-count balance.
- Validate against holdout periods or a persistence baseline before using predictions in optimization.

## Paper Usage
- Present Markov chains as "state definition + transition source + matrix prediction + chain-type-specific validation".
- Include the transition matrix near the state table and show a row-sum audit.
- Use finite-horizon tables for near-term forecasts and steady-state/absorption tables only when justified.
- Phrase long-run results as model-implied distributions under fixed transition probabilities, not deterministic facts.
- For policy sections, state how the policy changes `P`, inflow `r`, or the state partition, then recompute the metrics.

## Source Materials
- Useful sections: Markov/no-memory definition, `a(n+1)=a(n)P`, regular-chain steady state, absorbing-chain fundamental matrix, piano inventory example, genetic inheritance example, grade-structure model with exit and inflow.
- Reliability: medium teaching source; promotes basic finite-state discrete-time Markov-chain obligations, not advanced stochastic-process methods.

## Confidence
- medium: strong for contest-level Markov-chain forecasting, absorbing-state analysis, inventory-state modeling, and grade-structure evolution; hidden Markov models, MDP, and continuous-time chains require separate specialist cards.

