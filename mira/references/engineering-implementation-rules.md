# Engineering Implementation Rules

Use this reference when a contest-final paper should convert mathematical
results into an executable enterprise or engineering workflow. The goal is to
make the conclusion usable by a real operator, manager, or system owner.

## Implementation Targets

For high-award `contest_final` output, convert final recommendations into at
least one of these deliverables when the problem has an operational setting:

| target | purpose | typical section |
|---|---|---|
| `workflow` | step-by-step execution flow | `企业执行流程` |
| `role_matrix` | who does what and when | `岗位分工与责任` |
| `data_requirements` | what data must be collected or updated | `落地数据需求` |
| `decision_rule` | how to use the model output in daily decisions | `决策规则与触发条件` |
| `exception_handling` | what to do when assumptions fail or inputs are abnormal | `异常处理机制` |
| `kpi_review` | how to monitor effect after deployment | `实施效果评估` |

## Minimum High-Award Behavior

Do not end with only formulas and final numbers. Add a short implementation
block that answers:

1. Who executes the recommendation?
2. What data are needed before execution?
3. What is the step-by-step operating procedure?
4. What threshold or trigger changes the action?
5. What abnormal cases require manual review or re-sampling?
6. What KPI verifies the recommendation after deployment?
7. What model inputs should be updated in the next cycle?

## Preferred Artifacts

- `planning/implementation_plan.md`
- `results/tables/implementation_checklist.csv`
- `results/tables/kpi_review_plan.csv`

Suggested `implementation_checklist.csv` columns:

```csv
step,owner,input_data,action,model_output_used,trigger,exception_rule,output_record
```

Suggested `kpi_review_plan.csv` columns:

```csv
kpi,definition,baseline,target,review_frequency,data_source,repair_action
```

## Writing Pattern

Use an operations-ready structure:

1. **输入**: list data sources, collection frequency, and required precision.
2. **决策**: state the model rule, threshold, or table lookup.
3. **执行**: give a numbered workflow or checklist.
4. **异常**: state manual-review, re-sampling, or fallback rules.
5. **复盘**: state KPIs and update cycle.

Good phrasing:

> 企业可将本文策略嵌入来料检验流程：质检员先按表 12 的抽样规则获得批次
> 次品率后验区间，系统再根据表 15 的策略阈值选择检测动作；若后验上界
> 超过 12% 或边际利润差小于 0.2 元，则进入复抽样和人工复核流程。

Weak phrasing:

> 本模型具有较强实用性，可为企业提供参考。

## Scope Control

Do not invent unavailable factory systems, legal obligations, or management
facts. If the problem statement lacks real deployment context, write a scoped
generic workflow and mark required data as assumptions or future collection
items.
