# Mira 0.5.3

Mira 0.5.3 upgrades high-award critique response with assumption-relaxation
evidence.

## Added Capability

**Assumption relaxation**

Contest-final papers should not leave strong assumptions as generic limitations.
They should explain how at least one important assumption can be relaxed and how
the model equation, state transition, or decision would change.

Priority relaxations:

- imperfect detection: false negatives, false positives, sensitivity,
  specificity, confusion matrix;
- dismantling or rework damage;
- correlated component defects;
- finite inspection/repair capacity;
- sample-size or confidence-level dependence.

Preferred artifacts:

- `planning/assumption_relaxation_plan.md`
- `results/tables/imperfect_detection_sensitivity.csv`
- `results/tables/assumption_relaxation.csv`
- `figures/imperfect_detection_*.png`

## New Gate Behavior

The award gate checks whether papers that assume perfect detection, independence,
or no damage include concrete extension language. Generic "future work" without
state-transition or equation direction is treated as weak evidence for
high-award targets.

