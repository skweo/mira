# Contest Final Writing Contract

Use this contract before drafting or revising a `contest_final` Chinese mathematical modeling paper. It supplements `paper-template-zh.md` and `template-writing-rules.md`.

Also read `template-writing-rules.md`, `abstract-layout-rules.md`,
`derivation-density-rules.md`,
`derivation-logic-rules.md`, `prose-density-rules.md`,
`figure-table-rules.md`, and `validation-patterns.md` before writing a
comparison-quality final paper.
Excellent-paper examples are genre and evidence-placement references, not model
templates: never copy their problem-specific assumptions, mechanisms, methods,
values, routes, or prose into a different problem without independent fit and
validation.

## Format Policy

- Final delivery must be PDF unless the user asks otherwise.
- Use LaTeX or Typst for `contest_final`; Markdown or ReportLab output is a draft format, not final-comparison quality.
- Prefer the official or closest available contest template. Search
  user-provided and local template catalogs by contest key, then copy or adapt
  the minimal required template into `paper/`; the project must not depend on a
  fixed external checkout path.
- For high-award comparison targets, use official-style front matter even when the exact template is unavailable: team-number placeholder, problem-number row, formal title, abstract, keywords, and page numbering. A generic article title page is not enough.
- Keep source files under `paper/`, with section files under `paper/sections/` for anything longer than a short draft.
- Compile from source and record the command in `checks/compliance_report.md`.

## Adaptive Paper Architecture

Create `planning/paper_strategy.json/md` after result freeze and before drafting.
Choose the dominant argument from the evidence shape, not from a house style:

| Architecture | Lead with | Best fit |
|---|---|---|
| `mechanism-first` | mechanism, state evolution, and causal structure | physical, dynamic, control, or process-mechanism problems |
| `decision-first` | decision object, objective, constraints, and tradeoffs | optimization, routing, scheduling, allocation, or policy selection |
| `evidence-first` | data credibility, identifiable structure, and empirical evidence | prediction, classification, evaluation, or data-rich inference |
| `theorem-first` | definitions, propositions, proof chain, and bounds | proof-led, analytic, or exact-structure problems |
| `scenario-first` | scenario space, simulation design, and contrast | stochastic simulation, intervention, risk, or policy experiments |

Hybrid structures are allowed when the supporting architecture has a named
role. Record the thesis, contributions, section roles, dependencies, evidence,
keep/delete decisions, paragraph rhythm, terminology boundaries, and internal
language exclusions. Run `paper_strategy_gate.py` at plan, draft, and verify
stages. Do not judge architecture quality by section-title keywords alone.

## Legacy Multi-Question Example

The following question-by-question structure is one fallback for loosely coupled
multi-question papers. It is not Mira's default and must not override the
selected paper strategy or its argument dependencies:

1. 封面或参赛信息页（如模板要求）
2. 摘要、关键词
3. 目录（papers over 15 pages, or any contest-final comparison paper）
4. 问题重述
5. 问题分析（按子问题展开）
6. 模型假设
7. 符号说明
8. 问题一模型建立与求解
9. 问题二模型建立与求解
10. 后续问题模型建立与求解（按实际题面数量）
11. 灵敏度分析、误差分析或鲁棒性检验
12. 模型评价、局限性与推广
13. 参考文献

Do not compress all subquestions into a generic "模型建立" section when the contest asks multiple tasks.

## Per-Question Minimum

Each subquestion section must contain:

| Part | Requirement |
|---|---|
| Task restatement | State input, output, objective, constraints, and dependency |
| Difficulty and transformation | Name what makes the task nontrivial and the mathematical object it becomes |
| Model rationale | Explain why this model fits the subquestion |
| Variables and parameters | Define symbols, units, and parameter sources |
| Mathematical formulation | Objective/equations/constraints detailed enough to implement |
| Solver or algorithm | Steps, stopping criteria, packages/tools, complexity, runtime/solver status, and scale rationale |
| Results | Tables and figures placed near the paragraphs that use them |
| Validation | Constraint audit, baseline comparison, sensitivity, seed robustness, error analysis, or lower-bound comparison |
| Interpretation | Explain what the result means for the original contest question |

