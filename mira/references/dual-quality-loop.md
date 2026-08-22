# Dual Quality Loop

Use this reference whenever Mira is asked to improve itself, compare against other agents, write a `contest_final` paper, or revise a paper that feels too thin, too mechanical, or weaker than a previous version.

Mira must optimize two qualities together:

1. **Model depth**: the solution is mathematically correct, task-specific, reproducible, audited, and honestly worded.
2. **Contest-paper fullness**: the paper looks and reads like a strong mathematical modeling submission, with complete structure, derivations, figures, tables, validation, and a first-pages quality signal.

A paper fails the balanced-final standard if either axis is weak. Engineering correctness without contest-paper fullness is still a draft. Polished prose without audited model evidence is a paper tiger.

## Quality Axes

| Axis | Pass signal | Failure signal |
|---|---|---|
| Model depth | Variables, objective, constraints, solver route, task-specific adaptation, result provenance, baseline, constraint audit, and sensitivity/robustness evidence exist for each subquestion | Generic algorithm names, unsupported optimum claims, no baseline, no constraint audit, no saved result tables, or no explanation of why the method fits this task |
| Paper fullness | Abstract with per-question methods and numbers, table of contents, per-question sections, symbol table, figures/tables near claims, validation sections, and enough derivation density across the whole body | Short report feel, list-only writing, formulas only in the first half, long prose-only tail sections, figures dumped at the end, result tables missing, no visual first-pages signal, or 10-15 pages for a four-question advanced final |

Do not trade one axis for the other. If the user says an older Mira version had better prose or paper feel, treat that as a **balanced-quality regression**, not as a request to polish the current paper only.

## Balanced-Final Gate

Before presenting a paper as `contest_final`, create or update `checks/quality_balance_report.md`. The report must cover:

| Check | Required evidence |
|---|---|
| Model-depth readiness | Per-subquestion problem contract, task-specific adaptation, formulation, solver route, baseline/comparison, validation, and final deliverable |
| Result integrity | Key numbers trace to files, objective is recomputed, hard constraints are audited, stochastic runs record seeds/settings |
| Paper-fullness readiness | Page count or source-length estimate, section map, abstract/keywords/TOC status, and figure/table/citation counts |
| Balance judgment | Whether weakness is model-side, paper-side, or both; next stage to return to |

Recommended command when the portable script is available:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\check_quality_balance.py --root . --write-report checks\quality_balance_report.md
```

## Revision Routing

Use the quality-balance result to choose the next action:

| Finding | Return to |
|---|---|
| Missing variables, objective, constraints, or adaptation | modeling Modeling Plan |
| Unsupported number, no recomputation, no constraint audit | implementation Code or implementation Result Analysis |
| Weak baseline, no sensitivity, no seed/stability evidence | implementation Code or implementation Result Analysis |
| Figures/tables too sparse or disconnected from claims | implementation Figure Generation or paper Paper Writing |
| Paper has a short-report feel but artifacts are strong | paper Paper Writing with structural expansion |
| Long later sections have no formulas, quantitative rules, tables, or figures | modeling, 4, or 7 according to missing evidence |
| PDF layout, overflow, missing assets, broken captions | paper Compile and Compliance Check |

Do not fix model-side failures by adding prose. Do not fix paper-side failures by changing numbers. The revision must return to the earliest stage that owns the missing evidence.

## Contest-Paper Fullness Pattern

For a comparison-quality Chinese contest final, each substantial subquestion should read as a miniature paper:

1. State the task contract and dependency on earlier questions.
2. Explain the special mechanism that makes the chosen model non-generic.
3. Define variables, parameters, units, objective terms, and hard constraints.
4. Present the solver route or algorithm steps at the scale of the current data.
5. Place a compact result table and one supporting figure or diagram near the claim when useful.
6. Validate with constraint audit, baseline, sensitivity, seed stability, lower bound, residual, or limiting-case evidence.
7. Interpret the result in the original problem language.

If a subquestion has only a formula and a final number, it is underwritten. If it has only prose and no audited result table, it is unsupported.
If the first half has equations but the second half becomes long credibility,
implementation, contribution, or discussion prose, it is a derivation-density
regression. Use `scripts/derivation_density_audit.py` and return to the phase
that owns the missing mathematical or computed evidence.

## First-Pages Balance Test

The first pages should quickly show both qualities:

- The abstract names every subquestion, method route, and key numerical result.
- The keywords match the actual model families.
- The table of contents shows per-question modeling and validation structure.
- The problem analysis and assumptions are not generic; they foreshadow actual constraints and risks.
- A framework diagram is used only if it maps to real sections and artifacts.

If a reader cannot tell from the first pages what was solved, how it was solved, and why the paper is substantial, continue revising.

## Comparison Learning

When comparing Mira output with previous Mira, Claude, DeepSeek, or other agents:

1. Treat generated papers as `agent_output_sample`, not ground truth.
2. Extract candidate strengths into `materials/extracted/agent-output-comparison/` when doing a formal comparison.
3. Separate reusable patterns from one-off content:
   - reusable: section pacing, figure/table placement, validation style, and explanation depth;
   - not reusable: copied prose, fabricated citations, unsupported numbers, task-specific assumptions.
4. Promote only stable rules into Mira references after checking them against official judging signals, excellent papers, or successful reproduced runs.

The goal is not to make Mira more decorative. The goal is to make Mira produce papers whose visual fullness is backed by real mathematical and computational evidence.
