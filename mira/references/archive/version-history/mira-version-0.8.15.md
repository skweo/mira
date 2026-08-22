# Mira 0.8.15

Mira 0.8.15 absorbs the useful Step 0 idea from Claude's
`data-auditor-cleaner` without importing its full data-cleaning workflow.

## Added

- `scripts/attachment_mapping_guard.py`
  - Inventories raw attachments before modeling or cleaning.
  - Previews only file metadata, headers, and the first three rows.
  - Writes `planning/attachment_mapping.json`,
    `planning/attachment_mapping.md`, and
    `checks/attachment_mapping_report.md`.
  - Supports human mapping overrides such as `file.xlsx=Q2` and
    `file.xlsx=SHARED:Q1,Q3`.
- `references/attachment-mapping-guard-rules.md`
  - Defines the P0 attachment-to-subquestion mapping contract.

## Behavior Change

- A data-rich run may not jump from modeling plan to code until each attachment
  is mapped to `Qx`, `[SHARED: ...]`, or explicitly unused.
- Ambiguous or missing official attachments block downstream work.
- For `contest_final`, every attachment mapping requires human confirmation
  before result freeze or final delivery; this confirmation should usually be
  bundled into G1 problem-understanding review.

## Why

A wrong attachment mapping is upstream of every result-quality audit. If Q2 data
is silently fed into a Q1 model, later consistency and completeness checks may
all pass while the paper is fundamentally wrong. This guard catches that class
of failure before code starts.
