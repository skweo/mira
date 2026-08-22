# Prose Density Rules

Use these rules when drafting or revising a `contest_final` Chinese
mathematical modeling paper.

## Core Rule

Every main-body paragraph must do at least one real job:

| Job | Acceptable evidence |
|---|---|
| Define | variable, parameter, unit, state, constraint, objective, input/output |
| Derive | equation, transformation, proof step, bound, complexity expression |
| Solve | algorithm step, operator, stopping rule, solver status, runtime, scale |
| Report | result value, table, figure, route/strategy ledger, ranking |
| Validate | baseline, sensitivity, residual/error, convergence, robustness, feasibility check |
| Interpret | decision implication tied to a result, figure, table, or named scenario |
| Limit | exact assumption, failure condition, data limitation, parameter sensitivity |

If a paragraph only announces structure, praises the method, or repeats the
question, delete it or merge it into a paragraph that contains evidence.

## Sentences To Remove Or Rewrite

Rewrite these only when they are immediately followed by specific evidence:

- `本文首先...然后...最后...`
- `综上所述`
- `通过上述分析`
- `由此可见`
- `可以看出`
- `具有一定意义`
- `较好地`
- `有效地`
- `合理性和可行性`
- `为后续研究提供参考`
- `结果较为理想`
- `验证了模型的有效性`

Preferred replacement:

```text
claim -> number/equation/table/figure/citation -> why this changes the contest decision
```

## Model Evaluation

Do not write generic evaluation such as:

- `模型简单、适用性强`
- `缺点是忽略了一些因素`
- `未来可进一步研究`

Use this form instead:

```text
Strength/limitation -> exact condition -> evidence -> repair or use boundary
```

Examples:

- `该 DP 的优势不在于形式简单，而在于状态数由 2^n 压缩为 K·n·T；表 X 给出 n=... 时的运行时间。`
- `该结论依赖固定成本 M_fixed；当 M_fixed 在 [a,b] 内变化时推荐 K 不变，超过 b 后需切换方案。`

## Paper-Visible Boundary

Do not let internal agent workflow leak into the final paper body:

- tool/agent names such as Mira, Codex, Claude, DeepSeek;
- local paths, script names, JSON ledgers, check/gate/report names;
- phrases such as `PASS_WITH_WARNINGS`, legacy approval labels, `审计报告`, `门禁`, `本轮优化`.

Translate internal evidence into paper-native language. For example:

| Internal wording | Paper wording |
|---|---|
| `result_ledger.json 中记录...` | `各问题结果由同一组计算输出统一复核...` |
| `通过 result_quality.py` | `对目标函数分量、约束满足和灵敏度进行了复核...` |
| `为通过门禁补充图表` | omit; add the actual figure/table and explain the result |

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\prose_density_gate.py `
  --root <project-root> `
  --write-report checks\prose_density_report.md `
  --write-json checks\prose_density_report.json
```

Findings return to paper. For `contest_final`, unresolved WARN findings remain
visible as `PASS_WITH_WARNINGS` and should guide revision, but they do not
block the paper stage. An explicit `FAIL` remains blocking.
