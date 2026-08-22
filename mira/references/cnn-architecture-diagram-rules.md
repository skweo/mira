# CNN Architecture Diagram Rules

Use this reference when Mira needs a paper-grade convolutional neural network
architecture diagram for image, matrix, raster, sensor-grid, signal, spectrum,
or time-series convolution models. This is for real CNN or convolution-based
feature extraction, not for making a weak model look advanced.

## Trigger Pattern

Use a CNN architecture diagram when the paper has one of:

- image, grid, spatial field, spectrogram, heatmap, defect map, remote-sensing
  patch, medical image, traffic image, or other tensor input;
- 1D convolution over time series, signal sequence, spectrum, or feature
  sequence;
- CNN as a feature extractor before classification, regression, evaluation,
  fusion, optimization, or decision output;
- CNN combined with LSTM, attention, transformer, XGBoost, SVM, BP/MLP, or an
  ensemble head.

Avoid it when the data are tiny tabular indicators, when no CNN is implemented,
or when a simple regression/feature table explains the method better.

## Visual Grammar

| Element | Meaning | Required label |
|---|---|---|
| Input tensor | Raw image/matrix/sequence input | Size, channel count, or sequence length such as `64x64x3` or `Txd` |
| Convolution block | Local feature extraction | Kernel size, channel count, stride/padding when important |
| Activation/normalization | Nonlinear or stabilized transform | `ReLU`, `BN`, `Dropout`, or omit only if table states it |
| Pooling/downsampling | Resolution reduction | `MaxPool`, `AvgPool`, stride, or output size |
| Feature map stack | Channel-depth representation | Channel count must match text/table if shown |
| Flatten/GAP | Transition from feature maps to vector | `Flatten` or `Global Average Pooling` |
| Dense/output head | Classification, regression, score, or policy | Unit count and output meaning |
| Loss/metric callout | Training objective and validation evidence | Loss, metric, split/cross-validation, baseline or ablation |

## Layout Contract

- Use left-to-right reading direction: input -> conv/pool blocks -> vector ->
  dense head -> output.
- Use block depth or stacked offsets only to show real channel count; do not
  imply 3D tensor detail that the model does not define.
- Keep repeated blocks compact: `Conv-BN-ReLU x2` is acceptable when exact
  layer parameters are listed in a nearby table.
- Show spatial size changes at least at major downsampling points.
- For 1D CNN, label the input as sequence/spectrum and show kernel length
  rather than a 2D image block.
- If CNN feeds another model, make the handoff explicit: feature vector,
  embedding, probability, score, or learned descriptor.

## Paper Requirements

- Put a layer-parameter table near the diagram when CNN is a main model:
  layer name, output size, kernel, channels, stride/padding, activation, and
  trainable parameters when feasible.
- State training setup: train/validation/test split, batch size, epochs,
  optimizer, learning rate, loss, and early stopping or regularization.
- Provide validation metrics appropriate to the task: accuracy/F1/AUC for
  classification, MAE/RMSE/R2 for regression, IoU/Dice for segmentation, or a
  domain-specific score.
- Include a baseline or ablation for high-award `contest_final`: non-CNN
  baseline, CNN without augmentation, CNN without attention/fusion, or smaller
  architecture comparison.
- Do not call the CNN globally optimal. Treat it as a learned predictor or
  feature extractor whose quality is measured empirically.

## PPT Generation

Use the PPT reasoning diagram engine when an editable CNN architecture source is
needed:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py `
  --root <project-root> `
  --demo cnn_architecture `
  --prefix cnn_architecture `
  --export auto
```

For precise publication-style non-PPT diagrams, `plot_neural_network_diagram.py
--demo cnn` remains available. Prefer the PPT version when the paper needs
editable blocks, callouts, or Chinese labels.

## Failure Signs

- The diagram says CNN, but the code uses only an MLP, SVM, random forest, or
  hand-crafted features.
- Input/output sizes do not match the preprocessing or data table.
- Convolution kernels, channels, pooling, and output head are absent from both
  the diagram and the text.
- The paper has a pretty architecture diagram but no train/validation split,
  training settings, validation metric, or baseline.
- The sample size is too small for the stated CNN, with no augmentation,
  transfer learning, cross-validation, or waiver.

