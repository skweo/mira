# Mira 0.4.5 Standard

Mira 0.4.5 is the active Mira baseline after the A053 figure-text-loop learning pass. It is a paper-revision-loop upgrade over Mira 0.4.4.

## Upgrade Theme

| Area | 0.4.4 behavior | 0.4.5 behavior |
|---|---|---|
| Visual reasoning audit | Detects weak captions, references, abstract emphasis, final-formula emphasis, figure-text loop, and visual evidence issues | Keeps the audit and adds a repair loop that can plan and patch writing-level issues on a paper copy |
| Revision planning | Iteration reports grouped findings by source audit and phase | `paper_revision_plan.py` separates auto-repairable paper writing issues from manual implementation artifact gaps |
| Paper text repair | Manual editing was required after visual-reasoning warnings | `repair_paper_text.py` can add figure-purpose sentences, figure interpretation, missing figure references, abstract bolding, and final-formula boxes without changing numeric values |
| Revision verification | User/agent had to rerun commands manually and compare outputs | `paper_revision_loop.py` runs original audit, storyboard, revision plan, repair copy, repaired audit, and metric deltas |
| Safety | Final paper could be edited directly during repair | Default repair output is `paper/main_final_repaired.tex`; original paper is untouched unless `--overwrite` is explicit |

## New Files

- `scripts/paper_revision_plan.py`
- `scripts/repair_paper_text.py`
- `scripts/paper_revision_loop.py`
- `references/mira-version-0.4.5.md`

## Standard Revision Commands

Plan paper repairs from current audit artifacts:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_revision_plan.py `
  --root <project-root> `
  --write-report revisions\paper_revision_plan.md `
  --write-json revisions\paper_revision_plan.json
```

Create a repaired paper copy:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\repair_paper_text.py `
  --root <project-root> `
  --out paper\main_final_repaired.tex `
  --write-report revisions\paper_repair_report.md `
  --write-json revisions\paper_repair_report.json
```

Run the full paper-revision loop:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_revision_loop.py `
  --root <project-root> `
  --repaired-paper paper\main_final_repaired.tex `
  --write-report revisions\paper_revision_loop_report.md `
  --write-json revisions\paper_revision_loop_report.json
```

## Compatibility

Mira 0.4.5 is backward-compatible with 0.4.4 projects. It does not change result computation, ledger semantics, figure generation, visual asset auditing, or award-review scoring. It adds a conservative paper-writing repair loop after audits.

The repair scripts are intentionally limited. They may patch:

- missing nearby figure references;
- weak figure pre-introduction and post-interpretation;
- abstract result bolding;
- boxed or emphasized final formulas.

They must not change:

- numeric values;
- source data or result files;
- model assumptions;
- figure images;
- solver or validation claims.

Manual storyboard gaps remain manual. If `planning/figure_storyboard.md` shows missing `derive`, `result`, `zoom`, `compare`, or `validate` visuals, Mira must return to implementation before treating the paper as high-award ready.

