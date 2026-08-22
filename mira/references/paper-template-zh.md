# Chinese Contest Paper Template

Use this template only after the modeling and result artifacts exist. Do not draft numerical claims before `results/result_report.md` exists. For `contest_final`, also read `contest-final-writing-contract.md` and `template-writing-rules.md`.

## Template Policy

- `contest_final` papers should be written in LaTeX or Typst and compiled to PDF.
- Markdown or ReportLab output is acceptable only for `quick_draft` or local checking drafts.
- Use the official or closest available contest template whenever available.
- For papers longer than 15 pages, include a table of contents unless the official template forbids it.
- A local CUMCM-style Word template may be used as a section and formatting
  reference, but `contest_final` delivery still defaults to LaTeX or Typst PDF
  unless the user explicitly asks for DOCX.

## Recommended Structure

1. 摘要
   - State the problem, model route, main results, and validation in concise Chinese.
   - Include 4-6 keywords for CUMCM-style papers unless the official template specifies otherwise.
   - Source from final results, not from intended plans.
   - For `contest_final`, keep title, abstract, and keywords on a standalone
     first page; insert `\newpage` or `\clearpage` before the main body.
   - For multi-question contests, write one abstract paragraph per official
     subquestion and start it with a bold label such as `\textbf{针对问题一：}`.

2. 问题重述
   - Restate the contest problem in your own words.
   - Identify each subquestion and required output.
   - Source from `planning/problem_analysis.md`.

3. 问题分析
   - Explain the modeling logic for each subquestion.
   - Clarify dependencies among subquestions.
   - Do not introduce unvalidated methods.

4. 模型假设
   - List necessary and simplifying assumptions separately.
   - Explain the reason and possible impact of each assumption.

5. 符号说明
   - Use `planning/symbol_table.md`.
   - Include symbol, meaning, and units in a table.
   - Important symbols should also be explained at first use in the model text.

6. 模型建立与求解
   - Define variables, objective functions, constraints, and algorithms.
   - Keep equations consistent with code and symbols.
   - Mention baseline or backup methods when relevant.

7. 结果分析
   - Use `results/result_report.md` as the primary source.
   - Every result paragraph should name the supporting table, figure, or calculation.
   - Avoid words such as "显著优于" unless supported by a concrete comparison.

8. 灵敏度、误差或稳健性分析
   - Explain how key parameters or data uncertainty affect results.
   - If robustness analysis was not possible, state the limitation explicitly.

9. 模型评价、优缺点与推广
   - Discuss strengths and limitations honestly.
   - Do not add new unsupported claims.

10. 参考文献
   - Include only real sources that were actually used.
   - Do not fabricate bibliographic entries.

## Section Source Map

| Paper section | Primary source artifact |
|---|---|
| 问题重述 | `planning/problem_analysis.md` |
| 问题分析 | `planning/problem_analysis.md`, `planning/modeling_plan.md` |
| 模型假设 | `planning/modeling_plan.md` |
| 符号说明 | `planning/symbol_table.md` |
| 模型建立 | `planning/modeling_plan.md`, `code/` |
| 模型求解 | `code/`, `results/logs/` |
| 结果分析 | `results/result_report.md`, `results/frozen_numbers.json` |
| 图表 | `figures/figure_index.md`, `diagrams/diagram_index.md` |
| 稳健性 | `results/result_report.md` or robustness-specific outputs |
| 修改记录 | `revisions/round_XX.md` |

## Writing Rules

- Write in formal Chinese contest-paper style.
- Prefer clear equations, tables, and traceable claims over ornate wording.
- Define every symbol before or at first use.
- Keep figure and table captions self-contained.
- Keep figure, table, and equation numbering consistent and check that no
  template instruction text remains.
- Keep units consistent across text, tables, and figures.
- State uncertainty and limitations instead of hiding them.
