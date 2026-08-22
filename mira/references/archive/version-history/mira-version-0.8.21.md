# Mira 0.8.21

## Scope

Mira 0.8.21 removes the active AI-use compliance/disclosure chain from the
contest-paper workflow at the user's request.

## Active Behavior

- Do not generate or require `planning/ai_usage_ledger.json`.
- Do not generate or require `planning/ai_usage_ledger.md`.
- Do not generate or require `supporting/AI 工具使用详情.pdf`.
- Do not run `scripts/ai_usage_ledger.py` from command profiles.
- Do not run `scripts/ai_compliance_gate.py` from command profiles.
- Do not route `references/ai-tool-use-compliance-rules.md` from normal phase
  routing.

## Preserved Behavior

- Human decision gates G0/G1/G2/G3/G5/G7 remain mandatory for
  `contest_final`.
- Triggered G4/G6 risk gates remain mandatory when their risk conditions occur.
- Decision-lineage, artifact manifest, data-quality, result-confidence,
  visual, diagram, prose, derivation, and presentation checks remain active.
- AI image generation remains allowed only for non-precise illustrative visuals
  when the generated-image route and figure/diagram index record prompt, tool,
  date, generated asset, human edits, and paper placement.

## Migration Note

Existing projects may still contain old AI-use ledger files or AI compliance
reports. Mira 0.8.21 treats them as ordinary historical artifacts and does not
use them as final-delivery gates.
