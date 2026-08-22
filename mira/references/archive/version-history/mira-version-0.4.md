# Mira 0.4 Standard

Mira 0.4 is the active Mira baseline as of 2026-06-28. It promotes the former
candidate gate set to the standard delivery contract for high-award Chinese
mathematical modeling contest-paper work.

## Upgrade Target

Mira 0.4 targets papers that can compete for strong provincial/national awards
when the underlying model, data, and available compute are sufficient. The
system must optimize both:

| Axis | Requirement |
|---|---|
| Model strength | correct formulation, appropriate algorithms, reproducible results, baselines, bounds/sensitivity, honest solver lineage |
| Paper strength | official-style template, strong visual evidence, real references, complete section development, polished appendix, readable figures |

## Gate Set

The standard includes:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\check_presentation_strength.py --root . --write-report checks\presentation_strength_report.md
```

This gate checks official front matter, figure density, figure-index evidence,
citation/reference support, short sections, appendix polish, and audit-report
language leaking into the paper.

It also tightens warning handling: for `contest_final`, unresolved WARN findings
from result-quality, semantic, model-solver, control-plane, quality-balance,
presentation, or decision-gate reports block final delivery through the
iteration loop unless explicitly waived and disclosed.

## High-Award Defaults

- Historical 0.4 default, superseded by Mira 0.7: four-question contest-final papers used page-count floors and page-count targets. Current Mira must not use page or word counts as quotas; use evidence-density checks instead.
- Useful figures: at least 6 for a four-question final; prefer 8-12 when supported by data/results.
- References: fewer than 8 real used references is blocking for multi-method high-award comparison; 12-18 is a stronger target.
- Short sections: multiple core sections below the threshold block final delivery.
- Appendix: include polished Chinese tables plus code/module map or reproducibility commands.

## Non-Negotiable Boundary

Presentation strength must not weaken honesty. If Kaiwu SDK, a solver, or a
quantum backend was not actually executed, the paper must disclose that and
attribute numerical results to the real executed solver.

## Historical Note

Mira 0.36 was the final pre-0.4 repair label. The MathorCup 2026 A redo paper
remains a Mira 0.3 benchmark artifact and still fails the Mira 0.4 high-award
gate; that failure is evidence that the new gate blocks weak presentation,
numeric, and control-plane warnings by default, not evidence that the active
standard should stay in candidate status.
