# Mira 0.8.20

Scope: make implementation structural diagrams executable, not only planned.

## What changed

- Downloaded the real `next-ai-draw-io` repository to `$PROJECT_ROOT\next-ai-draw-io`.
- Built its local MCP package under `$PROJECT_ROOT\next-ai-draw-io\packages\mcp-server`.
- Added `scripts/generate_drawio_diagrams.py` as Mira's deterministic local generator.
- The generator reads `planning/diagram_intent_pack.json` and writes `.drawio`
  source files plus SVG paper exports.
- Added `checks/drawio_generation_report.md/json` as a implementation/final-gate audit
  artifact and iteration-loop source.

## Operating rule

Use `diagram_tool_router.py` to detect structural-diagram opportunities and
check routing. Use `generate_drawio_diagrams.py` to create actual editable and
paper-ready assets. Rerun the router after generation before inserting diagrams
into a `contest_final` paper.

## Tool boundary

`next-ai-draw-io` MCP is useful for session preview, editing, and export. It
does not remove Mira's responsibility to create a truthful diagram specification
with Chinese labels, real nodes/edges, source artifacts, privacy mode, and a
paper claim.
