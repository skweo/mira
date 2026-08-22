# Mira 0.6.14

Mira 0.6.14 adds an official-paper-style showcase work-map template on top of
the PowerPoint reasoning diagram engine.

## New Standard

- Use `scripts/plot_ppt_reasoning_diagram.py --demo showcase_work` when a paper
  needs a high-level "our work" or modeling-framework overview figure.
- Support nested dashed containers, a top goal bar, side input/preprocessing
  chain, main model stack, solution-condition stack, sensitivity branches, and
  bottom objective decomposition.
- Keep PPTX as the editable source, export PNG/PDF for paper insertion, and save
  normalized JSON, node/edge/group CSV files, parameters, and diagram index.
- Treat the template as reusable visual grammar. Replace all content with the
  current problem's real data, models, sensitivity objects, and final objective.

## Non-goals

- Do not copy the screenshot, wording, domain, or paper-specific content of an
  example work map.
- Do not use the showcase map when the paper lacks enough linked modules.
- Do not let the overview figure replace formula derivations, result tables, or
  validation evidence.
