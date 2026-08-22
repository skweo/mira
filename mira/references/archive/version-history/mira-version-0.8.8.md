# Mira 0.8.8

## Scope

Mira 0.8.8 adds Python + JS dual chart-engine routing.

Mira should keep Python as the default engine for reproducible static paper
figures, and use Apache ECharts/ECharts GL when JS chart grammar gives a real
visual advantage: Graph, Sankey, Map/Geo, Calendar, Custom series, dashboard-
style composition, 3D surfaces, 3D point clouds, globe/map3D, and object-like
3D schematics.

## Preferred Sources

- https://gallery.pyecharts.org
- https://matplotlib.org.cn/stable/gallery/#widgets
- https://seaborn.pydata.org/examples/index.html
- https://echarts.apache.org/examples/zh/index.html#chart-type-bar

## Toolchain Rule

- Use Python/Matplotlib/Seaborn for exact, reproducible statistical evidence.
- Use JS/ECharts for high-impact visual grammar or interactive exploration.
- For final fixed PDFs, export the JS chart to a static PNG/PDF/SVG or rebuild
  the selected view with Python. Keep the `.html`/`.js` source when ECharts
  drives the figure.
- Use ECharts GL only when depth, 3D geometry, or spatial routing has real
  model meaning. Do not use 3D merely to look advanced.
- Do not upload contest data to external websites. Gallery examples are code
  templates; all project data stays local.

## Output Contract

`scripts/chart_gallery_router.py` should include Apache ECharts examples in
`planning/chart_gallery_route.md/json`. When a JS chart is selected, record the
ECharts example URL, local HTML/JS source, export path, and whether ECharts GL
was used in `figures/figure_index.md`.
