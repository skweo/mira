# Mira 0.7.4

## Scope

Mira 0.7.4 adds prose-density control for contest-final papers.

## Problem Fixed

Mira 0.7 removed hard page and word quotas, but later drafting could still
spend time on paragraphs that only connected sections, praised the model, or
announced that something was reasonable. Those sentences consumed tokens and
made the final PDF look longer without improving model depth or judge-facing
evidence.

## Active Rule

Do not optimize for length. Optimize for paragraph work.

Each substantial paragraph should carry at least one of:

- number or result value;
- equation, variable, objective, constraint, or complexity expression;
- figure/table/citation reference;
- algorithm step, operator, runtime, or solver status;
- validation, sensitivity, baseline, convergence, residual, or feasibility evidence;
- named limitation and use boundary.

Delete or rewrite empty transitions, vague praise, generic model-evaluation
sentences, and any internal agent/workflow wording.

## Gate

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\prose_density_gate.py `
  --root <project-root> `
  --write-report checks\prose_density_report.md `
  --write-json checks\prose_density_report.json
```

Findings return to paper. `agent_prose_leak` is a FAIL. Filler/vague prose
and evidence-light paragraphs become WARN or FAIL according to density and
frequency, then enter the iteration loop like other contest-final quality
findings.
