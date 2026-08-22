# Theoretical Threshold Rules

Use this reference when a contest-final paper claims a strategy is optimal,
stable, dominated, monotone, threshold-driven, or explainable by marginal
cost/benefit. The goal is to lift pure enumeration into reusable reasoning
without overclaiming proof.

## Proof Targets

Prefer one of these proof targets when the problem allows it:

| target | use when | output |
|---|---|---|
| `local_threshold` | two actions differ by one detect/repair/route/resource decision | inequality such as `benefit >= cost` |
| `dominance` | one policy is never better than another under stated conditions | dominance condition and excluded policy set |
| `monotonicity` | a decision should increase/decrease as a parameter changes | sign argument or derivative/finite-difference table |
| `exchange_argument` | order, matching, route, or scheduling swaps are meaningful | before/after objective difference |
| `boundary_condition` | strategy switches are observed in scans | analytic or semi-analytic switch condition |
| `waiver` | proof is not feasible in contest time | state why enumeration/simulation is the evidence scope |

## Minimum High-Award Behavior

For high-award `contest_final` output:

1. Do not say a policy is "always" or "strictly" optimal unless the scope is
   proved, fully enumerated, or explicitly bounded.
2. When enumeration finds an optimum, add at least one local explanation:
   marginal gain, threshold inequality, dominated action, or switch boundary.
3. When sensitivity scans reveal a strategy switch, explain the switch with a
   cost/probability inequality when feasible.
4. For dynamic programming or exact enumeration, state the exact state/action
   scope and why the search is complete.
5. If no proof is feasible, write a waiver with the evidence scope: exhaustive
   enumeration, solver gap, multi-seed stability, or bounded simulation.

## Preferred Artifacts

- `planning/theory_proof_plan.md`
- `results/tables/theoretical_thresholds.csv`
- `results/tables/dominance_conditions.csv`
- `results/tables/monotonicity_check.csv`

Suggested `theoretical_thresholds.csv` columns:

```csv
question,decision,condition,threshold_value,left_side,right_side,scope,evidence_file
```

Suggested `dominance_conditions.csv` columns:

```csv
question,dominated_policy,dominating_policy,condition,objective_gap,scope,evidence_file
```

## Writing Pattern

Use compact statements:

- `命题`: state the property and its scope.
- `证明`: compare objective terms, probabilities, or state transitions.
- `结论`: state how the property explains the computed policy.

Good phrasing:

> 当新增检测成本小于由调换损失降低带来的期望收益时，检测动作被保留；
> 该阈值与枚举结果中的策略切换点一致，因此全检零件的出现不是偶然搜索结果。

Weak phrasing:

> 枚举结果表明该策略最优，因此选择该策略。

