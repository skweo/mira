#!/usr/bin/env python3
"""Evaluate Mira PoC/method-screening results.

PoC code proves a method can run. This script checks whether the numbers should
change method selection: promising, weak, rejected, or smoke-test-only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = [
    "results/tables/poc_results.csv",
    "results/tables/method_screening.csv",
    "results/tables/baseline_comparison.csv",
]

TRUE_VALUES = {"true", "yes", "y", "1", "feasible", "ok", "pass"}
FALSE_VALUES = {"false", "no", "n", "0", "infeasible", "fail", "failed"}


@dataclass
class Candidate:
    source: str
    case: str
    method: str
    objective: float | None
    feasible: bool | None
    runtime_sec: float | None
    seed: str
    sample_size: str
    notes: str
    raw: dict[str, str]


@dataclass
class Finding:
    level: str
    phase: str
    case: str
    method: str
    message: str
    recommended_action: str


class PocEvaluator:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.inputs = [self._resolve(path) for path in (args.input or DEFAULT_INPUTS)]
        self.candidates: list[Candidate] = []
        self.findings: list[Finding] = []
        self.case_summaries: dict[str, dict[str, Any]] = {}

    def run(self) -> int:
        self._load()
        self._evaluate()
        if self.args.write_report:
            path = self._resolve(self.args.write_report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._markdown(), encoding="utf-8")
            print(f"wrote: {path}")
        if self.args.write_json:
            path = self._resolve(self.args.write_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._json_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"wrote: {path}")
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _load(self) -> None:
        for path in self.inputs:
            if not path.exists() or not path.is_file():
                continue
            with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    normalized = {str(k).strip().lstrip("\ufeff"): "" if v is None else str(v).strip() for k, v in row.items()}
                    candidate = self._candidate_from_row(path, normalized)
                    if candidate:
                        self.candidates.append(candidate)

    def _candidate_from_row(self, path: Path, row: dict[str, str]) -> Candidate | None:
        case = first_present(row, ["case", "qid", "question", "problem", "instance", "scenario"]) or path.stem
        method = first_present(row, ["method", "algorithm", "model", "solver", "route", "name"])
        objective = first_number(row, ["objective", "value", "score", "cost", "total_objective", "best_objective"])
        if not method or objective is None:
            return None
        feasible = parse_bool(first_present(row, ["feasible", "is_feasible", "constraint_status", "status"]))
        runtime = first_number(row, ["runtime_sec", "runtime", "time_sec", "seconds"])
        return Candidate(
            source=self._rel(path),
            case=case,
            method=method,
            objective=objective,
            feasible=feasible,
            runtime_sec=runtime,
            seed=first_present(row, ["seed", "random_seed"]) or "",
            sample_size=first_present(row, ["sample_size", "n", "customers", "nodes", "size"]) or "",
            notes=first_present(row, ["notes", "comment", "remarks"]) or "",
            raw=row,
        )

    def _evaluate(self) -> None:
        if not self.candidates:
            self.findings.append(
                Finding(
                    "WARN",
                    "implementation",
                    "-",
                    "-",
                    "no structured PoC or method-screening rows found",
                    "save comparable rows to results/tables/poc_results.csv or method_screening.csv before using PoC evidence in modeling",
                )
            )
            return

        by_case: dict[str, list[Candidate]] = {}
        for item in self.candidates:
            by_case.setdefault(item.case, []).append(item)

        for case, rows in sorted(by_case.items()):
            comparable = [row for row in rows if row.objective is not None and row.feasible is not False]
            best = min(comparable, key=lambda row: row.objective if row.objective is not None else math.inf) if comparable else None
            summary_rows: list[dict[str, Any]] = []
            for row in rows:
                ratio = None
                decision = "smoke_test_only"
                level = "INFO"
                action = "record as runnable PoC only; do not use as method-selection evidence without a comparable candidate"
                if row.feasible is False and best is not None:
                    decision = "reject"
                    level = "FAIL"
                    action = "reject this method for the case or repair feasibility before modeling"
                elif best is None:
                    decision = "no_feasible_reference"
                    level = "WARN"
                    action = "add a feasible baseline or repair all candidates before selecting the method"
                elif len(comparable) < 2:
                    decision = "smoke_test_only"
                    level = "WARN"
                    action = "run at least one baseline or alternative before using this PoC to justify method choice"
                elif row.objective is not None:
                    ratio = row.objective / max(best.objective or 1.0, 1e-12)
                    if row.method == best.method and row.objective == best.objective:
                        decision = "promising"
                        level = "INFO"
                        action = "may remain a candidate; still require full-size validation, feasibility audit, and stability evidence"
                    elif ratio >= self.args.reject_ratio:
                        decision = "reject"
                        level = "FAIL"
                        action = "downgrade or reject this method for the current structure; do not select it in modeling without explicit waiver or later stronger evidence"
                    elif ratio >= self.args.warn_ratio:
                        decision = "weak"
                        level = "WARN"
                        action = "keep only as backup unless it has compensating advantages such as constraints, runtime, or scalability"
                    else:
                        decision = "competitive"
                        level = "INFO"
                        action = "keep as candidate and compare on full data"

                if row.seed == "" and looks_stochastic(row.method):
                    self.findings.append(
                        Finding(
                            "WARN",
                            "implementation",
                            case,
                            row.method,
                            f"{row.method} PoC has no seed/settings record",
                            "rerun with fixed seed/settings before using the result as method-selection evidence",
                        )
                    )

                if level in {"FAIL", "WARN"}:
                    ratio_text = f"; ratio_to_best={ratio:.2f}" if ratio is not None else ""
                    self.findings.append(
                        Finding(
                            level,
                            "modeling",
                            case,
                            row.method,
                            f"{row.method} PoC decision is {decision}{ratio_text}",
                            action,
                        )
                    )

                summary_rows.append(
                    {
                        "method": row.method,
                        "objective": row.objective,
                        "feasible": row.feasible,
                        "ratio_to_best": ratio,
                        "decision": decision,
                        "source": row.source,
                    }
                )

            self.case_summaries[case] = {
                "best_method": best.method if best else "",
                "best_objective": best.objective if best else None,
                "candidate_count": len(rows),
                "comparable_count": len(comparable),
                "rows": summary_rows,
            }

    def _markdown(self) -> str:
        lines = [
            "# Mira PoC Decision Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{self._verdict()}**",
            f"- Reject ratio: {self.args.reject_ratio}",
            f"- Warn ratio: {self.args.warn_ratio}",
            "",
            "## Case Summary",
            "",
            "| Case | Best method | Best objective | Candidates | Comparable |",
            "|---|---|---:|---:|---:|",
        ]
        for case, summary in self.case_summaries.items():
            lines.append(
                f"| {case} | {summary['best_method'] or '-'} | {format_number(summary['best_objective'])} | {summary['candidate_count']} | {summary['comparable_count']} |"
            )

        lines.extend(["", "## Method Decisions", "", "| Case | Method | Objective | Feasible | Ratio to best | Decision | Source |", "|---|---|---:|---|---:|---|---|"])
        for case, summary in self.case_summaries.items():
            for row in summary["rows"]:
                lines.append(
                    "| {case} | {method} | {objective} | {feasible} | {ratio} | {decision} | `{source}` |".format(
                        case=case,
                        method=row["method"],
                        objective=format_number(row["objective"]),
                        feasible="unknown" if row["feasible"] is None else str(row["feasible"]).lower(),
                        ratio=format_number(row["ratio_to_best"]),
                        decision=row["decision"],
                        source=row["source"],
                    )
                )

        lines.extend(["", "## Findings", "", "| Level | Return to | Case | Method | Finding | Recommended action |", "|---|---|---|---|---|---|"])
        for item in self.findings:
            lines.append(
                f"| {item.level} | {item.phase} | {item.case} | {item.method} | {escape_table(item.message)} | {escape_table(item.recommended_action)} |"
            )
        lines.extend(
            [
                "",
                "## Gate Use",
                "",
                "- Use this report as modeling evidence.",
                "- A rejected method must not be selected as the main route unless a waiver or later stronger benchmark is recorded.",
                "- A smoke-test-only method proves code can run, not that the method is good.",
                "",
            ]
        )
        return "\n".join(lines)

    def _json_payload(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(self.root),
            "verdict": self._verdict(),
            "reject_ratio": self.args.reject_ratio,
            "warn_ratio": self.args.warn_ratio,
            "inputs": [self._rel(path) for path in self.inputs],
            "case_summaries": self.case_summaries,
            "findings": [asdict(item) for item in self.findings],
        }

    def _emit(self) -> None:
        print(f"candidates: {len(self.candidates)}")
        print(f"cases: {len(self.case_summaries)}")
        for item in self.findings:
            print(f"{item.level}: [{item.case}/{item.method}] {item.message} -> {item.recommended_action}")
        print(f"VERDICT: {self._verdict()}")

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--input", action="append", help="CSV input path; may be repeated")
    parser.add_argument("--reject-ratio", type=float, default=2.0, help="Reject minimization candidates at or above this ratio to best")
    parser.add_argument("--warn-ratio", type=float, default=1.25, help="Warn minimization candidates at or above this ratio to best")
    parser.add_argument("--write-report", help="Markdown report path")
    parser.add_argument("--write-json", help="JSON report path")
    return parser.parse_args()


def first_present(row: dict[str, str], names: list[str]) -> str:
    lower_map = {key.lower(): value for key, value in row.items()}
    for name in names:
        value = lower_map.get(name.lower())
        if value not in {None, ""}:
            return str(value).strip()
    return ""


def first_number(row: dict[str, str], names: list[str]) -> float | None:
    for name in names:
        value = first_present(row, [name])
        parsed = parse_number(value)
        if parsed is not None:
            return parsed
    return None


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_bool(value: str) -> bool | None:
    if value is None or value == "":
        return None
    lower = str(value).strip().lower()
    if lower in TRUE_VALUES:
        return True
    if lower in FALSE_VALUES:
        return False
    return None


def looks_stochastic(method: str) -> bool:
    lower = method.lower()
    return any(term in lower for term in ["sa", "ga", "pso", "anneal", "genetic", "random", "heuristic"])


def format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 10000 or (0 < abs(number) < 0.001):
        return f"{number:.6g}"
    return f"{number:.4f}".rstrip("0").rstrip(".")


def escape_table(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def main() -> int:
    return PocEvaluator(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
