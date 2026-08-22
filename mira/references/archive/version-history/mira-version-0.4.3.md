# Mira 0.4.3 Standard

Mira 0.4.3 is the active Mira baseline as of 2026-06-29. It is a high-award
final-paper stability upgrade over Mira 0.4.2. The 0.4.2 reasoning chain remains
intact; 0.4.3 adds a canonical result ledger, paper/report numeric consistency
checking, figure/table evidence planning, and a contest-reviewer gate.

## Upgrade Theme

| Area | 0.4.2 behavior | 0.4.3 behavior |
|---|---|---|
| Result source of truth | `frozen_numbers.json` and confidence report were checked separately | `result_ledger.py` creates a single canonical result ledger with strings, evidence, confidence, and final-claim flags |
| Paper consistency | Benchmark caught known stale values | `paper_consistency.py` checks result reports, final papers, and legacy drafts against the ledger and distinguishes candidate scan values from final stale values |
| Evidence planning | Figure/table counts were checked | `evidence_planner.py` maps each final claim to supporting figures, tables, or diagrams |
| Award readiness | Presentation checks measured format strength | `award_review_gate.py` gives a reviewer-style score, findings, and award-band estimate |
| Excellent-paper writing pattern | Writing quality rules were spread across older references | `contest-final-writing-patterns.md` promotes A070-derived abstract, per-question, evidence, validation, model-evaluation, and appendix patterns into paper writing |

## New Scripts

- `scripts/result_ledger.py`
- `scripts/paper_consistency.py`
- `scripts/evidence_planner.py`
- `scripts/award_review_gate.py`

## A070 Writing Pattern Add-On

The CUMCM 2020 A excellent paper `A070.pdf` was promoted as a writing-pattern
source, not as a source of reusable problem-specific numbers. Its durable lesson
is final-paper genre control: page-one result density, per-question
difficulty-to-model transformation, mechanism-to-equation derivation, nearby
claim-bearing figures/tables, validation with metrics, concrete model
evaluation, and useful appendix code organization.

Use `references/contest-final-writing-patterns.md` before paper drafting.
The corresponding trace note is
`materials/extracted/paper-learning/S31_CUMCM_2020A_reflow_oven_A070.md`.

## B108 Strategy-Decision Add-On

The CUMCM 2020 B excellent paper `B108.pdf` was added as a complementary
strategy-paper source. Its durable lesson is not the desert-game route itself,
but the way a final paper turns rules into a decision system, proves or scopes a
graph/state simplification, writes a complete DP block, extracts stochastic
rules from scenario statistics, validates them with random simulation, and
grounds game-theory claims in payoff matrices.

Use `references/contest-final-writing-patterns.md` for these B108-derived
strategy, stochastic, and game-writing obligations. The corresponding trace note
is `materials/extracted/paper-learning/S32_CUMCM_2020B_desert_game_B108.md`.

## Standard 0.4.3 Final Chain

Before final delivery, run the 0.4.2 confidence check, then build the ledger:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\result_confidence.py `
  --root <project-root> `
  --write-report checks\result_confidence_report.md `
  --write-json checks\result_confidence_report.json

python $PROJECT_ROOT\.codex\skills\mira\scripts\result_ledger.py `
  --root <project-root> `
  --confidence-json checks\result_confidence_report.json `
  --write-report planning\result_ledger.md `
  --write-json planning\result_ledger.json
```

Then check paper/report consistency and evidence coverage:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\paper_consistency.py `
  --root <project-root> `
  --ledger-json planning\result_ledger.json `
  --write-report checks\paper_consistency_report.md `
  --write-json checks\paper_consistency_report.json

python $PROJECT_ROOT\.codex\skills\mira\scripts\evidence_planner.py `
  --root <project-root> `
  --ledger-json planning\result_ledger.json `
  --write-report planning\evidence_plan.md `
  --write-json planning\evidence_plan.json
```

Finally run reviewer readiness:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\award_review_gate.py `
  --root <project-root> `
  --write-report checks\award_review_report.md `
  --write-json checks\award_review_report.json
```

For dry-run validation, `award_review_gate.py` can also read non-canonical
intermediate reports without overwriting final artifacts:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\award_review_gate.py `
  --root <project-root> `
  --ledger-json planning\result_ledger_test.json `
  --evidence-json planning\evidence_plan_test.json `
  --consistency-json checks\paper_consistency_test.json `
  --confidence-json checks\result_confidence_test.json
```

## Stale-Result Control

Correct frozen numbers are not enough when stale reports or old drafts still
carry pre-repair values. A final paper may mention an old sampled or coarse-grid
value only as candidate evidence, with the refined canonical value nearby and
clearly identified as final.

## Compatibility

Mira 0.4.3 is backward-compatible with 0.4.2 projects. Existing projects can
run the new final-chain scripts without regenerating models. A high-award final
delivery should not ignore a failing paper-consistency report, missing evidence
plan items, or award-review warnings.
