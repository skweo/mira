# Evidence Authenticity Rules

Use these rules when problem interpretation, statistical analysis, figure
generation, citation checking, or final claim binding can change a contest
paper's evidential meaning.

## Statistical Mode

- Classify each analysis as `deterministic`, `descriptive`, `inferential`, or
  `simulation` before choosing a statistical check.
- Do not require significance tests for a deterministic derivation. Mark every
  inferential-only field as `not_applicable` and record one substantive reason.
- For descriptive work, define the observation unit, sample construction,
  missing values, and reported summaries.
- For inferential work, record observed and independent sample sizes, effect
  size, interval estimate, test and assumptions, multiplicity handling, and
  missing-data counts. Repeated measurements are not independent replicates.
- For simulation work, record scenario design, seeds, repetitions, convergence,
  uncertainty summaries, and the domain over which the claim is supported.
- Never infer that two groups differ merely because one result is significant
  and the other is not.

## Figure Source Preflight

- Audit the Python or MATLAB source named by each provenance record before
  accepting a claim-bearing figure.
- Require readable labels and units, a non-misleading scale, a colorblind-safe
  palette, vector export, and a raster export of at least 300 DPI.
- Guard logarithmic transforms with a positive-domain check. Avoid rainbow and
  `jet` colormaps unless the variable is genuinely cyclic and the choice is
  justified.
- A rendered image does not replace source, data, route, and export provenance.
- Missing or malformed provenance and an audit that reaches zero sources are
  failures, not empty PASS results.

## Reference Authenticity

- Bind every bibliography entry to a real in-text source line and a claim that
  exists in `planning/result_ledger.json`.
- Use `VERIFIED` only when authoritative metadata matches the cited record.
- Use `LOCAL_ONLY` for an existing, locally anchored authoritative document
  whose issuing authority, core metadata, locator, and cited passage can be
  checked offline. An arbitrary local file is not authoritative evidence.
- Use `UNVERIFIABLE` when lookup is unavailable or evidence is insufficient;
  offline access never counts as verification.
- Use `CONFLICT` when DOI, title, authorship, year, or locator contradicts the
  cited record. `UNVERIFIABLE` and `CONFLICT` block `contest_final`.

## Material Anchors

- Preserve raw material unchanged and index extracted text by source, page, and
  paragraph under `materials/extracted/`.
- Label a material-backed statement as `quoted`, `inferred`, or `not_explicit`.
  Exact quotations must match the anchored text. Inferences need an explicit
  reasoning bridge and must not be presented as source wording.
- Absence of a statement in the supplied material is not evidence that the
  opposite statement is true.

## Contest Evidence Chain

- Every central frozen claim must trace through: problem interpretation,
  model or derivation, result evidence, validation, and paper conclusion.
- Each stage needs a substantive statement, an existing artifact, and a
  resolvable locator. A line locator must exist in the named artifact. Record
  decision value, scope, and any evidence gap.
- Return incomplete chains to their earliest owning stage; polished prose cannot
  compensate for a missing model, result, or validation artifact.

## Explicit Exclusions

- AI-generated illustrations may explain a concept but cannot serve as
  quantitative evidence, validation, measured geometry, or a numerical result.
- Do not import Nature journal structure, fixed English prose, R workflows,
  draw.io, Zotero/CNKI/MCP dependencies, or publisher submission machinery into
  Mira's Chinese mathematical-modeling contest workflow.
