# Skill Compaction

Use this reference when Mira would otherwise load granular mathematical-modeling skills such as `problem-parser`, `problem-classifier`, `method-selector`, code generators, paper writers, or auditors.

## Core Rule

Long skill instructions are not the workflow. The workflow is the canonical
four-stage contract, executable scripts, and saved artifacts.

In `compact` and `standard` lanes, do not load a long granular `SKILL.md` when
the same work fits into one canonical stage artifact:

| Long granular skill | Compact replacement |
|---|---|
| `problem-parser`, `problem-classifier` | `planning/problem_analysis.md` |
| `symbol-table-builder` | `planning/symbol_table.md` |
| `method-selector`, `model-assumptions-builder` | `planning/modeling_plan.md` + `stage_gate.py --stage modeling` |
| `python/matlab-code-generator` | executable code under `code/` + run logs |
| `result-report-generator`, `robustness-checker` | `results/result_report.md`, audit tables, semantic audit |
| `paper-section-writer`, `paper-polisher` | `paper/main.*` + contest-final writing contract |
| `consistency/completeness/QA auditor` | decision, semantic, quality-balance, artifact, and compliance scripts |

## 50-Line Contract Pattern

A compact skill or phase note should fit this shape:

```text
Purpose: one sentence.
Inputs: exact files.
Output: one canonical artifact.
Required fields: 5-12 bullets or table columns.
Check: pass/fail checks.
Stop condition: blockers and return stage.
Scripts/templates: commands to run.
```

Avoid:

- long examples that restate common modeling knowledge;
- duplicate JSON and Markdown outputs for the same content;
- separate parser/classifier/method notes when `problem_analysis.md` or `modeling_plan.md` already carries the fields;
- placeholder human-decision files;
- skill chains that exist only to create low-value artifacts.

## Expansion Rule

Load or invoke a granular skill only when one of these is true:

1. `planning/workflow_lane.md` selected `deep`;
2. `revisions/iteration_report.md` names the skill's owning stage as open/blocking;
3. a task-specific mechanism is too fragile for the canonical contract alone;
4. an executable helper or template in that skill is needed.

If a long skill is loaded, extract only the relevant input/output/check contract
first. Do not keep reading hundreds of lines of prose unless the stage remains
blocked.

## Audit Command

Run the compaction audit on external skill sets:

```powershell
$externalSkillsRoot = '<external-skill-checkout>'
python scripts\compact_skill_contracts.py --skills-root $externalSkillsRoot --write-report checks\skill_compaction_report.md
```

Run the command from the live Mira skill root and supply the checkout to audit;
Mira does not require or assume a permanent external skill repository.

For Mira itself, the report should stay small and focus on long external skills that would otherwise be loaded by the workflow.

## Design Target

For routine contest papers:

- `problem_analysis.md` should replace parser + classifier artifacts;
- `modeling_plan.md` should replace method selector + assumption builder artifacts;
- scripts should replace repeated audit/check instructions;
- references should hold domain knowledge, not stage-control prose.

The goal is not to remove expertise. The goal is to put expertise where it is cheapest and least confusing: short contracts for control flow, scripts for deterministic checks, references for optional deep knowledge.
