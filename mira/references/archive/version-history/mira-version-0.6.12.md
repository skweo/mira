# Mira 0.6.12

Mira 0.6.12 adds reproducible parallel-coordinate, Pareto-front, and
Gantt/timeline figures.

## New Standard

- Route `references/parallel-pareto-gantt-visualization-rules.md` when a figure,
  paper section, result analysis, or revision mentions parallel coordinates,
  multi-indicator scheme screening, Pareto front, multi-objective tradeoff,
  Gantt chart, implementation schedule, project timeline, or execution plan.
- Use `scripts/plot_parallel_pareto_gantt.py` with `--kind parallel`,
  `--kind pareto`, or `--kind gantt`.
- Save PNG/PDF figures, cleaned plot data, summary table, parameters, and a
  caption/caveat index.
- Treat these figures as decision and implementation evidence: parallel
  coordinates screen schemes, Pareto plots explain tradeoffs, and Gantt charts
  express executable workflow.

## Non-goals

- Do not use parallel coordinates without normalization/direction discipline.
- Do not call a weighted best score a Pareto result unless nondominance is
  actually computed.
- Do not use Gantt charts as solver evidence; they are execution-plan visuals.
- Do not weaken the 0.6.1-0.6.11 layout, derivation, control-plane, and visual
  reproducibility rules.
