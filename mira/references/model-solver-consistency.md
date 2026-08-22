# Model-Solver Consistency

Use this reference when a contest problem asks for a named modeling form,
platform, SDK, solver, or hardware backend, especially QUBO, Kaiwu SDK,
quantum machine, MILP, DP, SA, GA, local search, or other solver-specific
claims.

## Core Rule

Separate three layers and keep them consistent:

| Layer | Meaning | Valid paper wording |
|---|---|---|
| Model form | Mathematical encoding, such as QUBO, MILP, graph model, DP recurrence | "we formulate", "can be converted", "model interface" |
| Execution solver | Code/backend that actually produced saved numbers | "we solved with", "result comes from", "run log shows" |
| Future/backend compatibility | A solver or SDK that could be used later but was not run | "can be connected", "not executed in this run", "limitation" |

A model form is not evidence that the corresponding solver ran. If QUBO is
formulated but Kaiwu SDK is unavailable, the paper may discuss QUBO as a model
interface, but the numerical results must be attributed to the actual solver
used in code.

## Required Checks

### Solver Lineage

For each subquestion, record:

- formulated model family;
- actual solver used in this run;
- result source file;
- run log or table that proves the solver produced the frozen number;
- whether any advertised platform was unavailable or not executed.

Preferred artifact:

```text
checks/model_solver_consistency_report.md
checks/model_solver_consistency_report.json
```

When useful, also write a project-owned table:

```text
results/tables/solver_lineage.csv
```

with columns `case,model_form,actual_solver,result_source,run_log,backend_status,notes`.

### QUBO And Backend Claims

Flag these as failures:

- the paper says Kaiwu SDK, quantum machine, or QUBO solver produced a result
  while logs or frozen settings say it did not run;
- a full QUBO variable count exceeds the backend limit, but the paper claims it
  was directly solved on that backend;
- QUBO is used as the headline method while actual results come from a different
  solver and the distinction is not stated near the results.

Flag these as warnings:

- the contest asks for SDK/hardware validation, but the environment did not run
  it and the paper only discloses the limitation;
- the frozen numbers lack per-question solver/source fields, even though other
  artifacts make the lineage recoverable;
- the paper title/abstract overemphasizes a backend that was not executed.

### Scale Feasibility

For QUBO or binary encodings, compare recorded binary-variable counts with the
available backend capacity. A 550-bit backend cannot directly solve a 2500- or
12505-variable compact QUBO. Large QUBO cases must be described as:

- decomposed into backend-sized subproblems and actually run; or
- kept as a model layer while another solver produced the submitted numbers; or
- intentionally not executed, with a limitation statement.

### Paper Wording

Allowed:

- "本文给出 QUBO 建模，并用经典算法进行可复现实验。"
- "当前环境未实际调用 Kaiwu SDK，数值结果来自 DP/SA/local search。"
- "50 客户 QUBO 超出 550 比特直接规模，因此采用分解或启发式求解。"

Not allowed:

- "利用 Kaiwu SDK 求解得到路线" when SDK did not run.
- "量子真机输出表明..." without a real output artifact.
- "QUBO 求解得到最优路线" when the saved result comes from SA or local search.

## Executable Gate

Recommended command:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\model_solver_consistency.py --root . --write-report checks\model_solver_consistency_report.md --write-json checks\model_solver_consistency_report.json
```

For `contest_final`, a `FAIL` blocks implementation and final delivery. A `WARN` must be
disclosed in compliance or repaired by adding solver lineage, run logs, or
corrected paper wording.

## Repair Routing

| Finding pattern | Return to | Required repair |
|---|---|---|
| backend execution falsely claimed | paper, possibly implementation | remove/replace claim, or produce real backend run logs |
| QUBO scale exceeds backend but direct solve is claimed | modeling | add decomposition, change solver route, or state QUBO as model layer only |
| actual solver differs from paper wording | implementation | add solver-lineage table and revise result text |
| SDK required but not executed | implementation | run SDK if available; otherwise disclose as limitation and do not claim SDK output |
| frozen numbers have no solver/source lineage | implementation | add solver/source fields or `solver_lineage.csv` |