## Modeling Route Rules

Before dense formulas, algorithms, or large result tables, the paper must give a
judge-readable modeling route. The route should not be a generic flowchart
caption; it must explain the decision path:

```text
题目任务 -> 输入/输出 -> 建模转化 -> 变量/目标/约束或状态 -> 求解路线 -> 结果证据 -> 验证解释
```

For multi-question papers, include an overall route section such as `本文技术路线`
or `建模思路`, then make each official subquestion expose a compact route card:

| Route item | Question-level requirement |
|---|---|
| Input/output | Name the data, state, or measurements entering the model and the answer produced |
| Transformation | State how the real task becomes optimization, prediction, evaluation, simulation, mechanics, DP, or another mathematical object |
| Model | Name variables, objective/constraints, equations, indicators, or state transition used for this question |
| Solver | State exact, heuristic, simulation, numerical, regression, or decomposition route and why it fits the scale |
| Result evidence | Name the table, figure, final value, schedule, ranking, policy, or parameter set that answers the question |
| Validation | Name the feasibility audit, baseline, sensitivity, residual, convergence, robustness, or limiting-case check |

Use a technical route diagram or route table when it helps the reader see
dependencies between questions or model layers. Do not add decorative route
figures when a concise table communicates the route more clearly.

For high-award comparison, keep the order above unless the selected paper
strategy requires a different dependency order. Any reordering must still make
the difficulty, transformation, model rationale, formulation, solver route,
result evidence, validation, and interpretation easy to locate.

For mechanism, simulation, physical, engineering, control, traffic,
communication, or process problems, explain the real process before dense
formulas; state each simplification and why it is acceptable; separate shared
mechanism preparation from per-question optimization or evaluation; and report
parameter-estimation evidence plus validation metrics when parameters are
fitted. Compare with a simpler mechanism or empirical baseline when feasible.

For strategy, stochastic, DP, Monte Carlo, or game-theory questions, the
per-question section must additionally expose the decision-system contract
(state, action, resource, exogenous event, terminal objective), state-space
reduction rationale, DP/game/simulation applicability, scenario statistics or
risk metrics, and a compact final strategy ledger.

For DP, enumeration, heuristic search, Monte Carlo, grid search, or
solver-backed optimization, each solver section must state the realized scale
(state/strategy/variable/constraint/sample count), time/space complexity or
operation count, runtime or solver-status evidence, and any pruning,
decomposition, state compression, or small-scale waiver. Use
`references/algorithm-complexity-efficiency-rules.md` when the algorithm route
is nontrivial.

For all substantial later sections, keep mathematical continuity. Results
credibility, solver efficiency, sensitivity, assumption relaxation, engineering
implementation, innovation/contribution, and discussion sections must not become
long prose-only blocks. Add a display equation, quantitative rule, complexity
expression, sensitivity/baseline table, validation figure, changed-state
equation, KPI definition, or explicitly bind the paragraph to an earlier
formula/table/figure. Use `references/derivation-density-rules.md` when the
second half of the paper feels thin.

For core formulas, keep derivation logic explicit. Symbols should be defined
before use; objectives and constraints should name their problem source; jump
phrases such as `显然`, `易得`, and `由此可得` should be replaced by the missing
transformation; strong claims such as `最优`, `收敛`, `鲁棒`, and `显著` require
proof, bounds, solver gap, repeated experiments, or sensitivity evidence. Use
`references/derivation-logic-rules.md` when formula count looks adequate but
the mathematical chain feels brittle.

When sensitivity evidence contains a policy switch, regime change, or decision
threshold, use `references/sensitivity-threshold-rules.md` and report the scan
range, threshold, and mechanism. When a strong optimality, dominance,
monotonicity, or boundary claim needs proof scope, use
`references/theoretical-threshold-rules.md` and connect its condition back to
the computed result.

