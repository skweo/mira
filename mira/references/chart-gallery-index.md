# Chart Gallery Index

Use this compact index before choosing a chart grammar for Mira paper figures.
It is a routing surface, not a code dump. Store chart names, evidence roles,
data shapes, and example URLs here; fetch or inspect example code only after a
specific project selects a chart.

## Priority Sources

| Source | URL | Best use |
|---|---|---|
| Pyecharts Gallery | https://gallery.pyecharts.org | interactive-style chart grammar, Sankey/Graph/Map/Geo, and polished HTML examples that can be adapted to static export |
| Matplotlib Chinese Gallery | https://matplotlib.org.cn/stable/gallery/#widgets | reproducible static paper plots, 2D/3D axes, annotations, subplots, contours, and low-level customization |
| Seaborn Examples | https://seaborn.pydata.org/examples/index.html | statistical graphics, distributions, regression, categorical comparison, pairwise relationships, and publication-ready themes |
| Apache ECharts Examples | https://echarts.apache.org/examples/zh/index.html#chart-type-bar | JS chart grammar, advanced interaction, Graph/Sankey/Map/Custom, ECharts GL 3D, and high-impact visual expression |

## Routing Rules

- First decide the evidence role: `define`, `derive`, `operate`, `result`,
  `validate`, `zoom`, or `compare`.
- Then match the data shape: time series, category table, paired samples,
  matrix/grid, network/flow, spatial/map, multi-indicator schemes, or
  distribution samples.
- Prefer a gallery example only when its grammar strengthens the nearby claim.
  Do not add an exotic gallery chart for decoration.
- For contest-final static PDFs, Matplotlib/Seaborn examples are the default
  for reproducible statistical figures. Use Pyecharts/ECharts when JS chart
  grammar gives a real advantage: Graph, Sankey, Map/Geo, Calendar, Custom
  series, dashboard-like composition, ECharts GL 3D, or object-like 3D
  schematics. Export or rebuild the final figure as static PNG/PDF/SVG when
  the paper needs a fixed image.
- Skip dynamic widgets, repeated minor variants, dashboard-only demos, and pure
  interaction examples unless the project explicitly needs interactivity.
- Keep contest data local. Do not upload private contest data to external
  websites or hosted notebooks.
- Record the selected gallery example URL in `figures/figure_index.md` or
  `planning/chart_gallery_route.md` when it informs a figure.
- When an ECharts/ECharts GL route is selected, use
  `scripts/render_echarts_chart.py` to keep a local HTML/JS source and export a
  static image when possible.

## Chart Grammar Index

