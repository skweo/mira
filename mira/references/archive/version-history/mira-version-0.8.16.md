# Mira 0.8.16

Mira 0.8.16 absorbs the useful core of Claude's
`modeler-decision-logger` without adopting its per-skill long workflow.

## Added

- `scripts/decision_lineage_ledger.py`
  - Folds existing gate artifacts into an append-only decision history.
  - Writes `planning/decision_lineage_ledger.json`,
    `planning/decision_lineage_ledger.md`, and
    `checks/decision_lineage_report.md`.
  - Stamps active records as `G0-D01`, `G1-D01`, `G2-D01`, and so on.
  - Appends a new record with `supersedes` when a gate decision changes.
  - Stores source-artifact hashes and reports stale decisions after artifact
    changes.
- `references/decision-lineage-ledger-rules.md`
  - Defines how paper rationale traces to human decision IDs.

## Behavior Change

- For `contest_final`, G0/G1/G2/G3/G5/G7 need active human-confirmed lineage
  records; triggered G4/G6 need them too.
- G1/G2/G3/G5 and triggered G4/G6 lineage must include anti-anchoring human
  judgment answers.
- A method-choice, modeling-plan, result-freeze, or final-submission decision
  becomes stale if its watched artifacts change after logging.
- Paper prose may not claim a human modeling reason unless the reason traces to
  an active `decision_id`.

## Why

Earlier Mira versions could record a human choice but still let later writing
re-compose the method story. The new ledger gives the decision side the same
discipline as frozen numbers: numbers come from the result ledger, and modeling
judgments come from the decision-lineage ledger.
