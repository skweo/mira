# Mira Changelog

## 1.0.0 - 2026-08-22

### Added

- First release distribution (sanitized for sharing): machine paths and personal corpus references replaced with `$PROJECT_ROOT` placeholders, private calibration benchmarks removed, portable TeX detection with MIRA_TEX_BIN override.
## 0.13.4 - 2026-08-01

### Changed

- Removed the active deferred-validation roadmap and release-blocking semantics
  for fresh multi-paper double runs, external dual review, and unfinished
  migration candidates. Historical comparison records remain provenance only
  and create no future work obligation.
- Kept the requirement to consider structurally different candidate models, but
  made their discrimination contest-budget-aware: use analytic or tiny-case
  screening first, declare a time/run cap, and allow a scoped budget waiver for
  an expensive candidate tournament.
- Budget waivers cannot bypass feasibility, hard-constraint checks, or final
  validation of the selected model.

## 0.13.3 - 2026-07-28

### Changed

- Removed a retired problem-specific benchmark, answer fixtures, hard-coded
  paper repairs, comparison records, and source-specific learning notes.
- Retained rigid-chain kinematics, separating-axis collision detection, and
  continuous extremum refinement as generic domain-knowledge cards routed by
  problem mechanisms rather than historical problem names.
- Generalized benchmark regression tests, figure-repair routing, confidence
  evidence matching, and MATLAB validation keys so no retired answer can be
  applied to an unrelated paper.

## 0.13.2 - 2026-07-27

### Changed

- Replaced the workspace-specific external skill audit example with an
  explicit caller-supplied checkout path. Mira's maintenance documentation no
  longer points to or assumes a local `MathModeling-skills` repository.

## 0.13.1 - 2026-07-24

### Changed

- Replaced persistent dependency propagation with a stateless, optional
  changed-path advisor. It reads only command-line path strings, writes no
  project state, and cannot block a workflow stage.
- Removed change-impact state and dependency-graph files from new-project
  initialization; legacy files are ignored.
- Removed submission compliance from the ordinary paper-stage gate. It remains
  a final-delivery component and blocks only actual generic or explicitly
  configured violations.
- Made competition-specific title, keyword, section, page, anonymity, and
  disclosure settings optional. Missing or invalid requirements fall back to
  generic final-artifact checks with a warning.
- Removed mandatory competition identity, official-rule dates, human
  confirmations, configuration sentinels, and AI-prohibition policy.

## 0.13.0 - 2026-07-24

### Added

- Added explicit, dependency-ordered change-impact propagation. A material
  change records the smallest affected result, figure, paper, and delivery
  path instead of triggering a whole-project scan or a new public stage.
- Added a fail-closed, competition-specific submission contract for official
  title, keyword, section, page, anonymity, required-file, placeholder, and
  AI-disclosure rules, plus human confirmations for checks automation cannot
  prove.
- Treat cleaned-data changes as implementation inputs so affected results,
  figures, and paper sections are rechecked without reopening unrelated work.
- Added the submission compliance gate to `contest_final_pipeline.py`; an
  incomplete contract or failed requirement prevents a READY delivery.

### Changed

- Made unresolved change impacts block only the affected public stage and its
  downstream stages. Clean projects pay only the cost of reading a small JSON
  state file during a stage check.
- Kept official page limits separate from Mira's existing presentation-length
  quality target.

### Attribution

- Adapted the local-repair and submission-readiness ideas from
  `handsomeZR-netizen/mathmodel-skill` at commit
  `d3941e14d8693fb4a79948e59afff3098734127e`. Mira's implementation is new;
  no upstream code, workflow tree, phrase bank, or scoring system was copied.

## 0.12.2 - 2026-07-24

### Added

- Added live Matplotlib artist-level layout QA, informed by Mathodology's
  `figqa.py`, for text collisions, legend/data overlap, line or point
  occlusion, and text crossing the figure canvas.
- Added `warn`, `strict`, and `off` policies to `save_mira_figure`; the
  nonblocking `warn` policy remains the default and cached results avoid
  repeating work or warnings during paired PNG/PDF export.
- Added deterministic coverage for Chinese labels, titles, ticks, tables,
  multiple axes, hidden axes, legends, lines, scatter points, canvas bounds,
  and intentional-overlap opt-out.

### Changed

- Restricted text discovery to artists that Matplotlib actually draws through
  public figure and axes surfaces, avoiding phantom tick findings on axes that
  have been turned off.
- Kept live artist QA inside the `implementation` stage and separate from
  existing raster, vector, provenance, and final-PDF checks.

### Attribution

- Retained the upstream Mathodology version, commit, MIT license, integration
  notice, and adaptation boundary under `references/`.

## 0.12.1 - 2026-07-20

### Changed

- Removed default paper-appendix production and changed code, long tables,
  logs, diagnostics, and low-priority visuals to independent supporting files.
- Removed the obsolete AI-decision, human-approval, and numbered-gate control
  plane from active maintenance files.
- Made only a current explicit `FAIL` or `requires_user_decision` block a stage;
  ordinary WARN findings remain visible as `PASS_WITH_WARNINGS` and do not stop
  the next stage.
- Fixed the iteration controller's stale `clean_phase` variable and normalized
  all queued return locations to the four public stages.
- Removed superseded 0.9/0.11 control documents, release reports, and generated
  Python caches from the live skill tree.
- Removed the unused 0.11 release-evidence gate and generalized the reusable
  comparison-package template and output path.

### Compatibility

- Existing attachment labels and appendix headings remain readable so Mira can
  inspect user-provided or official files without generating a new appendix.
- `--allow-warnings` remains accepted by existing commands but no longer changes
  the default nonblocking WARN policy.

## 0.12.0 - 2026-07-19

