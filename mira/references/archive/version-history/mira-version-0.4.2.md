# Mira 0.4.2 Standard

Historical note: Mira 0.7.1 supersedes the default-delivery behavior described
here. Explicit project benchmarks must not run as generic final-delivery
blockers for unrelated problems.

Mira 0.4.2 was the active Mira baseline as of 2026-06-29. It was an automation
and regression-control upgrade over Mira 0.4.1. The modeling knowledge added in
0.4.1 remained unchanged; 0.4.2 made that knowledge easier to route, validate,
and compare against known repaired runs.

## Upgrade Theme

| Area | 0.4.1 behavior | 0.4.2 behavior |
|---|---|---|
| Method routing | The agent manually chose knowledge-retrieval query terms | `method_route.py` scans project artifacts and writes route IDs, validation groups, and a recommended retrieval query |
| Knowledge validation | `knowledge_application_audit.py` checked whether retrieved cards were used | `validation_plan.py` turns routes/cards into concrete expected evidence before implementation and final checks |
| Regression memory | Repaired project results were described only as rules | `benchmark_regression.py` checks explicitly supplied project fixtures and catches stale pre-repair artifacts |
| Result confidence | Result quality gates checked numeric symptoms | `result_confidence.py` grades each frozen result as certified, refined, audited, heuristic, sampled, or unverified |
| Final delivery | Control-plane and quality gates were separate checks | 0.4.2 adds benchmark and confidence checks before final comparison or delivery |

## New Scripts

- `scripts/method_route.py`
- `scripts/validation_plan.py`
- `scripts/benchmark_regression.py`
- `scripts/result_confidence.py`

## Benchmark Fixtures

Project-specific fixtures may be passed explicitly to
`benchmark_regression.py`. They belong with the project that owns the expected
results, not in Mira's reusable skill tree. A project may have correct frozen
numbers and still fail its fixture when old reports or drafts contain stale
values.

## Standard 0.4.2 Modeling Sequence

For `contest_final`, `deep`, risky, or comparison runs:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\method_route.py `
  --root <project-root> `
  --write-report planning\method_route.md `
  --write-json planning\method_route.json
```

Then run `knowledge_retrieve.py` with the route's recommended query and write
both Markdown and JSON outputs:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\knowledge_retrieve.py `
  --root <project-root> `
  --query "<recommended query>" `
  --write-report planning\knowledge_injection.md `
  --write-json planning\knowledge_injection.json
```

Then generate the validation plan:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\validation_plan.py `
  --root <project-root> `
  --write-report planning\validation_plan.md `
  --write-json planning\validation_plan.json
```

## Standard 0.4.2 Final Checks

Before final delivery, keep the 0.4.1 gates and add:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\result_confidence.py `
  --root <project-root> `
  --write-report checks\result_confidence_report.md `
  --write-json checks\result_confidence_report.json
```

When the project matches a known benchmark, or when the user asks to compare
with public/known results:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\benchmark_regression.py `
  --root <project-root> `
  --benchmark auto `
  --write-report checks\benchmark_regression_report.md `
  --write-json checks\benchmark_regression_report.json
```

## Compatibility

Mira 0.4.2 is backward-compatible with Mira 0.4.1 artifacts. Existing projects
do not need to regenerate code or papers merely to use the new scripts, but a
0.4.2 final delivery should not ignore stale-artifact or low-confidence findings
from the new checks.
