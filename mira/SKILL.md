---
name: mira
description: Build, run, verify, compare, and improve Chinese mathematical modeling contest papers. Use for staged contest-paper work, reproducible modeling, and Mira maintenance; not for general academic writing.
---

# Mira

## Version

Current baseline: **Mira 1.0.0**.

Mira uses four public stages. Detailed audit scripts remain available inside a
stage, but users and agents should not operate a separate sequence of numbered
phases or lettered gates.

- Machine-readable version: `VERSION`
- Release history: `CHANGELOG.md`
- Version index: `references/mira-version-index.md`
- Benchmark registry: `benchmarks/registry.json`

## Boundary

Mira produces Chinese mathematical modeling contest deliverables: problem
analysis, model derivations, executable Python or MATLAB code, reproducible
results, figures, paper sources, and a checked PDF. Research papers may inform
methods and citations, but the target genre remains a contest paper.

Never invent data, solver runs, citations, approvals, or evidence. Do not
execute unknown binaries. Keep user-provided raw material unchanged.

## Four-Stage Workflow

| Stage | Purpose | Canonical evidence | Exit condition |
|---|---|---|---|
| `analysis` | Understand the problem and data | `planning/delivery_brief.md`, `planning/problem_analysis.md` | subquestions, fields, units, outputs, ambiguities, and data readiness are explicit |
| `modeling` | Build and derive the model | `planning/modeling_plan.md`, `planning/validation_plan.md` | variables, assumptions, objectives, constraints, derivation, solver, baseline, and validation are specified |
| `implementation` | Write code, run it, freeze results, and draw figures | `code/`, logs, structured results, result ledger, `figures/` | code is reproducible, results trace to runs, and visuals truthfully support claims |
| `paper` | Write, compile, inspect, and deliver the paper | `paper/main.*`, compiled PDF, consistency reports | wording, formulas, numbers, figures, citations, and final files agree |

Stage order is strict. A later stage includes all earlier stage checks. Legacy
phase or gate names are accepted by scripts and immediately normalized to one
of these four names.

## Startup

For a new or resumed project:

1. Inventory the problem, attachments, template, code, results, figures, paper,
   and existing reports. Do not overwrite useful work.
2. Read `references/workflow-orchestration.md` and select `compact`, `standard`,
   or `deep` with `scripts/select_workflow_lane.py --root <project-root> --write`.
3. Create or refresh `planning/delivery_brief.md` with contest, template,
   language, output level, privacy boundary, and expected artifacts.
4. Route only the current stage:
   `python scripts/route_references.py --root <project-root> --stage <stage> --write`.
5. Read only `Load Now` in `planning/reference_route.md`.
6. Work the stage and run its concise command profile.
7. Close the stage with
   `python scripts/stage_gate.py --root <project-root> --stage <stage>`.

Refresh shared state when resuming or after material changes:

```powershell
python scripts/mira_state.py --root <project-root> --stage <stage> --write --write-report planning\mira_state.md
```

When a material input, assumption, model, result, figure, or paper source
changes and the affected scope is unclear, optionally run
`scripts/change_impact.py --changed <project-relative-path>`. It prints targeted
recheck advice only: it reads no project files, writes no state, and never
blocks a stage.

## Output Levels

- `quick_draft`: analysis or a scaffold; execution and PDF may be omitted.
- `reproducible_draft`: executable model, traceable results, clear limitations,
  and stage checks; unresolved human choices remain visible.
- `contest_final`: official or closest template, complete evidence chain,
  frozen results, traceable claims, compiled PDF, and final checks.

A request for a complete, submittable, or comparison-ready paper defaults to
`contest_final` unless the user asks for less.

## Decisions And Diagnostics

Only a real ambiguity that materially changes the interpretation, model, data,
or requested output becomes a `requires_user_decision` blocker. Record the
question, options, recommendation, owner stage, and resolution in the owning
artifact. Do not create legacy decision or approval sentinel files or labels.

