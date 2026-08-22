# Knowledge Card: statistics/neural-network-miv-feature-screening

## Tags
- MIV
- mean impact value
- neural network variable screening
- BP neural network
- feature importance
- sensitivity analysis
- perturbation
- supervised feature screening
- 神经网络
- 变量筛选
- 平均影响值
- 特征重要性

## Problem Patterns
- A supervised prediction/evaluation model has many candidate input indicators and needs feature importance.
- A BP/MLP model is already trained and the user wants to identify which variables most influence outputs.
- The paper needs a data-driven variable-screening method complementary to PCA/factor analysis.
- The task asks which indicators should be retained, prioritized, or interpreted.

## Applicability Conditions
- A trained neural network has acceptable validation performance.
- Inputs are scaled consistently and perturbing one variable by a fixed percentage is meaningful.
- The output metric is scalar or can be summarized per output.
- Repeated training or fixed initialization is possible to handle neural-network randomness.

## Contraindications
- Do not use MIV if the neural network itself has not passed validation.
- Do not treat MIV as causal importance; it is model-based sensitivity.
- Do not perturb raw variables with different units/ranges without scaling or range checks.
- Do not report one random training run as stable variable ranking.

## Algorithm Core
1. Train a validated neural network on normalized input data.
2. For each feature `x_j`, construct `X_j+` and `X_j-` by increasing/decreasing that feature, often by 10%.
3. Predict outputs with the fixed trained network.
4. Compute `MIV_j = mean(y_j+ - y_j-)`.
5. Rank variables by `abs(MIV_j)` and use sign for direction under the model.
6. Repeat across seeds or folds and report stability.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| feature perturbation | Measures model response to one input | Perturb within plausible range |
| fixed-network prediction | Avoids retraining during each perturbation | Network validation must precede MIV |
| absolute MIV ranking | Feature-importance order | Check stability across seeds |
| signed MIV | Direction of influence | Valid only locally under the model |
| repeated MIV | Handles random initialization | Report mean/rank spread |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Perturbation size | 10% is a default, not universal | Test 5%, 10%, 20% or domain ranges |
| Input scaling | Apply perturbation in original or normalized scale intentionally | State convention and range clipping |
| Neural architecture | Must be chosen before MIV | Validation curve and baseline |
| Seed count | Multiple runs when ranking matters | Rank stability table |
| Feature correlation | MIV is one-at-a-time | Compare with ablation/permutation when features correlate |

## Validation Requirements
- Neural-network validation first: split/cross-validation, baseline, overfitting check, seed record.
- Perturbation contract: feature scale, perturbation size, clipping/range handling.
- MIV table: signed MIV, absolute MIV, rank, and repeated-run stability.
- Sensitivity to perturbation size.
- Comparison to at least one alternative importance method when feasible, such as permutation importance, ablation, regression coefficient, or tree importance.

## Failure Signs
- MIV is computed from a network with only training accuracy.
- Feature rankings change across random seeds.
- Perturbed values leave the physically possible range.
- Correlated features split or flip importance but the paper interprets them independently.
- MIV is described as causal influence.

## Repair Moves
- Validate and simplify the neural network before using MIV.
- Repeat training and report rank stability.
- Use domain-based perturbation intervals and clip impossible values.
- Add ablation/permutation importance for comparison.
- If ranking is unstable, use MIV only as exploratory evidence or switch to a more transparent model.

## Paper Usage
- Present MIV as "model sensitivity based feature screening".
- Use it to support indicator selection or interpretation, not as proof of causality.
- Place MIV ranking beside validation metrics and baseline performance.

## Source Materials
- `$PROJECT_ROOT\Math_Model\neural_network_MIV`
- Files inspected: `neural_network_miv.m`, `README_import.md`.

## Confidence
- medium: useful for supervised feature-screening workflow; reliability depends strongly on network validation and rank stability.
