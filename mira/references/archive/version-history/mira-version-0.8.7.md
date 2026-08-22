# Mira 0.8.7

## Scope

Mira 0.8.7 adds a gallery chart-grammar router.

When Mira needs to draw a figure, it should first consider the curated chart
examples from:

- https://gallery.pyecharts.org
- https://matplotlib.org.cn/stable/gallery/#widgets
- https://seaborn.pydata.org/examples/index.html

The goal is not to memorize every implementation. Mira records chart names,
data shapes, evidence roles, warnings, and example URLs, then fetches or adapts
specific example code only when a project selects that chart.

## Behavior

- Before implementation chart generation, run `scripts/chart_gallery_router.py`
  or read `references/chart-gallery-index.md`.
- Match chart grammar by claim and data shape before choosing code.
- Prefer Matplotlib/Seaborn for static contest-paper output.
- Use Pyecharts for Sankey, Graph, Map/Geo, Calendar, and interactive-style
  grammar inspiration; rebuild or export a static figure when the paper is a
  fixed PDF.
- Do not load full gallery pages at startup. Open example pages only after the
  router selects a small candidate set.
- Do not upload contest data to gallery websites or external notebooks.

## Output Contract

`scripts/chart_gallery_router.py` writes:

- `planning/chart_gallery_route.md`
- `planning/chart_gallery_route.json`

Each route entry should include chart name, library, gallery URL, data shape,
paper role, best-use reason, avoid note, and a score. Selected gallery URLs
should be copied into `figures/figure_index.md` when they influence the final
figure implementation.
