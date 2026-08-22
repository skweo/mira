# Visual Expression Rules

Use this reference when generating or revising figures, diagrams, and tables for a `contest_final` Chinese mathematical modeling paper.

This file complements `figure-table-rules.md`. `figure-table-rules.md` decides what evidence is needed; this file controls whether the visual assets look readable and final-paper ready.
For Mira 0.8.2 visual selection, also use
`checks/visual_opportunity_report.md` to decide whether a better chart grammar
should be generated or explicitly waived before final writing.

## Visual Contract

Every main-text visual should pass four checks:

| Check | Requirement | Common failure |
|---|---|---|
| Claim | The visual supports one nearby claim or comparison. | Decorative plot or copied generic flowchart. |
| Readability | Labels, legends, annotations, units, and line widths remain readable after PDF compilation. | Tiny English labels, crowded legend, low-resolution raster. |
| Traceability | Source data/script or editable diagram source is known. | Screenshot-only figure with no reproducible source. |
| Placement | The visual appears near the paragraph that interprets it. | All figures dumped at the end or detached from their claims. |
| Toolchain | The source tool is recorded truthfully. | Claiming PPT/Excel/MATLAB was used when no artifact or command proves it. |

## Figure-Text Loop

For high-award `contest_final` papers, an important figure should usually form
a closed reasoning loop:

```text
pre-figure purpose -> figure/callout -> formula or table bridge
-> post-figure interpretation -> decision or conclusion
```

- Before a nontrivial figure, write a short purpose sentence that tells the
  reader what the figure is about to define, compare, validate, or decide.
- The caption should name the visual object and the claim it supports, not only
  the plotted file or variable.
- After a claim-bearing figure, add an interpretation sentence. It should state
  what can be seen from the figure and how that evidence leads to the next
  formula, table, threshold, branch choice, or conclusion.
- For `define` and `derive` visuals, figure labels should reappear in the
  following symbols, formulas, or variable explanation.
- For `zoom` visuals, the nearby text should say why the full-scale view is not
  enough and what the local panel proves.
- For `compare` visuals, the nearby text should say what remains fixed, what
  changes, and which case is selected or rejected.
- `scripts/visual_reasoning_audit.py` checks this loop with `figure_pre_intro`
  and `figure_post_interpretation` metrics. Treat a weak loop as a writing
  defect even when captions and labels are present.

## Numbering And Emphasis

- Every main-text figure and table must have a numbered caption. In LaTeX, this means using `figure`/`table` environments with `\caption{...}`; in Typst/Markdown, use the equivalent numbered figure/table syntax.
- Every figure/table that supports a claim should have a stable `label` and be referenced in nearby text as "图/表 ...". Do not rely on an unreferenced image floating below a paragraph.
- Abstracts of final papers should bold the main answer phrases or key final numbers. Do not bold every sentence; emphasize the result ledger.
- Formula numbering and emphasis must be selective. Number or label formulas that later paragraphs reference, especially objectives, constraint groups, recurrences, calibration equations, validation metrics, and final conclusions.
- Auxiliary algebra, local substitutions, and one-line definitions can remain unnumbered when later text does not cite them.
- Important terminal formulas should be visually marked when they are final answers, such as `\boxed{...}`, bold variables, or a clearly named "最终结果" equation. Do not box every displayed formula.
- Derivation sections should not jump from assumptions to final formulas. Use a chain: mechanism or decision object -> variables -> intermediate relation -> constraint/objective -> final highlighted formula -> nearby visual/table evidence.

## Visual Reasoning Chain

Strong contest-final figures work as reasoning components. For geometry,
kinematics, path, collision, scheduling, routing, or algorithm-heavy papers,
prefer this chain when artifacts support it:

```text
definition diagram -> derivation/formula -> operational algorithm or theorem
diagram -> result figure/table -> local zoom, boundary comparison, or validation
```

- Put a labeled mechanism diagram before the first dense formula block when a
  new coordinate system, geometric object, state variable, or constraint is
  introduced.
- A theorem-based method should include an operational diagram or flowchart
  whose labels match the named steps in the text. For example, a collision
  theorem figure should show the compared objects, projection axes or intervals,
  overlap/no-overlap meaning, and the final decision.
- For search-derived thresholds, show the search process rather than only the
  final number. Use a coarse scan to locate the range, then a local/fine scan or
  inset around the final value.
