# Mira 0.6.16

## Scope

Mira 0.6.16 adds CNN-specific architecture diagram discipline and an editable
PowerPoint CNN architecture demo. It is designed for image, matrix, raster,
sensor-grid, spectrum, and 1D/2D convolution models.

## Added

- `references/cnn-architecture-diagram-rules.md`
- `plot_ppt_reasoning_diagram.py --demo cnn_architecture`
- routing triggers for CNN/convolution/pooling/feature-map architecture figures

## Contest-Paper Rule

Use CNN diagrams only when the model actually uses convolution. The diagram must
be paired with layer parameters, training settings, validation metrics, and
baseline or ablation evidence for `contest_final` output.
