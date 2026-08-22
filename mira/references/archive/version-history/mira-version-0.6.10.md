# Mira 0.6.10

Mira 0.6.10 adds reproducible neural-network-like diagram support for real
neural models, learned surrogate models, feature embeddings, feature-fusion
networks, and explicitly layered mappings.

## New Standard

- Route `references/neural-network-diagram-rules.md` when a figure, diagram,
  paper section, or revision mentions neural-network architecture, BP/MLP, CNN,
  DNN, feature fusion network, learned mapping, input-hidden-output layer
  structure, or a "类神经网络图".
- Use `scripts/plot_neural_network_diagram.py` for JSON specs or built-in
  `mlp`, `cnn`, and `fusion` demos.
- Save PNG/PDF diagrams, normalized spec, layer table, connection table,
  parameters, and a caption/caveat index.
- Treat these diagrams as architecture and feature-flow evidence. They must be
  paired with formulas, training details, validation metrics, result tables, or
  an explicit "layered mapping, not neural network" wording when appropriate.

## Non-goals

- Do not draw decorative neural-network-style figures for models that do not
  have layers, feature flow, learned mappings, or a justified analogy.
- Do not use a neural-network diagram as evidence for predictive accuracy,
  optimality, or robustness.
- Do not weaken the 0.6.1-0.6.9 layout, derivation, control-plane, statistical
  visualization, flow, 3D, or structure-schematic rules.
