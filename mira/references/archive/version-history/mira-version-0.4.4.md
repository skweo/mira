# Mira 0.4.4 Standard

Mira 0.4.4 is the active Mira baseline as of 2026-06-29. It is a visual-expression upgrade over Mira 0.4.3.

## Upgrade Theme

| Area | 0.4.3 behavior | 0.4.4 behavior |
|---|---|---|
| Visual evidence planning | `evidence_planner.py` checks whether final claims have figure/table/diagram evidence | Keeps that gate and adds asset-level plus reasoning-level visual checks |
| Plot style | Individual scripts could choose their own matplotlib style | `visual_style.py` provides a reusable Chinese contest-paper plotting style |
| Visual asset audit | Presentation strength checked figure counts and paper-level readability | `visual_asset_audit.py` checks visual files for resolution, size, placeholder names, and figure/diagram index coverage |
| Visual reasoning audit | Figure quality was mainly judged by count/readability | `visual_reasoning_audit.py` checks figure numbering/reference, abstract result emphasis, final-formula highlighting, visual roles, operation diagrams, coarse-to-fine threshold visuals, zoom/detail evidence, multi-case visuals, and heatmap/3D choice |
| Figure storyboarding | Figures were selected mostly from available artifacts | `figure_storyboard.py` plans visual roles, nearby claims, source artifacts, and callout text before final plotting/writing |
| Excellent visual examples | A070/B108 lessons mainly improved writing and problem structure | A053 official-showcase lessons add diagram-callout pairing, theorem-operation diagrams, global-plus-local details, boundary-state comparisons, and page-level figure grammar |
| Phase routing | implementation loaded figure-table rules | implementation also route `visual-expression-rules.md` |

## New Files

- `scripts/visual_style.py`
- `scripts/figure_storyboard.py`
- `scripts/visual_asset_audit.py`
- `scripts/visual_reasoning_audit.py`
- `references/visual-expression-rules.md`

## Standard Visual Commands

Before implementation final visual selection:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plan_presentation_budget.py `
  --root <project-root>
```

Before final delivery:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\figure_storyboard.py `
  --root <project-root> `
  --write-report planning\figure_storyboard.md `
  --write-json planning\figure_storyboard.json
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_asset_audit.py `
  --root <project-root> `
  --write-report checks\visual_asset_audit_report.md `
  --write-json checks\visual_asset_audit_report.json
```

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_reasoning_audit.py `
  --root <project-root> `
  --write-report checks\visual_reasoning_audit_report.md `
  --write-json checks\visual_reasoning_audit_report.json
```

When generating matplotlib figures, import and apply the style:

```python
from visual_style import apply_mira_style, save_mira_figure

apply_mira_style()
# build figure
save_mira_figure(fig, "figures/q2_route_resource_ledger.png")
```

## Compatibility

Mira 0.4.4 is backward-compatible with 0.4.3 projects. It does not change the result ledger, paper consistency, evidence planner, or award-review semantics. It adds stricter visual gates so low-resolution, placeholder, unindexed, or suspiciously tiny/oversized images return to implementation, while weak caption/reference coverage, weak abstract/result emphasis, unhighlighted final formulas, compressed critical plots, unjustified heatmaps/3D views, or weak multi-case visuals return to implementation before final delivery.

The A053 official-showcase learning pass adds a stronger visual reasoning
standard: figures should form a chain from definition to derivation, operation,
result, and validation where the problem needs it. For critical parameters or
collision/boundary claims, Mira should prefer coarse-to-fine search visuals and
global-plus-local detail panels over isolated final-number plots.

The second A053 learning pass adds tooling for that standard: a page-level
visual grammar extraction, a figure-storyboard planner, and plotting helpers for
callout boxes, bracketed search intervals, linked zoom/detail panels, panel
labels, and boundary comparison layouts.
