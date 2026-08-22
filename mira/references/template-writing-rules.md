# Template Writing Rules

Use this reference when drafting or revising Chinese mathematical modeling contest papers, especially `contest_final` outputs. It consolidates stable rules learned from local CUMCM-style templates and contest-writing experience notes.

## Source Scope

Promoted from:

- `MathModelAgent/backend/app/config/template.md`
- `MathModelAgent/skills/5writing/templates/zh/cumcm-latex/`

Use these as structure and quality signals only. Do not copy source prose.

## Judge-Facing Priorities

Write for four priorities:

1. Assumptions are reasonable and tied to the task.
2. The model is practical, mathematical, and not needlessly complex.
3. Results are correct, reasonable, and answer every subquestion.
4. Expression is clear, concise, logically ordered, and easy to verify.

When choosing between two valid methods, prefer the one that is easier to justify, implement, validate, and explain under contest time.

## Final Paper Skeleton

Use this section order unless the official template conflicts:

1. 标题
2. 摘要、关键词
3. 目录
4. 问题重述
5. 问题分析
6. 模型假设
7. 符号说明
8. 数据预处理或描述性统计（有数据题时）
9. 按子问题展开的模型建立与求解
10. 灵敏度分析、稳健性分析、误差分析或模型检验
11. 模型评价、改进与推广
12. 参考文献

For multi-question problems, each subquestion should have its own modeling and solution subsection. Do not hide results in a single generic "结果分析" section when the official task asks separate deliverables.

For CUMCM-style papers, the common Word-template scaffold is compatible with
this order: 问题重述, 问题分析, 模型假设, 符号说明, 模型的建立与求解,
模型的分析与检验, 模型的评价/改进/推广, 参考文献. Treat the
Word template as a formatting and section guide, not as content to copy.

## Abstract Contract

- Write the abstract last, after numerical results and validation are frozen.
- Use continuous paragraphs, not bullets.
- The title, abstract, and keywords should occupy a standalone first page in
  `contest_final`; insert `\newpage` or `\clearpage` before contents or the
  first main-body section.
- Paragraph 1: problem background and task framing.
- Middle paragraphs: one paragraph per subquestion, including method/model, construction or computation, and concrete result numbers.
- Each middle paragraph should start with a bold problem label such as
  `\textbf{针对问题一：}` or `\textbf{对于问题二：}`.
- Final paragraph: sensitivity, robustness, model effect, overall conclusion, or practical recommendation.
- Add 4-6 keywords when following the local CUMCM Word scaffold, or 3-5 if the official template asks for fewer; base them on model, method, task, and data type.
- Do not include formulas, internal file paths, unsupported adjectives, or numbers that are absent from `results/`.

## Section Contracts

| Section | Contract |
|---|---|
| 问题重述 | Rewrite the background and list each official task. Do not solve the problem here. |
| 问题分析 | Explain task information, conditions, method route, and subquestion dependencies. Do not place final conclusions here. |
| 模型假设 | Use necessary assumptions only. Each assumption needs a reason and expected influence. |
| 符号说明 | Include symbol, meaning, and unit in a table. Keep notation consistent with formulas, code, tables, and figures; explain important symbols at first use as well. |
| 数据预处理 | State cleaning, transformation, descriptive statistics, and generated visual outputs. |
| 模型建立 | Define variables, objectives, constraints, and derivations. Explain model suitability before formulas and tie the model tightly to the official question. |
| 模型求解 | State algorithm idea, implementation steps, software/backend, parameters, stopping rule, and scale rationale. |
| 结果分析 | Answer the original question directly. Put key numbers in body tables and save exhaustive machine-readable tables as supporting result files. |
| 模型检验 | Use constraint audit, baseline comparison, sensitivity, robustness, error analysis, or plausibility check. |
| 模型评价 | State concrete strengths, limitations, improvements, and applicable scenarios. Avoid empty praise. |
| 参考文献 | Include only real sources actually used. Cite method references for major algorithms. |

## Result And Figure Rules

- Before drafting, decide which key numbers answer each subquestion and which table/figure will present them.
- Place tables and figures near the claim they support.
- Captions must explain what the item proves or compares.
- Surround each inserted figure/table with interpretation: what it shows, why it matters for the subquestion, and which conclusion it supports.
- Use `figures/figure_index.md`, `diagrams/diagram_index.md`, and figure feature summaries from `results/figures_data/` when writing figure interpretation. Do not guess a plot's contents from its filename.
- Use concise summary tables in the body; save exhaustive tables under `results/`.
- Every "optimal", "better", "robust", or "reasonable" claim needs a proof, comparison, audit, sensitivity result, or source-backed explanation.
- Insert only claim-critical or high-value explanatory figures in the main body. Keep useful diagnostics as separate result files or omit them.
- Check figure, table, and equation numbering before delivery. Broken manual numbering is a final-format defect.

## Reference Rules

- De-duplicate references. The same source should not appear twice under different numbering.
- Cite a reference only when it supports a method, parameter, algorithm, dataset/source, or important domain claim.
- Do not add unused references to make the paper look fuller.
- If a method is standard but nontrivial, such as AHP, TOPSIS, ARIMA, integer programming, Monte Carlo, simulated annealing, or VRP/TSP, include a real method reference when possible.

## Common Failure Patterns

- Abstract has no concrete numbers.
- Abstract shares a page with `问题重述` or starts the main body before a page
  break.
- Abstract problem summaries are not separated by question, or the `问题一`
  labels are not bold.
- Assumptions are generic and do not affect the model.
- Formulas appear before the modeling rationale.
- Symbols appear in equations but not in the symbol table.
- Main results exist only in external supporting files.
- Figure/table captions are labels rather than explanations.
- Figure interpretation is guessed from a filename instead of using the recorded figure data or summary.
- References are listed but never used in the text.
- The paper uses advanced terminology without changing the model, solver, validation, or interpretation.
- Template notes, red instructional text, placeholders, or wording like "这里换成" and "关键词1" remain in the final paper.
