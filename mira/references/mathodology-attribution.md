# Third-Party Attribution: `mathodology`

Mira's live Matplotlib layout QA was informed by the open-source repository
[`sweetcornna/mathodology`](https://github.com/sweetcornna/mathodology), fixed
at tag `v0.8.0` and commit
`8b57eb0f5e00db6e7b53310729e5d02e71cfc7e1`.

- Upstream component: `.claude/skills/mathodology-award-gates/scripts/figqa.py`.
- License: MIT. The complete upstream license and an integration notice are
  retained at `references/third-party/mathodology/LICENSE` and
  `references/third-party/mathodology/NOTICE.md`.
- Learned design: inspect the live Matplotlib artist graph after drawing;
  compare real text and legend extents; test line segments and scatter centers
  in display coordinates; exempt value labels fully inside a host patch; and
  keep arrow patches out of the data-patch set.
- Mira adaptation: `scripts/matplotlib_layout_qa.py` adds standard titles,
  axis labels, ticks, offset text, figure text, tables, multiple axes, colorbar
  axes, structured findings, warning/strict/off policies, and paired-export
  caching through `scripts/visual_style.py`.
- Boundary: Mira did not import Mathodology's workflow, CLI, skill tree, award
  gates, or paper templates. Live artist QA remains an internal diagnostic in
  Mira's existing `implementation` stage; raster and final-PDF inspection stay
  separate.

This record documents source, license, adaptation, and exclusions. It does not
imply endorsement by the upstream project.
