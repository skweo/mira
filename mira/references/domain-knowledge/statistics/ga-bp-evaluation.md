# Knowledge Card: statistics/ga-bp-evaluation

## Tags
- GA-BP
- genetic algorithm
- BP neural network
- MLP
- neural-network evaluation
- classification
- water quality evaluation
- indicator normalization
- membership grade
- chromosome encoding
- weight initialization
- threshold optimization
- ablation
- cross-validation
- 遗传算法
- BP神经网络
- 神经网络评价
- 水质评价
- 评价模型
- 分类
- 隶属度
- 权值阈值
- 染色体编码
- 归一化
- 交叉验证
- 消融对照

## Problem Patterns
- A contest problem needs data-driven evaluation, classification, grading, or nonlinear mapping from indicators to quality/level/risk class.
- Ordinary BP/MLP is considered but initialization/local-minimum/slow-convergence risk is material.
- There are labeled historical samples or standard-grade samples that can supervise a neural network.
- Indicator values are heterogeneous in units and ranges, requiring normalization.
- A hybrid intelligent algorithm is proposed for water quality, environmental quality, safety grade, credit grade, or similar evaluation tasks.

## Applicability Conditions
- The task is supervised: inputs and target labels/scores/membership values are available or can be constructed from official standards.
- The sample size is large enough for a neural network, or the paper explicitly uses small-sample validation such as leave-one-out and downgrades claims.
- The output grade/membership rule is defined.
- GA encoding of BP weights and thresholds is feasible at the chosen network size.
- Baselines such as ordinary BP, logistic/regression/tree, TOPSIS, fuzzy evaluation, or standard-threshold rule are available.

## Contraindications
- Do not use GA-BP when data are too few to validate generalization and a transparent standard-threshold/evaluation model is sufficient.
- Do not use GA-BP only because it sounds stronger than BP; require validation gain over ordinary BP and simpler baselines.
- Do not claim global optimality; GA gives heuristic initialization, BP gives local refinement.
- Do not use test data to fit normalization or grade mapping.
- Do not hide interpretability: evaluation/ranking tasks still need indicator meaning, direction, and standard thresholds.

## Algorithm Core
- GA-BP route:
  1. build input indicators, labels/grades, and normalization using training data;
  2. choose BP/MLP structure and compute total number of weights and thresholds;
  3. encode all weights and thresholds into a real-valued chromosome;
  4. define fitness, usually validation/training loss or classification error;
  5. evolve population by selection, crossover, mutation, and optional elitism;
  6. decode best chromosome as BP initialization;
  7. fine-tune with BP/trainer;
  8. evaluate on held-out or cross-validated samples against baselines.
- For grade evaluation, convert network output into class/membership using a stated threshold, nearest-grade, one-hot, or membership decoding rule.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| indicator normalization | Makes heterogeneous indicators trainable | Fit on training data; save min/max or scaling parameters |
| chromosome encoding | Represents BP weights and thresholds for GA | Dimension must equal all trainable parameters |
| fitness function | Guides GA search | Prefer validation loss/error when data allow |
| selection | Retains better initializations | Record method and selection pressure |
| crossover | Recombines candidate weight sets | Use real-valued crossover compatible with encoding |
| mutation | Preserves diversity | Report rate and range; repeated seeds needed |
| BP fine-tuning | Local gradient refinement after GA | Record trainer, learning rate, stopping rule |
| grade decoding | Converts output to evaluation class | Must match official standards or label design |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Network structure | Choose based on sample size and task complexity; `2m+1` is only a candidate heuristic | Compare simple hidden sizes or justify fixed structure |
| Chromosome length | Include all input-hidden, hidden-output weights and thresholds | Dimension audit |
| Population/generations | Large enough for search but not a substitute for validation | Convergence and runtime record |
| Crossover/mutation | Tune or use conservative defaults with repeated seeds | Sensitivity or stability table |
| Learning rate/trainer | Record BP optimizer and stopping rule | Training/validation curve |
| Normalization | Map indicators consistently; avoid sigmoid saturation if using sigmoid | Train-only scaling and out-of-range handling |
| Output grade | Define grade/membership threshold | Confusion or grade-error table |

## Validation Requirements
- Dataset and preprocessing table: indicators, units, direction, grade labels, sample count, split, and normalization parameters.
- Network and GA parameter table: architecture, chromosome length, population, generations, crossover, mutation, fitness, trainer, seed.
- Baseline comparison: ordinary BP with repeated random initialization and at least one simple interpretable evaluation/classification baseline.
- Ablation: GA initialization vs BP-only; optionally compare GA-only, BP-only, and GA-BP.
- Generalization: holdout, k-fold, leave-one-out, or bootstrapped validation depending on sample size.
- Stability: repeated GA-BP runs and spread of validation performance.
- Error analysis: confusion matrix, grade-error table, or membership-output residuals.
- Claim boundary: if sample size is tiny, state it as a demonstration/auxiliary model rather than a decisive contest-final model.

## Failure Signs
- The paper reports only training convergence or training accuracy.
- No chromosome length or decoding rule is given.
- GA parameters are copied without seed, convergence, or sensitivity.
- A small dataset is split poorly or not split at all.
- Neural output is interpreted as a water-quality grade without a grade-decoding rule.
- The hybrid model is compared only to the real label, not to ordinary BP or simple baselines.
- The model is used for policy recommendation without feature importance, indicator direction, or sensitivity.

## Repair Moves
- Add ordinary BP and simple evaluation/classification baselines.
- Add leave-one-out or k-fold validation when samples are scarce.
- Publish a parameter/encoding table and a decoded network-dimension audit.
- Replace single-output grade regression with one-hot/membership outputs if class boundaries are ambiguous.
- Add repeated seeds and report mean plus spread.
- If validation is weak, demote GA-BP to an auxiliary comparison and use interpretable standard-threshold/TOPSIS/fuzzy model as the main route.
- Add indicator sensitivity or perturbation analysis to support evaluation interpretation.

## Paper Usage
- Explain GA-BP as "GA searches good initial weights/thresholds, BP fine-tunes them" in one paragraph.
- Use a workflow diagram only if it shows data preprocessing, GA encoding, BP fine-tuning, and validation.
- Put GA/BP parameters in a compact table, not scattered prose.
- For contest papers, emphasize dataset, validation, and baselines over neural-network theory.
- Avoid saying "global optimal"; write "improved initialization and convergence in validation experiments."

## Source Materials
- Useful sections: hybrid GA-BP steps, weight/threshold chromosome idea, water-quality indicators, normalization to `[0.1,0.9]`, training error curve, grade-output table.
- Reliability: medium-low. Workflow is useful; evidence is weak due to small sample and limited baseline comparison.

## Confidence
- medium-low: useful as an operational hybrid-model card, but must be paired with Mira's neural-network boundary and validation rules before contest-final use.
