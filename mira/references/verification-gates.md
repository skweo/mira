# Stage Verification

Mira exposes four stage checks. Specialized audit scripts remain internal
diagnostics owned by one of those stages.

## Public Check

```powershell
python scripts\stage_gate.py --root <project-root> --stage analysis
python scripts\stage_gate.py --root <project-root> --stage modeling
python scripts\stage_gate.py --root <project-root> --stage implementation
python scripts\stage_gate.py --root <project-root> --stage paper
```

Each invocation writes:

- `checks/stage_1_analysis.md/json`
- `checks/stage_2_modeling.md/json`
- `checks/stage_3_implementation.md/json`
- `checks/stage_4_paper.md/json`

The selected stage is written; its report includes recursively evaluated
upstream stages.

## Verdicts

- `PASS`: required evidence exists and no blocking signal is open.
- `PASS_WITH_WARNINGS`: the stage may proceed, but a limitation or optional
  artifact should be reviewed.
- `FAIL`: required evidence, a user decision, or an internal diagnostic blocks
  the selected stage.

The CLI returns nonzero only for `FAIL`.

## Analysis Checks

- delivery brief and output level are present
- problem analysis defines subquestions, outputs, fields, units, and ambiguity
- attachment mapping and data-quality reports do not contain an explicit FAIL
- source/privacy choices are resolved or listed as `requires_user_decision`

## Modeling Checks

- analysis still passes
- modeling and validation plans exist
- variables, assumptions, objectives, constraints, derivation, solver, and
  validation route are explicit
- available reasoning/modeling diagnostics do not contain an explicit FAIL

## Implementation Checks

- modeling still passes
- executable Python, MATLAB, or notebook source exists
- run logs or structured result artifacts exist
- `contest_final` has generated evidence figures and a result ledger
- available result, solver-consistency, and visual diagnostics do not fail

## Paper Checks

- implementation still passes
- canonical paper source exists
- numbers, figures, citations, and paper claims remain consistent
- `contest_final` has a compiled PDF and READY delivery manifest
- available paper-quality and evidence-chain diagnostics do not fail

## User Decisions

Human choices are represented only as `requires_user_decision`. The report
names the owning stage, source, and message. Legacy decision records are read
for compatibility and normalized to the same field.

## Internal Diagnostics

The concise command profile exposes three to five commands per stage. The
`contest_final_pipeline.py` may call additional specialized scripts for data,
reasoning, solver, evidence, visual, citation, layout, and delivery quality.
Those scripts add evidence; they do not add public workflow states.

An explicit internal `FAIL`, `BLOCKED`, or `ERROR` blocks the owner stage. A
warning stays visible but does not become a new gate. After material changes,
re-run the owner stage check because an older PASS is not authoritative.

