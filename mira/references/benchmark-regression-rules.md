# Benchmark Regression Rules

Historical benchmarks are opt-in known-case checks. Run one only when the
project matches a registered case or the user explicitly requests it.

Use `benchmarks/registry.json` to discover projects and `benchmarks/*.json` for
executable numeric checks. A benchmark freezes trusted numbers and required
evidence; it is not a full paper archive and cannot act as a universal final
delivery gate.

```powershell
python <mira-root>\scripts\benchmark_regression.py `
  --root <project-root> `
  --benchmark <benchmark-id-or-json> `
  --write-report checks\benchmark_regression_report.md `
  --write-json checks\benchmark_regression_report.json
```

With `--benchmark auto`, no safe match is an informational result. Never infer
that similarly named competitions or problem letters share expected values.
Historical project content lives in the workspace archive and stays outside
default runtime context.
