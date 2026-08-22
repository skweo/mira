# Mira 0.6.2

Mira 0.6.2 repairs a derivation-density regression found after comparing a
Mira 0.6 paper with a stronger Mira 0.5 paper.

## Diagnosis

The weakness is not only page layout. The paper can be long while becoming
mathematically thin in the second half: early sections contain formulas and
derivations, while later sections expand into confidence, implementation,
contribution, and discussion prose with almost no display equations or
quantitative anchors.

Skill compaction in 0.5.12 is not a direct instruction to remove derivations.
The actual failure mode is missing counter-pressure: prose-oriented gates and
repair sections accumulated, but no gate checked that formulas, constraints,
validation evidence, and quantitative rules remain distributed through the
whole paper.

## New Standard

For `contest_final`, substantial later sections must stay evidence-bearing:

- validation/credibility sections need residuals, audits, baseline deltas,
  sensitivity tables, or inequalities;
- solver-efficiency sections need scale, complexity, runtime, or pruning
  expressions;
- assumption-relaxation sections need changed equations, transitions,
  posterior updates, or new parameters;
- engineering sections need trigger formulas, decision rules, KPI definitions,
  or workflow tables;
- contribution/discussion sections should be short unless each claim binds to a
  table, figure, formula, or computed result.

## New Gate

Run:

```bash
python scripts/derivation_density_audit.py --root <project-root> --write-report checks/derivation_density_report.md --write-json checks/derivation_density_report.json
```

Unresolved findings return to:

- modeling if a missing formula, variable, objective, constraint, or proof must
  be modeled;
- implementation if missing sensitivity, baseline, runtime, validation, or result
  evidence must be computed;
- paper if the evidence exists but was not written into the paper.
