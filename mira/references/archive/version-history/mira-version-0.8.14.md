# Mira 0.8.14

## Scope

Mira 0.8.14 absorbs the most important idea from Claude's
`decision-prompt-builder`: at modeling-judgment gates, ask the human to state
their trade-off before Mira reveals a recommendation.

## Added

- `scripts/human_judgment_prompts.py`
  - `--prepare` writes `planning/human_judgment_prompts.json` and `.md`.
  - `--record` stores the human's selected trade-off and explanation.
  - `--check --output-level contest_final` fails missing, unanswered, rubber-
    stamp, or learning-mode anchor-order-broken prompts.
- `references/human-judgment-prompt-rules.md`
  - Defines G1/G2/G3/G5 prompts.
  - Defines risk-triggered G4/G6 prompts.
  - Defines `learning` vs `speed` mode.

## Behavior

For `contest_final`, G1/G2/G3/G5 need an answered human judgment prompt before
the final gate can pass. Triggered G4/G6 need the same.

In `learning` mode, Mira's recommendation must be withheld until after the
human answers. In `speed` mode, the prompt and recommendation may appear in the
same decision package, but bare approvals such as `同意` or `按推荐` still fail.

## Why It Matters

Mira 0.8.13 proved that the human was asked. Mira 0.8.14 makes the human answer
carry modeling content, so the workflow is less vulnerable to AI anchoring and
rubber-stamp approval.
