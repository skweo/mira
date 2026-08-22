# Mira 0.8.4

## Scope

Mira 0.8.4 adds formula hierarchy and numbering discipline for Chinese
mathematical modeling contest papers.

The rule is selective presentation, not maximum formatting:

| Formula level | Typical content | Presentation |
|---|---|---|
| Auxiliary derivation | algebraic substitution, local simplification, temporary relation | unnumbered display or inline math; no box |
| Reference-worthy core formula | objective, main constraint block, recurrence, calibration equation, validation metric, complexity expression | numbered/labeled when later text refers to it |
| Final answer or key conclusion | final decision rule, selected objective expression, threshold, optimum condition, strategy formula | visually emphasized, such as `\boxed{...}`, bold key symbol, or a named final-result equation |

## Writing Rules

1. Do not number every displayed formula.
2. Do not put `\boxed{...}` around every important-looking equation.
3. Number formulas only when they will be referenced later or carry a central
   modeling role.
4. Group related constraints in one numbered block when that is cleaner than
   numbering every line.
5. Leave short intermediate steps unnumbered unless a later proof, algorithm,
   table, or result paragraph explicitly points back to them.
6. A final formula marker should expose the answer to the reviewer, not decorate
   the derivation.

## Gate Behavior

`final_polish_language_gate.py` should require at least one final-formula marker
only when a paper has many displayed equations and no visible terminal result
formula. This does not imply every displayed equation needs emphasis.

`derivation_logic_gate.py` should warn only when most reference-worthy core
formulas are unlabeled. It should not warn because auxiliary equations or local
substitutions are unnumbered.

## Repair Behavior

- If core formulas are hard to reference, label the objective, constraint
  group, recurrence, validation metric, or final conclusion that the text uses.
- If too many formulas are boxed or numbered, demote auxiliary steps to
  unnumbered display math and keep only final-answer equations emphasized.
- If a formula is numbered but never referenced, either reference it in the
  solver/result explanation or remove the number.
