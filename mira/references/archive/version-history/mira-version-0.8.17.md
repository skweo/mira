# Mira 0.8.17

Mira 0.8.17 absorbs the useful core of Claude's `figure-table-planner` without
copying its long sentinel workflow.

## Added

- `scripts/figure_claim_ownership_gate.py`
  - Collects visuals from `figures/figure_index.md`,
    `diagrams/diagram_index.md`, and `planning/figure_storyboard.json`.
  - Writes `planning/figure_claims_template.json` for human completion.
  - Checks `planning/figure_claims.json`.
  - Blocks `contest_final` when a main-paper visual lacks a human-confirmed
    `core_claim`.
- `references/figure-claim-ownership-rules.md`
  - Defines visual claim ownership, type/use classification, required ledger
    fields, and failure conditions.

## Why

Previous Mira versions could generate more visuals, but a visual could still be
decorative or agent-authored rather than claim-bearing. This upgrade makes
paper figures part of the human decision surface: Mira proposes the figure,
the human owns the single sentence it is meant to prove.

## Policy

For `contest_final`, main-paper visuals must have:

- `core_claim`
- `claim_author: human:<name>`
- `claim_confirmed: true`
- `source_artifact`
- `paper_section`

Appendix and diagnostic visuals do not block unless they carry a main-body
conclusion.
