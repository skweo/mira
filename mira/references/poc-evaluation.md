# PoC Evaluation

Use this reference whenever Mira runs a short proof of concept, prototype, sample-size experiment, or method smoke test. A PoC is useful only if its result changes a later decision.

## Core Rule

A PoC has two different jobs:

| Job | Meaning | Required output |
|---|---|---|
| Smoke test | Prove the implementation can run on a small or simplified instance | run log and minimal result |
| Method screening | Decide whether a candidate method is promising, weak, rejected, or needs a larger benchmark | structured comparison table and decision report |

The `<=30` line convention applies only to smoke-test code. It must not limit the evidence collected after the code runs. If the PoC produces a numerical objective, that number must enter a comparison table and affect method selection.

## Required Artifacts

When a PoC is actually run and used for a `contest_final`, `deep`, heuristic,
stochastic, or method-choice-sensitive decision, create one of:

```text
results/tables/poc_results.csv
results/tables/method_screening.csv
results/tables/baseline_comparison.csv
```

Recommended columns:

| Column | Required? | Meaning |
|---|---:|---|
| `case` | yes | Same value for comparable methods, such as `Q3_20_customer` |
| `method` | yes | Candidate method, such as `SA`, `GA`, `DP`, `greedy` |
| `objective` | yes | Main comparable objective; lower is better by default |
| `feasible` | recommended | `true/false` or `yes/no` |
| `runtime_sec` | recommended | Runtime for the PoC |
| `seed` | recommended | Seed or run setting |
| `sample_size` | recommended | Instance size, such as number of customers |
| `notes` | optional | Constraint status, simplification, or known caveat |

Then run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\poc_evaluate.py `
  --root <project-root> `
  --write-report checks\poc_decision_report.md `
  --write-json checks\poc_decision_report.json
```

## Decision Rules

For minimization objectives:

| Signal | Decision |
|---|---|
| Candidate infeasible while another candidate is feasible | reject for that case |
| Candidate objective is at least `2.0x` the best comparable candidate | reject or downgrade; do not select as main route without a reason |
| Candidate objective is `1.25x` to `<2.0x` best | warning; use only if it has compensating advantages |
| Candidate is best but lacks feasibility/seed/runtime evidence | promising but needs validation |
| Only one method ran | smoke-test only; cannot by itself justify method selection, though a separate analytic feasibility, complexity, proof, or dominance screen may do so |

Thresholds are defaults, not universal truth. If the objective is maximized, invert the comparison and state it in the report.

Set a time, case, sample, or run cap before starting. Prefer a tiny shared case
or existing baseline, and stop after the decision threshold is crossed. Do not
expand a PoC into a full candidate tournament merely because the output level is
`contest_final`; use the full comparison only when it can materially change the
paper's conclusion and the remaining contest budget permits it.

## Gate Integration

modeling does not pass a high-risk automated method decision when the chosen method was rejected by PoC evaluation, unless the rejection is explicitly waived with a technical reason.

modeling must record:

| Subquestion | Candidate methods | PoC/baseline evidence | Decision |
|---|---|---|---|

implementation must save PoC output as a table, not only console text.

implementation must interpret poor PoC results. Do not let a weak candidate disappear silently.

## Example

If `Q3_20_customer` has:

```text
SA objective = 216466
GA objective = 720904
```

then `GA / SA = 3.33`. Under the default `reject_ratio=2.0`, GA is rejected or downgraded for that problem structure. Mira should not select GA as the main route unless there is a recorded reason such as GA solving a constraint SA did not handle, better scalability on the real size, or later full-scale evidence reversing the PoC.
