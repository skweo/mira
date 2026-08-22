# Mira 0.7.7

Mira 0.7.7 makes the interactive workflow sparse and enforceable.

## Change

- Added `scripts/human_decisions.py`.
- Added `planning/human_decisions.json` as the canonical human-decision ledger.
- Added `checks/human_decision_report.md`.
- Promoted the main human gates to `G0`, `G1`, `G2`, `G3`, `G5`, and `G7`.
- Made `G4` and `G6` risk-triggered only.
- Kept `modeling` and `implementation` as legacy aliases for `G2` and `G5`.
- Added `references/interactive-human-workflow-rules.md`.

## Delivery Rule

If required human approvals are missing, Mira may continue only as
`reproducible_draft`. It must not mark the output as `contest_final` or claim
that a human approved an AI decision.

## Non-goal

This version does not add more popups. It reduces interruption by making only
high-leverage gates mandatory and making PoC/draft gates conditional on risk.
