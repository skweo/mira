# Domain Knowledge Injection

Use this reference when Mira absorbs algorithm materials, chooses a model for a contest problem, or repairs a weak heuristic/modeling result. The goal is not to memorize long notes. The goal is to turn materials into small operational knowledge cards that can change modeling decisions, code design, validation, and paper claims.

## Core Rule

For contest-final or risky modeling work, generic method names do not pass by themselves. If Mira writes "SA", "GA", "DP", "clustering", "network flow", "TSP", "VRP", "time window", or another known method family, the modeling plan must also state:

| Required detail | Meaning |
|---|---|
| Problem pattern | Why this card matches the current subquestion |
| Applicability conditions | Data scale, constraints, objective structure, and assumptions needed |
| Contraindications | When the method/card should not be used |
| Operators or mechanism | Neighborhoods, transition, recurrence, relaxation, repair, or solver structure |
| Parameter/scaling rule | Parameter ranges, normalization, penalty scaling, or calibration route |
| Validation requirement | Baseline, audit, sensitivity, multi-seed, bound, or certificate |
| Failure signs | Numerical or logical symptoms that mean the first plan is weak |
| Repair move | What to try next before writing around the result |
| Paper usage | How to phrase the method and avoid overclaiming |

If no relevant card exists, write `no_relevant_card_found` and create a candidate card under `materials/extracted/knowledge-cards/` after reading the new material.

## Knowledge Card Lifecycle

```text
raw material
  -> extracted note
  -> candidate knowledge card
  -> validated project card
  -> promoted Mira reference card
```

| Stage | Location | Promotion condition |
|---|---|---|
| Raw material | `materials/raw/` | User supplied or copied without editing |
| Extracted note | `materials/extracted/material-extraction/` or topic note | Text/tables/code were actually inspected |
| Candidate card | `materials/extracted/knowledge-cards/` | Includes use/avoid conditions, operators, parameters, validation, and source |
| Validated card | Current project `materials/extracted/knowledge-cards/` | Used in a run, result checked, limitations recorded |
| Promoted card | Mira `references/domain-knowledge/` | General beyond one problem and supported by reliable source or repeated project evidence |

Do not promote copied prose. Promote decisions, constraints, operators, parameter ranges, diagnostics, and repair moves.

## Card Schema

Use this compact schema for algorithm experience cards:

```markdown
# Knowledge Card: <domain>/<method or pattern>

## Tags
- <keywords in Chinese and English>

## Problem Patterns
- <signals that should retrieve this card>

## Applicability Conditions
- <when this advice is valid>

## Contraindications
- <when to avoid or downgrade it>

## Algorithm Core
- <formulation, recurrence, solver structure, or search skeleton>

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|

## Validation Requirements
- <baseline, bound, feasibility audit, multi-seed, sensitivity, convergence>

## Failure Signs
- <symptoms>

## Repair Moves
- <next stronger changes>

## Paper Usage
- <contest-paper phrasing and claim limits>

## Source Materials
- <path/citation/reliability>

## Confidence
- low / medium / high, with reason
```

## Retrieval Workflow

Before modeling modeling for `contest_final`, `deep`, or any heuristic/routing/time-window/inverse/ML-heavy problem:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\knowledge_retrieve.py `
  --root <project-root> `
  --query "<problem terms and candidate method terms>" `
  --write-report planning\knowledge_injection.md `
  --write-json planning\knowledge_injection.json
```

Mira 0.4.1 also scans `$PROJECT_ROOT\Math_Model\extended_knowledge_cards`
by default when that directory exists. Keep those DeepSeek-provided cards as
source material unless a project-validated pattern deserves promotion into
`references/domain-knowledge/`.

Then paste or summarize the selected card obligations into `planning/modeling_plan.md`:

| Subquestion | Card used | Required model detail | Where implemented |
|---|---|---|---|
| Qx | `...` | operators/parameters/validation/repair | plan/code/result/paper path |

The retrieved cards are obligations, not citations. If Mira rejects a card, it must record why the current task violates applicability conditions or hits a contraindication.

For continuous extrema, threshold crossings, collision boundaries, or scale
factors, retrieval should include `validation/continuous-extremum-search` when
any grid, integer-second, sampled, or coarse scan appears in the method route.

## Feeding New Algorithms

When the user feeds algorithm materials:

1. Extract supported files with `scripts/extract_materials.py`.
2. Read the relevant extracted text, tables, images, and code snippets.
3. Create one candidate knowledge card per reusable algorithmic idea.
4. Prefer operational details over summaries: exact neighborhood, recurrence, repair rule, parameter grid, convergence check, or failure mode.
5. Record source reliability and scope. A single generated paper or untested code example is `low` confidence.
6. Use the card in a small project or validation run before promoting it to `references/domain-knowledge/`.

## Gate Integration

modeling does not pass for contest-final risky models unless `planning/modeling_plan.md` includes the knowledge-injection table or explicitly states no relevant card exists. implementation does not pass for heuristic/stochastic methods unless code outputs include the validation requirements named by the card or a recorded waiver. implementation does not pass when a failure sign appears and the listed repair moves were not attempted or waived.

Run the executable gate before final delivery:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\knowledge_application_audit.py `
  --root <project-root> `
  --write-report checks\knowledge_application_report.md `
  --write-json checks\knowledge_application_report.json
```

This gate closes the loop: retrieval alone is not enough. A selected card must
be traceable into modeling, code/result validation, repair moves, or an
explicit waiver.
