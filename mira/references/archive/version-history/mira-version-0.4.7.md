# Mira 0.4.7 Standard

Mira 0.4.7 is a quality-repair bridge over Mira 0.4.6.

## Upgrade Theme

| Area | 0.4.6 behavior | 0.4.7 behavior |
|---|---|---|
| Quality review | Detects mechanical prose, weak visuals, and contest-final feel gaps | Keeps the review and turns findings into an ordered repair queue |
| Figure repair | Says which visuals are weak or low-value | Adds a concrete redesign brief for each weak figure |
| Prose repair | Flags template-like repair sentences | Adds line-level rewrite targets and replacement patterns |
| Repair workflow | Review findings are useful but still need manual sorting | `paper_quality_repair_plan.py` creates priority, owner phase, target artifact, and next check for each issue |
| Loop closure | The next action still had to be inferred | Review -> repair plan -> revise -> rerun review |

## New Files

- `scripts/paper_quality_repair_plan.py`
- `references/mira-version-0.4.7.md`

## Standard Repair-Plan Command

Run after `paper_quality_review.py` and before presentation-strength or final
iteration checks:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_quality_repair_plan.py `
  --root <project-root> `
  --quality-json checks\paper_quality_review_report.json `
  --write-report revisions\paper_quality_repair_plan.md `
  --write-json revisions\paper_quality_repair_plan.json
```

## What It Produces

| Output surface | Purpose |
|---|---|
| `repair_items` | Ordered queue of paper / implementation-7 / paper-8 tasks |
| `figure_briefs` | Redesign notes for weak or low-value figures |
| `prose_targets` | Line-level rewrite goals for mechanical repair sentences |
| `repair_order` | Suggested order for the next revision round |

## Compatibility

Mira 0.4.7 is backward-compatible with 0.4.6 projects. It does not change
numeric results, model assumptions, source data, figures, or solver lineage.
It only makes the review output actionable by turning the review into a
structured repair plan.

The repair plan is intentionally conservative. It does not overwrite the paper
or invent new fixes. It tells the agent what to repair first, which artifact to
touch, and which audit to rerun after the change.

## Repair-Queue Rule

Detection alone is insufficient. Once Mira identifies a low-value visual or
mechanical prose, it still needs a clear repair queue. Version 0.4.7 closes that
gap without relying on problem-specific file names.