- For boundary feasibility claims, include paired states just below and just
  above the boundary when the geometry or policy visibly changes.
- For local failure, collision, crossing, bottleneck, or peak claims, pair a
  global-context figure with a local-detail figure or inset. Use arrows,
  markers, or shared labels so the reader can connect the two panels.
- When a figure needs more explanation than a caption can carry, add a short
  nearby callout in prose or a compact side note. It should state what is
  highlighted, why it matters, and how it leads to the next formula or
  conclusion. Do not use callouts as decoration.
- In `figures/figure_index.md` or `diagrams/diagram_index.md`, record the role
  of each visual as one of: `define`, `derive`, `operate`, `result`, `validate`,
  `zoom`, or `compare`.
- If a shared index lists `diagrams/...` assets, treat them as diagrams when
  planning roles. A mechanism schematic should not be counted as a result plot
  merely because it appears in `figures/figure_index.md`.
- Before final plotting for `contest_final`, run `scripts/figure_storyboard.py`
  and use `planning/figure_storyboard.md` to decide which visual roles are
  actually needed. The storyboard is the planning surface for A053-style figure
  grammar; the figure index records the final realized assets.

## Gallery Chart Grammar Router

Before implementing a data chart, use `scripts/chart_gallery_router.py` or
`references/chart-gallery-index.md` to check the preferred example sources:

- https://gallery.pyecharts.org
- https://matplotlib.org.cn/stable/gallery/#widgets
- https://seaborn.pydata.org/examples/index.html
- https://echarts.apache.org/examples/zh/index.html#chart-type-bar

The gallery route chooses chart grammar by data shape and paper claim. It is
not a decoration list and not proof that a chart fits. Open or adapt example
code only after a small candidate set is selected. For static contest PDFs,
prefer Matplotlib/Seaborn output for exact reproducible statistics. Use
Pyecharts/ECharts when JS grammar materially improves expression: Sankey,
Graph, Geo/Map, Calendar, Custom series, dashboard-like composition, ECharts
GL 3D, or object-like 3D schematics. Keep local HTML/JS sources and export or
rebuild static PNG/PDF/SVG assets when needed.

When using ECharts, prefer `scripts/render_echarts_chart.py` with a local
option JSON. The script writes a local HTML source and can export PNG when
Playwright is available. Record the gallery URL, HTML/JS source, exported
image, and whether ECharts GL was used.

## AI-Generated Illustrations

Use `references/image-generation-visual-rules.md` when an illustration is
better served by a model's image-generation tool than by a data chart or an
editable diagram.

Good uses include mechanism scenes, physical equipment, conceptual legends,
and visual intuition for a structure or process. Bad uses include numeric
result figures, solver evidence, route maps, heatmaps, forecasts, sensitivity
plots, fake experimental photos, or precise algorithm/constraint diagrams.

Generated images must be traceable. Record the tool/model, developer, date,
prompt summary, generated asset path, human edits, and paper location in
`planning/generated_image_route.json` and the visual index. Avoid generated text in
the image; add exact Chinese labels, arrows, numbers, formulas, and captions in
an editable post-processing layer.

## Semantic Color

Before final plotting, choose colors by what color encodes. Use
`references/color-palette-rules.md` and Seaborn's color-palette principles:
https://seaborn.pydata.org/tutorial/color_palettes.html#general-principles-for-using-color-in-plots

| Encoding role | Palette choice | Figure obligation |
|---|---|---|
| Unordered categories, methods, scenarios, clusters | qualitative hue, preferably `colorblind`, `deep`, `muted`, `Set2`, or `tab10` | Legend labels must name categories; use markers/line styles when grayscale or color-blind readability matters. |
| Ordered levels, ranks, stages | ordered qualitative or discrete sequential palette such as `crest`, `flare`, `cubehelix`, or sampled `Blues` | Caption or legend must state the order. |
| Continuous nonnegative magnitude, density, counts | sequential luminance palette such as `mako`, `rocket`, `viridis`, `magma`, `crest`, or `flare` | Include a colorbar with unit/value meaning. |
| Residual, signed error, deviation from baseline, correlation around 0 | diverging palette such as `vlag`, `icefire`, `coolwarm`, or a balanced blue-orange custom map | Record the midpoint, usually 0 or the baseline. |
| One important threshold, winner, selected policy, or failure | neutral base plus one accent color | Caption or annotation must explain the highlight rule. |

