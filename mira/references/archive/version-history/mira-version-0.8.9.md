# Mira 0.8.9

## Scope

Mira 0.8.9 adds Seaborn-informed color-palette routing.

The upgrade turns color from a style afterthought into a semantic decision:
categorical data use hue, numeric data use luminance, and midpoint-centered
data use diverging palettes.

## Source

- https://seaborn.pydata.org/tutorial/color_palettes.html#general-principles-for-using-color-in-plots

## Behavior

- Before final plotting, choose a palette class from the visual claim and data
  encoding: qualitative, sequential, diverging, ordered, or highlight.
- Use `references/color-palette-rules.md` for human-readable rules.
- Use `scripts/visual_style.py` helpers `mira_palette`,
  `mira_cmap`, and `choose_palette_for_encoding` in plotting scripts.
- Use `scripts/color_palette_router.py` to create
  `planning/color_palette_route.md/json` for contest-final figure planning.
- Avoid rainbow and red-green palettes unless the user explicitly waives the
  risk and records why.

## Output Contract

Every important figure should state what color means in its caption, colorbar,
legend, or nearby text. Numeric color scales need a unit or value meaning;
diverging scales need the midpoint; category colors need readable labels and,
when necessary, marker or line-style redundancy.

