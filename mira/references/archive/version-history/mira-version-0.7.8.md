# Mira 0.7.8

Mira 0.7.8 adds CUMCM-style AI-tool-use compliance.

## Changes

- Adds `planning/ai_usage_ledger.json` as the canonical AI-use ledger.
- Adds `scripts/ai_usage_ledger.py` to record tools, key interactions, adoption
  and human modification, body markers, reference entries, and human decision
  evidence.
- Adds PDF generation for `supporting/AI 工具使用详情.pdf`.
- Adds `scripts/ai_compliance_gate.py` to block `contest_final` when AI-use
  transparency or human core-decision evidence is missing.
- Routes AI compliance rules into G0, paper writing, final gate, verify, and
  iteration phases.

## Design Intent

This version does not pretend AI use disappears. It makes AI assistance
transparent, records where human decisions occurred, and prevents
`contest_final` delivery when the required disclosure package is missing.