- Avoid rainbow, `jet`, `nipy_spectral`, and red-green-only palettes in final
  contest-paper figures unless a waiver explains why.
- Do not use color as decoration. Each final figure should record color meaning
  in `figures/figure_index.md`, a manifest, a caption, a legend, or a colorbar.
- Use `scripts/color_palette_router.py` to generate
  `planning/color_palette_route.md/json`, then use `mira_palette`,
  `mira_cmap`, or `choose_palette_for_encoding` from `scripts/visual_style.py`
  in Matplotlib/Seaborn plotting scripts.

## Standard Style

Use `scripts/visual_style.py` from plotting scripts when matplotlib is used.
Export figures through `save_mira_figure` so Mira can inspect the live
Matplotlib artists before writing the file. Its `layout_qa` policy is `warn`
by default for nonblocking iteration, `strict` for final batch exports that
must stop on detected collisions, and `off` only for a reviewed intentional
overlap such as text placed on a Sankey band or structural connector. This
artist-level check shortens the fix-and-export loop, but it does not replace
inspection of the final PNG/PDF or the compiled paper page.

Default expectations:

- Prefer Chinese labels and concise units in axis labels.
- Use 300 dpi output for PNG when vector output is not practical.
- Prefer PDF/SVG for diagrams and line-heavy plots when the LaTeX/Typst workflow supports them.
- Avoid saturated rainbow palettes. Use a small, print-safe palette and line/marker differences for comparisons.
- Use clean white plotting backgrounds. Do not enable default chart grid backdrops
  such as `ax.grid(True)`, `axes.grid=True`, or seaborn `whitegrid/darkgrid`.
  Use threshold lines, annotated bands, tick marks, or very light structural
  guides only when they directly support reading the figure.
- Use a short title only when it helps standalone reading; do not duplicate the caption.
- Put explanatory conclusions in captions or nearby text, not inside a crowded chart.
- Use stable claim-oriented filenames, such as `q2_route_resource_ledger.png`, not `plot1.png` or `test.png`.
- Record the actual source tool in the visual index: Python script,
  PPT/PowerPoint source, Excel-compatible CSV/XLSX chart/table,
  MATLAB/Octave-style output, or another reproducible tool. Tool names are
  provenance, not decoration.
- When a full-scale plot makes the important feature look like a point, flat line, or a few disconnected samples, add one of: local zoom inset, separate zoom figure, logarithmic/normalized axis, residual plot, or annotated threshold band.
- If a plot has only a few discrete points, use markers and a table or stem/bar plot rather than pretending it is a smooth curve.
- For A053-style explanatory figures, use the helpers in `visual_style.py` when
  applicable: `add_callout_box`, `annotate_bracket`,
  `connect_axes_with_arrow`, `label_panel`, and
  `make_boundary_comparison_figure`.

## Figure Types

