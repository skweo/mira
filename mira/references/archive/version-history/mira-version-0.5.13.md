# Mira 0.5.13

Mira 0.5.13 adds journal-grade figure aesthetics on top of Mira 0.5.12.

This upgrade is motivated by the user's teacher's advice to study strong
biology and medical journal figures. Mira should learn their transferable visual
grammar: multi-panel structure, visual center, direct labels, clean palette,
local detail, and polished mechanism diagrams.

## New Standard

For `contest_final`, Mira should try to produce at least one "eye-catching"
core figure that is also evidence-bearing. A beautiful figure must still trace
to data, equations, mechanisms, algorithms, or validated decisions.

The figure set should show:

- at least one core multi-panel or mechanism/result composite when the problem
  has enough structure;
- direct in-figure callouts, arrows, shaded windows, threshold labels, or local
  zooms for key claims;
- consistent palette, typography, line width, and panel labeling;
- high-resolution or vector-ready output;
- restraint: no decorative pseudo-scientific visuals.

## New Gate

Run:

```bash
python scripts/journal_figure_gate.py --root <project-root> --write-report checks/journal_figure_report.md --write-json checks/journal_figure_report.json
```

Unresolved findings return mainly to implementation for figure redesign and paper
for captions, text loops, and figure references.

