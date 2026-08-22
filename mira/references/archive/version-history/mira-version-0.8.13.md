# Mira 0.8.13

## Scope

Mira 0.8.13 closes the gap between "human-decision files exist" and "the human
actually got an interactive choice".

## Added

- `scripts/interactive_gate_adapter.py`
  - `--prepare` writes `planning/interactive_gate_request.json` and `.md`.
  - The request contains a Codex `request_user_input`-style payload.
  - `--record` writes the human choice back into `planning/decision_gates.json`
    and `planning/human_decisions.json`.
  - `--check --output-level contest_final` fails when a required human-approved
    gate lacks a popup or explicit-chat fallback interaction record.
- `references/interactive-gate-adapter-rules.md`
  - Defines popup-first behavior.
  - Defines chat fallback.
  - Defines choice-to-gate-status mapping.

## Behavior

For G0/G1/G2/G3/G5/G7 and triggered G4/G6:

1. create the recommendation card;
2. prepare the interactive request;
3. use Codex/Claude Code interactive input when available;
4. record the human answer;
5. continue as `contest_final` only after the interaction record exists.

If no platform popup is available, Mira must stop in chat and wait for an
explicit answer. Silent continuation is limited to `reproducible_draft`.