| Figure type | Best use | Visual requirement |
|---|---|---|
| Trend/fit curve | Forecasting, fitting, mechanism validation | Raw and fitted/predicted curves must be distinguishable; include unit and error metric nearby. |
| Residual/error plot | Model validation | Axis should show error meaning; do not hide large outliers with excessive smoothing. |
| Sensitivity curve | Parameter robustness | Mark recommended parameter or stable interval when possible. |
| Coarse-to-fine search | Threshold, critical time, limiting pitch/parameter, maximum speed | Show full-domain/coarse trend plus local refined view; mark bracket and final selected value. |
| Radar chart | Small scheme-by-indicator comparison after normalization or direction adjustment | Use few schemes/indicators, record normalization, and pair final ranking with an explicit scoring table. |
| Taylor diagram | Forecast/simulation model comparison against observations | Use paired observed-predicted samples; add bias/residual statistics when model accuracy claims matter. |
| Parallel coordinates | Many schemes across several normalized indicators | Record direction transforms, limit clutter, and use it for screening rather than final proof. |
| Pareto front | Two-objective tradeoff, such as cost-quality or time-risk | State min/max direction for each objective and interpret front points as candidate choices, not a single answer. |
| Gantt/timeline | Scheduling, implementation workflow, production plan, or execution roadmap | Tie tasks to model outputs, assumptions, or management actions; do not use it as solver evidence. |
| Route/network diagram | Path, logistics, game maps | Show final route/action grouping and keep node labels legible. |
| State-transition diagram | DP, Markov, cellular automata, game process | Show state, action, and transition meaning; avoid oversized decorative flowcharts. |
| Structure schematic | Problem object, model variable relation, system structure, geometry/local detail, or module topology | Every node and arrow must correspond to a real object, variable, equation, constraint, module, or reasoning step. |
| Python/MATLAB structural diagram | Flowchart, architecture map, state transition, variable relation, mechanism, or computed engineering schematic | Keep `.py` or `.m` source plus PDF/PNG export, Chinese labels, clean background, and source-data/spec records. Use Mermaid for suitable sequence diagrams. |
| AI-generated illustration | Physical scene, equipment, mechanism intuition, or conceptual legend that improves explanation but is not data evidence | Record prompt/tool/provenance and human edits; add exact Chinese labels later; caption must not imply measured data or solver evidence. |
| PPT reasoning diagram | Idea map, model logic chain, process lane, execution workflow, or callout-rich schematic needing editable shape layout | Keep PPTX as source, export PNG/PDF for paper insertion, and map every shape to a real model, formula, result, or action. |
| Pseudo-3D PPT schematic | Semantic layer depth, tensor/channel stack, spatial/module topology, or scenario cards where depth has a real paper meaning | State what depth represents, keep labels readable on front faces, and pair with a module/layer/scenario/variable table. |
| Multi-branch feature-fusion architecture | Multi-source features, parallel encoders, graph/sequence/statistical branches, attention/fusion, ensemble, or prediction head | Use consistent branch colors, latent vector bars, dashed auxiliary paths, and a validation/ablation table nearby. |
| CNN architecture | Image/matrix/grid/signal convolution model, CNN feature extractor, or CNN plus downstream prediction head | Show input size, conv kernel/channel blocks, pooling/downsampling, Flatten/GAP, output head, and nearby training/validation evidence. |
| Neural-network-like architecture | BP/MLP/CNN/DNN, learned surrogate, feature embedding/fusion, or explicit layered mapping | Show real layers/modules and feature flow; pair with formulas, training settings, validation metrics, or a clear non-neural wording. |
| Heatmap/matrix | Dense matrix, grid, spatial field, correlation, normalized indicators | Include colorbar and unit/scale meaning; do not use heatmap for a tiny table. |
| Hexbin joint distribution | Large paired numeric samples where scatter points overlap, such as Monte Carlo samples, residual pairs, feature-response pairs, or observation-prediction pairs | Main panel color means sample count per hexagon; show marginal histograms, record `gridsize`, add Pearson/Spearman or quantile summary nearby, and avoid causal claims from the plot alone. |
| t-SNE/embedding plot | High-dimensional feature vectors, sample embeddings, clustering/classification visual companion | Standardize features, save coordinates/parameters, color by label or cluster, and state that t-SNE is visual evidence rather than proof of global distance or true cluster count. |
| Violin plot | Distribution shape, skewness, multimodality, and quartile comparison across groups | Show quartiles or medians, avoid tiny per-group samples, and pair visual shape claims with summary statistics. |
| Box plot | Median, IQR, range, and outlier comparison | Preserve outliers when possible; use violin/JoyPlot if multimodality matters. |
| JoyPlot/ridgeline | Many ordered group, scenario, time-window, or parameter distributions | Use meaningful group order, readable labels, and avoid treating density shape as statistical significance. |
| Sankey diagram | Directed source-process-result flow, resource allocation, material/energy/cost transfer | Use one consistent unit for width, keep node labels readable, and place exact values in a nearby table or saved edge data. |
| Circular Sankey/chord | Many-to-many association, OD flow, cross-category transfer, or mutual coupling | Use meaningful node order and explain whether color means source, category, or stage; do not rely on line width for exact values. |
| 3D scatter/point cloud | Spatial samples, 3D coordinates, three-variable coupling, clustered feature space, or parameter-response samples | Record camera view, use color/size only for real variables, and add projection panels or tables when exact comparison matters. |
| 3D bar/bar3D | Small two-way category or parameter matrix, such as scheme x metric or parameter A x parameter B | Keep bar count low, record camera view, and pair with heatmap/table when exact cell comparison matters. |
| 3D surface/trajectory | Curved surface, spatial path, parameter-response surface, two-parameter sensitivity, or geometry that is hard to read in 2D | Record camera/interpolation settings and pair with 2D contour/heatmap or table if exact comparison matters. |
| Zoom/detail figure | Collision boundary, peak, threshold, local feasible interval, or dense curve crossing | Show the local scale, annotate the value, and state why full-scale view is insufficient. |
| Multi-case subplots | Scenario, branch, candidate, or before/after comparison | Use shared axes when comparison matters; captions should state the difference between cases. |
| Theorem-operation diagram | Separating axis, DP recurrence, Markov transition, cellular automata update, game payoff construction | Text step labels should correspond to visible colors, arrows, intervals, states, or matrices in the diagram. |
| Payoff matrix | Game theory | Entries must be derived from original costs, resources, or utilities; interpret equilibrium nearby. |
| Resource/timeline chart | Scheduling, implementation, dynamic strategy | Align time axis with the decision unit and show constraint thresholds when relevant. |

