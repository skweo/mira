#!/usr/bin/env python3
"""Check consistency between modeled methods, executed solvers, and paper claims.

The checker is designed for Mira contest-paper projects. It catches the failure
mode where a paper formulates QUBO or mentions a platform such as Kaiwu SDK, but
the saved numerical results actually come from DP, SA, local search, or another
solver.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow_stages import normalize_stage_path

from delivery_contract import DeliveryContractError, canonical_source, load_manifest, manifest_path


BACKEND_LIMIT_DEFAULT = 550

TEXT_SUFFIXES = {".md", ".tex", ".typ", ".txt", ".json"}
MODEL_TERMS = ["qubo", "milp", "dp", "dynamic programming", "sa", "simulated annealing", "local search", "ga", "pso"]
# "相干" and "真机" are ordinary Chinese words outside a quantum-computing
# context (for example, "互不相干"). Keep only unambiguous backend signals.
BACKEND_TERMS = ["kaiwu", "sdk", "quantum", "量子", "伊辛"]
DISCLOSURE_TERMS = [
    "未实际",
    "没有实际",
    "未调用",
    "未执行",
    "未完成",
    "不声称",
    "不伪造",
    "不能展示真实",
    "not executed",
    "not run",
    "not claim",
    "not fabricated",
    "no kaiwu",
    "unavailable",
    "not directly solved",
    "model interface",
    "classical algorithm",
    "classical algorithms",
    "未实际",
    "没有实际",
    "未调用",
    "未执行",
    "未运行",
    "未检测到",
    "未被实际调用",
    "没有运行",
    "没有调用",
    "不声称",
    "不伪造",
    "无法展示真实",
    "数值结果由经典算法产生",
    "经典算法产生",
    "作为模型接口",
    "没有真实后端运行日志",
    "没有后端运行日志",
    "直接声称",
    "不能声称",
    "造成模型与结果来源脱节",
    "明确披露边界",
]

DANGEROUS_BACKEND_PATTERNS = [
    r"(?:kaiwu|sdk|量子真机|量子计算机|真机|相干伊辛机).{0,30}(?:求解得到|求得|运行得到|调用得到|输出|结果)",
    r"(?:调用|运行|执行|使用).{0,20}(?:kaiwu|sdk|量子真机|量子计算机|真机).{0,20}(?:求解|得到|输出)",
    r"(?:kaiwu|sdk|quantum).{0,40}(?:executed|ran|solved|output|produced|result)",
]

DANGEROUS_QUBO_PATTERNS = [
    r"qubo.{0,20}(?:求解得到|求得|运行得到|输出路线|输出结果)",
    r"(?:将|交给).{0,20}qubo.{0,20}(?:求解器|solver).{0,20}(?:求解|得到)",
    r"qubo.{0,30}(?:solver|annealer).{0,30}(?:produced|solved|output)",
]


@dataclass
class Finding:
    level: str
    axis: str
    phase: str
    message: str


class ModelSolverConsistency:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.frozen_path = self._resolve(args.frozen) if args.frozen else self.root / "results" / "frozen_numbers.json"
        self.tables_dir = self.root / "results" / "tables"
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}
        self.frozen: dict[str, Any] = {}
        self.tables: dict[str, list[dict[str, str]]] = {}
        self.texts: dict[str, str] = {}
        self.all_text = ""
        self.paper_text = ""
        self.planning_text = ""
        self.problem_text = ""
        self.log_text = ""

    def run(self) -> int:
        self._load()
        self._check_solver_lineage()
        self._check_backend_execution_claims()
        self._check_qubo_scale_and_claims()
        self._check_paper_method_wording()
        self._check_contest_backend_requirement()
        self._write_outputs()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _load(self) -> None:
        if self.frozen_path.exists():
            try:
                self.frozen = json.loads(self.read_text(self.frozen_path))
            except json.JSONDecodeError as exc:
                self.fail("model_solver_consistency", "implementation", f"cannot parse frozen numbers: {exc}")
        else:
            self.warn("model_solver_consistency", "implementation", f"missing frozen numbers: {self.rel(self.frozen_path)}")

        if self.tables_dir.exists():
            for path in sorted(self.tables_dir.glob("*.csv")):
                with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as fh:
                    self.tables[path.name] = [_normalize_row(row) for row in csv.DictReader(fh)]

        for folder in ("planning", "problem", "results/logs", "checks"):
            base = self.root / folder
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                    self.texts[self.rel(path)] = self.read_text(path)

        paper_source = self._paper_source()
        if paper_source is not None and paper_source.is_file():
            paper_rel = self.rel(paper_source)
            self.texts[paper_rel] = self.read_text(paper_source)
            self.paper_text = self.texts[paper_rel]
            self.metrics["paper_source"] = paper_rel
        else:
            self.warn("canonical_source", "paper", "no canonical paper source was found")
            self.metrics["paper_source"] = None

        self.all_text = "\n".join(self.texts.values())
        self.planning_text = "\n".join(text for rel, text in self.texts.items() if rel.startswith("planning/"))
        self.problem_text = "\n".join(text for rel, text in self.texts.items() if rel.startswith("problem/"))
        self.log_text = "\n".join(text for rel, text in self.texts.items() if rel.startswith("results/logs/"))

        self.metrics["backend_status"] = self._backend_status()
        self.metrics["text_sources"] = sorted(self.texts)
        self.metrics["tables_loaded"] = sorted(self.tables)

    def _paper_source(self) -> Path | None:
        delivery = manifest_path(self.root)
        if delivery.is_file():
            try:
                load_manifest(self.root)
            except DeliveryContractError as exc:
                self.fail("delivery_manifest", "paper", str(exc))
            return canonical_source(self.root)

        # Controlled compatibility fallback for pre-0.11 draft projects. Never
        # concatenate arbitrary files under paper/, because stale drafts can
        # change the meaning of the canonical paper audit.
        for relative in ("paper/main.tex", "paper/main.typ", "paper/main.md", "paper/paper.md"):
            candidate = self.root / relative
            if candidate.is_file():
                return candidate
        return None

    def _check_solver_lineage(self) -> None:
        actual = self._actual_methods()
        planned = self._planned_methods()
        lineage: dict[str, Any] = {}
        for qid in sorted(key.upper() for key in self.frozen if _is_qid(key)):
            data = self.frozen.get(qid.lower(), {})
            analysis_only = _is_analysis_only_case(data)
            method = actual.get(qid) or planned.get(qid) or ("input data audit only" if analysis_only else "")
            lineage[qid] = {
                "actual_method": method,
                "planned_method": planned.get(qid, ""),
                "categories": sorted(_method_categories(method)),
                "evidence": self._lineage_evidence(qid, method),
                "solver_required": not analysis_only,
            }
            if not method and not analysis_only:
                self.warn("solver_lineage", "implementation", f"{qid} frozen result has no recoverable actual solver method; add solver_lineage.csv or method/source fields")
        self.metrics["solver_lineage"] = lineage

        if not (self.tables_dir / "solver_lineage.csv").exists():
            if all(item.get("actual_method") or not item.get("solver_required") for item in lineage.values()):
                self.info("solver_lineage", "implementation", "solver lineage is recoverable from baseline/modeling artifacts; consider writing results/tables/solver_lineage.csv for stronger traceability")
            else:
                self.warn("solver_lineage", "implementation", "results/tables/solver_lineage.csv is missing and some solver lineage is ambiguous")

    def _check_backend_execution_claims(self) -> None:
        status = self._backend_status()
        executed = bool(status.get("kaiwu_sdk_executed") or status.get("quantum_machine_executed"))
        dangerous = self._dangerous_sentences(self.paper_text, DANGEROUS_BACKEND_PATTERNS)
        self.metrics["dangerous_backend_claims"] = dangerous
        if dangerous and not executed:
            self.fail(
                "backend_execution",
                "paper",
                f"paper contains backend-execution wording but frozen/log evidence says Kaiwu SDK or quantum machine did not run. Examples: {_examples(dangerous)}",
            )
        elif _has_backend_terms(self.paper_text) and not executed:
            if _has_disclosure(self.paper_text):
                self.warn(
                    "backend_execution",
                    "paper",
                    "paper mentions Kaiwu/SDK/quantum while no backend execution is recorded; disclosure exists, but final wording must keep QUBO/backend as model interface or limitation, not result source",
                )
            else:
                self.fail(
                    "backend_execution",
                    "paper",
                    "paper mentions Kaiwu/SDK/quantum while no backend execution is recorded and no clear non-execution disclosure was found",
                )

    def _check_qubo_scale_and_claims(self) -> None:
        qubo_rows = self.frozen.get("qubo_scale", []) if isinstance(self.frozen, dict) else []
        scale_metrics: list[dict[str, Any]] = []
        for row in qubo_rows if isinstance(qubo_rows, list) else []:
            if not isinstance(row, dict):
                continue
            case = str(row.get("case", ""))
            variables = _num(row.get("binary_variables"))
            qids = _qids_from_text(case)
            exceeds = variables is not None and variables > self.args.backend_limit
            item = {
                "case": case,
                "qids": qids,
                "binary_variables": variables,
                "backend_limit": self.args.backend_limit,
                "exceeds_backend_limit": exceeds,
                "comment": row.get("comment", ""),
            }
            scale_metrics.append(item)
            if not exceeds:
                continue
            for qid in qids or [""]:
                window = self._paper_window_for(qid) if qid else self.paper_text
                direct_claims = self._dangerous_sentences(window, DANGEROUS_BACKEND_PATTERNS + DANGEROUS_QUBO_PATTERNS)
                has_fallback = _has_classical_or_decomposition_fallback(window)
                if direct_claims:
                    self.fail(
                        "qubo_scale",
                        "modeling",
                        f"{case} has {variables:g} binary variables above backend limit {self.args.backend_limit}, but paper has direct QUBO/backend solve wording: {_examples(direct_claims)}",
                    )
                elif not has_fallback:
                    self.warn(
                        "qubo_scale",
                        "modeling",
                        f"{case} has {variables:g} binary variables above backend limit {self.args.backend_limit}; paper should state decomposition/classical fallback or limitation near the result",
                    )
                else:
                    self.info(
                        "qubo_scale",
                        "implementation",
                        f"{case} exceeds backend limit and paper appears to state fallback/decomposition/classical verification",
                    )
        self.metrics["qubo_scale"] = scale_metrics

    def _check_paper_method_wording(self) -> None:
        lineage = self.metrics.get("solver_lineage", {})
        claim_metrics: dict[str, Any] = {}
        for qid, item in lineage.items():
            if not item.get("solver_required", True):
                claim_metrics[qid] = {"claim_terms": [], "actual_categories": [], "analysis_only": True}
                continue
            method = str(item.get("actual_method", ""))
            categories = set(item.get("categories", []))
            window = self._paper_window_for(qid)
            terms = _claim_terms(window)
            claim_metrics[qid] = {"claim_terms": sorted(terms), "actual_categories": sorted(categories)}
            if not window.strip():
                continue
            if {"qubo", "backend"} & terms and not ({"qubo", "backend"} & categories):
                if categories & {"sa", "local_search", "dp", "exact", "partition"}:
                    actual_label = method or ", ".join(sorted(categories))
                    if _mentions_actual_solver(window, categories):
                        continue
                    self.warn(
                        "paper_wording",
                        "paper",
                        f"{qid} paper window emphasizes QUBO/backend terms but does not clearly name actual solver `{actual_label}` near the result",
                    )
            if "optimality_strong" in terms and categories & {"sa", "local_search", "ga", "pso"}:
                self.fail(
                    "paper_wording",
                    "paper",
                    f"{qid} uses strong optimality wording while actual solver is heuristic `{method}`",
                )
        self.metrics["paper_claim_terms"] = claim_metrics

    def _check_contest_backend_requirement(self) -> None:
        status = self._backend_status()
        problem_requires = _problem_requires_backend(self.problem_text)
        self.metrics["contest_backend_requirement"] = {
            "problem_requires_backend": problem_requires,
            "disclosure_in_paper": _has_disclosure(self.paper_text),
        }
        if not problem_requires:
            return
        if status.get("kaiwu_sdk_executed") or status.get("quantum_machine_executed"):
            return
        if _has_disclosure(self.paper_text):
            self.warn(
                "backend_requirement",
                "implementation",
                "problem text appears to require or strongly request Kaiwu/quantum validation, but no backend execution is recorded; paper discloses the limitation, so treat this as a contest-compliance risk",
            )
        else:
            self.fail(
                "backend_requirement",
                "implementation",
                "problem text appears to require Kaiwu/quantum validation, but no backend execution or clear limitation disclosure is recorded",
            )

    def _backend_status(self) -> dict[str, Any]:
        settings = self.frozen.get("settings", {}) if isinstance(self.frozen, dict) else {}
        available = settings.get("kaiwu_sdk_available")
        executed = settings.get("kaiwu_sdk_executed")
        quantum_executed = settings.get("quantum_machine_executed")
        log_lower = self.log_text.lower()
        if available is None:
            if "kaiwu" in log_lower and "false" in log_lower:
                available = False
        if executed is None:
            executed = bool(re.search(r"(kaiwu|sdk|quantum).{0,40}(executed|ran|success)", log_lower))
        if quantum_executed is None:
            quantum_executed = bool(re.search(r"(quantum machine|量子真机|相干光量子).{0,40}(executed|ran|调用成功|运行成功)", log_lower))
        return {
            "kaiwu_sdk_available": bool(available) if available is not None else None,
            "kaiwu_sdk_executed": bool(executed),
            "quantum_machine_executed": bool(quantum_executed),
            "environment_evidence": [rel for rel in self.texts if rel.startswith("results/logs/")],
        }

    def _actual_methods(self) -> dict[str, str]:
        out: dict[str, str] = {}
        rows = self.tables.get("baseline_comparison.csv", [])
        for qid, data in self.frozen.items() if isinstance(self.frozen, dict) else []:
            if not _is_qid(qid) or not isinstance(data, dict):
                continue
            qlabel = qid.upper()
            frozen_method = str(data.get("method") or "")
            if frozen_method:
                out[qlabel] = frozen_method
            final_value, metric = _case_metric(qlabel, data)
            if final_value is None:
                continue
            matched = _match_baseline_method(rows, qlabel, final_value, metric)
            if matched and (qlabel not in out or _method_priority(matched) > _method_priority(out[qlabel])):
                out[qlabel] = matched
        return out

    def _planned_methods(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in self._read_modeling_plan().splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or "---" in stripped:
                continue
            cols = [col.strip() for col in stripped.strip("|").split("|")]
            if len(cols) >= 2 and re.fullmatch(r"Q\d+", cols[0], flags=re.I):
                if _looks_like_solver(cols[1]):
                    out[cols[0].upper()] = cols[1]
        return out

    def _read_modeling_plan(self) -> str:
        path = self.root / "planning" / "modeling_plan.md"
        return self.read_text(path) if path.exists() else self.planning_text

    def _lineage_evidence(self, qid: str, method: str) -> list[str]:
        evidence: list[str] = []
        if method and self.tables.get("baseline_comparison.csv"):
            evidence.append("results/tables/baseline_comparison.csv")
        if self.root.joinpath("results/logs/run_summary.json").exists():
            evidence.append("results/logs/run_summary.json")
        return evidence

    def _paper_window_for(self, qid: str) -> str:
        if not qid:
            return self.paper_text
        labels = [qid, f"问题{_qid_cn(qid)}", f"问题 {qid[-1]}", f"Problem {qid[-1]}"]
        windows: list[str] = []
        for label in labels:
            for match in re.finditer(re.escape(label), self.paper_text, flags=re.I):
                start = max(0, match.start() - 1200)
                end = min(len(self.paper_text), match.end() + 2500)
                windows.append(self.paper_text[start:end])
        return "\n".join(windows) if windows else self.paper_text

    def _dangerous_sentences(self, text: str, patterns: list[str]) -> list[str]:
        sentences = _sentences(text)
        out: list[str] = []
        for sentence in sentences:
            if _has_disclosure(sentence):
                continue
            lower = sentence.lower()
            if any(re.search(pattern, lower, flags=re.I | re.S) for pattern in patterns):
                out.append(_compact(sentence))
        return out[:8]

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
            "# Mira Model-Solver Consistency Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{self._verdict()}**",
            f"- Root: `{self.root}`",
            "",
            "## Solver Lineage",
            "",
            "| Case | Actual solver | Planned solver | Categories | Evidence |",
            "|---|---|---|---|---|",
        ]
        for qid, item in self.metrics.get("solver_lineage", {}).items():
            lines.append(
                "| {qid} | {actual} | {planned} | {categories} | {evidence} |".format(
                    qid=qid,
                    actual=_escape(item.get("actual_method", "-")),
                    planned=_escape(item.get("planned_method", "-")),
                    categories=", ".join(item.get("categories", [])) or "-",
                    evidence=", ".join(f"`{path}`" for path in item.get("evidence", [])) or "-",
                )
            )

        lines.extend(["", "## Backend And QUBO Scale", "", "| Case | Binary variables | Limit | Status |", "|---|---:|---:|---|"])
        for item in self.metrics.get("qubo_scale", []):
            status = "exceeds" if item.get("exceeds_backend_limit") else "within"
            lines.append(
                f"| {_escape(item.get('case', '-'))} | {_fmt(item.get('binary_variables'))} | {_fmt(item.get('backend_limit'))} | {status} |"
            )

        lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---|"])
        for key in ("backend_status", "dangerous_backend_claims", "contest_backend_requirement", "paper_claim_terms"):
            if key in self.metrics:
                lines.append(f"| {key} | {_escape(_json_short(self.metrics[key]))} |")

        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        for item in self.findings:
            lines.append(f"| {item.level} | {item.axis} | {item.phase} | {_escape(item.message)} |")
        if not self.findings:
            lines.append("| INFO | model_solver_consistency | - | no model-solver consistency findings |")

        lines.extend(
            [
                "",
                "## Gate Use",
                "",
                "- Use this report before closing the implementation stage or final delivery.",
                "- A FAIL means the paper/model/code lineage is inconsistent and must return to the owning public stage.",
                "- Do not claim SDK, quantum-machine, or QUBO-solver output unless a real run artifact exists.",
                "",
            ]
        )
        return "\n".join(lines)

    def _json_payload(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": str(self.root),
            "verdict": self._verdict(),
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }

    def _emit(self) -> None:
        for key, value in self.metrics.items():
            _print(f"METRIC: {key}={_json_short(value, 600)}")
        for item in self.findings:
            _print(f"{item.level}: [{item.axis}] {item.phase}: {item.message}")
        _print(f"VERDICT: {self._verdict()}")
        if self.args.write_report:
            _print(f"INFO: wrote {self.rel(self._resolve(self.args.write_report))}")
        if self.args.write_json:
            _print(f"INFO: wrote {self.rel(self._resolve(self.args.write_json))}")

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, normalize_stage_path(phase, "implementation"), message))

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, normalize_stage_path(phase, "implementation"), message))

    def info(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("INFO", axis, normalize_stage_path(phase, "implementation"), message))

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
    return bool(re.fullmatch(r"q\d+", str(key), flags=re.I))


def _case_metric(qid: str, data: dict[str, Any]) -> tuple[float | None, str]:
    if qid == "Q4" and _num(data.get("routing_objective")) is not None:
        return _num(data.get("routing_objective")), "routing_objective"
    if _num(data.get("objective")) is not None:
        return _num(data.get("objective")), "objective"
    if _num(data.get("travel")) is not None:
        return _num(data.get("travel")), "travel"
    return None, "objective"


def _match_baseline_method(rows: list[dict[str, str]], qid: str, final_value: float, metric: str) -> str:
    matches: list[str] = []
    for row in rows:
        case = (row.get("case") or row.get("qid") or "").strip().upper()
        if case != qid:
            continue
        value = _baseline_value(row, metric)
        if value is None:
            continue
        distance = abs(value - final_value)
        if distance <= max(1e-6, abs(final_value) * 1e-6):
            matches.append(row.get("method") or row.get("algorithm") or row.get("model") or "")
    if matches:
        return max(matches, key=_method_priority)
    return ""


def _method_priority(method: str) -> int:
    lower = method.lower()
    score = 0
    if any(term in lower for term in ["exact", "certificate", "label", "dp", "held", "dynamic"]):
        score += 20
    if any(term in lower for term in ["local", "heuristic", "search"]):
        score += 5
    return score


def _baseline_value(row: dict[str, str], metric: str) -> float | None:
    if metric == "routing_objective":
        return _num(row.get("routing_objective")) or _num(row.get("objective")) or _sum(row, ["travel", "penalty"])
    if metric == "travel":
        return _num(row.get("travel")) or _num(row.get("objective"))
    return _num(row.get("objective")) or _num(row.get("total_objective")) or _num(row.get("routing_objective"))


def _sum(row: dict[str, str], keys: list[str]) -> float | None:
    values = [_num(row.get(key)) for key in keys]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _method_categories(method: str) -> set[str]:
    lower = method.lower()
    out: set[str] = set()
    if any(term in lower for term in ["qubo"]):
        out.add("qubo")
    if any(term in lower for term in ["kaiwu", "sdk", "quantum"]):
        out.add("backend")
    if any(term in lower for term in ["held", "dp", "label", "dynamic"]):
        out.add("dp")
        out.add("exact")
    if any(term in lower for term in ["exact", "精确"]):
        out.add("exact")
    if any(term in lower for term in ["sa", "anneal", "模拟退火"]):
        out.add("sa")
    if any(term in lower for term in ["local", "search", "局部"]):
        out.add("local_search")
    if any(term in lower for term in ["partition", "capacity", "route", "车辆", "划分"]):
        out.add("partition")
    if any(term in lower for term in ["ga", "genetic", "遗传"]):
        out.add("ga")
    return out


def _claim_terms(text: str) -> set[str]:
    lower = text.lower()
    out: set[str] = set()
    if "qubo" in lower:
        out.add("qubo")
    if _has_backend_terms(text):
        out.add("backend")
    if any(term in lower for term in ["held", "dp", "动态规划", "标签"]):
        out.add("dp")
    if any(term in lower for term in ["exact", "精确"]):
        out.add("exact")
    if any(term in lower for term in ["sa", "anneal", "模拟退火"]):
        out.add("sa")
    if any(term in lower for term in ["local search", "局部搜索", "2-opt", "relocate", "swap"]):
        out.add("local_search")
    if any(term in lower for term in ["partition", "划分", "多车"]):
        out.add("partition")
    if any(term in lower for term in ["全局最优", "严格最优", "最优解", "global optimum"]):
        out.add("optimality_strong")
    return out


def _mentions_actual_solver(text: str, categories: set[str]) -> bool:
    terms = _claim_terms(text)
    comparable = {"sa", "local_search", "dp", "exact", "partition", "ga", "pso"}
    return bool((categories & comparable) & terms)


def _looks_like_solver(text: str) -> bool:
    lower = str(text).lower()
    solver_terms = [
        "held",
        "dp",
        "label",
        "exact",
        "sa",
        "anneal",
        "local",
        "search",
        "partition",
        "qubo",
        "kaiwu",
        "sdk",
        "milp",
        "ga",
        "pso",
        "动态规划",
        "标签",
        "精确",
        "模拟退火",
        "局部",
        "求解",
        "solver",
    ]
    problem_type_terms = {"tsp", "tsptw", "vrp", "cvrptw", "large no-waiting tsptw", "no-waiting tsptw"}
    stripped = lower.strip()
    if stripped in problem_type_terms:
        return False
    return any(term in lower for term in solver_terms)


def _is_analysis_only_case(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    kind = str(data.get("method_kind") or data.get("case_kind") or "").strip().lower().replace("-", "_")
    return bool(data.get("analysis_only")) or kind in {
        "data_audit",
        "input_audit",
        "diagnostic",
        "descriptive_analysis",
    }


def _has_backend_terms(text: str) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in BACKEND_TERMS)


def _has_disclosure(text: str) -> bool:
    lower = _claim_scan_text(text).lower()
    return any(term.lower() in lower for term in DISCLOSURE_TERMS)


def _claim_scan_text(text: str) -> str:
    cleaned = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", cleaned)


def _has_classical_or_decomposition_fallback(text: str) -> bool:
    lower = text.lower()
    terms = [
        "经典",
        "启发式",
        "模拟退火",
        "局部搜索",
        "分解",
        "分块",
        "超出",
        "超过",
        "不适合",
        "规模限制",
        "fallback",
        "classical",
        "decomposition",
        "local search",
        "simulated annealing",
        "exceeds",
    ]
    return any(term.lower() in lower for term in terms)


def _problem_requires_backend(text: str) -> bool:
    lower = text.lower()
    if "kaiwu" not in lower and "sdk" not in lower and "量子" not in lower:
        return False
    return any(term in lower for term in ["必须使用", "请附上调用", "采用 kaiwu", "采用kaiwu", "must use", "required"])


def _qids_from_text(text: str) -> list[str]:
    out: set[str] = set()
    for match in re.finditer(r"\bQ([1-9])\b", text, flags=re.I):
        out.add(f"Q{match.group(1)}")
    if "Q1/Q2" in text.upper() or "Q1-Q2" in text.upper():
        out.update({"Q1", "Q2"})
    mapping = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
    for cn, digit in mapping.items():
        if f"问题{cn}" in text:
            out.add(f"Q{digit}")
    return sorted(out)


def _qid_cn(qid: str) -> str:
    mapping = {"Q1": "一", "Q2": "二", "Q3": "三", "Q4": "四", "Q5": "五", "Q6": "六", "Q7": "七", "Q8": "八", "Q9": "九"}
    return mapping.get(qid.upper(), qid)


def _sentences(text: str) -> list[str]:
    rough = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
    return [part.strip() for part in rough if part.strip()]


def _compact(text: str, limit: int = 260) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _examples(items: list[str]) -> str:
    return "; ".join(_compact(item, 160) for item in items[:3])


def _escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _fmt(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "-"
    return f"{number:.6g}"


def _json_short(value: Any, limit: int = 1200) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 3] + "..."


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
    parser.add_argument("--backend-limit", type=int, default=BACKEND_LIMIT_DEFAULT, help="Direct backend binary-variable limit")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return ModelSolverConsistency(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
