# Workflow Orchestration

Mira has one public sequence:

`analysis -> modeling -> implementation -> paper`

Each stage owns a small set of canonical artifacts. Detailed audits run inside
the stage that owns their evidence and do not create more workflow states.

## Delivery Brief

Create or refresh `planning/delivery_brief.md` before modeling. Record:

| Field | Required content |
|---|---|
| Output level | `quick_draft`, `reproducible_draft`, or `contest_final` |
| Contest | competition, year, and problem number |
| Template | official or closest local template |
| Language | Chinese by default for Chinese contests |
| Final artifact | expected PDF or draft path |
| Source files | problem statement, attachments, datasets, and references |
| Privacy boundary | permitted local and external sources |
| Workflow lane | `compact`, `standard`, or `deep` |
| Current stage | earliest incomplete public stage |

Use `contest_final` for a complete/submittable paper or a comparison against
another agent unless the user explicitly requests a smaller output.

## Starting Or Resuming

1. Inventory existing artifacts and reports without deleting or overwriting.
2. Find the earliest incomplete stage from the table below.
3. Route that stage with `route_references.py --stage <stage> --write`.
4. Read only the routed `Load Now` references.
5. Run the stage command profile and update canonical evidence.
6. Run `stage_gate.py --stage <stage>`.
7. Move forward only on `PASS` or an understood nonblocking warning.

After a material change, use `change_impact.py --changed <path>` only when a
targeted recheck suggestion is useful. It classifies only the path supplied on
the command line, prints advice, and exits. It does not read project files,
save state, scan folders, hash artifacts, watch changes, or block a stage.

| Stage | Minimum evidence |
|---|---|
| `analysis` | delivery brief and problem analysis |
| `modeling` | modeling plan and validation plan |
| `implementation` | executable code, run/result artifacts, and justified visuals |
| `paper` | canonical source, internal consistency, and the required final artifact |

## Stage Transitions

`analysis -> modeling`: all subquestions, outputs, fields, units, attachment
roles, and unresolved ambiguities are explicit.

`modeling -> implementation`: variables, assumptions, objectives, constraints,
derivation, solver route, baseline, and validation route agree.

`implementation -> paper`: code runs, solver claims match the implementation,
canonical numbers are traceable, and figures have reproducible sources.

`paper -> delivery`: prose, formulas, numbers, tables, figures, citations, and
compiled files agree. `contest_final` additionally requires a READY delivery
manifest produced from the final build and audit batch. Complete
`planning/submission_requirements.json` when official rules add specific
constraints. Unconfigured title, keyword, section, page, anonymity, or
disclosure checks are skipped; actual configured violations still fail the
final batch.

## Blockers

Use `requires_user_decision` when a real user choice is missing. The record must
state the owning stage, question, viable options, recommendation and rationale,
and the resulting decision or waiver. This is a blocker field, not a fifth
stage or a separate gate sequence.

An internal diagnostic `FAIL` returns work to its owning stage:

| Finding owner | Return to |
|---|---|
| problem interpretation, source boundary, data readiness | `analysis` |
| assumptions, formulation, derivation, validation design | `modeling` |
| code, solver behavior, results, provenance, figures | `implementation` |
| paper structure, consistency, citations, compilation, delivery | `paper` |

For `contest_final`, run `python scripts\iteration_loop.py --root
<project-root>` after an audit batch reports findings. It writes
`revisions/iteration_queue.json` and `revisions/iteration_report.md`; repair the
root-cause groups by returning to their owning stages, then rerun the source
audits and stage check. Open `FAIL` items block delivery. Open `WARN` items stay
visible as `PASS_WITH_WARNINGS`. Mark an item `resolved` only after its source
finding disappears, and use `waived` only for an explicitly accepted limitation
that remains visible in the paper or compliance report.

Change-impact advice may suggest an earlier owning stage, but it is never a
workflow gate. Submission compliance belongs only to final delivery, not the
ordinary paper-stage gate or a general AI-use control plane.

## Lanes

- `compact`: minimal routed references and checks for narrow work.
- `standard`: normal contest-paper production.
- `deep`: adds task-specific method or quality references only when evidence
  requires them.

Lane selection changes depth, not the four-stage sequence.

## Commands

```powershell
python scripts\route_references.py --root <project-root> --stage <stage> --write
python scripts\command_profiles.py --stage <stage> --output-level <level> --json
python scripts\stage_gate.py --root <project-root> --stage <stage>
python scripts\mira_state.py --root <project-root> --stage <stage> --write --check
python scripts\change_impact.py --changed <project-relative-path>
```

Legacy phase and gate arguments remain accepted and normalize immediately to a
public stage. New automation should always write the four canonical names.
