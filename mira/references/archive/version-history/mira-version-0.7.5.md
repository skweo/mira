# Mira 0.7.5

## Scope

Mira 0.7.5 adds formula-derivation and logic-chain control for contest-final
papers.

## Problem Fixed

Mira 0.6.2 and 0.7.4 can detect formula density and prose padding, but they do
not directly check whether formulas form a credible chain. A paper can contain
many equations and still have undefined symbols, hidden constraints, jumpy
derivations, or strong optimality claims without proof.

## Active Rule

Every important formula should be traceable in two directions:

- backward to the contest condition, assumption, data definition, or symbol;
- forward to the solver, result table, validation, sensitivity analysis, or
  conclusion.

Do not use `显然`, `易得`, `由此可得`, `最优`, `收敛`, `鲁棒`, or `显著` as substitutes
for derivation, proof, solver gap, baseline comparison, or repeated
experiments.

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\derivation_logic_gate.py `
  --root <project-root> `
  --write-report checks\derivation_logic_report.md `
  --write-json checks\derivation_logic_report.json
```

Findings enter the iteration queue. Repairs may return to modeling when the
model is underspecified, implementation when evidence is missing, or paper when the
evidence exists but the paper failed to connect it.
