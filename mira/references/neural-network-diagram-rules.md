# Neural-Network Diagram Rules

Use this reference when a contest-final paper needs a neural-network-like
architecture diagram, such as BP/MLP, CNN, DNN, learned surrogate model,
feature embedding, feature-fusion network, or an explicitly layered mapping.

## When To Use

| Case | Use the diagram for | Avoid when |
|---|---|---|
| Real neural model | Show input features, hidden/conv/fusion layers, output heads, and training flow. | The paper does not train or use a neural model. |
| Learned surrogate | Explain how variables map through a fitted black-box or meta-model. | A formula, regression table, or sensitivity curve is clearer. |
| Feature fusion | Show branches, encoders, fusion operation, and output decision. | The "fusion" is only a weighted sum already clear from one equation. |
| Analog layered mapping | Explain a legitimate input-feature-decision hierarchy. | The diagram is only decorative deep-learning style. |

Neural-network diagrams are diagrams, not result figures. They explain model
structure and feature flow; they do not prove accuracy, optimality, or
robustness.

## Data Contract

- Prefer a JSON spec with `layers`, `connections`, and optional `callouts`.
- Each layer must correspond to a real input, feature group, hidden/conv block,
  fusion module, output head, or decision variable.
- Each connection must correspond to a real transform: normalization, encoding,
  convolution, dense mapping, skip connection, attention, fusion, regression, or
  classification.
- Save normalized spec, layer table, connection table, parameters, PNG/PDF, and
  a caption/caveat index.
- If the layer count or unit count is abbreviated visually, put exact sizes,
  activation functions, loss function, training data, and validation metrics in
  the text or a table.

## Diagram Standards

- MLP/BP: show input indicators, hidden layers, activations, output targets,
  and dense connections. Do not draw every unit when the layer is large.
- CNN: show input tensor, convolution/pooling blocks, flatten/global pooling,
  dense head, and output. Use block depth to indicate channels only when it is
  stated in the paper.
- For contest-final CNN figures, also read
  `references/cnn-architecture-diagram-rules.md`; the diagram must expose input
  size, kernel/channel/downsampling choices, output head, and nearby training
  or validation evidence.
- Feature fusion: show separate branches before fusion, label the fusion rule
  (`concat`, weighted sum, attention, or learned gate), and connect the fused
  representation to the final decision.
- Surrogate model: pair the diagram with training/validation evidence, such as
  train-test split, cross-validation, error metric, or baseline comparison.
- Use callouts only for model-critical mechanisms, such as the fusion layer,
  shared encoder, attention/gating, or output head.

## Interpretation Discipline

Good wording:

> 图中将输入指标、特征嵌入、融合层和输出决策放在同一结构中，说明模型如何把多源变量映射为预测值；模型精度仍由后续的误差表和交叉验证结果验证。

Avoid:

> 本文加入神经网络图，使模型看起来更高级。

If the method is not actually a neural network, name it as a "layered feature
mapping diagram" or "feature-flow diagram" instead of claiming a neural network.

## Script

Use the reusable script for JSON specs:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_neural_network_diagram.py `
  --root <project-root> `
  --spec diagrams\network_spec.json `
  --prefix q3_feature_fusion_network
```

Built-in demos for quick style checks:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_neural_network_diagram.py `
  --root <project-root> --demo mlp --prefix demo_mlp
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_neural_network_diagram.py `
  --root <project-root> --demo cnn --prefix demo_cnn
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_neural_network_diagram.py `
  --root <project-root> --demo fusion --prefix demo_fusion
```

The script writes PNG/PDF figures, normalized spec, layer/connection tables,
parameters, and a caption/caveat index.

For editable PowerPoint CNN architecture figures, use:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py `
  --root <project-root> --demo cnn_architecture --prefix cnn_architecture --export auto
```