## Abstract Rules

- Write the abstract last.
- Keep title, abstract body, and keywords on a standalone first page, followed
  by `\newpage` or `\clearpage` before contents or the main body.
- Cover every subquestion with method and key result.
- For multi-question papers, use one short overview paragraph plus one
  paragraph per official subquestion; do not merge all question summaries into
  one long paragraph.
- Start each subquestion paragraph with a bold label, for example
  `\textbf{针对问题一：}`.
- Include precise numbers from `results/result_report.md` or `results/frozen_numbers.json`.
- Do not include formulas, internal file names, or unsupported claims.
- Use 3-5 keywords.
- For multi-question contest-final papers, treat the abstract as a compressed
  result ledger: each official question should expose model, method, final
  number/table, and conclusion.

## Paper-Visible Boundary

Contest-final paper prose is for judges, not for agent handoff. Keep internal
workflow evidence in `planning/`, `checks/`, `results/`, or separate support
files; translate it into paper-native claims before it enters the main body.

Do not write these in the main paper body:

- agent, model, or tool names such as Mira, Codex, Claude, DeepSeek, or AI;
- internal constraints such as "未联网查答案", "没有使用公开答案", or user
  testing intentions;
- local file paths, script names, result-ledger names, frozen-number JSON names,
  check/gate/report names, or command paths;
- audit/process language such as "门禁通过", "结果账本检查正文", or "终稿冻结";
- thought-process narration such as "为了通过深度门禁补充..." or "本轮优化".

Allowed transformations:

| Internal artifact | Main-body wording | Supporting-file wording |
|---|---|---|
| `results/frozen_numbers.json` | "最终指标由同一组仿真结果统一复算" | support-file list may name the JSON |
| `planning/result_ledger.md` | "各问题结论保持同一参数体系和约束口径" | support manifest may list the ledger |
| `scripts/solve_x.py` | "采用数值仿真与边界复核求解" | support manifest may list the code module |
| "没有查公开答案" | omit from paper; record in delivery brief | never use as a contest-paper claim |

Before final delivery, `award_review_gate.py` may scan the paper body for
internal workflow/meta-process leakage and other internal quality-floor issues.
Any leakage hit returns to paper rewriting. Its diagnostic output is not an
award score, award-band estimate, or external-competitiveness claim.

## Figures and Tables

- Before paper drafting, read `planning/presentation_budget.md`. If it is
  missing for a `contest_final`, return to implementation and run
  `scripts/plan_presentation_budget.py`.
- Place figures/tables in the section where the claim is made.
- Do not dump all figures at the end of the body.
- Every figure/table must have a self-contained caption and be referenced in the surrounding text.
- Data figures must come from generated result data. Non-data diagrams must have editable sources when possible.
- Final-paper tables should prefer three-line style. In LaTeX, use `booktabs`
  with `\toprule`, `\midrule`, and `\bottomrule`; avoid vertical rules and
  repeated `\hline` unless the official template requires them.
- Save long route, schedule, assignment, or load tables as separate result files; the main text still needs concise summary tables.
- Save long strategy traces as separate result files; the main text must still show the actionable route/action/resource ledger and the risk or payoff summary.
- Choose figures/tables by evidence role: data structure, model logic, result evidence, or validation evidence.
- For a four-question high-award comparison paper, aim for at least one useful visual for data/problem structure, one for model/algorithm logic, one or more result visuals, and one or more validation/sensitivity visuals. Six useful figures is a lower bound; eight to twelve is often a stronger target when artifacts support it.
- If the generated paper has fewer useful figures than the budget or has weak
  citation binding, do not compensate by prose expansion alone; return to
  implementation for visuals or modeling for real method/source support.
- Figure labels must be readable in the compiled PDF, in Chinese when possible, and caption text must state the conclusion the reviewer should take away.
- Do not insert every generated plot. Insert the plots that answer a subquestion, justify a model choice, prove feasibility, or validate a claim.

