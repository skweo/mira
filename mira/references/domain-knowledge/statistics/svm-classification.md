# Knowledge Card: statistics/svm-classification

## Tags
- SVM
- support vector machine
- binary classification
- kernel method
- linear SVM
- RBF kernel
- LIBSVM
- fitcsvm
- C parameter
- gamma
- cross-validation
- margin
- 支持向量机
- 核函数
- 二分类

## Problem Patterns
- A contest task needs supervised classification with tabular features and possibly nonlinear class boundaries.
- Logistic regression or linear classifier is too weak, but sample size is not large enough for a deep neural network.
- The paper needs a robust classification baseline or main model with clear validation.
- Kernel choice, margin, and support vectors can be explained concisely.

## Applicability Conditions
- Labeled training data exist and features are scaled.
- Train/test split or cross-validation is possible.
- Binary or decomposable multi-class classification is appropriate.
- Hyperparameters `C` and kernel parameters can be tuned without test leakage.

## Contraindications
- Do not use SVM on unscaled heterogeneous features.
- Do not use a toy linear/RBF demo as evidence for a contest dataset.
- Do not choose kernel and parameters from test accuracy.
- Do not rely on MDS/2D visualization as validation for high-dimensional classification.
- Do not use obsolete MATLAB `svmtrain/svmclassify` wording without noting modern replacements when relevant.

## Algorithm Core
1. Clean and scale features using training data.
2. Split data or define k-fold cross-validation.
3. Train a baseline linear SVM/logistic model.
4. For nonlinear patterns, tune RBF/poly kernel with grid or Bayesian search over `C` and `gamma`.
5. Evaluate on validation/test data with task-appropriate metrics.
6. Calibrate probabilities only if the paper uses probabilities for decisions.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| feature scaling | Required before margin/kernel distances | Fit scaler on training data only |
| linear kernel | Interpretable baseline | Use when classes are near linear |
| RBF kernel | Nonlinear boundary | Tune `C` and `gamma` |
| cross-validation | Hyperparameter selection | Keep final test untouched |
| probability output | Risk ranking/threshold decisions | Requires calibration check |
| support vectors | Explains boundary complexity | Report count or ratio when useful |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| `C` | Controls margin vs errors | Cross-validation grid |
| `gamma`/kernel scale | Controls RBF locality | Cross-validation and overfit check |
| Class weights | Needed for imbalance | Recall/specificity or PR curve |
| Threshold | SVM score threshold may need tuning | Validation/cost sensitivity |
| Probability estimates | Use calibrated model if probabilities matter | Calibration curve/Brier score |

## Validation Requirements
- Dataset and split table: sample count, feature count, class balance, scaling rule.
- Baselines: majority class, logistic regression/linear SVM, and nonlinear SVM if used.
- Hyperparameter search record with validation metric.
- Test metrics: confusion matrix plus accuracy/precision/recall/F1; ROC/AUC or PR-AUC when threshold/imbalance matters.
- Overfitting check: train vs validation/test performance, support-vector ratio, or learning curve.
- Reproducibility: seed, package/version, command/options such as LIBSVM `-c`, `-g`, `-b`.

## Failure Signs
- Features are not scaled before RBF SVM.
- The paper reports only a plot of classified points.
- Test data are used to choose `C` and `gamma`.
- Accuracy hides poor minority-class recall.
- LIBSVM probability output is used as calibrated probability without checking.

## Repair Moves
- Add train-only scaling and rerun.
- Add nested or held-out hyperparameter selection.
- Add logistic/linear baseline and confusion matrix.
- Tune class weights or threshold for imbalance.
- If interpretability is central, use logistic/tree model as main and SVM as comparison.

## Paper Usage
- Present SVM as a margin-based supervised classifier.
- Keep kernel explanation short; put hyperparameter grid and metrics in tables.
- Avoid claiming causal feature effects from SVM weights unless using a linear, scaled, interpretable setting.

## Source Materials
- `$PROJECT_ROOT\Math_Model\SVM_cases`
- Files inspected: `LIBSVM_USE.m`, `SVM_L.m`, `SVM_NL.m`, `README_import.md`, `heart_scale`.

## Confidence
- high for validation obligations.
- medium for source-code API details because MATLAB's old SVM functions have modern replacements.
