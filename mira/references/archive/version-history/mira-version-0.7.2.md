# Mira 0.7.2

## Scope

Mira 0.7.2 makes final verification gates tiered instead of running every gate
for every paper.

## Problem Fixed

Older Mira final verification mixed four different purposes:

- core correctness checks;
- contest-final writing and evidence-density checks;
- high-award presentation checks;
- repair planning and automatic revision-loop checks.

This made final delivery slow, noisy, and sometimes circular. A paper could be
correctly modeled but still be sent into repair-loop gates that were meant only
after a reviewer finding. Conversely, findings from newly added reports did not
always enter the iteration queue.

## Gate Tiers

| Tier | When to use | Gate role |
|---|---|---|
| `core` | quick or reproducible draft | result confidence, ledger, paper consistency, evidence plan, control state, iteration queue |
| `contest` | `contest_final` | core plus solver efficiency, knowledge application, table/abstract/derivation/visual/paper-quality checks |
| `high_award` | explicit award target such as province-first/national-second comparison | contest plus flowchart, journal-figure, scenario-showcase, and award-review gates |
| `repair` | after paper-quality or visual-review findings | repair plan and paper revision-loop commands |
| `benchmark` | explicit known historical case | known-case regression only |

## Rules

- Do not run high-award gates merely because a paper is complete.
- Do not run repair-planning commands as part of default final verification.
- Route `high_award` only when the user, delivery brief, or comparison target
  asks for award-level output.
- Route all final findings through `iteration_loop.py`; the queue is still the
  authoritative return-to-phase mechanism.
- Keep benchmark regression separate from gate tiers; historical benchmarks are
  opt-in known-case checks.
