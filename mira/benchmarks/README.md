# Mira Benchmarks

This directory contains the generic benchmark contract and historical catalog.
It does not contain full historical paper projects or bundled problem-specific
answer fixtures.

- `registry.json`: all known historical projects, including complete runs,
  failed or incomplete runs, comparisons, and smoke tests.
- `HISTORICAL_PROJECTS.md`: human-readable catalog and retention policy.
- User/project-supplied case JSON files: optional executable frozen-value checks.

The former full-project archive was removed from this workspace on 2026-07-19.
Its remaining entries are cataloged for provenance only and are not runnable
benchmark inputs. A project-specific regression must use an explicit JSON
configuration kept with that project, not in Mira's reusable skill tree.

Run a matching benchmark with:

```powershell
python <mira-root>\scripts\benchmark_regression.py `
  --root <project-root> `
  --benchmark <benchmark-id-or-json> `
  --write-report checks\benchmark_regression_report.md `
  --write-json checks\benchmark_regression_report.json
```

Generic final verification must not apply historical expected values to a new
problem. `--benchmark auto` exits successfully with an informational report
when no safe known-case match exists.

## Candidate Comparison Packages

Use `scripts/prepare_comparison_package.py` only with a reviewed configuration
under `benchmarks/comparisons/`. The generator copies the declared papers and
problem inputs, records their real SHA256 values, creates anonymous A/B copies,
and runs the blind protocol harness. It never creates reviewer judgments or
upgrades historical runs to clean-root evidence.

```powershell
python -B <mira-root>\scripts\prepare_comparison_package.py `
  --config <mira-root>\benchmarks\comparisons\<comparison-id>.json `
  --output-root <workspace-root>\runs\mira_comparisons\<comparison-id> `
  --force
```

The resulting `checks/blind_comparison_report.json` is the canonical verdict.
Unknown budgets, historical roots, identity leakage, missing technical floors,
or missing authorized reviews must remain visible failures.