| Chart name | Library | Example URL | Data shape | Paper role | Best for | Avoid when | Static OK | Notes |
|---|---|---|---|---|---|---|---|---|
| Line plot | Matplotlib | https://matplotlib.org.cn/stable/gallery/lines_bars_and_markers/simple_plot.html | ordered x-y series | result/validate | trend, convergence, sensitivity, forecast fit | unordered categories or tiny exact tables | yes | Add markers, threshold bands, or zoom when the claim needs them. |
| Multi-line comparison | Matplotlib | https://matplotlib.org.cn/stable/gallery/lines_bars_and_markers/linestyles.html | several aligned series | compare/validate | scenario curves, baseline comparisons, ablation | too many lines or unclear legend | yes | Use direct labels or a compact legend. |
| Error band line plot | Seaborn | https://seaborn.pydata.org/examples/errorband_lineplots.html | repeated measures by x | validate | uncertainty around simulation or forecast curves | single deterministic series | yes | Pair with sample size and interval definition. |
| Scatter plot | Matplotlib | https://matplotlib.org.cn/stable/gallery/lines_bars_and_markers/scatter.html | paired numeric samples | result/validate | relationship overview and outlier inspection | severe overplotting | yes | Use hexbin or density when points overlap heavily. |
| Hexbin joint plot | Seaborn | https://seaborn.pydata.org/examples/hexbin_marginals.html | dense paired numeric samples | validate | bivariate density plus marginal distributions | small samples or matrix grids | yes | Mira also has `scripts/plot_hexbin_joint.py`. |
| Regression with marginals | Seaborn | https://seaborn.pydata.org/examples/regression_marginals.html | paired numeric samples | validate | fit direction with marginal context | nonlinear or causal claims without proof | yes | Report residual/error metrics nearby. |
| Pair plot | Seaborn | https://seaborn.pydata.org/examples/scatterplot_matrix.html | multiple numeric features | explore/validate | multivariate relationship screening | final proof or large high-dimensional data | yes | Keep as an exploratory result file unless it supports a clear body claim. |
| Correlation heatmap | Seaborn | https://seaborn.pydata.org/examples/many_pairwise_correlations.html | feature-feature matrix | validate/compare | correlation structure and redundancy | tiny matrix or causal claims | yes | Mask redundant triangle when useful. |
| Annotated heatmap | Seaborn | https://seaborn.pydata.org/examples/heatmap_annotation.html | 2D matrix/grid | result/validate | parameter grid, confusion matrix, normalized indicators | tiny table where exact values matter | yes | Colorbar must state unit/scale. |
| Contour plot | Matplotlib | https://matplotlib.org.cn/stable/gallery/images_contours_and_fields/contour_demo.html | 2D grid response | validate/zoom | level sets, feasible regions, objective surfaces | scattered data without interpolation notes | yes | Pair with optimum/threshold markers. |
| 3D surface | Matplotlib | https://matplotlib.org.cn/stable/gallery/mplot3d/surface3d.html | x-y-z grid | result/validate | response surface, two-parameter sensitivity, geometry surface | exact cell comparison | yes | Pair with 2D contour/heatmap for readability. |
| 3D scatter | Matplotlib | https://matplotlib.org.cn/stable/gallery/mplot3d/scatter3d.html | 3 numeric coordinates | result/explore | spatial samples, feature cloud, parameter-response cloud | precise comparisons hidden by perspective | yes | Record camera angle and use projections if needed. |
| 3D bar | Matplotlib | https://matplotlib.org.cn/stable/gallery/mplot3d/3d_bars.html | small 2D category matrix | compare/result | small scheme x metric matrix | dense matrix or one-dimensional ranking | yes | Pair with heatmap/table when exact values matter. |
| Bar chart | Pyecharts | https://gallery.pyecharts.org/#/Bar/bar_base | category-value table | result/compare | discrete comparison, ranking, count summaries | continuous trend or too many categories | yes | Final paper can rebuild with Matplotlib for static output. |
| Grouped bar chart | Seaborn | https://seaborn.pydata.org/examples/grouped_barplot.html | category x group x value | compare | grouped scenario or method comparison | many groups or long labels | yes | Add exact table when rankings are close. |
| Box plot | Seaborn | https://seaborn.pydata.org/examples/grouped_boxplot.html | numeric samples by group | validate/compare | spread, median, outliers | multimodal distribution is central | yes | Preserve outliers unless justified. |
| Violin plot | Seaborn | https://seaborn.pydata.org/examples/wide_form_violinplot.html | numeric samples by group | validate/compare | distribution shape, skewness, multimodality | very small sample per group | yes | Pair with medians/quantiles. |
| Ridgeline distribution | Seaborn | https://seaborn.pydata.org/examples/kde_ridgeplot.html | ordered grouped distributions | validate/compare | many scenario distributions or temporal density changes | few groups or exact comparisons | yes | Keep group order meaningful. |
| Histogram facets | Seaborn | https://seaborn.pydata.org/examples/faceted_histogram.html | samples split by group | validate | Monte Carlo or residual distribution by scenario | exact ranking | yes | State bin width and sample count. |
| Radar chart | Pyecharts | https://gallery.pyecharts.org/#/Radar/radar_base | normalized multi-indicator schemes | compare | few schemes across 3-8 indicators | unnormalized or direction-mixed metrics | yes | Pair with normalized score table; Matplotlib radar is preferred for static PDF. |
| Parallel coordinates | Matplotlib | https://matplotlib.org.cn/stable/gallery/specialty_plots/parallel_axis.html | many schemes x indicators | compare/explore | multi-indicator screening | final proof from crowded lines | yes | Normalize and align directions first. |
| Pareto/front scatter | Matplotlib | https://matplotlib.org.cn/stable/gallery/lines_bars_and_markers/scatter.html | two objectives by candidate | compare | cost-quality/time-risk tradeoff | single-objective ranking | yes | Mark nondominated candidates and objective directions. |
| Gantt/timeline | Matplotlib | https://matplotlib.org.cn/stable/gallery/lines_bars_and_markers/broken_barh.html | task start-end intervals | operate/result | schedules, implementation steps, resource windows | solver evidence without model tie-in | yes | Tie bars to model outputs or constraints. |
| Sankey diagram | Pyecharts | https://gallery.pyecharts.org/#/Sankey/sankey_base | source-target-value edges | result/operate | resource, cost, material, or information flows | exact values need dense reading | export/rebuild | Keep units consistent and record edge table. |
| Graph/network | Pyecharts | https://gallery.pyecharts.org/#/Graph/graph_base | nodes and edges | define/result | route networks, relation graphs, topology | labels are too dense | export/rebuild | Use static export or rebuild when PDF needs fixed output. |
| Chord/circular relation | Pyecharts | https://gallery.pyecharts.org/#/Graph/graph_circular_layout | many-to-many links | compare/result | cross-category associations and OD-like coupling | exact comparison by edge width | export/rebuild | Explain node order and color meaning. |
| Map/Geo scatter | Pyecharts | https://gallery.pyecharts.org/#/Geo/geo_base | geographic points/regions | define/result | spatial distribution and regional comparison | no real geographic meaning | export/rebuild | Use only when location is part of the model. |
| Calendar heatmap | Pyecharts | https://gallery.pyecharts.org/#/Calendar/calendar_heatmap | date-value series | result/validate | day-level temporal intensity | non-calendar data | export/rebuild | Useful for time-pattern evidence. |
| Polar plot | Matplotlib | https://matplotlib.org.cn/stable/gallery/pie_and_polar_charts/polar_demo.html | angle plus magnitude | result/define | direction, periodicity, circular force/allocation | ordinary category table | yes | Keep exact values in companion table. |
| Quiver/vector field | Matplotlib | https://matplotlib.org.cn/stable/gallery/images_contours_and_fields/quiver_simple_demo.html | grid/vector components | define/derive | force field, velocity field, gradient direction | values are not vectorial | yes | Add scale key and units. |
| Streamplot | Matplotlib | https://matplotlib.org.cn/stable/gallery/images_contours_and_fields/plot_streamplot.html | 2D vector field | derive/validate | continuous flow field or direction field | sparse vectors or exact point comparison | yes | Avoid if it implies unsupported dynamics. |
| Subplots/multi-panel | Matplotlib | https://matplotlib.org.cn/stable/gallery/subplots_axes_and_figures/subplots_demo.html | multiple related figures | compare/zoom | before-after, scenario panels, global/local zoom | unrelated plots in one figure | yes | Shared axes when comparisons matter. |
| Annotated callout plot | Matplotlib | https://matplotlib.org.cn/stable/gallery/text_labels_and_annotations/annotation_demo.html | plotted data plus highlighted point/range | zoom/result | critical thresholds, peaks, local failures | annotations crowd the chart | yes | Prefer concise Chinese callouts. |
| ECharts bar family | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-bar | category-value or stacked category table | result/compare | polished ranking, stacked contribution, waterfall-like summaries | simple static bars are enough | export/rebuild | Use when visual hierarchy or interaction helps choose cases. |
| ECharts line/area family | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-line | time series or ordered x-y series | result/validate | multi-series trends, zoomable histories, area accumulation | final PDF only needs a plain trend | export/rebuild | Use dataZoom/tooltip for exploration, then export the selected static view. |
| ECharts heatmap/calendar | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-heatmap | matrix/grid/date-value data | result/validate | dense temporal or spatial intensity, calendar-pattern evidence | exact values need a compact table | export/rebuild | Calendar heatmap is high value for day-level patterns. |
| ECharts Graph/force | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-graph | nodes and edges | define/result | network topology, relation graphs, dependency structures | graph layout is arbitrary or labels crowd | export/rebuild | Record node/edge meaning and layout parameters. |
| ECharts Sankey | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-sankey | source-target-value edges | result/operate | material, cost, resource, energy, information, or probability flow | width must be read as exact values without table | export/rebuild | Keep edge table as source evidence. |
| ECharts tree/treemap/sunburst | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-tree | hierarchy or nested categories | define/compare | decomposition structure, indicator hierarchy, risk taxonomy, nested contribution | no true hierarchy exists | export/rebuild | Sunburst/treemap can be visually strong but must map to real nested data. |
| ECharts map/geo/lines | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-map | geographic regions, points, or OD lines | define/result | regional distribution, logistics flows, spatial decision maps | location is not part of the model | export/rebuild | Use official/local map assets and record source. |
| ECharts gauge/funnel | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-gauge | scalar KPI or stage conversion data | result/operate | final score, pipeline conversion, staged loss | used as decoration or without real stage semantics | export/rebuild | Usually companion visual, not core proof. |
| ECharts custom series | ECharts JS | https://echarts.apache.org/examples/zh/index.html#chart-type-custom | geometry, interval, or bespoke shape data | define/derive/zoom | custom mechanism diagrams, timeline blocks, local geometry, nonstandard coordinates | a standard chart expresses the claim clearly | export/rebuild | Valuable for contest-specific objects and "one-off" mechanism figures. |
| ECharts GL bar3D | ECharts GL | https://echarts.apache.org/examples/zh/index.html#chart-type-bar3D | small x-y-z matrix or voxel-like values | result/compare | 3D category matrix, voxelized image/object-like schematic, impressive small matrices | dense matrix or exact comparison | export/rebuild | Pair with heatmap/table when exact values matter; requires ECharts GL. |
| ECharts GL scatter3D | ECharts GL | https://echarts.apache.org/examples/zh/index.html#chart-type-scatter3D | 3D point samples | result/explore | spatial samples, feature clouds, parameter-response samples | perspective hides the key comparison | export/rebuild | Record camera view and include 2D projection if needed. |
| ECharts GL surface | ECharts GL | https://echarts.apache.org/examples/zh/index.html#chart-type-surface | x-y-z mesh or parametric surface | define/validate | response surfaces, terrain-like fields, object-like parametric 3D schematics | data are not a true surface | export/rebuild | Strong for visual impact; caption must state what z/depth means. |
| ECharts GL globe/map3D/lines3D | ECharts GL | https://echarts.apache.org/examples/zh/index.html#chart-type-globe | geographic 3D or spatial routes | define/result | global/regional flow, 3D map, route arcs, spatial story | no geographic or spatial meaning | export/rebuild | High-impact but easy to overuse; keep data source and projection honest. |
