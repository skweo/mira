# Data Quality Gate Rules

Use this rule after attachment mapping and before modeling code consumes raw
data.

## Core Rule

Attachment mapping answers "which file belongs to which question?" Data quality
answers "is that file safe to model with?"

Mira must not treat a readable spreadsheet as model-ready. For contest-final
runs, mapped datasets need explicit readiness evidence:

- raw file remains unchanged;
- dataset is mapped to Qx/SHARED by the P0 attachment guard;
- rows, columns, sheets, and field types are audited;
- missing values, duplicate rows, suspicious negative values, and mixed formats
  are checked;
- quantitative physical fields have a header unit or a documented unit source;
- cleaning actions or waivers are recorded when risks exist;
- readiness is explicit and supported by technical evidence.

## Input-Type Routing

Classify the input before choosing exploratory checks or figures:

- For observed multi-sample datasets, apply the full data-quality contract and
  use distribution, trend, correlation, missing-value, and grouped checks only
  when the field roles and sample structure support them.
- For deterministic physical constants, geometry, or mechanism parameters,
  preserve sources, units, ranges, and scenario meaning; use dimensional,
  geometry, physical-consistency, and limiting-case checks. Do not force
  missing-value reports, box plots, or correlation heatmaps designed for
  sampled observations.
- For mixed inputs, audit the observed-data and mechanism-parameter tracks
  separately, then state which cleaned fields and derived parameters cross the
  boundary between them.

## Required Command

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\data_quality_gate.py --root <project-root> --output-level <output-level> --write-template planning\data_quality_template.json --write-report checks\data_quality_report.md --write-json checks\data_quality_report.json
```

The script reads:

- raw files under `data_raw/`, `data/raw/`, `workspace/data/data_raw/`, or
  paths listed in `planning/attachment_mapping.json`;
- `planning/attachment_mapping.json`;
- `planning/data_quality_overrides.json`;
- `planning/data_cleaning_log.json` when cleaned files exist.

It writes:

- `planning/data_quality_template.json`
- `checks/data_quality_report.md`
- `checks/data_quality_report.json`

## Readiness Evidence File

Resolved data decisions should be copied into
`planning/data_quality_overrides.json`:

```json
{
  "version": 1,
  "datasets": [
    {
      "artifact": "data_raw/attachment1.xlsx",
      "mapped_to": ["Q1"],
      "readiness": "accepted_with_warnings",
      "evidence": "Problem statement, table 1 field definition.",
      "notes": "Units confirmed from problem statement."
    }
  ],
  "field_units": {
    "data_raw/attachment1.xlsx::Sheet1::distance": "km"
  },
  "field_meanings": {
    "data_raw/attachment1.xlsx::Sheet1::distance": "route distance"
  },
  "cleaning_actions": [
    {
      "artifact": "data_raw/attachment1.xlsx",
      "action": "remove duplicate exact rows",
      "target": "all rows",
      "reason": "duplicate source records",
      "risk": "low",
      "evidence": "Exact duplicate audit in code/python/clean_data.py"
    }
  ],
  "waivers": []
}
```

## Cleaning Log

If cleaned files are produced, record row/column changes in
`planning/data_cleaning_log.json`:

```json
{
  "version": 1,
  "records": [
    {
      "raw_artifact": "data_raw/attachment1.xlsx",
      "clean_artifact": "data_clean/attachment1_clean.csv",
      "raw_rows": 120,
      "clean_rows": 118,
      "raw_columns": 8,
      "clean_columns": 8,
      "actions": ["removed 2 exact duplicate rows"],
      "script": "code/python/clean_data.py"
    }
  ]
}
```

## Contest-Final Failure Conditions

For `contest_final`, fail when:

- raw data is referenced but no raw file is found;
- a mapped dataset is unreadable;
- a mapped dataset lacks a clear attachment mapping;
- dataset readiness is `blocked`;
- a quantitative physical field has no header or documented unit;
- a field appears nonnegative but contains negative values;
- more than half of a field is missing;
- data risks exist but no reviewed cleaning action or waiver is recorded.

Warnings are acceptable only when the risk is explicitly waived and the waiver
does not change the meaning of the data.

## Boundary

This gate does not select a model, run final experiments, or invent cleaned
values. If required fields are absent or units cannot be resolved, return to
analysis or modeling instead of coding around the gap. Ask the user only when
the available evidence leaves a real choice.
