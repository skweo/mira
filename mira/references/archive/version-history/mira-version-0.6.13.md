# Mira 0.6.13

Mira 0.6.13 adds a PowerPoint-based reasoning diagram engine for polished,
editable paper figures.

## New Standard

- Route `references/ppt-reasoning-diagram-rules.md` when a paper needs a PPT
  shape-based idea map, model reasoning diagram, process flow, execution
  workflow, lane diagram, or callout-rich schematic.
- Use `scripts/plot_ppt_reasoning_diagram.py` to create an editable PPTX source
  from a JSON spec or a built-in demo.
- Save the PPTX source, normalized JSON spec, node/edge/group/callout CSV files,
  parameters, and diagram index.
- Export PNG/PDF through PowerPoint COM or LibreOffice when available; record a
  visible blocker if export is unavailable.
- Treat PPT diagrams as reasoning and communication assets, not as numerical
  proof or solver evidence.

## Non-goals

- Do not generate presentation decks or slide reports.
- Do not use PPT diagrams as decoration.
- Do not replace data figures, formula derivations, solver logs, or result
  tables with PPT shapes.
- Do not weaken the 0.6.1-0.6.12 layout, derivation, control-plane, and
  reproducible visualization rules.
