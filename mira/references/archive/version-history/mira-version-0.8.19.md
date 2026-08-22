# Mira 0.8.19

Mira 0.8.19 upgrades implementation from scattered diagram tools into a unified
structural-diagram router.

## Scope

- Add `scripts/diagram_tool_router.py`.
  - Generates `planning/diagram_intent_pack_template.json`.
  - Checks `planning/diagram_intent_pack.json`.
  - Writes `checks/diagram_tool_route_report.md` and
    `checks/diagram_tool_route_report.json`.
- Add `references/drawio-diagram-rules.md`.
- Route implementation structural diagrams toward draw.io / next-ai-draw-io as the
  preferred final editable lane.

## Policy

- implementation starts from diagram intent: claim, nodes, edges, route, privacy mode,
  source artifacts, editable source, export, and paper location.
- draw.io / next-ai-draw-io is preferred for polished flowcharts,
  architecture maps, roadmaps, mechanisms, state-transition diagrams, variable
  relations, and sequence diagrams.
- Mermaid remains a quick draft/fallback for interaction order.
- PPT remains for pseudo-3D or special editable layouts.
- Python, pyecharts, and ECharts remain implementation data-chart tools.
- AI image generation remains only for non-structural illustrations.

## Failure Modes Caught

- Structural diagrams referenced in the paper with no intent pack.
- Missing editable source or exported asset.
- Non-Chinese default labels.
- Data charts routed through implementation.
- Precise structural diagrams routed to AI image generation.
- draw.io MCP use without privacy mode or AI-use ledger record.
