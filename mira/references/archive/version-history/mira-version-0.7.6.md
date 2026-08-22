# Mira 0.7.6

Mira 0.7.6 makes human decisions recommendation-first.

## Change

- Added `scripts/human_decision_cards.py`.
- Added `planning/human_decision_cards.json` and `.md` as the canonical
  recommendation-card artifacts.
- Added `checks/human_decision_card_report.md`.
- modeling method selection and implementation result freeze now require a Mira
  recommendation package before human approval or high-risk review.
- `decision_gate.py` now fails human-facing gates when the recommendation card
  is missing or appears newer than a recorded human approval.

## Why

Interactive Mira should help the human spend attention at high-leverage
decision points. A beginner should not have to infer the best route from raw
options; Mira must recommend one option, explain its evidence and risks, and
state what happens if the human rejects it.

## Non-goal

This version does not add more human gates. It only hardens the gates that
already exist and gives future interactive gates a reusable card contract.
