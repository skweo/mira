# Knowledge Card: statistics/logistic-regression-classification

## Tags
- logistic regression
- logit
- binary classification
- binomial GLM
- maximum likelihood
- sigmoid
- decision threshold
- confusion matrix
- ROC
- AUC
- 逻辑回归
- 二分类
- 分类阈值

## Problem Patterns
- The response variable is binary or a probability of event occurrence.
- The task asks for risk classification, yes/no prediction, disease/default/failure occurrence, or probability ranking.
- Explanatory variables are tabular indicators and interpretability of coefficients matters.
- A simple, explainable classification baseline is needed before SVM, neural network, or ensemble models.

## Applicability Conditions
- Samples have labels in `{0,1}` or two classes that can be encoded consistently.
- Features are measured before the outcome and leakage is controlled.
- Sample size is sufficient for the number of predictors, or regularization/feature selection is used.
- Train/validation/test or cross-validation can be performed.

## Contraindications
- Do not fit `log(p/(1-p))` with OLS on smoothed 0/1 labels as the final contest model when proper binomial MLE is available.
- Do not report only fitted coefficients without classification metrics.
- Do not use the same data for threshold selection and final evaluation.
- Do not force logistic regression when class boundary is strongly nonlinear unless feature transforms or comparison models are included.

## Algorithm Core
- Standard route:
  1. encode labels and split data;
  2. scale or transform predictors when needed;
  3. fit binomial logistic regression by MLE, e.g. `glmfit`, `fitglm`, or Python `LogisticRegression`;
  4. predict probabilities `p = 1/(1+exp(-X beta))`;
  5. choose decision threshold using validation data or task cost;
  6. evaluate on held-out data.
- The manual logit-plus-OLS method is acceptable only as a teaching demonstration or rough baseline, and must be labeled as such.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| logit link | Maps probability to linear predictor | Requires probabilities in `(0,1)` |
| binomial likelihood | Proper coefficient estimation | Prefer over OLS-transformed labels |
| threshold selection | Converts probability to class | Use validation or cost matrix |
| coefficient odds ratio | Interpretability | Report feature units/scaling |
| regularization | Handles many/correlated predictors | Tune by cross-validation |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Decision threshold | Default 0.5 only if costs/classes are balanced | Threshold sensitivity or ROC |
| Class imbalance | Use stratified split, class weights, or calibrated threshold | PR/AUC, recall, specificity |
| Predictors | Check collinearity and leakage | VIF/correlation and domain audit |
| Regularization | Use L1/L2 when predictors are many or unstable | Cross-validation |
| Probability calibration | Needed when probabilities support decisions | Calibration curve or Brier score |

## Validation Requirements
- Dataset table: labels, predictors, sample count, class balance, split rule.
- Fit method: MLE/GLM or clearly marked OLS-logit approximation.
- Metrics: confusion matrix plus accuracy/precision/recall/F1 or sensitivity/specificity; ROC/AUC when threshold matters.
- Baselines: majority class, linear probability model, simple rule, or tree/SVM depending on task.
- Coefficient interpretation with sign, odds ratio, and unit/scaling.
- Threshold/cost sensitivity if decisions depend on false-positive/false-negative tradeoff.

## Failure Signs
- 0/1 labels are replaced by 0.25/0.75 and OLS is presented as standard logistic regression.
- The model reports probabilities but no threshold rule.
- Accuracy is high only because classes are imbalanced.
- Coefficients are interpreted without scaling or collinearity checks.
- No validation split or cross-validation exists.

## Repair Moves
- Refit with binomial GLM/MLE.
- Add stratified train/test split or k-fold validation.
- Add confusion matrix, ROC/AUC, and threshold sensitivity.
- Add class-imbalance handling and calibration if probabilities matter.
- If nonlinear patterns dominate, compare with SVM/tree/neural baseline while keeping logistic as interpretable baseline.

## Paper Usage
- Use logistic regression as an interpretable probability/classification model.
- State the logit link and report coefficient signs in relation to domain meaning.
- Avoid claiming causality from predictive coefficients without design support.

## Source Materials
- `$PROJECT_ROOT\Math_Model\Logistic_regression_cases`
- Files inspected: `Logistic.m`, `README_import.md`.

## Confidence
- high for logistic-regression validation discipline.
- medium-low for the source code's OLS-logit implementation as final estimation; use it as a cautionary baseline.
