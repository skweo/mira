# Anti Paper Tiger Rules

Use these rules before problem analysis, modeling, code execution, result analysis, and final writing. A paper tiger is a contest paper that looks polished but has weak problem interpretation, loose assumptions, unaudited data, unsupported numbers, or unchecked constraints.

## Five Hard Gates

| Gate | Required artifact | Pass condition | Blocker sign |
|---|---|---|---|
| Problem contract | `planning/problem_analysis.md` | Each subquestion has input, output, hard constraints, objective/evaluation metric, data source, ambiguity, and dependency | The model starts before the task is translated into inputs, variables, constraints, objective, and outputs |
| Assumption risk | `planning/modeling_plan.md` | Each assumption states type, reason, affected subquestion, risk if false, and validation or sensitivity plan | Assumptions are generic praise, ignore explicit constraints, or silently change the official task |
| Data audit | `planning/attachment_mapping.json`, `planning/problem_analysis.md`, `data_clean/schema.md`, or `results/logs/data_audit.*` | Every attachment used by the model has a confirmed Qx/[SHARED] mapping, file/sheet inventory, fields, units, row/column scale, missing/abnormal values, cleaning rules, and model-entry table | A result depends on a dataset whose subquestion mapping, fields, units, or cleaning rules are unknown |
| Result reproducibility | `results/`, `results/frozen_numbers.json`, `checks/artifact_manifest.json` | Every key number, minimum value, ranking, route, parameter, or decision traces to code, result file, log, or documented external source | A paper number appears only in prose, console output, or generated text |
| Constraint audit | `results/audits/`, `results/logs/`, or result tables | Every reported optimum or feasible scheme has hard-constraint checks and objective recomputation | A "best" or "minimum" result lacks feasibility checks or cannot be recomputed |

## Problem Contract Rules

- Do not build the model before writing a subquestion contract.
- Separate background facts from tasks, hard constraints, objectives, and evaluation criteria.
- Record alternative interpretations when they change numerical results. Choose one only after a quick sanity check or an explicit documented assumption.
- Record task-specific mechanisms that can make a generic method wrong, such as
  transfer penalties, workflow stages, unsignalized intersections, coordinate
  offsets, detector geometry, interface conditions, fault timing, or local
  platform rules. A known algorithm is only admissible after these mechanisms are
  either modeled or deliberately excluded with risk noted.
- Treat historical problem-method mappings as routing hints only. A method is selected only after objective components, decision variables, hard constraints, data sources, and evaluation criteria are identified.
- For multi-question contests, record dependency direction. Do not let later questions use results that were never generated in the owning stage.
- In service-planning problems, explicitly separate forecast, allocation, and downstream facility/transport decisions. Record which upstream numbers feed later stages.
- In calibration, inverse, or parameter-identification problems, explicitly
  separate the forward problem from the inverse problem: first define the
  mechanism mapping from parameters to observations, then define how raw data
  identify the unknown parameters.

## Assumption Rules

Classify each important assumption:

| Type | Meaning | Required note |
|---|---|---|
| Simplification | Reduces complexity while preserving the official task | Why it is acceptable and what error it may introduce |
| Data | Handles missing, noisy, abnormal, or incomplete data | Which data fields and results it affects |
| Mechanism | Describes a real process, system, or behavior | What evidence, baseline, or limiting case supports it |
| Boundary | Defines model scope or applicability | Where the result should not be extrapolated |
| Risk | Could materially change the answer | Sensitivity, scenario, or fallback plan |

Never use an assumption to remove an explicit official requirement. If a requirement must be relaxed, mark the result as draft-only or infeasible under the original task.

## Data Audit Rules

- Inspect every provided attachment before modeling.
- Before inspecting full data or writing cleaning/modeling code, run
  `scripts/attachment_mapping_guard.py` and map each raw attachment to `Qx`,
  `[SHARED: ...]`, or explicitly unused. Do not assume `附件1 -> Q1` from file
  order.
- Record file type, sheet/table names, row/column scale, field meanings, units, missing values, duplicates, abnormal values, and cleaning decisions.
- Build a data-use ledger for data-rich problems: each used field, extracted
  video/image/survey feature, derived variable, ignored field, and cleaning rule
  should map to a model term, indicator, constraint, or validation check.
- Save cleaned or derived tables before optimization, fitting, evaluation, or plotting.
- If a unit conversion, distance/time matrix, cost matrix, or resource table is constructed, save the construction method and the generated table.
- For data-rich problems, record which fields or attachments are ignored and why. Watch for duplicated information, inconsistent totals, abnormal units, and fields that should not be counted twice.
- Before fitting or parameter identification, distinguish measured values,
  displayed values, cumulative values, interval changes, model-derived values,
  and legacy-calibration values. Do not fit against a field whose semantics do
  not match the model output.
- Record the stakeholder for each cost or preference. Do not optimize a cost for the organizer if the problem states that participants or customers pay it.
- If data are insufficient, record the blocker or assumption. Do not invent hidden data.

## Result And Constraint Rules

- Every key paper number must have provenance: source file, script, run log, table row, or formula derivation.
- Every optimum claim must include objective recomputation from primitive terms.
- Every feasible-scheme claim must include hard-constraint audit before the result enters the paper.
- Every requested final artifact must exist before writing the conclusion:
  route, schedule, assignment, ranking, parameter table, calibration/correction
  table, support spreadsheet, strategy rule, or policy recommendation as the
  problem requires.
- Every estimated parameter must state the fitted target, residual definition,
  data segment, parameter bounds, validation evidence, and sensitivity or
  identifiability check when the parameter affects a final decision.
- For stochastic or heuristic methods, record seed, parameters, stopping rule, baseline, and stability or repeated-run evidence.
- Use claim-strength wording: "best-found" or "current experimental solution" unless exact optimality is proved by solver certificate, bound, or derivation.
- Practical recommendations must cite the computed indicator, scenario,
  optimization result, or simulation evidence that supports them. Generic advice
  without model evidence is not contest-final quality.

## Contest-Final Rule

For `contest_final`, any missing hard gate above is a major issue. Do not deliver the paper as final until the blocker is fixed or explicitly reported in `checks/compliance_report.md`.
