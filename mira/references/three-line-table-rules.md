# Three-Line Table Rules

Use this reference when drafting or revising tables in a `contest_final`
Chinese mathematical modeling paper.

## Core Principle

For formal contest papers, prefer three-line tables. They look closer to strong
Chinese mathematical modeling submissions and reduce visual clutter for
reviewers. This is a presentation-quality rule, not a reason to change numeric
results.

## LaTeX Standard

Use `booktabs`:

```latex
\usepackage{booktabs}

\begin{table}[htbp]
\centering
\caption{...}
\begin{tabular}{cccc}
\toprule
列1 & 列2 & 列3 & 列4 \\
\midrule
... & ... & ... & ... \\
\bottomrule
\end{tabular}
\end{table}
```

Rules:

- Prefer `\toprule`, `\midrule`, and `\bottomrule`.
- Avoid vertical rules such as `|c|c|c|` unless the official template requires
  them.
- Avoid repeated `\hline`; replace with `booktabs` rules.
- Put units in column headers, not repeated in every cell.
- Keep main-text tables compact; save long raw tables as separate result files.
- Align decimals and use consistent significant digits.
- Captions should state what the table supports, not only list its contents.

## Typst / Markdown Equivalent

When using Typst or Markdown, render tables in a three-line-equivalent style:

- top boundary, header separator, bottom boundary;
- no full grid unless the template forces it;
- restrained row padding and readable font size;
- no raw CSV-style headers in final paper body.

## When Not To Force It

Do not force a three-line table if:

- an official template explicitly requires full grid tables;
- a confusion matrix or special audit table genuinely needs grid separation;
- the table is a raw supporting artifact that is better kept as code/result
  evidence rather than polished body text.

If not using three-line style, record the reason in the table-style report or
paper revision notes.

## Preferred Gate

Before final delivery, run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\table_style_audit.py --root <project-root> --write-report checks\table_style_report.md --write-json checks\table_style_report.json
```

Treat findings as paper presentation repairs.
