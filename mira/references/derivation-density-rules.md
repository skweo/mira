# Derivation Density And Math Continuity Rules

Use these rules when a `contest_final` paper looks long but the mathematical
chain weakens in the second half. This is a regression guard against papers
that front-load equations, then finish with long prose about implementation,
confidence, contribution, or evaluation without formulas, tables, figures, or
auditable evidence.

Use `derivation-logic-rules.md` when equations are present but their symbols,
objective/constraint source, derivation steps, or strong claims are not
logically connected.

## Core Principle

A strong modeling paper should keep the chain

```text
problem mechanism -> variables -> equation/objective/constraint -> solver ->
result evidence -> validation/sensitivity -> interpretation
```

visible throughout the body. Later sections may be more interpretive, but they
must still point to mathematical evidence.

## Required Continuity

- Do not place all governing equations in early shared sections and then let
  later problem, validation, robustness, or implementation sections become
  prose-only.
- For every substantial subquestion section, include at least one mathematical
  anchor: equation, objective/constraint block, recurrence, algorithm state,
  parameter table, result table, validation figure, or explicit reference to
  the shared formulation it specializes.
- For sensitivity, robustness, assumption-relaxation, solver-efficiency,
  engineering-implementation, and contribution sections, include quantitative
  evidence when feasible: threshold inequality, sensitivity table, complexity
  expression, state-transition correction, KPI formula, baseline delta, or a
  compact decision rule.
- Model evaluation and conclusion may be prose-heavy, but they should be short
  and should not replace missing derivations from previous sections.

## Tail-Section Guardrail

The last third of the main body should not be a long pure-prose tail. If a
paper has more than several pages after the last display equation, table, or
claim-bearing figure, return to modeling:

- modeling if the missing item is a real model, equation, proof, or variable
  definition;
- implementation if the missing item is computed sensitivity, baseline, validation,
  or solver evidence;
- paper only if the evidence exists but was not written into the paper.

## Repair Moves

Use these repairs before adding more explanatory text:

| Weakness | Repair |
|---|---|
| Long validation prose | Add residual/error table, constraint audit table, baseline delta, or sensitivity curve |
| Solver discussion without math | Add complexity expression, state/strategy count, pruning condition, or runtime table |
| Assumption relaxation as prose | Add changed equation, posterior update, confusion matrix, or new parameter definition |
| Engineering recommendation as prose | Add decision-rule formula, trigger threshold, workflow table, KPI definition, or exception condition |
| Contribution section as praise | Add evidence binding: baseline/table/figure/formula and scope |
| Discussion section too long | Compress it into a short model-evaluation section or omit low-value prose |

## Common Failures

- Pages after the middle of the paper contain almost no display equations,
  formulas, tables, or figures.
- Sections named `结果可信度`, `证据链`, `创新贡献`, `工程落地`, or `综合讨论` are long
  but contain no quantitative anchors.
- The paper says "结果可信" or "具有应用价值" without a nearby calculation,
  inequality, table, or validation figure.
- The conclusion and evaluation sections compensate for missing derivation by
  adding more prose.