## 2D Heatmap And 3D Use

- Heatmaps are appropriate for dense two-dimensional data: time-by-object speed fields, parameter grids, spatial raster fields, confusion/error matrices, correlation matrices, or normalized indicator matrices.
- Heatmaps are not appropriate for a tiny table, a one-dimensional curve, or a result that can be read more clearly as a compact table.
- Hexbin joint-distribution plots are for dense paired samples, not matrices.
  Use them when point overlap hides bivariate density and when the marginal
  distribution of each variable helps the interpretation.
- Structure schematics explain modeling logic and object relationships; they do not prove numerical conclusions without formulas, results, or validation evidence.
- 3D plots are useful when the geometry or response surface is inherently spatial, such as 3D trajectory, surface reconstruction, two-parameter objective surface, or physical layout.
- 3D scatter is appropriate for point clouds or sample-level three-variable structure; use 3D surface only when values form a meaningful surface or trajectory.
- 3D bars are appropriate for small two-way matrices, not for one-dimensional rankings or dense tables; use grouped bars or heatmaps in those cases.
- 3D plots can hide exact values and occlude points. When the conclusion depends on precise comparison, pair the 3D plot with a 2D contour/heatmap/table.
- Pseudo-3D PPT schematics are not numerical 3D plots. Use them for semantic
  depth, layered architecture, tensor/channel stacks, spatial topology, or
  scenario cards; the caption must state what depth represents.
- Mira should choose visual form by claim: table for exact values, 2D line/bar for ordered comparison, heatmap for dense 2D structure, 3D for spatial intuition, and zoom view for local critical behavior.
- Mira should choose toolchain by evidence shape: Python for general
  reproducible plots and structural diagrams; MATLAB for verified
  surface/field, signal/control, engineering-response, matrix, image-processing,
  or optimization-trajectory work; Mermaid for sequence diagrams; PPT only for
  special editable layouts. MATLAB installation alone does not justify the route.

## Tables

- Main-text tables should be compact and answer a claim.
- Long route schedules, full parameter grids, full normalized matrices, and complete simulation replications belong in separate result files.
- Table captions should state the takeaway, not only the object.
- Numeric columns need units, precision discipline, and source/result traceability.

## Audit Command

Before final delivery, run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_asset_audit.py `
  --root <project-root> `
  --write-report checks\visual_asset_audit_report.md `
  --write-json checks\visual_asset_audit_report.json
```

Also run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_opportunity_audit.py `
  --root <project-root> `
  --output-level contest_final `
  --write-report checks\visual_opportunity_report.md `
  --write-json checks\visual_opportunity_report.json
```

Then route chart examples:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\chart_gallery_router.py `
  --root <project-root> `
  --from-project `
  --write-report planning\chart_gallery_route.md `
  --write-json planning\chart_gallery_route.json
```

Then route color palettes:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\color_palette_router.py `
  --root <project-root> `
  --from-project `
  --write-report planning\color_palette_route.md `
  --write-json planning\color_palette_route.json
```

Then run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\visual_reasoning_audit.py `
  --root <project-root> `
  --write-report checks\visual_reasoning_audit_report.md `
  --write-json checks\visual_reasoning_audit_report.json
```

Warnings do not automatically invalidate the model, but unresolved warnings should be reviewed before submitting a high-award final paper.
