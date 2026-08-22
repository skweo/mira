# Semantic Audit Rules

Use this reference before freezing results, before final paper writing, and before final delivery. Semantic audit answers the question that formal auditors miss: not only "does the artifact exist?", but "is the result plausible, supported, and honestly argued?"

Consistency, completeness, and artifact-manifest checks are necessary but not sufficient. A number can match `frozen_numbers.json` and still be a bad result. A figure can exist and still prove nothing. A paper can compile and still overclaim.

## Audit Layers

| Layer | Checks | Cannot replace |
|---|---|---|
| Formal existence audit | required files, figures, references, frozen numbers, compile status | semantic audit |
| Consistency audit | paper numbers match saved outputs | plausibility, parameter, or proof audit |
| Semantic audit | result scale, objective decomposition, parameter evidence, solver evidence, validation strength, and paper claim logic | formal existence and traceability checks |
| Result-quality evaluation | computed component ratios, baseline regression, convergence tail, stability spread, recommendation sensitivity | semantic audit and paper claim logic |
| Model-solver consistency | model/backend claims match actual executed solver and frozen-number lineage | result-quality and semantic claim logic |

For `contest_final`, all three layers must pass or have explicit warnings in `checks/compliance_report.md`.

## Required Semantic Checks

### Result Scale

For each important objective, penalty, error, score, or parameter:

- Compare it with same-problem baselines when available.
- Compare objective components against each other, such as penalty/travel, vehicle cost/routing cost, fitting error/noise scale.
- Flag values that are orders of magnitude larger than related quantities unless a bound, derivation, or scenario explanation exists.
- Check whether units make the scale interpretable.

Large values are not automatically wrong. They become acceptable only when the paper or result report gives a quantitative reason, such as a lower bound, bottleneck analysis, infeasibility pressure, time-window pressure, residual distribution, or sensitivity table.

### Parameter Evidence

Each important weight, penalty coefficient, fixed cost, threshold, capacity, target, iteration count, temperature schedule, hidden-layer size, or solver tolerance must have:

- data source, official statement, estimate method, calibration, sensitivity check, or explicit assumption;
- a note on which result it affects;
- sensitivity or scenario check when it materially changes the answer.

If a recommendation depends on an arbitrary coefficient, the semantic audit must warn even when the coefficient is consistently used.

### Solver Evidence

For exact claims, require proof, recurrence, solver gap, or certificate. For heuristics, require:

- baseline comparison;
- seed/settings;
- convergence or improvement history;
- repeated run or stability evidence when feasible;
- constraint audit and objective recomputation.

If a heuristic result is called "最优", "全局最优", or "optimal" without evidence, semantic audit fails.

### Paper Claim Logic

Check whether the paper's argument matches its evidence:

- A conclusion must cite a computed table, figure, bound, audit, or sensitivity result.
- A surprising result must be interpreted where it appears.
- A limitation cannot be generic; it must follow from the actual model or data.
- A recommendation must name the scenario and computed indicator that supports it.
- A method that was not actually executed must not be presented as a source of numerical results.

## Routing

| Semantic issue | Return to |
|---|---|
| implausible result scale without explanation | implementation Result Analysis; possibly implementation Code |
| parameter sensitivity missing | implementation Code or implementation Result Analysis |
| heuristic evidence missing | implementation Code |
| unsupported optimality or method claim | paper Paper Writing or implementation Result Analysis |
| paper conclusion unsupported by artifact | paper Paper Writing |
| method/result mismatch | modeling Modeling Plan or implementation Code |

Do not fix semantic failures by editing frozen numbers by hand. Regenerate results or weaken claims.

## Executable Gate

Recommended command:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\semantic_audit.py --root . --write-report checks\semantic_audit_report.md
```

Pair it with the numeric result-quality gate:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\result_quality.py --root . --write-report checks\result_quality_report.md --write-json checks\result_quality_report.json
```

For QUBO, SDK, hardware, or solver-heavy tasks, also pair it with model-solver
consistency:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\model_solver_consistency.py --root . --write-report checks\model_solver_consistency_report.md --write-json checks\model_solver_consistency_report.json
```

For `contest_final`, a `FAIL` in `semantic_audit_report.md` blocks final delivery. A `PASS_WITH_WARNINGS` must be summarized in `checks/compliance_report.md`.
