#!/usr/bin/env python3
"""Grade the evidence confidence of final Mira numeric results."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


CONFIDENCE_ORDER = {
    "exact_or_certified": 5,
    "refined_continuous": 4,
    "audited_simulation": 3,
    "heuristic_best_found": 2,
    "single_run_or_sampled": 1,
    "assumed_or_unverified": 0,
}


@dataclass
class ResultGrade:
    path: str
    value: Any
    confidence: str
    evidence: list[str]
    warnings: list[str]


class ResultConfidence:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.frozen_path = resolve_path(self.root, args.frozen)
        self.frozen: dict[str, Any] = {}
        self.validation_plan: dict[str, Any] = {}
        self.project_text = ""
        self.grades: list[ResultGrade] = []
        self.findings: list[str] = []

    def run(self) -> int:
        self._load()
        if self.frozen:
            self._grade()
        self._write_outputs()
        self._emit()
        return 1 if self.verdict() == "FAIL" else 0

    def _load(self) -> None:
        if not self.frozen_path.exists():
            self.findings.append(f"missing frozen numbers: {rel(self.root, self.frozen_path)}")
            return
        try:
            self.frozen = json.loads(read_text(self.frozen_path))
        except json.JSONDecodeError as exc:
            self.findings.append(f"cannot parse frozen numbers: {exc}")
        plan_path = resolve_existing(
            self.root,
            self.args.validation_json,
            ["planning/validation_plan.json"],
        )
        if plan_path:
            try:
                self.validation_plan = json.loads(read_text(plan_path))
            except json.JSONDecodeError:
                self.validation_plan = {}
        self.project_text = collect_project_text(self.root)

    def _grade(self) -> None:
        for path, value in flatten_numbers(self.frozen):
            if not is_reportable_result(path, value):
                continue
            grade = classify_result(self.root, path, value, self.project_text, self.validation_plan)
            self.grades.append(grade)
        for grade in self.grades:
            if grade.confidence == "assumed_or_unverified":
                self.findings.append(f"{grade.path} has no visible verification evidence")
            if grade.confidence == "single_run_or_sampled" and is_extremum_path(grade.path):
                if "integer_second" in grade.path.lower() or "candidate" in grade.path.lower():
                    grade.warnings.append("sampled value is acceptable only as candidate evidence, not as a final claim")
                else:
                    self.findings.append(f"{grade.path} appears to be an extremum/threshold but only sampled evidence was found")
        self.grades.sort(key=lambda item: (item.path.lower(), -CONFIDENCE_ORDER[item.confidence]))

    def _write_outputs(self) -> None:
        if self.args.write_report:
            path = resolve_path(self.root, self.args.write_report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._markdown(), encoding="utf-8")
        if self.args.write_json:
            path = resolve_path(self.root, self.args.write_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _markdown(self) -> str:
        lines = [
            "# Mira Result Confidence",
            "",
            f"- Generated: {now()}",
            f"- Verdict: **{self.verdict()}**",
            f"- Root: `{self.root}`",
            "",
            "## Grades",
            "",
            "| Result path | Value | Confidence | Evidence | Warnings |",
            "|---|---:|---|---|---|",
        ]
        for item in self.grades:
            lines.append(
                "| {path} | {value} | {confidence} | {evidence} | {warnings} |".format(
                    path=f"`{item.path}`",
                    value=escape(format_value(item.value)),
                    confidence=item.confidence,
                    evidence=escape(", ".join(item.evidence[:8]) or "-"),
                    warnings=escape(", ".join(item.warnings) or "-"),
                )
            )
        if not self.grades:
            lines.append("| - | - | assumed_or_unverified | - | no reportable numeric results found |")
        lines.extend(["", "## Findings", ""])
        if self.findings:
            for finding in self.findings:
                lines.append(f"- {finding}")
        else:
            lines.append("- No blocking confidence findings.")
        lines.extend(
            [
                "",
                "## Confidence Classes",
                "",
                "- `exact_or_certified`: proof, closed-form identity, solver certificate, or tight independent benchmark.",
                "- `refined_continuous`: local continuous refinement/root search around a sampled candidate.",
                "- `audited_simulation`: reproducible simulation with constraint, residual, or consistency audit.",
                "- `heuristic_best_found`: heuristic result with baselines/convergence/multi-run evidence but no proof.",
                "- `single_run_or_sampled`: one run or coarse grid evidence only.",
                "- `assumed_or_unverified`: no visible artifact-level support.",
                "",
            ]
        )
        return "\n".join(lines)

    def _payload(self) -> dict[str, Any]:
        return {
            "generated_at": now(),
            "root": str(self.root),
            "verdict": self.verdict(),
            "grades": [asdict(item) for item in self.grades],
            "findings": self.findings,
        }

    def _emit(self) -> None:
        _print(f"VERDICT: {self.verdict()}")
        _print(f"graded_results: {len(self.grades)}")
        for finding in self.findings:
            _print("FAIL: " + finding)
        if self.args.write_report:
            _print(f"wrote: {resolve_path(self.root, self.args.write_report)}")
        if self.args.write_json:
            _print(f"wrote: {resolve_path(self.root, self.args.write_json)}")

    def verdict(self) -> str:
        if self.findings:
            return "FAIL"
        if any(item.confidence in {"single_run_or_sampled", "heuristic_best_found"} for item in self.grades):
            return "PASS_WITH_WARNINGS"
        return "PASS"


def classify_result(root: Path, path: str, value: Any, project_text: str, validation_plan: dict[str, Any]) -> ResultGrade:
    evidence = find_evidence(root, path, value)
    warnings: list[str] = []
    evidence_text = "\n".join(read_text(resolve_path(root, item)) for item in evidence).lower()
    plan_groups = present_validation_groups(validation_plan)

    exact_terms = ["certified optimum", "optimality certificate", "closed-form proof", "solver gap", "proof of optimality"]
    refined_terms = ["continuous", "refined", "refinement", "bisection", "root_scalar", "minimize_scalar", "ternary", "golden", "continuous_peak", "binary search", "bracket"]
    audit_terms = ["audit", "residual", "max_distance_error", "constraint", "feasible", "collision", "min_collision_gap", "validation"]
    heuristic_terms = ["heuristic", "best-found", "best found", "genetic", "pso", "annealing", "convergence", "multi-seed", "baseline"]
    sampled_terms = ["grid scan", "coarse scan", "integer second", "sample", "scan", "sweep"]

    local = local_context(evidence_text, path, value)
    context = local or evidence_text[:6000]
    evidence_names = " ".join(evidence).lower()
    if any(term in context for term in exact_terms):
        confidence = "exact_or_certified"
    elif is_extremum_path(path) and (any(term in context for term in refined_terms) or refined_evidence_path(path, evidence_names)):
        confidence = "refined_continuous"
    elif related_plan_present(path, plan_groups, {"continuous_refinement"}, evidence_names) and evidence:
        confidence = "refined_continuous"
    elif evidence and any(term in context for term in audit_terms):
        confidence = "audited_simulation"
    elif evidence and any(term in context for term in heuristic_terms):
        confidence = "heuristic_best_found"
    elif evidence and any(term in context for term in sampled_terms):
        confidence = "single_run_or_sampled"
    elif evidence:
        confidence = "audited_simulation"
    else:
        confidence = "assumed_or_unverified"

    if confidence == "single_run_or_sampled" and is_extremum_path(path):
        warnings.append("extremum or threshold result lacks visible continuous refinement")
    if "integer_second" in path.lower() or "integer" in path.lower():
        warnings.append("integer/coarse scan value should be treated as candidate evidence only")
        if confidence in {"refined_continuous", "exact_or_certified"}:
            confidence = "single_run_or_sampled"
    return ResultGrade(path=path, value=value, confidence=confidence, evidence=evidence, warnings=warnings)


def find_evidence(root: Path, result_path: str, value: Any) -> list[str]:
    needles = evidence_needles(result_path, value)
    candidates: list[Path] = []
    for rel_dir in ["results", "checks", "planning", "paper"]:
        folder = root / rel_dir
        if folder.exists():
            candidates.extend(
                path
                for path in sorted(folder.rglob("*"))
                if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".csv", ".tex", ".typ"}
            )
    out: list[str] = []
    for path in candidates:
        rel_path = rel(root, path)
        if is_self_or_meta_report(rel_path):
            continue
        text = read_text(path)
        lower = text.lower()
        if any(needle.lower() in lower for needle in needles):
            out.append(rel_path)
    return out[:12]


def evidence_needles(path: str, value: Any) -> list[str]:
    parts = [part for part in re.split(r"[._]", path) if part and part not in {"q1", "q2", "q3", "q4", "q5", "full", "chain"}]
    needles = [path.split(".")[-1], "_".join(parts[-3:])]
    if isinstance(value, float):
        needles.append(f"{value:.8g}")
        needles.append(f"{value:.6f}".rstrip("0").rstrip("."))
    else:
        needles.append(str(value))
    return [needle for needle in needles if needle]


def local_context(text: str, path: str, value: Any) -> str:
    needles = evidence_needles(path, value)
    snippets: list[str] = []
    for needle in needles:
        idx = text.find(needle.lower())
        if idx >= 0:
            snippets.append(text[max(0, idx - 1200) : idx + 1200])
    return "\n".join(snippets)


def related_plan_present(path: str, groups: set[str], required: set[str], evidence_names: str) -> bool:
    if not (groups & required):
        return False
    return is_extremum_path(path) and refined_evidence_path(path, evidence_names)


def refined_evidence_path(path: str, evidence_names: str) -> bool:
    lower = path.lower()
    names = evidence_names.lower()
    if "integer_second" in lower or "integer" in lower:
        return False
    evidence_tokens = (
        "continuous_peak",
        "local_search",
        "local_refinement",
        "boundary_refinement",
        "collision_audit",
        "threshold_audit",
        "feasibility_audit",
        "root_finding",
        "refinement",
    )
    return any(token in names for token in evidence_tokens)


def is_self_or_meta_report(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    if name.startswith("result_confidence"):
        return True
    if name.startswith("benchmark_regression"):
        return True
    if name.startswith("method_route_") or name.startswith("validation_plan_") or name.startswith("knowledge_injection_042"):
        return True
    return False


def present_validation_groups(plan: dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    for item in plan.get("items", []) if isinstance(plan, dict) else []:
        if isinstance(item, dict) and item.get("status") == "present":
            groups.add(str(item.get("validation_group")))
    return groups


def collect_project_text(root: Path) -> str:
    parts: list[str] = []
    for rel_dir in ["planning", "results", "checks", "paper", "code"]:
        folder = root / rel_dir
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".csv", ".py", ".tex", ".typ"}:
                parts.append(read_text(path)[:40000])
    return "\n".join(parts)


def flatten_numbers(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.extend(flatten_numbers(value, next_prefix))
    elif isinstance(data, list):
        if all(is_number(item) for item in data):
            out.append((prefix, data))
        else:
            for index, value in enumerate(data):
                out.extend(flatten_numbers(value, f"{prefix}.{index}"))
    elif is_number(data):
        out.append((prefix, data))
    return out


def is_reportable_result(path: str, value: Any) -> bool:
    if path.startswith("result_files"):
        return False
    if path.endswith(".search_records"):
        return False
    if isinstance(value, (int, float)) and abs(float(value)) < 1e-14:
        return any(term in path for term in ["error", "gap", "margin"])
    important_terms = [
        "time",
        "speed",
        "pitch",
        "radius",
        "length",
        "gap",
        "error",
        "margin",
        "factor",
        "objective",
        "travel",
        "penalty",
        "cost",
    ]
    return any(term in path.lower() for term in important_terms)


def is_extremum_path(path: str) -> bool:
    lower = path.lower()
    return any(term in lower for term in ["max", "min", "peak", "critical", "threshold", "stop_time", "pitch", "factor", "speed"])


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.10g}"
    return json.dumps(value, ensure_ascii=False)


def resolve_existing(root: Path, explicit: str | None, defaults: list[str]) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(resolve_path(root, explicit))
    candidates.extend(resolve_path(root, item) for item in defaults)
    for path in candidates:
        if path.exists():
            return path
    return None


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    parser.add_argument("--frozen", default="results/frozen_numbers.json", help="Frozen numbers JSON path")
    parser.add_argument("--validation-json", help="Validation plan JSON path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return ResultConfidence(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
