#!/usr/bin/env python3
"""Evaluate numeric result quality for a Mira contest-paper project.

This gate computes quality signals from result artifacts: component ratios,
baseline improvement, convergence history, multi-run stability, and
recommendation sensitivity. It complements semantic_audit.py, which checks
whether the paper and result report argue the evidence honestly.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from workflow_stages import normalize_stage_path
except ModuleNotFoundError:
    # runpy/importlib callers do not always add this script's directory to sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from workflow_stages import normalize_stage_path


PENALTY_WARN_RATIO = 100.0
PENALTY_FAIL_RATIO = 1000.0
PENALTY_SEVERE_RATIO = 10000.0
OBJECTIVE_TRAVEL_WARN_RATIO = 10000.0
BASELINE_REGRESSION_WARN = 1.02
BASELINE_REGRESSION_FAIL = 1.10
WEAK_IMPROVEMENT_MARGIN = 0.05
TAIL_WARN_IMPROVEMENT = 0.005
TAIL_FAIL_IMPROVEMENT = 0.02
MULTIRUN_WARN_SPREAD = 0.25
MULTIRUN_FAIL_SPREAD = 1.00
PERTURBATIONS = [
    (0.5, "0.50x"),
    (0.75, "0.75x"),
    (0.9, "0.90x"),
    (1.0, "1.00x"),
    (1.1, "1.10x"),
    (1.25, "1.25x"),
    (1.5, "1.50x"),
]


@dataclass
class Finding:
    level: str
    axis: str
    phase: str
    message: str


class ResultQuality:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.frozen_path = self._resolve(args.frozen) if args.frozen else self.root / "results" / "frozen_numbers.json"
        self.tables_dir = self.root / "results" / "tables"
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}
        self.frozen: dict[str, Any] = {}
        self.tables: dict[str, list[dict[str, str]]] = {}
        self.output_level = self._detect_output_level()

    def run(self) -> int:
        self._load()
        if self.frozen:
            self._check_component_ratios()
            self._check_baselines()
            self._check_histories()
            self._check_vehicle_fixed_cost_sensitivity()
            self._check_parameter_criticality()
        self._finalize_policy_metrics()
        self._write_outputs()
        self._emit()
        return 1 if self._blocks_delivery() else 0

    def _load(self) -> None:
        if not self.frozen_path.exists():
            self.fail("result_quality", "implementation", f"missing frozen numbers: {self.rel(self.frozen_path)}")
            return
        try:
            self.frozen = json.loads(self.read_text(self.frozen_path))
        except json.JSONDecodeError as exc:
            self.fail("result_quality", "implementation", f"cannot parse frozen numbers: {exc}")
            return

        if self.tables_dir.exists():
            for path in sorted(self.tables_dir.glob("*.csv")):
                with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as fh:
                    reader = csv.DictReader(fh)
                    self.tables[path.name] = [_normalize_row(row) for row in reader]

        self.metrics["tables_loaded"] = sorted(self.tables)
        self.metrics["frozen_cases"] = sorted(key.upper() for key in self.frozen if _is_qid(key))

    def _check_component_ratios(self) -> None:
        ratio_metrics: dict[str, dict[str, Any]] = {}
        for qid, data in sorted(self.frozen.items()):
            if not _is_qid(qid) or not isinstance(data, dict):
                continue
            qlabel = qid.upper()
            travel = _num(data.get("travel"))
            penalty = _num(data.get("penalty"))
            objective = _num(data.get("objective"))
            if travel is None or abs(travel) < 1e-12:
                continue

            exact_evidence = bool(data.get("exact_or_certified")) or self._has_exact_baseline_evidence(qlabel, objective)
            ratio_record: dict[str, Any] = {"travel": travel, "exact_or_certified_evidence": exact_evidence}

            if penalty is not None:
                ratio = penalty / max(abs(travel), 1.0)
                structural = self._structural_penalty_evidence(data, penalty)
                scale_certification = self._penalty_scale_certification(
                    qlabel,
                    data,
                    travel,
                    penalty,
                    objective,
                    exact_evidence,
                    structural,
                )
                scale_certified = bool(scale_certification.get("valid"))
                ratio_record["penalty"] = penalty
                ratio_record["penalty_travel_ratio"] = ratio
                ratio_record["scale_certification"] = scale_certification
                if structural:
                    ratio_record.update(structural)
                if ratio > PENALTY_SEVERE_RATIO:
                    message = (
                        f"{qlabel} penalty/travel ratio is {ratio:.1f} ({penalty:g}/{travel:g}); "
                        "this is a severe scale-dominating result"
                    )
                    if scale_certified:
                        self.info(
                            "result_quality",
                            "implementation",
                            message + f"; structured scale certification passed ({scale_certification['basis']}, {scale_certification['claim_scope']})",
                        )
                    elif exact_evidence:
                        self.warn("result_quality", "implementation", message + " but exact/certified evidence exists, so the paper must separate travel from penalty scale")
                    elif structural.get("supports_scale") if structural else False:
                        self.warn(
                            "result_quality",
                            "implementation",
                            message
                            + f" but structural lower-bound evidence explains the scale (gap {structural['gap_ratio'] * 100:.1f}%); disclose this as time-window pressure, not solver optimality",
                        )
                    else:
                        self.fail(
                            "result_quality",
                            "implementation",
                            message + "; repair the model or add exact/certified or close structural-bound evidence",
                        )
                elif ratio > PENALTY_FAIL_RATIO:
                    message = (
                        f"{qlabel} penalty/travel ratio is {ratio:.1f} ({penalty:g}/{travel:g}); "
                        "objective scale is dominated by penalties"
                    )
                    if scale_certified:
                        self.info(
                            "result_quality",
                            "implementation",
                            message + f"; structured scale certification passed ({scale_certification['basis']}, {scale_certification['claim_scope']})",
                        )
                    elif exact_evidence:
                        self.warn("result_quality", "implementation", message + " but exact/certified baseline evidence exists, so explain the scale before freezing")
                    elif structural.get("supports_scale") if structural else False:
                        self.warn(
                            "result_quality",
                            "implementation",
                            message + f" but structural lower-bound evidence supports it (gap {structural['gap_ratio'] * 100:.1f}%)",
                        )
                    else:
                        self.fail("result_quality", "implementation", message + "; add baseline/bound/sensitivity evidence or repair the model")
                elif ratio > PENALTY_WARN_RATIO and scale_certified:
                    self.info(
                        "result_quality",
                        "implementation",
                        f"{qlabel} penalty/travel ratio is {ratio:.1f}; structured scale certification passed",
                    )
                elif ratio > PENALTY_WARN_RATIO:
                    self.warn(
                        "result_quality",
                        "implementation",
                        f"{qlabel} penalty/travel ratio is {ratio:.1f}; explain why the penalty scale is acceptable",
                    )

            if objective is not None:
                objective_ratio = objective / max(abs(travel), 1.0)
                ratio_record["objective"] = objective
                ratio_record["objective_travel_ratio"] = objective_ratio
                if objective_ratio > OBJECTIVE_TRAVEL_WARN_RATIO and penalty is not None and scale_certified:
                    self.info(
                        "result_quality",
                        "implementation",
                        f"{qlabel} objective/travel ratio is {objective_ratio:.1f}; the certified component audit and paper disclosure separate travel from penalty scale",
                    )
                elif objective_ratio > OBJECTIVE_TRAVEL_WARN_RATIO:
                    self.warn(
                        "result_quality",
                        "implementation",
                        f"{qlabel} objective/travel ratio is {objective_ratio:.1f}; paper-ready interpretation must separate physical travel cost from penalty/weight terms",
                    )

            ratio_metrics[qlabel] = ratio_record
        self.metrics["component_ratios"] = ratio_metrics

    def _check_baselines(self) -> None:
        rows = self.tables.get("baseline_comparison.csv", [])
        if not rows:
            self.warn("baseline_quality", "implementation", "missing results/tables/baseline_comparison.csv; final result quality cannot be judged against alternatives")
            self.metrics["baseline_comparison"] = {"available": False}
            return

        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            case = (row.get("case") or row.get("qid") or row.get("question") or "").strip().upper()
            if case:
                grouped.setdefault(case, []).append(row)

        baseline_metrics: dict[str, Any] = {}
        for qid, data in sorted(self.frozen.items()):
            if not _is_qid(qid) or not isinstance(data, dict):
                continue
            qlabel = qid.upper()
            case_rows = grouped.get(qlabel, [])
            final_value, metric_name = self._case_objective(qlabel, data, case_rows)
            if final_value is None:
                continue
            if not case_rows:
                self.warn("baseline_quality", "implementation", f"{qlabel} has no comparable baseline row")
                baseline_metrics[qlabel] = {"available": False, "final_metric": metric_name, "final_value": final_value}
                continue

            comparable: list[tuple[str, float]] = []
            for row in case_rows:
                value = _row_metric_value(row, metric_name)
                method = row.get("method") or row.get("algorithm") or row.get("model") or "unknown"
                if value is not None:
                    comparable.append((method, value))
            if not comparable:
                self.warn("baseline_quality", "implementation", f"{qlabel} baseline rows exist but contain no numeric objective column")
                continue

            comparable.sort(key=lambda item: item[1])
            best_method, best_value = comparable[0]
            ratio_to_best = final_value / max(best_value, 1e-12)
            matched_method = _closest_method(comparable, final_value)
            second_value = _second_distinct_value(comparable, final_value)
            improvement_margin = None
            if second_value is not None and final_value <= best_value * BASELINE_REGRESSION_WARN:
                improvement_margin = second_value / max(final_value, 1e-12) - 1.0

            baseline_metrics[qlabel] = {
                "available": True,
                "final_metric": metric_name,
                "final_value": final_value,
                "best_method": best_method,
                "best_value": best_value,
                "matched_method": matched_method,
                "ratio_to_best": ratio_to_best,
                "improvement_margin_to_next": improvement_margin,
                "candidate_count": len(comparable),
            }

            if ratio_to_best >= BASELINE_REGRESSION_FAIL:
                self.fail(
                    "baseline_quality",
                    "implementation",
                    f"{qlabel} frozen {metric_name}={final_value:g} is {ratio_to_best:.2f}x worse than baseline `{best_method}`={best_value:g}",
                )
            elif ratio_to_best >= BASELINE_REGRESSION_WARN:
                self.warn(
                    "baseline_quality",
                    "implementation",
                    f"{qlabel} frozen {metric_name}={final_value:g} is {ratio_to_best:.2f}x worse than best baseline `{best_method}`={best_value:g}",
                )
            elif improvement_margin is not None and improvement_margin < WEAK_IMPROVEMENT_MARGIN and not self._has_exact_baseline_evidence(qlabel, final_value):
                self.warn(
                    "baseline_quality",
                    "implementation",
                    f"{qlabel} improves over the next comparable method by only {improvement_margin * 100:.1f}%; claim strength should be modest or more validation is needed",
                )

        self.metrics["baseline_comparison"] = baseline_metrics

    def _check_histories(self) -> None:
        history_tables = {name: rows for name, rows in self.tables.items() if "history" in name.lower()}
        self.metrics["history_tables"] = sorted(history_tables)
        if not history_tables:
            return

        history_metrics: dict[str, Any] = {}
        for name, rows in history_tables.items():
            best_col = _first_existing_column(rows, ["best_objective", "best", "best_cost", "objective_best", "min_objective", "objective"])
            current_col = _first_existing_column(rows, ["current_objective", "objective", "current_cost", "cost"])
            if not best_col:
                self.warn("convergence_quality", "implementation", f"{name} has no recognizable best-objective column")
                continue

            groups = _history_groups(rows)
            group_metrics: dict[str, Any] = {}
            final_bests_by_context: dict[str, list[float]] = {}
            tail_warnings: list[tuple[str, float]] = []
            tail_failures: list[tuple[str, float]] = []
            increase_warnings: list[tuple[str, int]] = []
            current_gap_warnings: list[tuple[str, float, float]] = []
            for group_id, group_rows in sorted(groups.items(), key=lambda item: _sort_key(item[0])):
                ordered = _sort_rows(group_rows, "iteration")
                values = [_num(row.get(best_col)) for row in ordered]
                best_values = [value for value in values if value is not None]
                if len(best_values) < 5:
                    group_metrics[str(group_id)] = {"rows": len(best_values), "status": "too_sparse"}
                    continue
                tail_index = max(0, min(len(best_values) - 1, int(math.floor(len(best_values) * 0.8))))
                initial = best_values[0]
                tail_start = best_values[tail_index]
                final = best_values[-1]
                overall_improvement = _relative_decrease(initial, final)
                tail_improvement = _relative_decrease(tail_start, final)
                increases = _count_best_increases(best_values)
                group_metrics[str(group_id)] = {
                    "rows": len(best_values),
                    "initial_best": initial,
                    "tail_start_best": tail_start,
                    "final_best": final,
                    "overall_improvement": overall_improvement,
                    "tail_improvement": tail_improvement,
                    "best_increases": increases,
                }
                final_bests_by_context.setdefault(_stability_context(group_id), []).append(final)

                qlabel = _qid_from_name(name)
                prefix = f"{qlabel} " if qlabel else ""
                if increases:
                    increase_warnings.append((str(group_id), increases))
                if tail_improvement > TAIL_FAIL_IMPROVEMENT:
                    tail_failures.append((str(group_id), tail_improvement))
                elif tail_improvement > TAIL_WARN_IMPROVEMENT:
                    tail_warnings.append((str(group_id), tail_improvement))

                if current_col:
                    final_current = _num(ordered[-1].get(current_col))
                    if final_current is not None and final_current > final * 1.5:
                        current_gap_warnings.append((str(group_id), final_current, final))

            qlabel = _qid_from_name(name)
            prefix = f"{qlabel} " if qlabel else ""
            if increase_warnings:
                worst = sorted(increase_warnings, key=lambda item: item[1], reverse=True)[:3]
                self.warn(
                    "convergence_quality",
                    "implementation",
                    f"{prefix}{name} has {len(increase_warnings)} trace(s) where best objective increases; check history logging or objective recomputation. Worst: {_format_pairs(worst, suffix=' increases')}",
                )
            if tail_failures:
                worst = sorted(tail_failures, key=lambda item: item[1], reverse=True)[:3]
                self.warn(
                    "convergence_quality",
                    "implementation",
                    f"{prefix}{name} has {len(tail_failures)} trace(s) still improving more than {TAIL_FAIL_IMPROVEMENT * 100:.1f}% in the last 20% of iterations; convergence evidence is weak. Worst: {_format_percent_pairs(worst)}",
                )
            if tail_warnings:
                worst = sorted(tail_warnings, key=lambda item: item[1], reverse=True)[:3]
                self.warn(
                    "convergence_quality",
                    "implementation",
                    f"{prefix}{name} has {len(tail_warnings)} trace(s) with tail improvement above {TAIL_WARN_IMPROVEMENT * 100:.1f}%; add longer run or stopping-rule evidence. Worst: {_format_percent_pairs(worst)}",
                )
            if current_gap_warnings:
                worst = sorted(current_gap_warnings, key=lambda item: item[1] / max(item[2], 1e-12), reverse=True)[:3]
                details = ", ".join(f"{gid}: current/best={current / max(best, 1e-12):.2f}" for gid, current, best in worst)
                self.warn(
                    "convergence_quality",
                    "implementation",
                    f"{prefix}{name} has {len(current_gap_warnings)} trace(s) whose final current objective is far above the best objective; preserve best solution and explain stochastic traces. Worst: {details}",
                )

            stability_metrics = {}
            comparable_stability_contexts = _comparable_stability_contexts(groups)
            selected_vehicle_count = None
            if qlabel == "Q4" and isinstance(self.frozen.get("q4"), dict):
                selected_vehicle_count = _num(self.frozen["q4"].get("vehicle_count"))
            for context, final_bests in sorted(final_bests_by_context.items()):
                if context not in comparable_stability_contexts:
                    continue
                if len(final_bests) < 3:
                    continue
                best = min(final_bests)
                worst = max(final_bests)
                median = statistics.median(final_bests)
                spread = (worst - best) / max(abs(best), 1e-12)
                stability_metrics[context] = {
                    "runs": len(final_bests),
                    "best_final": best,
                    "median_final": median,
                    "worst_final": worst,
                    "spread_ratio": spread,
                }
                qlabel = _qid_from_name(name)
                prefix = f"{qlabel} " if qlabel else ""
                context_text = "" if context == "all" else f" ({context})"
                if spread > MULTIRUN_FAIL_SPREAD:
                    message = f"{prefix}{name}{context_text} final best values vary by {spread:.2f}x across comparable runs; selected heuristic result is unstable without stronger tuning/decomposition"
                    if qlabel == "Q4" and selected_vehicle_count is not None and not _context_matches_selected_vehicle(context, selected_vehicle_count):
                        self.warn("stability_quality", "implementation", message + " for a non-selected vehicle-count scenario")
                    else:
                        self.fail("stability_quality", "implementation", message)
                elif spread > MULTIRUN_WARN_SPREAD:
                    self.warn(
                        "stability_quality",
                        "implementation",
                        f"{prefix}{name}{context_text} final best values vary by {spread:.2f}x across comparable runs; report multi-seed stability or tune operators",
                    )
            if stability_metrics:
                group_metrics["multi_run_stability"] = stability_metrics

            history_metrics[name] = group_metrics
        self.metrics["convergence"] = history_metrics

    def _check_vehicle_fixed_cost_sensitivity(self) -> None:
        settings = self.frozen.get("settings", {}) if isinstance(self.frozen.get("settings"), dict) else {}
        fixed_cost = _num(settings.get("vehicle_fixed_cost"))
        q4 = self.frozen.get("q4") if isinstance(self.frozen.get("q4"), dict) else {}
        selected_k = _num(q4.get("vehicle_count")) if isinstance(q4, dict) else None
        rows = self._vehicle_sensitivity_rows()

        if selected_k is None and not rows:
            return
        if fixed_cost is None:
            fixed_cost = _infer_fixed_cost(rows)
        if fixed_cost is None:
            self.warn("recommendation_sensitivity", "implementation", "vehicle-count recommendation exists but vehicle_fixed_cost cannot be found or inferred")
            return
        if not rows:
            self.warn("recommendation_sensitivity", "implementation", "vehicle_fixed_cost affects vehicle-count recommendation but no q4_sensitivity table was found")
            return

        options = []
        for row in rows:
            k = _num(row.get("vehicle_count") or row.get("k") or row.get("vehicles"))
            route_cost = _num(row.get("routing_objective")) or _sum_numbers(row, ["travel", "penalty"]) or _num(row.get("objective"))
            if k is None or route_cost is None:
                continue
            options.append({"vehicle_count": k, "route_cost": route_cost})
        options = _dedupe_options(options)
        if len(options) < 3:
            self.warn("recommendation_sensitivity", "implementation", "vehicle-count sensitivity has fewer than three comparable K scenarios")
        if selected_k is None:
            best = _best_vehicle_option(options, fixed_cost)
            if best:
                selected_k = best["vehicle_count"]

        selected = next((item for item in options if _same_number(item["vehicle_count"], selected_k)), None)
        if not selected:
            self.fail("recommendation_sensitivity", "implementation", f"selected vehicle_count={selected_k:g} is missing from sensitivity rows")
            return

        current_best = _best_vehicle_option(options, fixed_cost)
        perturbation_winners = {}
        for factor, label in PERTURBATIONS:
            winner = _best_vehicle_option(options, fixed_cost * factor)
            if winner:
                perturbation_winners[label] = winner["vehicle_count"]
        breakpoints = _vehicle_breakpoints(options, selected, fixed_cost)
        nearest = breakpoints[0] if breakpoints else None
        metric = {
            "fixed_cost": fixed_cost,
            "selected_vehicle_count": selected_k,
            "current_best_vehicle_count": current_best["vehicle_count"] if current_best else None,
            "perturbation_winners": perturbation_winners,
            "nearest_breakpoint": nearest,
            "options": options,
        }
        self.metrics["vehicle_fixed_cost_sensitivity"] = metric

        if current_best and not _same_number(current_best["vehicle_count"], selected_k):
            selected_value = selected["route_cost"] + selected["vehicle_count"] * fixed_cost
            best_value = current_best["route_cost"] + current_best["vehicle_count"] * fixed_cost
            self.fail(
                "recommendation_sensitivity",
                "implementation",
                f"selected K={selected_k:g} is not optimal at M_fixed={fixed_cost:g}; selected combined={selected_value:g}, best K={current_best['vehicle_count']:g} combined={best_value:g}",
            )

        changed_10 = _winner_changes(perturbation_winners, selected_k, ["0.90x", "1.10x"])
        changed_25 = _winner_changes(perturbation_winners, selected_k, ["0.75x", "1.25x"])
        changed_50 = _winner_changes(perturbation_winners, selected_k, ["0.50x", "1.50x"])
        if changed_10:
            self.fail(
                "recommendation_sensitivity",
                "modeling",
                f"vehicle-count recommendation K={selected_k:g} changes under +/-10% fixed-cost perturbation; recommendation is too fragile",
            )
        elif changed_25:
            self.warn(
                "recommendation_sensitivity",
                "implementation",
                f"vehicle-count recommendation K={selected_k:g} changes under +/-25% fixed-cost perturbation; state scenario-specific recommendation",
            )
        elif changed_50:
            self.warn(
                "recommendation_sensitivity",
                "implementation",
                f"vehicle-count recommendation K={selected_k:g} changes under +/-50% fixed-cost perturbation; state valid cost interval",
            )
        elif nearest:
            rel_margin = nearest["relative_margin"]
            self.info(
                "recommendation_sensitivity",
                "implementation",
                f"vehicle-count K={selected_k:g} is stable for tested +/-50% fixed-cost perturbations; nearest switch is K={nearest['alternative_vehicle_count']:g} at M_fixed={nearest['breakpoint']:.6g} (relative margin {rel_margin * 100:.1f}%)",
            )

        if nearest:
            rel_margin = nearest["relative_margin"]
            if rel_margin <= 0.10:
                self.fail(
                    "recommendation_sensitivity",
                    "modeling",
                    f"nearest K-switch breakpoint is only {rel_margin * 100:.1f}% away from M_fixed={fixed_cost:g}; recommendation needs redesign or scenario split",
                )
            elif rel_margin <= 0.25:
                self.warn(
                    "recommendation_sensitivity",
                    "implementation",
                    f"nearest K-switch breakpoint is {rel_margin * 100:.1f}% away from M_fixed={fixed_cost:g}; disclose sensitivity interval",
                )

    def _check_parameter_criticality(self) -> None:
        settings = self.frozen.get("settings", {}) if isinstance(self.frozen.get("settings"), dict) else {}
        if not settings:
            return
        sensitivity_names = " ".join(name.lower() for name in self.tables)
        has_penalty_sensitivity = any(term in sensitivity_names for term in ["alpha", "penalty", "weight"])
        component_ratios = self.metrics.get("component_ratios", {})
        dominant_penalty_cases = [
            qid
            for qid, record in component_ratios.items()
            if isinstance(record, dict) and _num(record.get("penalty_travel_ratio")) and _num(record.get("penalty_travel_ratio")) > PENALTY_WARN_RATIO
        ]
        for key in ("alpha_early", "alpha_late"):
            if key in settings and dominant_penalty_cases and not has_penalty_sensitivity:
                self.warn(
                    "parameter_criticality",
                    "implementation",
                    f"`{key}` affects dominant penalty cases {', '.join(dominant_penalty_cases)} but no penalty-weight sensitivity table was found",
                )
        if "vehicle_fixed_cost" in settings and "vehicle_fixed_cost_sensitivity" not in self.metrics:
            if isinstance(self.frozen.get("q4"), dict) and "vehicle_count" in self.frozen["q4"]:
                self.warn(
                    "parameter_criticality",
                    "implementation",
                    "`vehicle_fixed_cost` affects Q4 vehicle-count recommendation but no usable fixed-cost sensitivity result was found",
                )

    def _vehicle_sensitivity_rows(self) -> list[dict[str, str]]:
        for name in ("q4_sensitivity.csv", "vehicle_sensitivity.csv", "sensitivity.csv"):
            rows = self.tables.get(name)
            if rows and any("vehicle_count" in row or "k" in row for row in rows):
                return rows
        for name, rows in self.tables.items():
            if "sensitivity" in name.lower() and any("vehicle_count" in row or "k" in row for row in rows):
                return rows
        frozen_rows = self.frozen.get("q4_sensitivity")
        if isinstance(frozen_rows, list):
            return [{str(k): "" if v is None else str(v) for k, v in row.items()} for row in frozen_rows if isinstance(row, dict)]
        return []

    def _case_objective(self, qlabel: str, data: dict[str, Any], case_rows: list[dict[str, str]]) -> tuple[float | None, str]:
        objective = _num(data.get("objective"))
        routing = _num(data.get("routing_objective"))
        combined = _num(data.get("combined_objective"))
        if qlabel == "Q4" and routing is not None:
            row_values = [_num(row.get("objective")) for row in case_rows]
            if any(value is not None and _same_number(value, routing) for value in row_values):
                return routing, "routing_objective"
        if objective is not None:
            return objective, "objective"
        if routing is not None:
            return routing, "routing_objective"
        if combined is not None:
            return combined, "combined_objective"
        travel = _num(data.get("travel"))
        return travel, "travel"

    def _has_exact_baseline_evidence(self, qlabel: str, final_value: float | None) -> bool:
        if final_value is None:
            return False
        rows = self.tables.get("baseline_comparison.csv", [])
        exact_terms = ["exact", "held", "dp", "dynamic", "milp", "integer", "certificate", "gap", "label"]
        for row in rows:
            case = (row.get("case") or row.get("qid") or "").strip().upper()
            if case != qlabel:
                continue
            value = _num(row.get("objective")) or _num(row.get("total_objective")) or _num(row.get("routing_objective"))
            method = (row.get("method") or row.get("algorithm") or "").lower()
            if value is not None and _same_number(value, final_value) and any(term in method for term in exact_terms):
                return True
        return False

    def _structural_penalty_evidence(self, data: dict[str, Any], penalty: float) -> dict[str, Any]:
        bound = _num(data.get("structural_penalty_lower_bound"))
        if bound is None:
            bound = _num(data.get("penalty_pressure_lower_bound"))
        if bound is None or bound <= 0:
            return {}
        gap = (penalty - bound) / max(abs(bound), 1e-12)
        return {
            "structural_penalty_lower_bound": bound,
            "gap_ratio": gap,
            "supports_scale": gap >= -1e-6 and gap <= 0.25,
        }

    def _penalty_scale_certification(
        self,
        qlabel: str,
        data: dict[str, Any],
        travel: float,
        penalty: float,
        objective: float | None,
        exact_evidence: bool,
        structural: dict[str, Any],
    ) -> dict[str, Any]:
        cert = data.get("penalty_scale_certification")
        result: dict[str, Any] = {"status": "MISSING", "valid": False, "errors": []}
        errors: list[str] = result["errors"]
        if not isinstance(cert, dict):
            errors.append("missing penalty_scale_certification object")
            return result

        result["status"] = str(cert.get("status") or "").upper()
        result["basis"] = str(cert.get("basis") or "")
        result["claim_scope"] = str(cert.get("claim_scope") or "")
        if result["status"] != "CERTIFIED":
            errors.append("status must be CERTIFIED")

        basis = result["basis"]
        scope = result["claim_scope"].lower().replace("-", "_")
        if basis not in {"exact_solution", "structural_lower_bound"}:
            errors.append("basis must be exact_solution or structural_lower_bound")
        if basis == "exact_solution" and (not exact_evidence or scope not in {"exact", "global_exact"}):
            errors.append("exact_solution requires exact evidence and exact claim scope")
        if basis == "structural_lower_bound":
            if not structural.get("supports_scale"):
                errors.append("structural lower bound does not support the reported scale")
            if scope not in {"best_found", "bounded", "local"}:
                errors.append("structural lower bound must use a limited claim scope")

        components = cert.get("component_check")
        if not isinstance(components, dict):
            errors.append("missing component_check")
        else:
            tolerance = _num(components.get("tolerance")) or 1e-6
            for name, expected in (("travel", travel), ("penalty", penalty), ("objective", objective)):
                if expected is not None and not _same_number(components.get(name), expected, rel=tolerance, abs_tol=tolerance):
                    errors.append(f"component_check.{name} does not match frozen result")
            if objective is not None and not _same_number(travel + penalty, objective, rel=tolerance, abs_tol=tolerance):
                errors.append("frozen objective is not travel + penalty")

        evidence = cert.get("evidence")
        checked_evidence: list[str] = []
        if not isinstance(evidence, list) or not evidence:
            errors.append("at least one evidence path is required")
        else:
            for value in evidence:
                rel = str(value or "").strip()
                path = self._resolve(rel)
                if not rel or not path.is_file() or path.stat().st_size == 0:
                    errors.append(f"missing or empty evidence: {rel or '<empty>'}")
                else:
                    checked_evidence.append(self.rel(path))
        result["evidence"] = checked_evidence

        if basis == "exact_solution":
            certificate = data.get("certificate")
            certificate_path = self._resolve(str(certificate.get("path") or "")) if isinstance(certificate, dict) else None
            certified_objective = certificate.get("certified_objective") if isinstance(certificate, dict) else None
            if certificate_path is None or not certificate_path.is_file():
                errors.append("exact certificate path is missing")
            if objective is None or not _same_number(certified_objective, objective):
                errors.append("exact certificate objective does not match frozen objective")
        elif basis == "structural_lower_bound":
            source = str(cert.get("structural_bound_source") or "").strip()
            source_path = self._resolve(source)
            if not source or not source_path.is_file() or self.rel(source_path) not in checked_evidence:
                errors.append("structural_bound_source must be an existing listed evidence file")

        anchor = str(cert.get("paper_anchor") or "").strip()
        result["paper_anchor"] = anchor
        paper_path = self.root / "paper" / "main.tex"
        if not anchor or not paper_path.is_file():
            errors.append("paper_anchor or paper/main.tex is missing")
        else:
            paper = self.read_text(paper_path)
            token = f"\\label{{{anchor}}}"
            position = paper.find(token)
            if position < 0:
                errors.append(f"paper anchor not found: {anchor}")
            else:
                window = paper[max(0, position - 1800) : min(len(paper), position + 2200)]
                for name, value in (("travel", travel), ("penalty", penalty), ("objective", objective)):
                    if value is not None and not _text_contains_number(window, value):
                        errors.append(f"paper disclosure near {anchor} omits {name}={value:g}")
                lower = window.lower()
                if basis == "exact_solution" and "exact" not in lower and "\u7cbe\u786e" not in window:
                    errors.append("paper disclosure does not state exact scope")
                if basis == "structural_lower_bound" and "best-found" not in lower and "best found" not in lower:
                    errors.append("paper disclosure does not state best-found scope")

        result["valid"] = not errors
        result["status"] = "CERTIFIED" if result["valid"] else "INVALID"
        return result

    def _write_outputs(self) -> None:
        if self.args.write_report:
            path = self._resolve(self.args.write_report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._markdown(), encoding="utf-8")
        if self.args.write_json:
            path = self._resolve(self.args.write_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._json_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _markdown(self) -> str:
        lines = [
            "# Mira Result Quality Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{self._verdict()}**",
            f"- Frozen numbers: `{self.rel(self.frozen_path)}`",
            f"- Output level: `{self.output_level}`",
            f"- Warning policy: `{self._warning_policy_label()}`",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        for key, value in self.metrics.items():
            lines.append(f"| {key} | {_render_metric(value)} |")
        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        for item in self.findings:
            lines.append(f"| {item.level} | {item.axis} | {item.phase} | {_escape_table(item.message)} |")
        if not self.findings:
            lines.append("| INFO | result_quality | - | no numeric quality findings |")
        lines.extend(
            [
                "",
                "## Gate Use",
                "",
                "- Use this report before closing the implementation stage or final delivery.",
                "- Open FAIL findings return to the owning stage before paper writing.",
                "- Open WARN findings remain visible as nonblocking diagnostics and produce `PASS_WITH_WARNINGS`.",
                "- Use `--strict-warnings` only when a caller deliberately wants every warning to fail the run.",
                "- Do not clear a result-quality finding by prose alone; rerun results, add numeric evidence, or record a waiver.",
                "",
            ]
        )
        return "\n".join(lines)

    def _json_payload(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(self.root),
            "verdict": self._verdict(),
            "output_level": self.output_level,
            "warning_policy": self._warning_policy_label(),
            "blocks_delivery": self._blocks_delivery(),
            "frozen_numbers": self.rel(self.frozen_path),
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }

    def _emit(self) -> None:
        for key, value in self.metrics.items():
            _print(f"METRIC: {key}={_compact_metric(value)}")
        for item in self.findings:
            _print(f"{item.level}: [{item.axis}] {item.phase}: {item.message}")
        _print(f"WARNING_POLICY: {self._warning_policy_label()}")
        _print(f"VERDICT: {self._verdict()}")
        if self.args.write_report:
            _print(f"INFO: wrote {self.rel(self._resolve(self.args.write_report))}")
        if self.args.write_json:
            _print(f"INFO: wrote {self.rel(self._resolve(self.args.write_json))}")

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if self._blocking_warnings():
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def _blocks_delivery(self) -> bool:
        return any(item.level == "FAIL" for item in self.findings) or bool(self._blocking_warnings())

    def _blocking_warnings(self) -> list[Finding]:
        if not self._warnings_block_delivery():
            return []
        return [item for item in self.findings if item.level == "WARN"]

    def _warnings_block_delivery(self) -> bool:
        if self.args.allow_warnings:
            return False
        return bool(self.args.strict_warnings)

    def _warning_policy_label(self) -> str:
        if self.args.allow_warnings:
            return "warnings_allowed_by_explicit_waiver"
        if self.args.strict_warnings:
            return "warnings_block_by_strict_flag"
        return "warnings_recorded_only"

    def _finalize_policy_metrics(self) -> None:
        self.metrics["output_level"] = self.output_level
        self.metrics["warning_policy"] = self._warning_policy_label()
        self.metrics["fail_count"] = sum(1 for item in self.findings if item.level == "FAIL")
        self.metrics["warn_count"] = sum(1 for item in self.findings if item.level == "WARN")
        self.metrics["blocking_warning_count"] = len(self._blocking_warnings())

    def _detect_output_level(self) -> str:
        requested = getattr(self.args, "output_level", None)
        if requested in {"quick_draft", "reproducible_draft", "contest_final"}:
            return requested
        brief = self.root / "planning" / "delivery_brief.md"
        if not brief.exists():
            return "unknown"
        text = self.read_text(brief)
        for line in text.splitlines():
            if "Output level" not in line:
                continue
            parts = [part.strip(" `") for part in line.strip().strip("|").split("|")]
            if len(parts) >= 2 and parts[0].lower() == "output level":
                value = parts[1].strip()
                if value in {"quick_draft", "reproducible_draft", "contest_final"}:
                    return value
        return "unknown"

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8-sig", errors="ignore")

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, normalize_stage_path(phase, "implementation"), message))

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, normalize_stage_path(phase, "implementation"), message))

    def info(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("INFO", axis, normalize_stage_path(phase, "implementation"), message))


def _normalize_row(row: dict[str, Any]) -> dict[str, str]:
    return {str(key).strip().lstrip("\ufeff"): "" if value is None else str(value).strip() for key, value in row.items()}


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_qid(key: str) -> bool:
    text = str(key).lower()
    return len(text) >= 2 and text[0] == "q" and text[1:].isdigit()


def _same_number(a: Any, b: Any, rel: float = 1e-6, abs_tol: float = 1e-6) -> bool:
    left = _num(a)
    right = _num(b)
    if left is None or right is None:
        return False
    return abs(left - right) <= max(abs_tol, rel * max(abs(left), abs(right), 1.0))


def _text_contains_number(text: str, value: float) -> bool:
    normalized = text.replace(",", "").replace(" ", "")
    candidates = {f"{value:g}"}
    if float(value).is_integer():
        candidates.add(str(int(value)))
    return any(re.search(rf"(?<![0-9.]){re.escape(candidate)}(?![0-9.])", normalized) for candidate in candidates)


def _closest_method(comparable: list[tuple[str, float]], final_value: float) -> str:
    if not comparable:
        return ""
    method, value = min(comparable, key=lambda item: abs(item[1] - final_value))
    return method if _same_number(value, final_value, rel=1e-4, abs_tol=1e-4) else ""


def _row_metric_value(row: dict[str, str], metric_name: str) -> float | None:
    if metric_name == "routing_objective":
        return _num(row.get("routing_objective")) or _sum_numbers(row, ["travel", "penalty"]) or _num(row.get("objective"))
    if metric_name == "combined_objective":
        return _num(row.get("combined_objective")) or _num(row.get("objective")) or _num(row.get("routing_objective"))
    if metric_name == "travel":
        return _num(row.get("travel")) or _num(row.get("objective"))
    return _num(row.get("objective")) or _num(row.get("total_objective")) or _num(row.get("routing_objective")) or _num(row.get("combined_objective"))


def _second_distinct_value(comparable: list[tuple[str, float]], final_value: float) -> float | None:
    for _, value in sorted(comparable, key=lambda item: item[1]):
        if not _same_number(value, final_value, rel=1e-4, abs_tol=1e-4):
            return value
    return None


def _first_existing_column(rows: list[dict[str, str]], names: list[str]) -> str:
    if not rows:
        return ""
    columns = {key.lower(): key for row in rows[:5] for key in row}
    for name in names:
        if name.lower() in columns:
            return columns[name.lower()]
    return ""


def _history_groups(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    if not rows:
        return {"all": rows}
    if any("vehicle_count" in row for row in rows) and any("run" in row for row in rows):
        return _group_rows(rows, ["vehicle_count", "run"])
    if any("run" in row for row in rows):
        return _group_rows(rows, ["run"])
    if any("vehicle_count" in row for row in rows) and any("variant" in row for row in rows):
        return _group_rows(rows, ["vehicle_count", "variant"])
    if any("vehicle_count" in row for row in rows):
        return _group_rows(rows, ["vehicle_count"])
    return {"all": rows}


def _stability_context(group_id: str) -> str:
    parts = [part for part in str(group_id).split(",") if part]
    context_parts = [part for part in parts if not part.startswith("run=") and not part.startswith("variant=") and not part.startswith("seed=")]
    return ",".join(context_parts) if context_parts else "all"


def _context_matches_selected_vehicle(context: str, selected_vehicle_count: float) -> bool:
    for part in str(context).split(","):
        if part.startswith("vehicle_count="):
            return _same_number(part.split("=", 1)[1], selected_vehicle_count)
    return False


def _comparable_stability_contexts(groups: dict[str, list[dict[str, str]]]) -> set[str]:
    group_ids = list(groups)
    if any("run=" in group_id or "seed=" in group_id for group_id in group_ids):
        return {_stability_context(group_id) for group_id in group_ids}
    return set()


def _format_percent_pairs(pairs: list[tuple[str, float]]) -> str:
    return ", ".join(f"{name}={value * 100:.2f}%" for name, value in pairs)


def _format_pairs(pairs: list[tuple[str, int]], suffix: str = "") -> str:
    return ", ".join(f"{name}={value}{suffix}" for name, value in pairs)


def _group_rows(rows: list[dict[str, str]], keys: list[str]) -> dict[str, list[dict[str, str]]]:
    if not rows or not any(key in row for row in rows for key in keys):
        return {"all": rows}
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        parts = [f"{key}={row.get(key) or 'missing'}" for key in keys if key in row]
        group = ",".join(parts) if parts else "missing"
        groups.setdefault(str(group), []).append(row)
    return groups


def _sort_rows(rows: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    if not any(key in row for row in rows):
        return list(rows)
    return sorted(rows, key=lambda row: (_num(row.get(key)) is None, _num(row.get(key)) or 0.0))


def _sort_key(value: str) -> tuple[int, float | str]:
    number = _num(value)
    return (0, number) if number is not None else (1, value)


def _relative_decrease(start: float, end: float) -> float:
    return max(0.0, (start - end) / max(abs(start), 1e-12))


def _count_best_increases(values: list[float]) -> int:
    count = 0
    previous = values[0] if values else 0.0
    for value in values[1:]:
        if value > previous * (1.0 + 1e-8) + 1e-8:
            count += 1
        previous = min(previous, value)
    return count


def _qid_from_name(name: str) -> str:
    lower = name.lower()
    for idx in range(1, 10):
        token = f"q{idx}"
        if token in lower:
            return token.upper()
    return ""


def _sum_numbers(row: dict[str, str], keys: list[str]) -> float | None:
    values = [_num(row.get(key)) for key in keys]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _infer_fixed_cost(rows: list[dict[str, str]]) -> float | None:
    estimates: list[float] = []
    for row in rows:
        k = _num(row.get("vehicle_count") or row.get("k") or row.get("vehicles"))
        combined = _num(row.get("combined_objective"))
        route = _num(row.get("routing_objective")) or _sum_numbers(row, ["travel", "penalty"])
        if k and combined is not None and route is not None:
            estimates.append((combined - route) / k)
    if not estimates:
        return None
    return statistics.median(estimates)


def _dedupe_options(options: list[dict[str, float]]) -> list[dict[str, float]]:
    by_k: dict[float, dict[str, float]] = {}
    for option in options:
        k = option["vehicle_count"]
        old = by_k.get(k)
        if old is None or option["route_cost"] < old["route_cost"]:
            by_k[k] = option
    return sorted(by_k.values(), key=lambda item: item["vehicle_count"])


def _best_vehicle_option(options: list[dict[str, float]], fixed_cost: float) -> dict[str, float] | None:
    if not options:
        return None
    return min(options, key=lambda item: item["route_cost"] + item["vehicle_count"] * fixed_cost)


def _vehicle_breakpoints(options: list[dict[str, float]], selected: dict[str, float], fixed_cost: float) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    selected_value = selected["route_cost"] + selected["vehicle_count"] * fixed_cost
    for option in options:
        if _same_number(option["vehicle_count"], selected["vehicle_count"]):
            continue
        alt_value = option["route_cost"] + option["vehicle_count"] * fixed_cost
        if alt_value < selected_value - 1e-7:
            continue
        denom = selected["vehicle_count"] - option["vehicle_count"]
        if abs(denom) < 1e-12:
            continue
        breakpoint = (option["route_cost"] - selected["route_cost"]) / denom
        if breakpoint <= 0 or not math.isfinite(breakpoint):
            continue
        out.append(
            {
                "alternative_vehicle_count": option["vehicle_count"],
                "breakpoint": breakpoint,
                "relative_margin": abs(breakpoint - fixed_cost) / max(abs(fixed_cost), 1e-12),
                "alternative_route_cost": option["route_cost"],
            }
        )
    return sorted(out, key=lambda item: item["relative_margin"])


def _winner_changes(winners: dict[str, float], selected_k: float, keys: list[str]) -> bool:
    for key in keys:
        if key in winners and not _same_number(winners[key], selected_k):
            return True
    return False


def _render_metric(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _escape_table(text if len(text) <= 1200 else text[:1200] + " ...")


def _compact_metric(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 500 else text[:500] + " ..."


def _escape_table(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _print(text: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(text, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--frozen", help="Frozen numbers JSON path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    parser.add_argument(
        "--output-level",
        choices=("quick_draft", "reproducible_draft", "contest_final"),
        help="Override the output level detected from planning/delivery_brief.md",
    )
    parser.add_argument("--strict-warnings", action="store_true", help="Treat WARN findings as blocking regardless of output level")
    parser.add_argument("--allow-warnings", action="store_true", help="Deprecated compatibility flag; WARN findings are nonblocking by default")
    args = parser.parse_args()
    if args.strict_warnings and args.allow_warnings:
        parser.error("--strict-warnings and --allow-warnings cannot be used together")
    return args


def main() -> int:
    return ResultQuality(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
