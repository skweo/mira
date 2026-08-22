# Journal-Grade Figure Rules

Use these rules when Mira targets a high-award mathematical modeling paper and
the user wants figures with the visual impact of strong biology or medical
journal figures.

## Core Principle

Make figures beautiful because they make the argument easier to see. Do not add
decorative scientific-looking artwork that is not tied to data, mechanism,
model structure, or a decision.

## Required Qualities

For `contest_final`, try to include at least one journal-grade core figure and
several ordinary but polished support figures.

1. **Visual center**: every important figure should make the key object obvious
   within two seconds: optimum, threshold, high-risk zone, decision branch,
   mechanism path, or cost source.
2. **Multi-panel structure**: use `(a)`, `(b)`, `(c)`, `(d)` panels when one
   figure needs to tell a chain: mechanism/process -> model/data -> result ->
   validation or local detail.
3. **Direct labels and callouts**: put the essential labels on the figure, not
   only in the legend. Use arrows, shaded windows, brackets, and short callout
   boxes for key points.
4. **Unified visual language**: keep typography, line width, palette, marker
   size, spacing, axis style, and panel labels consistent across the paper.
5. **Local detail**: add inset zooms or paired local panels when the important
   difference is visually compressed in the full-scale plot.
6. **Mechanism diagrams**: for operational/modeling problems, include at least
   one polished mechanism/process/state/decision diagram. The diagram should
   look like part of the same visual system as the data charts.
7. **High-resolution output**: save raster figures at 300 dpi or higher and keep
   the long side large enough for A4 print. Prefer vector output when diagrams
   or line art dominate.

## When To Use 3D

Use 3D only when it clarifies a genuine surface, interaction, spatial path, or
time-state-result relationship. Pair 3D with a 2D projection, contour, heatmap,
or annotated slice when exact comparison matters.

## Figure Types To Prefer

- Core overview figure: one multi-panel figure combining process, variables,
  solver route, and final decision.
- Mechanism-to-result figure: left panel shows mechanism, right panels quantify
  the resulting cost/profit/risk.
- Strategy boundary figure: heatmap or surface plus threshold curve, direct
  labels, and local zoom around the switch boundary.
- Robustness figure: posterior/simulation spread, winner frequency, and action
  recommendation in one panel set.
- Batch impact figure: per-unit result plus batch-scale enterprise impact.

## Implementation Hints

- Use `scripts/visual_style.py` helpers such as `label_panel`,
  `annotate_key_point`, `emphasize_window`, `add_callout_box`,
  `add_zoom_inset`, and `apply_3d_style`.
- Prefer `GridSpec`, `subplot_mosaic`, or `create_journal_multipanel` for
  composite figures instead of manually pasting images.
- Save planned high-impact figures in `planning/figure_storyboard.md` with a
  role such as `core`, `mechanism`, `boundary`, `robustness`, or `batch-impact`.
- Name composite figures clearly, e.g. `core_decision_storyboard.png`,
  `strategy_boundary_multipanel.png`, or `posterior_robustness_panel.png`.

## Waivers

Record a waiver when:

- the paper is only a quick draft;
- result artifacts are not ready;
- a multi-panel figure would duplicate a clearer single table or proof;
- page limits require supporting details to remain as separate result files.
