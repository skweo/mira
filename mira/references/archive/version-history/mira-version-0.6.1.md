# Mira 0.6.1

Mira 0.6.1 repairs front-matter and abstract layout defects found in
contest-final practice papers.

## New Standard

For `contest_final`, the first page should contain only the formal title,
abstract body, and keywords unless an official template says otherwise. The
main body or contents must begin after `\newpage` or `\clearpage`.

Multi-question abstracts should be reviewer-scannable:

- one opening paragraph for the overall task and model route;
- one paragraph per official subquestion;
- bold labels such as `\textbf{针对问题一：}`;
- bold final answers or critical contribution phrases, not every method name;
- keyword line before the page break.

## New Gate

Run:

```bash
python scripts/abstract_layout_audit.py --root <project-root> --write-report checks/abstract_layout_report.md --write-json checks/abstract_layout_report.json
```

Unresolved findings return to paper paper writing. Do not change numerical
results to satisfy this gate; repair only front matter, page breaks, abstract
segmentation, emphasis, and the main-body opening.
