# Mira 0.4.6 Standard

Mira 0.4.6 is a quality-review upgrade over Mira 0.4.5.

## Upgrade Theme

| Area | 0.4.5 behavior | 0.4.6 behavior |
|---|---|---|
| Automatic repair | Repairs paper visual-writing issues on a paper copy | Keeps the repair loop, then audits whether the repaired text sounds mechanical |
| Figure checking | Checks figure existence, captions, labels, references, and visual-reasoning loops | Reviews whether each figure is worth main-text space and returns `KEEP`, `REDRAW`, `MOVE_TO_APPENDIX`, or `DROP` |
| Weak visual detection | Treats many captioned/referenced figures as structurally acceptable | Flags low-information scans, flat candidate comparisons, generic heatmaps, and figures that add little beyond a nearby table |
| Final-paper feel | Uses award/presentation gates plus iteration queue | Adds a scorecard for reasoning chain, visual value, abstract result ledger, formula emphasis, and polish |
| Iteration routing | Routes repair-loop and presentation findings | Routes `mechanical_prose`, `figure_effectiveness`, `figure_value`, `pdf_polish`, and `contest_final_feel` into the iteration queue |

## New Files

- `scripts/paper_quality_review.py`
- `references/mira-version-0.4.6.md`

## Standard Quality Review Command

Run after `paper_revision_loop.py` and before presentation-strength or final
iteration checks:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_quality_review.py `
  --root <project-root> `
  --write-report checks\paper_quality_review_report.md `
  --write-json checks\paper_quality_review_report.json
```

When reviewing a named paper copy, pass `--paper`:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_quality_review.py `
  --root <project-root> `
  --paper paper\main_final_v045_rewrite.tex `
  --write-report checks\paper_quality_review_report.md `
  --write-json checks\paper_quality_review_report.json
```

## What It Catches

| Finding axis | Return to | Typical repair |
|---|---|---|
| `mechanical_prose` | paper | Replace generic repair phrases with figure-specific variables, values, local features, and decision logic |
| `figure_effectiveness` | implementation | Redraw weak visuals with annotations/local zoom, or replace them with tables/diagrams |
| `figure_value` | implementation | Move low-value support visuals to appendix or drop duplicates |
| `pdf_polish` | paper | Fix overfull tables/captions and inspect the rendered PDF |
| `contest_final_feel` | implementation | Improve the lowest scorecard axis before final comparison |

## Compatibility

Mira 0.4.6 is backward-compatible with 0.4.5 projects. It does not change
numeric results, model assumptions, source data, figures, or solver lineage. It
adds a reviewer-like gate that decides whether a structurally valid final paper
still looks mechanical, visually weak, or below strong contest-final standard.

The review is intentionally conservative: a weak figure is normally a WARN, not
an automatic FAIL. A paper fails only when quality score, mechanical prose, or
weak-visual density indicates the final paper is not ready for delivery.

## Figure-Value Rule

A figure may be correct but still weak. A candidate scan that only confirms no
improvement may be less valuable than an annotated comparison table or compact
decision diagram. Mira therefore asks not only whether a figure exists, but
what decision it makes easier for the reviewer.
