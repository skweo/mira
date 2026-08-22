# Figure Claim Ownership Rules

Use this rule before final paper writing and final verification when figures,
diagrams, or visual storyboards are part of the paper.

## Core Rule

Mira may draft:

- visual type and role;
- chart or diagram grammar;
- caption direction;
- a nearby claim draft.

For a main-paper visual, the final `core_claim` must be concrete and traceable
to model, code, or result evidence. It does not require a separate approval
marker.

## Required Artifact

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\figure_claim_ownership_gate.py --root <project-root> --output-level <output-level> --write-template planning\figure_claims_template.json --write-report checks\figure_claim_ownership_report.md --write-json checks\figure_claim_ownership_report.json
```

The script reads:

- `figures/figure_index.md`
- `diagrams/diagram_index.md`
- `planning/figure_storyboard.json`
- `planning/figure_claims.json`

It writes:

- `planning/figure_claims_template.json` as a fill-in draft;
- `checks/figure_claim_ownership_report.md`;
- `checks/figure_claim_ownership_report.json`.

## Claim Ledger

Resolved claims should be copied into `planning/figure_claims.json`:

```json
{
  "version": 1,
  "claims": [
    {
      "artifact": "figures/q1_result.pdf",
      "visual_type": "type3_paper",
      "paper_use": "main",
      "role": "result",
      "mira_claim_draft": "Mira's draft claim, if any",
      "core_claim": "Sentence this visual proves.",
      "source_artifact": "results/tables/q1_result.csv",
      "paper_section": "4.1 Results",
      "evidence_note": "Optional rationale or evidence boundary"
    }
  ]
}
```

## Classification

- `type1_diagnostic`: internal diagnostic visuals, usually not in the paper.
- `type2_comparison`: comparison visuals that may support method choice.
- `type3_paper`: main-paper claim visuals.
- supporting-only visuals: keep as separate result files or omit them.

For `contest_final`, every main-paper visual, including comparison visuals used
in the body, must have a concrete `core_claim`.

## Failure Conditions

Contest-final delivery fails when:

- a main-paper visual lacks a `planning/figure_claims.json` record;
- `core_claim` is empty or too short;

Warnings are issued when:

- the paper section is missing;
- the source artifact is missing;
- the claim has no traceable source artifact.

Diagnostic and external supporting visuals do not block delivery unless they
carry a main conclusion in the body.
