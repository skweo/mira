# Four-Stage Contracts

This file owns Mira's public stage inputs, outputs, and exit conditions. The
filename is retained for compatibility with existing routes.

## 1. Analysis

Purpose: turn the problem statement and attachments into an explicit modeling
contract.

Inputs: problem statement, attachments, datasets, contest rules, and template.

Canonical outputs:

- `planning/delivery_brief.md`
- `planning/problem_analysis.md`
- attachment mapping and data-quality evidence when attachments exist

Required content:

- a source anchor that preserves the official title and top-level task wording
  before paraphrase; only explicit top-level tasks become subquestions
- subquestions and dependencies
- required output for each subquestion
- fields, units, ranges, and source locations
- known facts, assumptions, ambiguities, and privacy boundary
- attachment-to-question mapping and unused-file reasons
- data-cleaning decisions or explicit waivers

Exit: run `stage_gate.py --stage analysis`. Missing interpretation or a real
choice is recorded as `requires_user_decision` and remains in `analysis`.

## 2. Modeling

Purpose: define a defensible mathematical model before implementation.

Inputs: passed analysis artifacts and usable data.

Canonical outputs:

- `planning/modeling_plan.md`
- `planning/validation_plan.md` or `.json`
- optional symbol table and method route when useful

Required content:

- variables, indices, parameters, units, and domains
- assumptions with reasons and validity boundaries
- objectives, constraints, governing relations, and derivation
- candidate or baseline route where method choice matters
- solver choice and model-to-solver mapping
- feasibility, validation, sensitivity, and uncertainty plan
- rules for changing route when evidence contradicts the plan
- an implementation task table with `Task`, `Input`, `Output`, `Method`, and
  `Check` columns

Exit: run `stage_gate.py --stage modeling`. Formula gaps, undefined symbols,
unsupported assumptions, or missing validation remain in `modeling`.

## 3. Implementation

Purpose: produce reproducible computations, canonical results, and truthful
visual evidence.

Inputs: passed modeling plan and prepared data.

Canonical outputs:

- executable `.py`, `.m`, or `.ipynb` sources under `code/`
- run logs and structured outputs under `results/`
- `planning/result_ledger.*` for final work
- generated figures and their source data/code

Required content:

- deterministic entry points, dependency notes, seeds, and solver status
- implementation that matches stated variables, objective, and constraints
- comparable baseline or validation outputs where required by the plan
- runtime, convergence, stability, sensitivity, and uncertainty evidence
- traceable canonical numbers with provenance
- figures that support specific claims and preserve reproducible sources

Exit: run `stage_gate.py --stage implementation`. Code failures, solver/model
mismatch, weak provenance, unvalidated results, or misleading visuals return to
`implementation`; formulation errors return to `modeling`.

## 4. Paper

Purpose: turn frozen evidence into a coherent contest paper and checked final
artifact.

Inputs: passed implementation artifacts, contest template, and citations.

Canonical outputs:

- `planning/paper_strategy.*` when an architecture choice is needed
- `paper/main.tex`, `paper/main.typ`, or `paper/main.md`
- compiled PDF for `contest_final`
- consistency, quality, citation, and delivery reports

Required content:

- problem-oriented argument structure rather than a universal template
- clear assumptions, notation, model derivation, algorithms, and validation
- numbers and claims that match the frozen result ledger
- readable tables and figures with precise captions and in-text interpretation
- exact citations for external methods, data, parameters, and factual claims
- limitations and applicability boundaries
- no internal workflow, agent, stage, or audit language in paper prose

Exit: run `stage_gate.py --stage paper`. `contest_final` additionally requires a
compiled PDF and a READY delivery manifest from the final build/audit batch.

## Cross-Stage Rule

Each stage gate evaluates all upstream contracts from current artifacts. A
later PASS cannot hide an earlier missing artifact, unresolved user decision,
or explicit internal diagnostic failure.
