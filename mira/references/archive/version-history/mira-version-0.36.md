# Mira 0.36 Repair Note

Mira 0.36 is Mira 0.35 plus the sixth DeepSeek defect repair. It is the final
pre-0.4 repair label; Mira was promoted to the active Mira 0.4 baseline on
2026-06-28.

## Closed Defect

| Defect | Repair |
|---|---|
| Knowledge retrieval produced suggestions but did not enforce application and validation | Added `scripts/knowledge_application_audit.py`; paper routing and iteration loop now consume `checks/knowledge_application_report.md` |

## New Contract

For risky `contest_final` models, knowledge-card hits are obligations. They
must be traceable into:

| Loop step | Required artifact |
|---|---|
| Retrieval | `planning/knowledge_injection.md/json` |
| Application | `planning/modeling_plan.md` Domain Knowledge Used table |
| Validation | code/results evidence such as audits, baselines, objective decomposition, multi-seed/convergence, or sensitivity |
| Repair | repair-move evidence or an explicit waiver when card failure signs appear |

## Verification

On the Mira MathorCup A redo benchmark, the new audit should fail because the
project contains risky routing/penalty/heuristic terms but lacks a saved
`planning/knowledge_injection.md/json` retrieval record. This is expected: the
benchmark had knowledge-like modeling text, but did not prove the retrieval to
application to validation chain.

This repair note is retained for history. New projects should use Mira 0.4 as
the active baseline and keep this file only as the version lineage record.
