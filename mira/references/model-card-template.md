# Model Card Template

Use this template to turn a mathematical model, algorithm, or method into reusable agent knowledge. One method should become one model card.

Use `domain-knowledge-injection.md` instead when the extracted material is expert execution experience: neighborhoods/operators, parameter ranges, objective scaling, failure signs, repair moves, or paper-claim limits for a known method family. A model card says what the method is and when it fits; a knowledge card says how to make that method work in a fragile domain.

## Model Card Fields

```markdown
# Model Card: <method name>

## Use When

- <Problem signal 1>
- <Problem signal 2>

## Avoid When

- <Failure condition 1>
- <Failure condition 2>

## Typical Contest Tasks

- <Optimization / prediction / evaluation / clustering / routing / simulation / network / differential equation / classification / queueing / other>

## Required Inputs

| Input | Meaning | Unit | Required? | Notes |
|---|---|---|---:|---|

## Outputs

| Output | Meaning | Paper use |
|---|---|---|

## Variables and Parameters

| Symbol | Type | Meaning | Unit | Source or estimation |
|---|---|---|---|---|

## Core Formulation

Write the objective, equations, constraints, or algorithm steps. Keep it executable and contest-friendly.

## Solver or Implementation Route

- Preferred language:
- Recommended packages:
- Data preprocessing:
- Baseline:
- Complexity or runtime notes:

## Validation

- Feasibility check:
- Sensitivity check:
- Baseline comparison:
- Error or uncertainty check:

## Figure and Table Outputs

| Artifact | Purpose | Source data |
|---|---|---|

## Paper Writing Notes

- How to explain the method in Chinese contest-paper style.
- What not to overclaim.

## Common Pitfalls

- <Pitfall 1>
- <Pitfall 2>

## Source Notes

- Raw source path or citation:
- Extracted by:
- Last updated:
```

## Example: TOPSIS Short Card

```markdown
# Model Card: TOPSIS

## Use When

- The task asks for comprehensive ranking or evaluation of multiple objects.
- Indicators can be made comparable by normalization.
- Indicator weights can be justified by entropy weight, AHP, expert choice, or sensitivity analysis.

## Avoid When

- The task is causal prediction or dynamic simulation rather than static evaluation.
- Indicator weights cannot be explained.
- The ranking is extremely sensitive to normalization method and no robustness check is possible.

## Required Inputs

| Input | Meaning | Unit | Required? | Notes |
|---|---|---|---:|---|
| Decision matrix | Objects by indicators | mixed | yes | Must handle positive, negative, and interval indicators |
| Weights | Indicator importance | none | yes | Must record source |

## Outputs

| Output | Meaning | Paper use |
|---|---|---|
| Closeness coefficient | Distance-based score | Final ranking and comparison table |
| Ranking | Ordered objects | Main result |

## Validation

- Run weight sensitivity analysis.
- Compare with at least one simple baseline such as normalized weighted sum.
- Check whether top rankings change under reasonable normalization choices.
```

Keep actual cards concise. If a method needs long derivation, place derivation in a separate source note and keep the card operational.
