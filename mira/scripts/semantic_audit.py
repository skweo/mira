#!/usr/bin/env python3
"""Run semantic audit for a Mira contest-paper project.

Semantic audit checks whether results are plausible and honestly supported. It
is intentionally different from existence/consistency checks: a value can match
frozen_numbers.json and still need a warning if its scale, parameters, or claim
strength are unsupported.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


RULE_REFERENCE = "references/semantic-audit-rules.md"


NUMERIC_KEYS = {
    "objective",
    "penalty",
    "travel",
    "routing_objective",
    "combined_objective",
    "total_early",
    "total_late",
    "vehicle_fixed_cost",
    "alpha_early",
    "alpha_late",
}

HEURISTIC_TERMS = ["SA", "模拟退火", "GA", "遗传", "PSO", "粒子群", "蚁群", "heuristic", "local search", "局部搜索"]
HEURISTIC_HISTORY_TERMS = ["history", "convergence", "trace", "iteration", "迭代", "收敛"]
VALIDATION_ARTIFACT_TERMS = [
    "baseline",
    "comparison",
    "audit",
    "check",
    "validation",
    "sensitivity",
    "threshold",
    "posterior",
    "precision",
    "residual",
    "enumeration",
]
QUESTION_FIELDS = ["qid", "question", "problem", "subquestion"]
EXACT_TERMS = ["Held-Karp", "exact", "精确", "DP", "MILP", "gap", "certificate", "证书", "下界", "上界"]
OPTIMALITY_TERMS = ["全局最优", "严格最优", "最优解", "optimal", "global optimum"]
EVIDENCE_TERMS = ["基线", "baseline", "对比", "敏感", "灵敏度", "收敛", "多种子", "重复", "seed", "稳定", "audit", "审计"]
EXPLANATION_TERMS = ["下界", "瓶颈", "压力", "高压", "不可行", "时间窗", "bound", "sensitivity", "baseline", "审计", "解释"]


@dataclass
class Finding:
    level: str
    axis: str
    phase: str
    message: str


class SemanticAudit:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.frozen_path = Path(args.frozen).resolve() if args.frozen else self.root / "results" / "frozen_numbers.json"
        self.results_dir = self.root / "results"
        self.tables_dir = self.results_dir / "tables"
        self.audits_dir = self.results_dir / "audits"
        self.logs_dir = self.results_dir / "logs"
        self.paper_dir = self.root / "paper"
        self.planning_dir = self.root / "planning"
        self.findings: list[Finding] = []
        self.frozen: dict[str, Any] = {}
        self.tables: dict[str, list[dict[str, str]]] = {}
        self.text_blobs: dict[str, str] = {}
        self.metrics: dict[str, Any] = {}

    def run(self) -> int:
        self._load()
        self._collect_metrics()
        self._check_result_scale()
        self._check_baselines_and_heuristics()
        self._check_parameter_evidence()
        self._check_claim_logic()
        self._check_method_execution_mismatch()
        self._check_poc_decisions()
        self._emit()
        if self.args.write_report:
            self._write_report(Path(self.args.write_report))
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="ignore")

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, phase, message))

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, phase, message))

    def info(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("INFO", axis, phase, message))

    def _load(self) -> None:
        if self.frozen_path.exists():
            try:
                self.frozen = json.loads(self.read_text(self.frozen_path))
            except json.JSONDecodeError as exc:
                self.fail("result_semantics", "implementation", f"cannot parse frozen numbers: {exc}")
        else:
            self.fail("result_semantics", "implementation", f"missing frozen numbers: {self.rel(self.frozen_path)}")

        if self.tables_dir.exists():
            for path in sorted(self.tables_dir.glob("*.csv")):
                with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as fh:
                    reader = csv.DictReader(fh)
                    self.tables[path.name] = [_normalize_row(row) for row in reader]

        text_sources: list[Path] = []
        for folder in (self.audits_dir, self.logs_dir, self.planning_dir, self.paper_dir):
            if folder.exists():
                text_sources.extend(path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".tex", ".typ", ".txt", ".json"})
        for path in text_sources:
            self.text_blobs[self.rel(path)] = self.read_text(path)

    def _collect_metrics(self) -> None:
        numbers = list(_walk_numbers(self.frozen))
        finite_numbers = [value for _, value in numbers if math.isfinite(value)]
        text = self._all_text()
        heuristic_hits = self._heuristic_execution_hits()
        question_evidence = self._question_validation_evidence()
        self.metrics = {
            "frozen_exists": self.frozen_path.exists(),
            "numeric_count": len(finite_numbers),
            "max_abs_number": max((abs(value) for value in finite_numbers), default=None),
            "tables": sorted(self.tables),
            "has_baseline_table": "baseline_comparison.csv" in self.tables,
            "audit_files": sorted(path.name for path in self.audits_dir.glob("*")) if self.audits_dir.exists() else [],
            "history_tables": sorted(
                name for name in self.tables if _has_any(name, HEURISTIC_HISTORY_TERMS)
            ),
            "heuristic_mentions_raw": _count_terms(text, HEURISTIC_TERMS),
            "heuristic_terms": len(heuristic_hits),
            "heuristic_execution_hits": heuristic_hits,
            "question_validation_evidence": question_evidence,
            "evidence_terms": _count_terms(text, EVIDENCE_TERMS),
            "optimality_terms": _count_terms(text, OPTIMALITY_TERMS),
        }

    def _check_result_scale(self) -> None:
        for qid in sorted(key for key in self.frozen if re.fullmatch(r"q\d+", key)):
            data = self.frozen.get(qid)
            if not isinstance(data, dict):
                continue
            travel = _num(data.get("travel"))
            penalty = _num(data.get("penalty"))
            objective = _num(data.get("objective"))
            combined = _num(data.get("combined_objective"))
            routing = _num(data.get("routing_objective"))
            if travel and penalty is not None:
                ratio = penalty / max(abs(travel), 1.0)
                if ratio > 1000:
                    explanation = self._nearby_explanation(qid)
                    level = "WARN" if explanation else "FAIL"
                    message = (
                        f"{qid.upper()} penalty/travel ratio is {ratio:.1f} "
                        f"({penalty:g}/{travel:g}); needs quantitative explanation, bound, or stress audit"
                    )
                    self._add(level, "result_scale", "implementation", message)
                elif ratio > 100:
                    self.warn(
                        "result_scale",
                        "implementation",
                        f"{qid.upper()} penalty dominates travel by ratio {ratio:.1f}; ensure objective scaling is justified",
                    )
            if objective is not None and travel and objective / max(abs(travel), 1.0) > 10000:
                self.warn(
                    "result_scale",
                    "implementation",
                    f"{qid.upper()} objective is more than 10000x travel; result interpretation should discuss scale and units",
                )
            if combined is not None and routing is not None:
                fixed_gap = combined - routing
                settings = self.frozen.get("settings", {}) if isinstance(self.frozen.get("settings"), dict) else {}
                fixed_cost = _num(settings.get("vehicle_fixed_cost"))
                vehicle_count = _num(data.get("vehicle_count"))
                if fixed_cost is not None and vehicle_count is not None:
                    expected_gap = fixed_cost * vehicle_count
                    if abs(fixed_gap - expected_gap) > max(1e-6, 0.01 * max(abs(expected_gap), 1)):
                        self.fail(
                            "result_scale",
                            "implementation",
                            f"{qid.upper()} combined objective gap {fixed_gap:g} does not match fixed vehicle cost {expected_gap:g}",
                        )

    def _check_baselines_and_heuristics(self) -> None:
        baseline_rows = self.tables.get("baseline_comparison.csv", [])
        question_evidence = self.metrics.get("question_validation_evidence", {})
        for qid in sorted(key for key in self.frozen if re.fullmatch(r"q\d+", key)):
            if not question_evidence.get(qid.upper()):
                self.warn(
                    "validation_strength",
                    "implementation",
                    f"{qid.upper()} has no question-scoped baseline or validation evidence",
                )

        text = self._heuristic_audit_text()
        heuristic_present = bool(self.metrics.get("heuristic_execution_hits"))
        if heuristic_present:
            if not self.metrics.get("history_tables"):
                self.fail(
                    "validation_strength",
                    "implementation",
                    "executed heuristic method is documented but no convergence/history table was found",
                )
            if not _has_any(text, ["seed", "种子"]):
                self.fail(
                    "validation_strength",
                    "implementation",
                    "executed heuristic method lacks seed/settings evidence",
                )
            if not _has_any(text, ["多种子", "重复", "multi-seed", "多次", "稳定性"]):
                self.warn(
                    "validation_strength",
                    "implementation",
                    "executed heuristic results lack multi-seed or repeatability evidence",
                )
            if not baseline_rows:
                self.fail("validation_strength", "implementation", "executed heuristic results lack baseline comparison table")

        for name in self.metrics.get("history_tables", []):
            rows = self.tables.get(name, [])
            if len(rows) < 5:
                self.warn("validation_strength", "implementation", f"{name} has too few rows to demonstrate convergence trend")

    def _check_parameter_evidence(self) -> None:
        settings = self.frozen.get("settings", {}) if isinstance(self.frozen.get("settings"), dict) else {}
        important = [
            "alpha_early",
            "alpha_late",
            "vehicle_fixed_cost",
            "vehicle_capacity",
        ]
        text = self._all_text()
        sensitivity_rows = self.tables.get("q4_sensitivity.csv", [])
        for key in important:
            if key not in settings:
                continue
            human_key = key.replace("_", " ")
            has_explanation = key in text or human_key in text.lower()
            if not has_explanation:
                self.warn("parameter_evidence", "modeling", f"important parameter `{key}` appears in frozen settings but is not explained in text artifacts")
            if key in {"alpha_early", "alpha_late", "vehicle_fixed_cost"}:
                has_sensitivity = key in text and _has_any(text, ["灵敏度", "敏感", "sensitivity"]) or bool(sensitivity_rows and key == "vehicle_fixed_cost")
                if not has_sensitivity:
                    self.warn("parameter_evidence", "implementation", f"important weight/cost `{key}` lacks explicit sensitivity evidence")

        if sensitivity_rows:
            vehicle_counts = [_num(row.get("vehicle_count")) for row in sensitivity_rows]
            if len([item for item in vehicle_counts if item is not None]) < 3:
                self.warn("parameter_evidence", "implementation", "vehicle-count sensitivity has fewer than three scenarios")

    def _check_claim_logic(self) -> None:
        paper_text = self._paper_text()
        all_text = self._all_text()
        if _count_terms(paper_text, OPTIMALITY_TERMS):
            has_exact = _count_terms(all_text, EXACT_TERMS) > 0
            has_heuristic = bool(self.metrics.get("heuristic_execution_hits"))
            if has_heuristic and not has_exact:
                self.fail(
                    "claim_logic",
                    "paper",
                    "paper uses strong optimality wording while heuristic evidence is present and no proof/gap/certificate is detected",
                )

        conclusion_text = _extract_conclusionish(paper_text)
        if conclusion_text and not _has_any(conclusion_text, ["表", "图", "结果", "指标", "目标", "敏感", "审计", "验证"]):
            self.warn("claim_logic", "paper", "conclusion-like section has weak links to computed evidence")

        if _has_any(paper_text, ["建议", "推荐", "策略"]) and not _has_any(paper_text, ["情景", "场景", "指标", "方案", "目标值", "灵敏度"]):
            self.warn("claim_logic", "paper", "recommendation language appears without scenario/result indicator wording")

    def _check_method_execution_mismatch(self) -> None:
        settings = self.frozen.get("settings", {}) if isinstance(self.frozen.get("settings"), dict) else {}
        paper_text = self._paper_text()
        if settings.get("kaiwu_sdk_available") is False or settings.get("kaiwu_sdk_executed") is False:
            if _has_any(paper_text, ["Kaiwu SDK求解", "SDK求解结果", "量子求解得到", "量子退火得到"]):
                self.fail(
                    "method_execution",
                    "paper",
                    "paper appears to claim SDK/quantum execution, but frozen settings say Kaiwu SDK was not executed",
                )
            elif _has_any(paper_text, ["Kaiwu", "SDK", "量子"]):
                self.warn(
                    "method_execution",
                    "paper",
                    "paper mentions Kaiwu/SDK/quantum; ensure wording clearly says it was not executed if unavailable",
                )

    def _check_poc_decisions(self) -> None:
        poc_tables = [name for name in ("poc_results.csv", "method_screening.csv") if name in self.tables]
        if not poc_tables:
            return
        report_md = self.root / "checks" / "poc_decision_report.md"
        report_json = self.root / "checks" / "poc_decision_report.json"
        if not report_md.exists() and not report_json.exists():
            self.warn(
                "poc_decision",
                "implementation",
                f"PoC tables exist ({', '.join(poc_tables)}) but checks/poc_decision_report.md is missing",
            )
            return
        if report_json.exists():
            try:
                data = json.loads(self.read_text(report_json))
            except json.JSONDecodeError:
                data = {}
            for finding in data.get("findings", []) if isinstance(data, dict) else []:
                if not isinstance(finding, dict):
                    continue
                level = str(finding.get("level", "WARN")).upper()
                message = str(finding.get("message", "")).strip()
                method = str(finding.get("method", "")).strip()
                case = str(finding.get("case", "")).strip()
                if level in {"FAIL", "WARN"} and message:
                    self._add(level, "poc_decision", "modeling", f"{case} {method}: {message}")

    def _nearby_explanation(self, qid: str) -> bool:
        text = self._all_text()
        q_label = qid.upper()
        windows = []
        for match in re.finditer(q_label + r"|问题" + _qid_cn(qid), text, flags=re.I):
            start = max(0, match.start() - 800)
            end = min(len(text), match.end() + 1200)
            windows.append(text[start:end])
        if not windows:
            windows = [text]
        return any(_has_any(window, EXPLANATION_TERMS) for window in windows)

    def _question_validation_evidence(self) -> dict[str, list[str]]:
        qids = sorted(key.upper() for key in self.frozen if re.fullmatch(r"q\d+", key))
        evidence: dict[str, set[str]] = {qid: set() for qid in qids}

        for name, rows in self.tables.items():
            lower_name = name.lower()
            if not _has_any(lower_name, VALIDATION_ARTIFACT_TERMS):
                continue
            filename_match = re.search(r"(?:^|[_-])q(\d+)(?:[_-]|\.)", lower_name)
            if filename_match:
                qid = f"Q{int(filename_match.group(1))}"
                if qid in evidence:
                    evidence[qid].add(f"results/tables/{name}")
            for row in rows:
                for field in QUESTION_FIELDS:
                    qid = _parse_qid(row.get(field, ""))
                    if qid in evidence:
                        evidence[qid].add(f"results/tables/{name}")

        ledger_path = self.planning_dir / "result_ledger.json"
        try:
            ledger = json.loads(self.read_text(ledger_path)) if ledger_path.exists() else {}
        except json.JSONDecodeError:
            ledger = {}
        for entry in ledger.get("entries", []) if isinstance(ledger, dict) else []:
            if not isinstance(entry, dict):
                continue
            qid = _parse_qid(entry.get("question")) or _parse_qid(entry.get("key"))
            if qid not in evidence:
                continue
            for artifact in entry.get("evidence", []) if isinstance(entry.get("evidence"), list) else []:
                artifact_text = str(artifact).strip().replace("\\", "/")
                if _has_any(Path(artifact_text).name, VALIDATION_ARTIFACT_TERMS):
                    evidence[qid].add(artifact_text)

        return {qid: sorted(paths) for qid, paths in evidence.items()}

    def _heuristic_execution_hits(self) -> list[str]:
        hits: list[str] = []
        for path, text in self._heuristic_text_blobs().items():
            for term, start, end in _term_matches(text, HEURISTIC_TERMS):
                context = text[max(0, start - 80) : min(len(text), end + 80)]
                if _is_negated_heuristic(context, term):
                    continue
                if _is_heuristic_execution_context(context, term, path):
                    snippet = re.sub(r"\s+", " ", context).strip()
                    hits.append(f"{path}:{term}: {snippet[:180]}")
        return sorted(set(hits))

    def _heuristic_text_blobs(self) -> dict[str, str]:
        selected: dict[str, str] = {}
        planning_names = {
            "planning/modeling_plan.md",
            "planning/modeling_plan.json",
            "planning/method_route.md",
            "planning/method_route.json",
        }
        for path, text in self.text_blobs.items():
            if path in planning_names or path.startswith("paper/") or path.startswith("results/logs/"):
                selected[path] = text
        result_report = self.results_dir / "result_report.md"
        if result_report.exists():
            selected[self.rel(result_report)] = self.read_text(result_report)
        return selected

    def _heuristic_audit_text(self) -> str:
        parts = list(self._heuristic_text_blobs().values())
        for name in self.metrics.get("history_tables", []):
            parts.extend(json.dumps(row, ensure_ascii=False) for row in self.tables.get(name, []))
        return "\n".join(parts)

    def _all_text(self) -> str:
        parts = [json.dumps(self.frozen, ensure_ascii=False)]
        parts.extend(self.text_blobs.values())
        for rows in self.tables.values():
            parts.extend(json.dumps(row, ensure_ascii=False) for row in rows[:200])
        return "\n".join(parts)

    def _paper_text(self) -> str:
        return "\n".join(text for path, text in self.text_blobs.items() if path.startswith("paper/"))

    def _add(self, level: str, axis: str, phase: str, message: str) -> None:
        if level == "FAIL":
            self.fail(axis, phase, message)
        elif level == "WARN":
            self.warn(axis, phase, message)
        else:
            self.info(axis, phase, message)

    def _emit(self) -> None:
        for key, value in self.metrics.items():
            print(f"METRIC: {key}={value}")
        for finding in self.findings:
            print(f"{finding.level}: [{finding.axis}] {finding.phase}: {finding.message}")
        print(f"VERDICT: {self._verdict()}")

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def _write_report(self, path: Path) -> None:
        if not path.is_absolute():
            path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._markdown_report(), encoding="utf-8")
        print(f"INFO: wrote {self.rel(path)}")

    def _markdown_report(self) -> str:
        lines = [
            "# Mira Semantic Audit Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{self._verdict()}**",
            f"- Root: `{self.root}`",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        for key, value in self.metrics.items():
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value) if value else "-"
            else:
                rendered = str(value)
            lines.append(f"| {key} | {rendered} |")
        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        for item in self.findings:
            lines.append(f"| {item.level} | {item.axis} | {item.phase} | {item.message} |")
        lines.extend(
            [
                "",
                "## Routing",
                "",
                "- Result-scale failures return to implementation and possibly implementation.",
                "- Parameter and heuristic evidence failures return to implementation.",
                "- Claim-logic failures return to paper after evidence is fixed.",
                "- Do not fix semantic failures by editing frozen numbers by hand.",
                "",
            ]
        )
        return "\n".join(lines)


def _walk_numbers(value: Any, prefix: str = "") -> Iterable[tuple[str, float]]:
    if isinstance(value, dict):
        for key, item in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_numbers(item, new_prefix)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _walk_numbers(item, f"{prefix}[{idx}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield prefix, float(value)


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_row(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in row.items():
        clean_key = str(key).strip().lstrip("\ufeff")
        out[clean_key] = "" if value is None else str(value).strip()
    return out


def _count_terms(text: str, terms: list[str]) -> int:
    total = 0
    for term in terms:
        # Short algorithm acronyms such as SA/GA are easy to confuse with
        # ordinary English substrings in words like "sample" or "usage".
        # Count them only as standalone tokens while keeping the existing
        # substring behavior for longer method names and Chinese terms.
        if term in {"SA", "GA", "PSO"}:
            total += len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text))
        else:
            total += text.lower().count(term.lower())
    return total


def _term_matches(text: str, terms: list[str]) -> Iterable[tuple[str, int, int]]:
    for term in terms:
        if term in {"SA", "GA", "PSO"}:
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])"
            flags = 0
        else:
            pattern = re.escape(term)
            flags = re.I
        for match in re.finditer(pattern, text, flags=flags):
            yield term, match.start(), match.end()


def _is_negated_heuristic(context: str, term: str) -> bool:
    escaped = re.escape(term)
    negative_patterns = [
        rf"(?:未|不|没有|无需|并非|而非|拒绝)(?:采用|使用|运行|执行|依赖)?[^。；;\n]{{0,16}}{escaped}",
        rf"{escaped}[^。；;\n]{{0,16}}(?:未采用|未使用|不采用|不使用|不作为|仅作对比)",
        rf"(?:not|never|without)\s+(?:use|using|run|running)?[^.;\n]{{0,16}}{escaped}",
    ]
    return any(re.search(pattern, context, flags=re.I) for pattern in negative_patterns)


def _is_heuristic_execution_context(context: str, term: str, path: str) -> bool:
    if path.startswith("results/logs/"):
        return True
    escaped = re.escape(term)
    before = rf"(?:采用|使用|运行|执行|调用|实现|基于|通过|used?|using|ran|run|implemented)\s*[^。；;\n]{{0,24}}{escaped}"
    after = rf"{escaped}[^。；;\n]{{0,24}}(?:求解|优化|迭代|运行|收敛|搜索|算法|solver|iterations?|runs?)"
    structured = rf"(?:method|solver|algorithm|方法|求解器|算法)(?:_family)?\s*[:：=]\s*[^,;\n]{{0,24}}{escaped}"
    return any(re.search(pattern, context, flags=re.I) for pattern in (before, after, structured))


def _parse_qid(value: Any) -> str:
    match = re.search(r"(?:^|[^A-Za-z0-9])q\s*([1-9]\d*)(?:$|[^A-Za-z0-9])", str(value or ""), flags=re.I)
    return f"Q{int(match.group(1))}" if match else ""


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _qid_cn(qid: str) -> str:
    mapping = {"q1": "一", "q2": "二", "q3": "三", "q4": "四", "q5": "五"}
    return mapping.get(qid.lower(), qid)


def _extract_conclusionish(text: str) -> str:
    patterns = [
        r"\\section\{(?:结论|模型评价|模型的评价|总结)[^}]*\}(.*)",
        r"(?m)^#+\s*(?:结论|模型评价|总结).*$([\s\S]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if match:
            return match.group(1)[-3000:]
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--frozen", help="Frozen numbers JSON path")
    parser.add_argument("--write-report", help="Write markdown report to this path")
    return parser.parse_args()


def main() -> int:
    return SemanticAudit(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
