# Adaptive Workflow Lanes

Use this reference at startup before loading granular skills or long method references. It fixes Mira's token-efficiency failure mode: a long skill chain should not run when a smaller stage contract can preserve the same quality check.

Mira has one external interface, `workflow_lane`, and three internal execution lanes:

| Lane | Use when | Execution style | Artifact policy |
|---|---|---|---|
| `compact` | quick checks, small single-method tasks, user asks for direction rather than a final PDF | Combine adjacent work inside the current stage artifacts | Write only `delivery_brief`, `workflow_lane`, and the smallest needed stage files |
| `standard` | normal contest work, including most `contest_final` papers with available data and clear subquestions | Use the four Mira stages directly; call specialized checks only for risky details | Write canonical artifacts, avoid duplicate JSON+MD pairs unless a script consumes the JSON |
| `deep` | ambiguous/high-risk tasks, failed quality checks, complex data extraction, inverse/PDE/neural/large optimization, or user explicitly asks for diagnosis | Expand selected stages with specialized methods and extra audits | Write extra artifacts only for the stages that need them; still skip empty reports |

The default lane for a formal paper is `standard`, not `deep`. `contest_final` means strong gates, not automatic over-decomposition.

## Startup Rule

Before loading detailed references or running granular skills:

1. Create or update `planning/delivery_brief.md`.
2. Select a lane and write `planning/workflow_lane.md`.
3. Apply `skill-compaction.md`: do not load long granular `SKILL.md` files in `compact` or `standard` when a canonical stage artifact can carry the same contract.
4. Load only the references required by the selected lane and the current stage.

Recommended command:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\select_workflow_lane.py --root . --write
```

If the script is unavailable, select the lane manually using the table above and record the decision in `planning/workflow_lane.md`.

## Lane Contracts

### Compact

Compact mode is allowed to merge:

- problem parsing + problem classification into `planning/problem_analysis.md`;
- method selection + assumptions + symbol table into `planning/modeling_plan.md` and `planning/symbol_table.md`;
- result summary + figure/table plan into `results/result_report.md`.

Compact mode must still preserve:

- problem contract per subquestion;
- model variables/objective/constraints when a model is proposed;
- result provenance for any numerical answer;
- honest claim wording.

Compact mode must not be used to deliver a comparison-quality final PDF unless a later gate upgrades the lane.

### Standard

Standard mode is the default for most serious runs. It uses four stages:

1. `analysis`: delivery setup, problem interpretation, attachment mapping, and data readiness.
2. `modeling`: assumptions, symbols, derivation, method choice, solver route, and validation design.
3. `implementation`: code, runs, frozen results, tables, figures, diagrams, and reproducibility evidence.
4. `paper`: Chinese paper writing, compilation, consistency checks, and final delivery.

Do not expose specialized checks as extra stages. For example, do not run a separate `problem-classifier` just to produce a full JSON and MD when the classification is one row in `problem_analysis.md`. If a granular skill's `SKILL.md` exceeds the local compaction limit, use its compact contract or the canonical artifact instead.

### Deep

Deep mode expands only the risky parts inside their owning stage:

| Risk | Expand |
|---|---|
| ambiguous task interpretation | problem parser/classifier, assumption-risk review |
| method choice uncertain | method selector, model-depth review, PoC |
| external solver/platform dependency | computation-backend check, fallback route |
| stochastic or heuristic results | robustness checker, multi-seed audit |
| data extraction/media/inverse problem | data audit, extraction validation, residual/sensitivity checks |
| final paper quality regression | dual-quality check, paper structure revision |

Deep mode is selective. A difficult subquestion does not force unrelated subquestions or stages to use every granular skill.

## Artifact Budget

Every artifact must have a downstream consumer.

| Artifact type | Write when | Skip when |
|---|---|---|
| Markdown stage report | Needed for review, paper writing, or later checks | It only repeats another canonical artifact |
| JSON artifact | A script, checker, or later phase reads it | It is only a structured duplicate of an MD report |
| Empty report | Almost never | Source folder is empty; record the skip in `workflow_lane.md` instead |
| Related-paper report | Real papers or verified web/literature sources were used | No papers were provided and no citation-sensitive method was chosen |
| Granular skill transcript | The stage is high-risk or failed once | The canonical stage artifact already satisfies the check |
| Long `SKILL.md` instruction text | `deep` lane or an open iteration item names that stage | The task is routine parsing, classification, method listing, or formatting |

Do not create placeholder reports such as `NO_USER_PAPERS.md` unless a checker explicitly requires that file. Prefer a one-line skip note in `planning/workflow_lane.md`.

## Expansion Triggers

Upgrade the lane or expand one stage when any trigger appears:

- A gate fails in `checks/compliance_report.md` or `checks/quality_balance_report.md`.
- The model choice changes a numerical answer materially.
- A result is unsupported by provenance, recomputation, or hard-constraint audit.
- A heuristic result needs baseline, multi-seed, convergence, or sensitivity evidence.
- A data source has unclear fields, units, missing values, or extraction rules.
- The paper is being compared against strong agent outputs or strong contest papers and the weakness is not localized.

Downgrade back to `standard` after the failing stage is repaired. Do not keep deep mode on for all future stages by inertia.

## Reporting Rule

`planning/workflow_lane.md` must list:

- selected lane;
- reasons;
- skipped granular skills and why they are safe to skip;
- references to load now;
- expansion triggers;
- current artifact budget.

This file replaces several low-value placeholder artifacts. It is the scheduler's compact memory of why Mira did less work without lowering quality.
