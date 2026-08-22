# Mira 0.8.18

Mira 0.8.18 absorbs the useful core of Claude's `data-auditor-cleaner` without
copying its long workflow.

## Added

- `scripts/data_quality_gate.py`
  - Inventories raw contest data after attachment mapping.
  - Reads CSV/TSV/TXT/JSON/XLSX without editing raw files.
  - Audits rows, columns, sheets, field types, missing values, duplicate rows,
    suspicious negative values, and unit confirmation needs.
  - Writes `planning/data_quality_template.json`,
    `checks/data_quality_report.md`, and `checks/data_quality_report.json`.
  - Checks human readiness records in `planning/data_quality_overrides.json`.
- `references/data-quality-gate-rules.md`
  - Defines the raw-data, field-unit, cleaning-log, and human-readiness
    requirements for contest-final runs.

## Why

Mira already had a P0 attachment-to-subquestion guard. That prevents the wrong
file from entering the wrong question, but it does not prove the file is safe
to model with. This upgrade adds the next guard: fields, units, missingness,
duplicates, cleaning actions, and human readiness.

## Contest-Final Policy

For mapped data used in `contest_final`, Mira must fail delivery when:

- attachment mapping is not human-confirmed;
- dataset readiness is not human-confirmed;
- physical numeric fields lack units;
- severe missing values, impossible ranges, or unreadable files remain;
- cleaning risks exist without a recorded action or waiver.

Raw data remains read-only. Cleaned data belongs under `data_clean/`, with row
and column changes recorded in `planning/data_cleaning_log.json`.
