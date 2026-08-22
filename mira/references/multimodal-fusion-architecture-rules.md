# Multimodal Fusion Architecture Rules

Use this reference when Mira needs a paper-grade architecture diagram for
multi-source features, multi-branch models, learned embeddings, attention
fusion, or prediction/classification heads. This pattern is for model
architecture figures, not generic process flowcharts.

## Trigger Pattern

Use this diagram grammar when the model has at least two of:

- multiple input modalities, feature families, or data views;
- parallel feature extractors such as sequence encoder, graph network, MLP,
  CNN, BP network, surrogate model, statistical feature block, or expert
  indicator block;
- a reconstruction, feedback, calibration, or auxiliary training path;
- a fusion layer such as attention, weighted aggregation, ensemble, stacking,
  or joint objective;
- a final prediction, classification, evaluation score, or optimization policy.

Do not use this figure when the method is a simple one-stage formula, a pure
data-cleaning flow, or a table is enough.

## Visual Grammar

| Element | Meaning | PPT shape rule |
|---|---|---|
| Left object/input | Raw sample, system, data source, or problem object | Image placeholder or compact object icon |
| Branch label | Named feature family such as sequence, structure, property, statistics, scenario, or indicator set | Rounded rectangle; one color per branch |
| Feature artifact | Encoded vector, graph, sequence tile, list of indicators, matrix, or embedding | Small editable icon or short table-like box |
| Encoder/model block | Branch-specific model module | Rounded rectangle, parallelogram, or trapezoid-like block with formula/module name |
| Latent bar/vector | Learned feature vector or normalized feature block | Narrow vertical rectangle with branch color |
| Feedback/reconstruction | Auxiliary path, reconstruction loss, calibration loop, or self-supervised signal | Dashed arrow above or around the main chain |
| Fusion module | Attention, weighted sum, stacking, ensemble, or joint decision layer | Larger central block, usually after branch vectors merge |
| Output head | Prediction, classification, ranking, score, or policy | Neural-network-like icon or result node |

## Layout Contract

- Use one left-to-right reading direction.
- Keep 2-4 parallel branches vertically aligned.
- Give each branch a consistent soft color and carry that color into its
  feature vector/bar before fusion.
- Put feedback/reconstruction arrows above the main chain and make them dashed.
- Put the fusion module right of the branch vectors; do not let branches cross.
- Place output/prediction on the far right and keep it visually smaller than the
  fusion module unless the output head is the paper's main contribution.
- If the left input is a real object image, keep the image source traceable. If
  no image is available, use an editable placeholder rather than a fake picture.

## Paper Requirements

- The caption must state what the branches are and what the fusion module does.
- The nearby text must map every branch label to variables, features, formulas,
  data columns, or model modules in the paper.
- A model architecture diagram is not numerical evidence. Pair it with training
  settings, validation metrics, baseline/ablation, sensitivity, or constraint
  audit as appropriate.
- If attention, ensemble weights, learned embeddings, or neural modules appear,
  include either a formula, parameter table, or validation table nearby.
- If a reconstruction or auxiliary loss appears, state the loss term and how it
  helps the final task; do not draw a dashed loop only for decoration.

## PPT Generation

Use the PPT reasoning diagram engine when a reusable editable source is needed:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_ppt_reasoning_diagram.py `
  --root <project-root> `
  --demo multimodal_fusion `
  --prefix multimodal_fusion `
  --export auto
```

For a real paper, replace the demo labels with problem-specific branches and
save the normalized JSON spec under `results/figures_data/`.

## Failure Signs

- Branch names are generic, such as "model 1/model 2/model 3", without real
  variables or feature families.
- The fusion block is drawn, but no weighting, attention, stacking, or decision
  formula is stated in the text.
- The output says "prediction" or "evaluation" but no validation metric follows.
- The figure uses a screenshot-only raster with no editable source, making the
  paper hard to revise.
- Colors are decorative and do not consistently mark branch identity.

