# Mira 0.35 Repair Note

Mira 0.35 is Mira 0.34 plus the fifth DeepSeek defect repair.

## Closed Defect

| Defect | Repair |
|---|---|
| Audit reports created duplicate flat iteration items without root-cause grouping | `scripts/iteration_loop.py` now preserves flat source items but also writes `root_causes` into `revisions/iteration_queue.json` and a Root Cause Groups table into `revisions/iteration_report.md` |

## New Contract

Use root-cause groups as the repair units. Flat queue items remain source
evidence and close-check history.

Examples:

| Repeated findings | Repair unit |
|---|---|
| Q3 penalty/travel warnings from semantic and result-quality reports | `rc-q3-result-scale` |
| Kaiwu/SDK/quantum wording warnings from semantic and model-solver reports | `rc-global-backend-lineage` |
| Thin references from quality-balance and presentation-strength reports | `rc-global-citation-support` |
| High-risk AI gate warnings/failures | `rc-g2-5-decision-review` or `rc-g4-5-decision-review` |

## Verification

On the Mira MathorCup A redo benchmark, `iteration_loop.py` should still return
FAIL because blockers remain, but the report should now show fewer root-cause
repair groups than flat source findings. This is expected: the fix reduces
duplicated repair planning, not the underlying benchmark weaknesses.

Mira is still not 0.4. Promote to 0.4 only after the remaining Mira 0.3 defect
repairs are closed and benchmarked.