### Changed

- Replaced the public analysis-9 and G0-G7 control plane with four stages:
  analysis, modeling, implementation, and paper.
- Reduced each public stage route to three or four commands while retaining
  specialized diagnostics inside the owning stage.
- Normalized legacy phase and gate arguments immediately to a public stage so
  existing projects and callers remain compatible.
- Represented real human choices as `requires_user_decision` blockers instead
  of separate workflow gates.
- Updated new-project templates to create four-stage state and stopped creating
  pending modeling/implementation records by default.
- Archived the 0.11 control documents under
  `references/archive/control-plane/` and activated compact four-stage
  contracts.
- Marked the removed full-project archive as unavailable and retained only its
  lightweight provenance catalog plus compact executable benchmarks.
- Removed the dormant legacy command matrix and routed commands directly by
  public stage.
- Removed 374 lines of unreachable legacy phase/reference routing tables; the
  active router now contains only the four public stage maps and risk triggers.
- Kept historical benchmark regression as an `implementation` maintenance mode
  instead of exposing it as a fifth workflow stage.
- Removed the obsolete control-plane audit from new contest-final runs and
  made the executable pipeline enforce the canonical result-ledger check.
- Normalized public report ownership and return locations to the same four
  stage names, including diagnostics that still accept legacy Phase/G labels.

### Compatibility

- Legacy decision records remain readable, but their unresolved items are
  reported under the owning stage.
- Historical diagnostic scripts remain available and are no longer part of the
  user-facing workflow sequence.

## 0.11.0 - 2026-07-17

### Added

- Selective evidence-authenticity integration informed by `nature-skills`:
  statistical evidence contracts, figure-source preflight, reference
  authenticity, material anchors, and central claim evidence chains. The
  integration is reimplemented in native Mira modules and keeps an attribution
  record without importing the external skill tree or training corpus.
- A single-entry XeLaTeX `contest_final` pipeline with one canonical source, one
  audited PDF, delivery manifests, build batches, explicit states, and
  fail-closed delivery semantics.
- Page-level paper audits for standalone front matter, effective body length,
  typography, figure/table readability, overflow, blank pages, and page rhythm.
- Structured Python-native flowcharts with deterministic hierarchy, swimlanes,
  orthogonal routing, vector PDF, and 300 DPI PNG outputs.
- Claim-bound Python and MATLAB figure evidence, including source code, input
  data, logs, backend rationale, local enlargements, captions, and ledger checks.
- Gates for LaTeX math environments, `booktabs` three-line tables, in-text
  citation binding, cross-artifact numeric consistency, modeling scope, boundary
  checks, residuals, and optimality claims.
- Anchored readiness evaluation and anonymized comparison infrastructure.

### Changed

- Promoted the contest paper from a generic report template to adaptive
  mechanism-, decision-, evidence-, theorem-, or scenario-first architectures.
- Made Python the ordinary structural-diagram backend and kept MATLAB as the
  preferred verified backend for fields, dynamics, spectra, optimization
  trajectories, parameter scans, and three-dimensional geometry.
- Added an ASCII temporary execution bridge for MATLAB R2025a so projects under
  non-ASCII Windows paths can still return audited figures, data, logs, and
  provenance to their canonical project locations.
- Released 0.11.0 by explicit user acceptance of the completed functional and
  paper-quality improvements. The original strict comparison report remains
  preserved as a separate, non-overwritten audit record.

## 0.10.0 - 2026-07-14

### Added

- Evidence-shape routing between Python and MATLAB with truthful capability
  states: installed, batch-executed, probe status, and selected backend.
- Reproducible Python and MATLAB claim-oriented figure templates that export
  300 DPI PNG, vector PDF, source data, summary JSON, and figure-index records.
- A rendered-output gate for image decoding, nonblank pixels, dimensions,
  vector companions, source data, summaries, and figure indexing.
- Regression tests for backend routing, Python rendering, MATLAB output
  contracts, and structural-diagram defaults.

### Changed

- Made figures evidence-bearing by default: fit, residual, sensitivity,
  uncertainty, objective-surface, dynamic-response, and spectrum views are
  selected for the claim they support, not to satisfy a figure quota.
- Made Python the default reproducible structural-diagram route, MATLAB a
  verified engineering-computation route, and Mermaid a scoped sequence route.
- Retired draw.io from active commands, references, templates, and iteration
  repair instructions while preserving its historical scripts and fixtures.
- Kept the compact 0.9 control plane and historical project registry intact.

## 0.9.0 - 2026-07-14

### Changed

- Reduced `SKILL.md` to the active control contract: scope, startup, state
  machine, hard rules, execution loop, routing, and maintenance.
- Resolved phase command paths from the installed skill location instead of the
  `$PROJECT_ROOT` checkout.
- Replaced stale agent metadata that advertised the retired AI-use compliance
  workflow.
- Moved per-version notes through 0.8.21 to
  `references/archive/version-history/` and retained the compact version index.
- Grouped historical test projects under the workspace archive and registered
  their result, status, and retention role.

### Added

- `VERSION` as the machine-readable release identifier.
- `benchmarks/registry.json` and `benchmarks/HISTORICAL_PROJECTS.md`.
- `tests/test_mira_smoke.py` for syntax, routing, command portability, metadata,
  version, and registry checks.
- Pre-release and post-release compaction audit reports for the 0.9 baseline.

### Preserved

- Mira 0.8.21 modeling, evidence, human-decision, figure-claim, diagram,
  contest-writing, verification, and iteration behavior.
- Complete historical version notes and project contents for regression work.

## 0.8.21 - 2026-07-08

- Retired the active CUMCM-style AI-use ledger, disclosure PDF, and compliance
  gate chain while retaining ordinary provenance and artifact checks.
