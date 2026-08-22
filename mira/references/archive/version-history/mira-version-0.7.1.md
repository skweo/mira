# Mira 0.7.1

## Scope

Mira 0.7.1 isolates historical known-case regression benchmarks from the
generic contest-final verification chain.

## Reason

A project fixture can preserve useful regression expectations for its owning
case, but it is not a universal mathematical-modeling quality gate. Applying a
fixture to an unrelated problem creates false failures for fields that the new
problem does not define.

## Active Rules

- Do not run historical benchmarks as part of the default `verify` profile.
- Run `scripts/benchmark_regression.py` only when the user asks for a known-case
  regression or passes an explicit benchmark id/path.
- `--benchmark auto` must skip with INFO and exit 0 when no benchmark hint
  clearly matches the project.
- A benchmark failure is meaningful only inside its declared known-case scope.
  It must not enter the generic iteration queue for unrelated contest problems.

## Command

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\benchmark_regression.py `
  --root <project-root> `
  --benchmark <project-owned-benchmark.json> `
  --write-report checks\benchmark_regression_report.md `
  --write-json checks\benchmark_regression_report.json
```
