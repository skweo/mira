# Derivation Logic Rules

Use these rules when drafting or reviewing a `contest_final` Chinese
mathematical modeling paper. This reference complements
`derivation-density-rules.md`.

## Core Rule

Formula quality is not formula count. A strong paper keeps this chain visible:

```text
problem condition -> assumption -> symbol -> objective/constraint/equation ->
solver route -> result -> validation/sensitivity -> conclusion scope
```

If a formula cannot be traced backward to a problem condition or forward to a
result/validation claim, it is not yet paper-ready.

## Formula Numbering Hierarchy

Formula presentation should show hierarchy, not mechanical decoration.

| Formula role | Numbering / emphasis rule |
|---|---|
| Auxiliary derivation, local substitution, one-line definition | Usually unnumbered; explain nearby if needed |
| Core reference formula: objective, constraint group, recurrence, calibration, validation metric, complexity expression | Number or label only when the paper references it later |
| Final answer or key conclusion formula | Use a named result, bold/boxed emphasis, or a clear final-result equation; do this selectively |

Do not use equation count as a quality target. A paper can be stronger with
fewer numbered formulas if the important model, solver, validation, and final
answer formulas are easy to trace.

## Required Checks

| Link | Requirement |
|---|---|
| Symbol | Define symbols before they are used in equations or result tables |
| Objective | State whether the model minimizes, maximizes, estimates, predicts, or only checks feasibility |
| Constraint | Bind each important constraint to a condition, assumption, data range, capacity, time, conservation rule, or boundary |
| Transformation | Do not jump from raw condition to final equation with only `显然` or `易得` |
| Solver | Explain why the algorithm solves the stated formulation, not a different surrogate |
| Result | Result indicators should come from the objective, constraint audit, or validation formula |
| Strong claim | `最优`, `收敛`, `鲁棒`, `显著`, and `稳定` need proof, bound, solver gap, repeated experiment, or sensitivity evidence |

## Bad Patterns

- Formula block appears with no `其中/式中/表示/令/由...得到` explanation.
- Objective function is shown but constraints are hidden in prose.
- Constraints appear but their source is not named.
- Result section reports numbers without referencing the objective or validation metric.
- Paper says `显然`, `容易得到`, or `由此可得` where a transformation or proof is missing.
- Heuristic result is called `最优` without lower bound, solver gap, exact enumeration, or wording downgrade.
- Every display formula is numbered even when many are local substitutions or
  auxiliary algebra.
- Every display formula is boxed/bolded so the final answer loses salience.

## Repair Moves

| Finding | Repair |
|---|---|
| Undefined symbols | Complete `符号说明` or add local `其中...表示...` explanations |
| Objective/constraint gap | Return to modeling and rewrite formulation as objective + constraints + domain |
| Constraint source gap | State the problem condition or assumption behind each important constraint |
| Jump phrase | Insert the missing algebraic step, inequality, recurrence, or cited formula |
| Strong claim gap | Add proof/bound/gap/stability evidence or weaken wording |
| Section chain gap | Return to modeling depending on whether the missing item is formulation, result evidence, or trace writing |
| Over-numbered formulas | Remove numbers from auxiliary substitutions, local definitions, and one-step algebra that are never referenced |
| Under-numbered core formulas | Label the objective, constraint group, recurrence, calibration/validation metric, complexity expression, or final conclusion when later text depends on it |

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\derivation_logic_gate.py `
  --root <project-root> `
  --write-report checks\derivation_logic_report.md `
  --write-json checks\derivation_logic_report.json
```

Findings return to modeling, implementation, or paper. Do not fix derivation-logic
findings by adding decorative formulas; repair the broken link in the model
chain.
