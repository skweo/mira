# t-SNE Visualization Rules

Use this reference when a contest-final paper needs a t-SNE, TSNE, embedding,
manifold, high-dimensional-feature, clustering-visualization, or feature
separability plot.

## When To Use

Use t-SNE only when the source object is genuinely high-dimensional:

| Situation | Good use |
|---|---|
| Feature vectors from many indicators | Show whether known classes, clusters, or schemes separate visually. |
| Model embeddings or latent features | Compare learned representation quality or feature screening outcomes. |
| Clustering/classification evidence | Provide an intuitive companion to quantitative metrics. |
| Scenario or sample libraries | Show local similarity structure among many simulated cases. |

Do not use t-SNE for already 2D/3D data, tiny tables, fewer than 5 complete
samples, or as a decorative substitute for a result table.

## Preprocessing Contract

- Build a numeric feature matrix and record the feature columns.
- Handle missing values explicitly; drop or impute rows before fitting and
  report the row count used.
- Standardize features unless all features already share the same scale and
  unit.
- For very wide matrices, use PCA pre-reduction to about 30-50 dimensions before
  t-SNE, bounded by sample count and feature count.
- Save the final t-SNE coordinates and the parameter JSON; a screenshot alone is
  not a reproducible figure.

## Parameter Discipline

- Set `random_state` for reproducibility.
- Use `init="pca"` and `learning_rate="auto"` unless a saved experiment justifies
  another choice.
- Ensure `perplexity < n_samples`; auto-selection may use
  `min(30, max(5, (n_samples - 1) // 3))` with a smaller fallback for tiny
  sample sets.
- If the paper's conclusion depends materially on the visual separation, repeat
  the plot with at least two perplexities or two seeds and report whether the
  qualitative separation is stable.
- Do not tune perplexity only to make a preferred conclusion look separated.

## Figure Standard

- Use color for class/cluster/scenario labels and keep the legend readable.
- For no more than about 12 categories, add direct centroid labels or light
  covariance ellipses when they do not hide points.
- Use axis labels such as `t-SNE 维度 1` and `t-SNE 维度 2`; do not attach physical
  units to t-SNE axes.
- The caption must state both what color means and what t-SNE cannot prove.
- Nearby text should connect the plot to a quantitative table, accuracy metric,
  silhouette/cluster index, confusion matrix, or robustness check.

## Paper Wording

Good wording:

> t-SNE 图用于展示高维指标在二维嵌入空间中的局部邻域结构。类别之间呈现较清晰的局部分离，但最终分类/聚类结论仍以表中指标和稳健性检验为依据。

Avoid wording:

> t-SNE 证明这些类别在真实空间中距离很远。

## Script

Use the reusable script when the data are in CSV/XLSX form:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_tsne.py `
  --root <project-root> `
  --input results\tables\feature_matrix.csv `
  --features feature1,feature2,feature3 `
  --label 类别 `
  --prefix q3_feature_embedding
```

The script writes:

- `figures/<prefix>_tsne.png`
- `figures/<prefix>_tsne.pdf`
- `results/figures_data/<prefix>_tsne_coordinates.csv`
- `results/figures_data/<prefix>_tsne_params.json`
- `figures/<prefix>_tsne_index.md`

Use `--demo iris` for a smoke test when no project data are available.
