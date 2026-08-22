# Mira 0.7

## Scope

Mira 0.7 removes hard page-count and word-count pressure from contest-final
paper generation. The goal is to stop agents from spending time and tokens on
padding once the model, results, validation, and paper evidence are complete.

## Core Rule

Length is a symptom, not a target.

- Do not require a minimum number of pages, visible characters, figures, or
  tables for final delivery.
- Do not extend sections only to satisfy page, word, figure, or table counts.
- Treat shortness as a prompt to check for missing evidence, not as a failure by
  itself.
- Treat longness as a risk when the added text does not carry equations,
  result evidence, validation, citations, implementation detail, or useful
  figure/table interpretation.

## Evidence-Density Gate

A contest-final paper is complete when every official subquestion has:

| Need | Acceptable evidence |
|---|---|
| Problem translation | input/output/constraint/objective contract |
| Model | variables, assumptions, equations, objective, or recurrence |
| Solver route | exact, simulation, search, heuristic, or solver-backed route with scope |
| Result | frozen number, table, figure, route, schedule, parameter, or policy |
| Validation | baseline, sensitivity, constraint audit, residual, proof, bound, or waiver |
| Paper support | nearby explanation, caption, table/figure reference, and limitation scope |

If these needs are met, do not pad the paper. If they are not met, add the
missing evidence rather than adding prose.

## Checker Behavior

Mira 0.7 checkers should:

- record `page_count`, `visible_chars`, figure count, and table count as metrics;
- avoid FAIL/WARN solely because those counts are below an old threshold;
- raise findings for missing evidence roles, missing validation, missing result
  traceability, weak figures, unbound citations, short outline-like sections
  only when the missing evidence is named;
- prefer messages such as "missing Q3 sensitivity evidence" over "paper is too
  short";
- use INFO-level notes for count-based diagnostics unless a concrete evidence
  gap is also detected.

## Writing Behavior

When drafting or revising:

1. Write the smallest complete version that answers the problem.
2. Run evidence and semantic checks.
3. Add only the missing artifacts named by checks.
4. Stop when the evidence chain is complete, even if the paper is shorter than
   a previous Mira output.

For comparison with excellent papers, compare reasoning density, result
credibility, visual usefulness, and reviewability, not raw page count.
