# Assumption Relaxation Rules

Use this reference when a contest-final paper relies on strong simplifying
assumptions such as perfect detection, independent defects, no dismantling
damage, fixed capacity, fixed sample size, or deterministic parameters. The
goal is to turn limitations into concrete model-extension formulas or decision
impact, not generic "future work".

## High-Value Relaxations

Prefer relaxing assumptions that can change the final recommendation:

1. **Imperfect detection**: false negative, false positive, sensitivity,
   specificity, or a detection confusion matrix.
2. **Dismantling/rework damage**: recovered parts remain good only with a
   survival probability.
3. **Correlated defects**: component defects share supplier, batch, or process
   risk instead of being independent.
4. **Finite capacity/time**: inspection stations, repair lines, queues, or
   delivery deadlines constrain the optimal policy.
5. **Uncertain sample size/confidence**: posterior or robust conclusions depend
   on \(N\), confidence level, or prior.

## Imperfect Detection Template

Avoid reusing `alpha`/`beta` if they already denote test error or confidence.
Prefer:

- \(\eta=\Pr(\text{detect bad}\mid \text{bad})\): sensitivity;
- \(\xi=\Pr(\text{pass good}\mid \text{good})\): specificity.

The observation matrix can be written as

\[
\bm H=
\begin{pmatrix}
\Pr(\text{pass}\mid \text{good}) & \Pr(\text{fail}\mid \text{good})\\
\Pr(\text{pass}\mid \text{bad}) & \Pr(\text{fail}\mid \text{bad})
\end{pmatrix}
=
\begin{pmatrix}
\xi & 1-\xi\\
1-\eta & \eta
\end{pmatrix}.
\]

Then update state probabilities with Bayes' rule rather than treating a passed
part as certainly good. In recursive cost equations, replace "known qualified"
states with posterior-qualified states when \(\eta<1\) or \(\xi<1\).

## Output Artifacts

When feasible, save one or more of:

- `planning/assumption_relaxation_plan.md`
- `results/tables/imperfect_detection_sensitivity.csv`
- `results/tables/assumption_relaxation.csv`
- `figures/imperfect_detection_*.png`

Recommended table columns:

| column | meaning |
|---|---|
| `case` or `qid` | question/case identifier |
| `assumption` | relaxed assumption |
| `parameter` | e.g. sensitivity, specificity, damage rate, correlation |
| `value` | tested value |
| `objective` / `cost` / `profit` | resulting metric |
| `best_policy` | policy under the relaxed assumption |
| `changed_from_base` | whether the original recommendation changes |
| `note` | interpretation |

## Paper Requirements

Include a concrete paragraph or subsection such as:

- `检测误差扩展`
- `假设放宽分析`
- `不完全检测下的状态转移`
- `模型推广`

The text should answer:

1. Which assumption is strongest or least realistic?
2. How would the equation or state transition change?
3. Would the final strategy likely become more conservative, less conservative,
   or require new data?

Good phrasing:

> 若检测存在漏检，则检测合格不再等价于已知合格，状态 \(\K\)
> 应改为后验合格概率状态；因此前端检测的收益会下降，而成品端复检或
> 市场调换风险项会增加。

Avoid weak phrasing:

> 本文未考虑漏检误检，未来可进一步研究。

## Gate Rules

For high-award `contest_final` output:

- If the paper assumes perfect detection, independence, or no damage, it should
  include at least one concrete relaxation paragraph or waiver.
- A generic limitations list without an equation/state-transition direction is a
  warning.
- If the relaxed assumption could plausibly change the decision, state what
  additional data would be needed before executing the original strategy.