## References For Strong Papers

- For high-award comparison targets, cite real support for every major method,
  parameter source, external dataset, software/toolbox claim, or domain
  assumption that needs backing.
- Do not treat any fixed reference count as a quality target. A short precise
  bibliography is better than a long decorative one.
- The citation-binding expectations should meet `planning/presentation_budget.md`.
- Do not pad references. Each listed reference must either be cited near the
  claim it supports or recorded in `planning/citation_binding.md` /
  `results/tables/citation_binding.csv` with its support scope.
- If source support is weak, return to method-context writing or parameter/data
  provenance repair instead of only enlarging the bibliography.

## Claim Wording

- Use "最优" only when the model and solver support exact optimality in the stated scope.
- For heuristic, decomposition, stochastic, or local-search results, use language such as "当前搜索得到的较优方案", "实验中最优方案", or "本文算法得到的可行最优候选".
- For forecast-based decisions, state that the decision is conditional on the forecast model and include the forecast validation evidence.
- For parameter estimates, state numerical precision only after discussing data noise, solver tolerance, convergence, residuals, or sensitivity.
- For data-scarce recommendations, place the governing caveat beside the result:
  name the analogy source, sample range, elasticity or transfer assumption,
  target service level, and sensitivity range that bound the conclusion.

## Evaluation, Extension, And Use

Write model evaluation as concrete engineering judgment: identify strengths
that are tied to the task and evidence, limitations tied to assumptions, data,
discretization, or computation, specific repairs for those limitations, and
transfer conditions that must be rechecked before reuse. Avoid generic praise
such as "simple and practical" without a mechanism or comparison.

When a strong assumption could change the recommendation, use
`references/assumption-relaxation-rules.md`: introduce the changed parameter or
state, update at least one governing equation, transition, or objective term,
and name the extra data needed. When the result is meant for real operations,
use `references/engineering-implementation-rules.md` to state the executor,
inputs, trigger, exception rule, fallback action, KPI, and review cycle.

If the paper claims nontrivial model, solver, robustness, visualization, or
engineering value, use `references/innovation-contribution-rules.md`. Keep only
three or four evidence-backed contributions and state the ordinary-method
weakness, evidence, benefit, and scope; do not rename routine method use as a
new algorithm.

## References

- Include only real references that were actually used.
- Use method references for major algorithms such as QUBO, TSP/VRP/VRPTW, simulated annealing, integer programming, ARIMA, TOPSIS, AHP, entropy weight, or Monte Carlo.
- Use platform/tool documentation only when the platform materially affected the method or result.
- Do not invent references to make the paper look academic.

## Supporting Result Files

Keep code modules, full tables, constraint audits, parameter sweeps, and
reproducibility commands outside the paper under structured `code/`, `results/`,
and `checks/` paths. Add a compact support manifest only when delivery rules
request one. Never move a main answer out of the body.

When the official task explicitly requests a management letter, policy memo,
short article, data-collection plan, or another audience-specific artifact,
produce it as a named deliverable in the requested form. Its recommendations
must trace to the same frozen results as the technical paper.

## Evidence Density Gate

A contest-final paper should earn every page through derivations, validation,
tables, figures, citations, or implementation detail. Do not use
page count or word count as a completion target. A concise paper can be final
when every official subquestion has a complete model-result-validation chain; a
long paper is weak when extra pages only repeat background, restate audit
language, or add decorative figures.

Use `prose-density-rules.md` and `prose_density_gate.py` to catch filler
transitions, vague model praise, generic evaluation, evidence-light long
paragraphs, and internal agent/workflow terms before final delivery.

For high-award comparison, inspect missing evidence rather than raw length. If
the paper feels thin, name the missing artifact: a subquestion model
specialization, result table, constraint audit, sensitivity scan, proof-scope
statement, citation binding, figure-text loop, or separate support artifact.
Add that artifact and stop. Do not expand text solely because a previous Mira
paper had more pages.
