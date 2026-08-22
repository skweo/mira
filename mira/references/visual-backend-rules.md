# Visual Backend Rules

Use this contract in the figure, diagram, paper, and verification phases.

## Evidence First

Every main-paper visual must name its supported claim, source artifact, paper
section, and reason a figure is better than a table or equation. Build a compact
portfolio across roles when evidence exists:

- definition or mechanism;
- primary result;
- validation or residual evidence;
- comparison, uncertainty, sensitivity, or local zoom.

Do not enforce a raw figure quota. A proof, table, or sentence may be better;
record that choice as a waiver in the storyboard.

## Secondary Visual Reference Route

The public stage route loads only the base visual contract. When the current
request or saved project facts name a concrete visual intent,
`scripts/route_references.py` selects exactly one leaf reference from four
categories:

| Category | Covers | Examples |
|---|---|---|
| `data_chart` | Numerical or statistical evidence | 3D surface, 3D scatter, distribution, t-SNE, Sankey, Pareto |
| `structural_diagram` | Model, process, geometry, state, or architecture structure | flowchart, structure schematic, CNN, multimodal fusion, Mermaid sequence |
| `style_spec` | Readability, composition, and paper placement | palette, three-line table, figure narrative, journal-grade figure |
| `special_visual` | Scoped visual workflows that need separate provenance or editing | chart-gallery lookup, AI illustration, pseudo-3D PPT |

An explicit current request takes precedence over vocabulary saved in project
files. If several leaves match the same request, the most specific registered
leaf is loaded and the other candidates are reported as deferred. Reroute the
next concrete figure intent to load another leaf; do not load a bundle of all
matched visual rules. Generic words such as sensitivity, validation, result,
or figure do not by themselves select a concrete visual leaf.

## Backend Selection

Run `visual_backend_router.py` before drawing. Its structured route is a
two-layer decision:

1. Select the evidence expression from the claim, intended inference, reader
   question, data shape, and evidence role. This layer may select a figure,
   structural diagram, table, proof/equation, or a documented no-visual choice.
2. Only after a plotted visual family is fixed, select Python or MATLAB from
   the required chart family, execution context, and recorded capability.

Python is not a fallback for missing visual intent. If the claim-level question
or data shape is missing, or they imply conflicting visual families, return
`NEEDS_EVIDENCE_DECISION` and leave the backend and library empty. A backend
override may change only the implementation; it must not change the selected
visual form or chart family.

For an already-selected statistical distribution, residual diagnostic, time
series, local detail, or structural diagram, the normal implementation is the
corresponding Python/Seaborn/Matplotlib route. For an already-selected scalar
field, vector field, simulation trajectory, local route geometry, or spatial
mesh, MATLAB is preferred when the execution capability is verified or is
being established by the executor. An explicitly unavailable MATLAB capability
uses the declared Python fallback without changing the chart family.

Installation is not execution evidence. Record MATLAB as `installed`,
`executed`, and, when relevant, `toolbox-confirmed`. On timeout or license
failure, save the probe result and use Python unless MATLAB is essential.

## Python Contract

- Use `visual_style.py` and stable paper dimensions.
- Use one claim-bearing main view by default. Add a local inset when a critical
  point, collision, threshold, boundary contact, or error peak needs inspection.
- Use side-by-side panels only when the views share a scale and direct visual
  comparison is the intended inference; record that reason in the figure
  evidence manifest.
- Add thresholds, callouts, insets, comparison baselines, and uncertainty only
  where they express reasoning.
- Export a 300-DPI PNG and vector PDF.
- Save source data and `<figure>_summary.json` under
  `results/figures_data/`.

`plot_claim_figure.py` is a runnable baseline, not a mandatory chart grammar.

## MATLAB Contract

- Keep source under `code/matlab/`. Use MATLAB MCP for Codex interactive work
  and `matlab -batch` for unattended or reproducibility runs.
- Use `tiledlayout`, explicit font/line settings, white backgrounds, and
  `exportgraphics` for 300-DPI PNG plus vector PDF.
- Save plotted arrays to CSV/MAT and a claim summary to JSON.
- Write the schema-version-3 execution record described in
  `computation-backends.md`. A successful record must contain transport,
  context, MATLAB version, source, request, command or tool identity,
  timestamps, logs, evidence, and outputs.

Use `run_matlab_visual.py --scaffold --run` only as the unattended batch
baseline. For interactive work, run `--prepare-mcp`, call the exact
`mcp__matlab__run_matlab_file` request emitted by the script, save the unedited
tool result in the response envelope, and run `--complete-mcp`. Completion
binds the unique request marker, source hashes, raw response, logs, outputs,
provenance, and claim into the schema-version-3 record. It does not fall back
to Python or batch. Adapt the copied `.m` source to the actual model; never
present demo data as evidence.

### Face-vertex 3D geometry

Use `run_matlab_visual.py --visual-kind geometry_3d --scaffold --run` for a
mesh, polyhedron, triangulated object, or other face-vertex structure. Supply
the actual `vertices`, `faces`, scalar color values, and unit through the
parameters JSON; the scaffold uses `patch` and exports a separate orthographic
projection. Record the camera view, data aspect ratio, face alpha, color
mapping, colormap, lighting, light position, material, and projection plane.

Treat lighting, transparency, and material as display transforms, never as
model evidence. A complete render proves only that the archived geometry can be
reconstructed. It does not establish collision freedom, strength, stability,
manufacturability, or physical feasibility without separate constraints or
tests. Keep the 2D projection, slice, or companion table required by the 3D
evidence gate.

## Structural Diagrams

draw.io is retired from the active Mira workflow. Use
`plot_structure_diagram.py` or another Python source for flowcharts,
architectures, mechanisms, and variable relations. Mermaid remains suitable
for sequence diagrams; MATLAB is acceptable for engineering schematics whose
geometry is generated from computed data. Keep the editable `.py`, `.m`, or
`.mmd` source and a PDF/PNG export.

## Render Gate

Run `visual_render_gate.py` after generation. A final visual must be decodable,
nonblank, large enough for A4 print, indexed, and paired with a source-data and
claim summary. Also inspect the compiled PDF for label size, clipping, overlap,
and whether surrounding text states the observation, implication, and next
reasoning step.
