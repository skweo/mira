# Mira 0.34 Repair Note

Mira 0.34 is Mira 0.33 plus the fourth DeepSeek defect repair.

## Closed Defect

| Defect | Repair |
|---|---|
| Figure and reference counts regressed because implementation had no generation budget | Added `scripts/plan_presentation_budget.py`; `check_presentation_strength.py` now reads `planning/presentation_budget.json` and blocks papers below budget |

## New Contract

For `contest_final`, run the presentation-budget planner before implementation and
paper:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plan_presentation_budget.py --root <project-root>
```

The budget records minimum and target counts for claim-bearing figures, tables,
real used references, and in-text citations. It also records the required
evidence ladder: data structure, model logic, result evidence, validation
evidence, and problem-specific additions.

## Verification

On the Mira 0.3 MathorCup redo benchmark, the generated budget requires more
figures/references than the paper currently contains, so
`check_presentation_strength.py` returns FAIL. This is expected: the benchmark
paper is treated as a regression example, not as the new target.

Mira is still not 0.4. Promote to 0.4 only after the remaining Mira 0.3 defect
repairs are closed and benchmarked.