Ignore legacy decision, approval, and control-plane files. Do not migrate their
pending state into the four-stage workflow. Internal quality scripts may run
specialized checks; their reports are diagnostic evidence, not extra workflow
stages. An explicit current `FAIL` blocks the owning stage.

## Hard Rules

- Parse structured data with structured tools and preserve field meaning and units.
- Map attachments and confirm data readiness before data-dependent modeling.
- Define symbols, assumptions, objectives, constraints, solver route, and validation.
- Route reusable methods by problem mechanisms; never import historical answers,
  problem-specific values, or retired benchmark fixtures into a new project.
- Record at least two structurally different candidates for each substantive
  modeling choice, except when a proof or dominance certificate establishes a
  unique route.
- Compare candidates with the cheapest decisive evidence first: analytic
  screening, complexity and feasibility checks, tiny cases, downsampling, or an
  existing baseline. Set a time or run cap before computation. A documented
  contest-time or compute-budget waiver may skip an expensive candidate
  tournament, but never the selected model's feasibility, constraint, and final
  result validation.
- A smoke test proves executability only; it does not prove model quality.
- Do not call a heuristic best-found result globally optimal without proof.
- Preserve seeds, convergence, stability, runtime, and solver status where relevant.
- Freeze canonical numbers before final claims and trace every important number.
- Keep model statements consistent with the code and solver actually run.
- Use figures only when they answer a question or support a claim.
- Preserve source data and reproducible Python or MATLAB figure code.
- Keep structural diagrams separate from data charts and retain editable sources.
- Use Chinese captions and labels for Chinese contest papers, except symbols and units.
- Cite exact claims and sources; never pad the bibliography.
- Keep internal workflow and audit language out of the paper.
- Do not generate or maintain a paper appendix as a Mira workflow artifact.
  Keep code, long tables, logs, and diagnostics as separate supporting result
  files. Existing appendix headings are read only for compatibility with
  user-provided or official source files.
- Compile and visually inspect the PDF before final delivery.
- For `contest_final`, block delivery on actual final-artifact violations such
  as a missing PDF, exceeded configured page limit, identity leak, or missing
  configured required file. Unconfigured competition-specific checks are skipped.
- A prior PASS never overrides newer artifacts or a newer blocker.

## Execution Loop

For each stage:

1. Inspect current inputs and existing evidence.
2. Route references and commands for that stage.
3. Update the canonical artifact instead of creating a parallel authority.
4. Run code or checks needed to support the stage claims.
5. Record any `requires_user_decision` blocker plainly.
6. Run `stage_gate.py`; return to the earliest failing stage when needed.
7. Continue only after the stage has no blocking findings.

For `contest_final`, `contest_final_pipeline.py` remains the internal build and
audit runner. It checks generic final artifacts plus explicitly configured
competition requirements and does not add another public stage.

## Materials

Keep raw files immutable. Index large collections before reading them, extract
only reusable notes, and promote only checked general rules into active
references. Reference papers are evidence and method input, not templates to
copy mechanically. Historical or archived files are never loaded by default.

## Maintenance

When changing Mira:

1. Read `references/skill-compaction-control-rules.md` and
   `references/skill-compaction.md`.
2. Treat `references/reference-registry.json` as the ownership and loading
   authority for every top-level reference. Run `scripts/reference_registry_audit.py`
   and `scripts/mira_skill_compaction_audit.py` before moving or merging files.
3. Preserve callers and keep specialized diagnostics separate when they test
   genuinely different quality dimensions.
4. Keep obsolete control documents out of the live skill root; preserve only a
   concise change-history entry when compatibility behavior matters.
5. Update `VERSION`, `CHANGELOG.md`, `references/mira-version-index.md`,
   `benchmarks/registry.json`, and agent metadata together.
6. Run unit tests, stage route smoke tests, syntax checks, and the compaction audit.

Runtime code must resolve the live skill root from its own location and must not
depend on an absolute checkout path.
