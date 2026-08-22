# Abstract And Layout Rules

Use these rules when drafting or revising a `contest_final` Chinese
mathematical modeling paper. They are promoted from the stable layout pattern
seen in local 2020 CUMCM excellent papers: the first page is a judge-facing
title/abstract/keyword page, and the main body starts cleanly on the next page.

## Standalone Abstract Page

- Put the paper title, `摘要`, abstract body, and `关键词` on the first page.
- Insert `\newpage` or `\clearpage` after keywords before `目录`,
  `问题重述`, or any main-body section.
- Do not let `问题重述`, `问题分析`, model assumptions, figures, or tables share
  the abstract page unless an official template explicitly requires it.
- If a table is needed in the abstract, keep it short and central to the final
  answer; never use long result tables on the abstract page.

## Abstract Structure

For multi-question contest papers, write the abstract as:

1. One short opening paragraph for task background and overall route.
2. One paragraph per official subquestion.
3. One short closing paragraph for validation, robustness, or practical value.
4. A keyword line with 3-6 terms.

Each subquestion paragraph should start with a bold problem label:

```tex
\textbf{针对问题一：}...
\textbf{针对问题二：}...
```

The label should be bold even if the later result numbers are also bold. This
helps reviewers scan whether every official question has been answered.

In Mira 0.8, these are delivery blockers for Chinese `contest_final` papers:

- two or more official subquestions appear in the abstract but their labels are
  not bold;
- several subquestions are summarized inside one undivided paragraph;
- the keyword line is missing, visually hidden, or has fewer than three real
  terms;
- the abstract contains many final numbers but no bold final answers or key
  strategy phrases.

Run `scripts/abstract_layout_audit.py` and
`scripts/final_polish_language_gate.py`; unresolved FAIL items return to the
paper stage before compilation is treated as final.

## Emphasis

- Bold each problem label in the abstract.
- Bold final answer numbers, final strategy phrases, or named model
  contributions when they are central to the abstract.
- Do not bold every method name; use emphasis to expose answers and structure.
- Keep formulas out of the abstract unless the official template or problem
  type makes one compact expression unavoidable.

## Main-Body Opening

- After the abstract page, start with `问题重述` or the official template's
  equivalent before model assumptions and solution sections.
- Use clear top-level section hierarchy; do not hide all subquestions inside
  one generic `模型建立与求解` section.
- For long papers, include `目录` after the abstract page unless the official
  template forbids it.

## Common Failures

- The abstract and first body section are on the same page.
- The abstract contains all subquestions in one unsegmented paragraph.
- Problem labels such as `问题一` are plain text instead of bold.
- The keyword line is missing or appears after the main body begins.
- The first body section starts directly with assumptions, code, or results.
