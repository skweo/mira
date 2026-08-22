# Color Palette Rules

Use this reference when choosing colors for Mira contest-paper figures.

Primary source:

- Seaborn color palette tutorial:
  https://seaborn.pydata.org/tutorial/color_palettes.html#general-principles-for-using-color-in-plots

## Core Rule

Choose colors by what the color channel means, not by what looks flashy.

| Data meaning | Palette class | Main visual channel | Good defaults | Avoid |
|---|---|---|---|---|
| Unordered categories | qualitative | hue | `deep`, `muted`, `colorblind`, `Set2`, `tab10` | lightness-only changes, too many categories |
| Ordered categories | ordered qualitative or discrete sequential | hue plus mild luminance | `crest`, `flare`, `cubehelix`, `Blues` sampled discretely | pretending ordered categories are unrelated |
| Continuous nonnegative value | sequential | luminance | `rocket`, `mako`, `viridis`, `magma`, `crest`, `flare` | rainbow/circular hue maps |
| Deviation around midpoint, often 0 | diverging | two hues around neutral midpoint | `vlag`, `icefire`, `coolwarm`, custom blue-orange | red-green, unbalanced endpoints |
| Highlight one important element | neutral base plus accent | accent hue | gray base + red/orange/blue highlight | coloring everything with equal strength |
| Accessibility-critical categories | qualitative with redundancy | color plus marker/line style | `colorblind`, marker shapes, line styles | relying on red/green alone |

## Contest-Paper Practice

- Use hue to distinguish categories, because readers can name and remember
  category colors.
- Use luminance for numeric magnitude, because light/dark changes reveal
  structure and importance.
- Use diverging palettes when both low and high values matter around a neutral
  midpoint.
- Avoid red-green diverging palettes.
- Avoid rainbow maps for heatmaps, surfaces, hexbin plots, residual fields, and
  other numeric scales.
- Do not use colors as decoration. The caption or nearby text must say what
  color encodes.
- When a figure may print in grayscale, pair color with marker, line style,
  label, annotation, or panel separation.
- Use colorbar labels for numeric colormaps and legend labels for categorical
  colors.

## Mira Defaults

| Purpose | Preferred palette |
|---|---|
| General categorical comparison | `colorblind` if seaborn is available; otherwise `MIRA_PALETTE` |
| Polished muted categories | `deep` or `muted` |
| Many categories | `husl` up to a readable count; otherwise aggregate |
| Heatmap/hexbin/count density | `mako`, `rocket`, or `viridis` |
| Line/point numeric color | `flare` or `crest`, because they avoid near-white endpoints |
| Positive/negative residual | `vlag`, `icefire`, or `coolwarm` |
| Critical threshold/highlight | neutral gray base plus `MIRA_COLORS["red"]` or `MIRA_COLORS["orange"]` |

## Required Metadata

For each final figure, record at least one of these in `figures/figure_index.md`
or the plotting manifest:

- categorical color meaning;
- numeric colormap name and colorbar unit;
- diverging midpoint value;
- highlight rule;
- accessibility fallback such as marker shape or line style.

