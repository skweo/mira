#!/usr/bin/env python3
"""Audit Mira's knowledge retrieval -> application -> validation loop."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


RISK_TERMS = [
    "heuristic",
    "local search",
    "simulated annealing",
    "sa",
    "ga",
    "pso",
    "routing",
    "route",
    "vrp",
    "vrptw",
    "tsptw",
    "time window",
    "penalty",
    "calibration",
    "inverse",
    "machine learning",
    "ml",
    "regression",
    "pca",
    "principal component",
    "factor analysis",
    "clustering",
    "decomposition",
    "ode",
    "differential equation",
    "sensitivity",
    "game theory",
    "nash",
    "multiobjective",
    "multi-objective",
    "pareto",
    "nsga",
    "queueing",
    "queue",
    "logistic",
    "logit",
    "binary classification",
    "svm",
    "support vector",
    "kernel",
    "miv",
    "mean impact value",
    "feature importance",
    "cellular automata",
    "traffic flow",
    "nasch",
    "lane changing",
    "finite capacity",
    "blocking probability",
    "loss probability",
    "yalmip",
    "sdpvar",
    "solver status",
    "grid search",
    "coarse scan",
    "discrete scan",
    "integer second",
    "integer-second",
    "extremum",
    "peak",
    "maximum",
    "minimum",
    "continuous refinement",
    "collision",
    "separating axis",
    "sat",
    "rigid chain",
    "chain kinematics",
    "spiral",
    "no-wait",
    "回归",
    "主成分",
    "因子分析",
    "微分方程",
    "灵敏度",
    "敏感性",
    "博弈",
    "纳什",
    "多目标",
    "帕累托",
    "排队",
    "逻辑回归",
    "二分类",
    "支持向量机",
    "核函数",
    "变量筛选",
    "平均影响值",
    "特征重要性",
    "交通流",
    "随机慢化",
    "换道",
    "有限容量",
    "损失率",
    "阻塞概率",
    "优化建模",
    "求解器状态",
    "网格扫描",
    "离散扫描",
    "整数秒",
    "极值",
    "峰值",
    "碰撞",
    "分离轴",
    "刚性链",
    "鍚彂",
    "璺緞",
    "鏃堕棿",
    "鎯╃綒",
]

VALIDATION_SIGNALS = {
    "feasibility_audit": ["audit", "feasibility", "capacity", "uniqueness", "arrival", "departure", "violation", "瀹¤"],
    "baseline": ["baseline", "comparison", "greedy", "nearest", "edd", "dp", "relaxed", "鍩虹嚎", "瀵规瘮"],
    "decomposition": ["travel", "penalty", "objective", "component", "ratio", "decomposition", "early", "late"],
    "multi_seed": ["seed", "multi", "history", "run", "std", "mean", "stability", "澶氱"],
    "convergence": ["history", "iteration", "convergence", "best_objective", "cooling", "temperature", "鏀舵暃"],
    "sensitivity": ["sensitivity", "perturb", "alpha", "beta", "coefficient", "fixed_cost", "鐏垫晱"],
    "repair": ["repair", "destroy", "relocate", "swap", "2-opt", "or-opt", "cluster", "lexicographic"],
    "regression_diagnostics": ["residual", "vif", "r2", "adjusted r", "heteroscedastic", "cross-validation", "holdout", "残差", "共线"],
    "cluster_validation": ["silhouette", "elbow", "dbscan", "cluster count", "stability", "簇", "轮廓", "肘部"],
    "pca_factor_diagnostics": ["kmo", "bartlett", "eigenvalue", "loading", "variance explained", "varimax", "载荷", "方差贡献"],
    "ode_validation": ["step size", "step-size", "tolerance", "rk45", "radau", "solve_ivp", "initial condition", "boundary condition", "stiff", "步长", "初始条件"],
    "pareto_validation": ["pareto", "non-dominated", "nondominated", "front", "crowding", "hypervolume", "hv", "帕累托", "非支配"],
    "queue_validation": ["little", "erlang", "utilization", "waiting time", "service level", "warm-up", "replication", "排队", "等待", "利用率"],
    "geometry_audit": ["arc length", "segment length", "rigid", "chain", "handle distance", "spacing", "coordinate", "spiral", "弧长", "刚性", "节长", "螺线"],
    "collision_audit": ["collision", "separating axis", "sat", "overlap", "oriented rectangle", "obb", "intersection", "碰撞", "分离轴", "重叠"],
    "continuous_refinement": ["refined value", "refined time", "refined peak", "refinement log", "bounded local", "sub-second", "brent", "minimize_scalar", "root_scalar", "ternary", "golden", "bisection", "bracket", "local maximum", "peak time", "neighbor interval", "局部加密", "连续加密", "三分", "黄金"],
    "classification_validation": ["confusion matrix", "accuracy", "precision", "recall", "f1", "roc", "auc", "specificity", "sensitivity", "cross-validation", "holdout", "混淆矩阵", "准确率", "召回率"],
    "feature_importance_validation": ["miv", "mean impact value", "feature importance", "permutation", "ablation", "rank stability", "perturbation size", "变量筛选", "特征重要性", "平均影响值"],
    "traffic_ca_validation": ["vehicle count", "collision", "flow", "density", "average speed", "lane change", "random slowdown", "fundamental diagram", "multi-seed", "车流密度", "随机慢化", "换道"],
    "finite_queue_validation": ["blocking", "loss probability", "time-weighted", "queue length distribution", "arrival rate", "service rate", "warm-up", "replication", "损失率", "阻塞概率", "队长概率"],
    "solver_status": ["sol.problem", "solver status", "solver log", "yalmiperror", "gap", "infeasible", "unbounded", "runtime", "求解器状态", "不可行"],
}


@dataclass
class Finding:
    level: str
    axis: str
    phase: str
    message: str


class KnowledgeApplicationAudit:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.planning = self.root / "planning"
        self.results = self.root / "results"
        self.checks = self.root / "checks"
        self.revisions = self.root / "revisions"
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}
        self.knowledge_json: dict[str, Any] = {}
        self.knowledge_md = ""
        self.modeling_plan = ""
        self.project_text = ""

    def run(self) -> int:
        self._load()
        self._collect_metrics()
        if not self.metrics["risk_triggered"]:
            self._write_outputs()
            self._emit()
            return 0
        self._check_retrieval()
        self._check_modeling_application()
        self._check_validation_evidence()
        self._check_failure_repairs()
        self._write_outputs()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _load(self) -> None:
        self.knowledge_md = self._read(self.planning / "knowledge_injection.md")
        json_path = self.planning / "knowledge_injection.json"
        if json_path.exists():
            try:
                self.knowledge_json = json.loads(self._read(json_path))
            except json.JSONDecodeError as exc:
                self.fail("knowledge_retrieval", "modeling", f"cannot parse planning/knowledge_injection.json: {exc}")
        self.modeling_plan = self._read(self.planning / "modeling_plan.md")
        self.project_text = self._collect_project_text()

    def _collect_metrics(self) -> None:
        context = "\n".join(
            [
                self.modeling_plan,
                self._read(self.planning / "problem_analysis.md"),
                self._read(self.revisions / "iteration_report.md"),
                self._read(self.checks / "semantic_audit_report.md"),
                self._read(self.checks / "result_quality_report.md"),
                self._read(self.checks / "quality_balance_report.md"),
            ]
        )
        hits = self.knowledge_json.get("hits", []) if isinstance(self.knowledge_json, dict) else []
        card_paths = [str(hit.get("path", "")) for hit in hits if isinstance(hit, dict)]
        card_signal_text = self._card_signal_text(hits)
        self.metrics = {
            "risk_triggered": _has_any(context, RISK_TERMS),
            "retrieval_report_exists": bool(self.knowledge_md.strip()),
            "retrieval_json_exists": bool(self.knowledge_json),
            "retrieved_card_count": len(card_paths),
            "retrieved_cards": card_paths,
            "retrieved_card_signals": sorted(extract_signal_terms(card_signal_text))[:80],
            "modeling_plan_has_domain_table": "domain knowledge used" in self.modeling_plan.lower(),
            "validation_signals": {name: self._signal_paths(terms) for name, terms in VALIDATION_SIGNALS.items()},
            "failure_signs_detected": self._failure_signs_detected(context),
            "discrete_extremum_risk": self._has_discrete_extremum_risk(context),
        }

    def _check_retrieval(self) -> None:
        if not self.metrics["retrieval_report_exists"] and not self.metrics["retrieval_json_exists"]:
            self.fail(
                "knowledge_retrieval",
                "modeling",
                "risky modeling or iteration findings are present, but planning/knowledge_injection.md/json is missing",
            )
            return
        if self.metrics["retrieved_card_count"] == 0 and "no_relevant_card_found" not in (self.knowledge_md + self.modeling_plan):
            self.fail(
                "knowledge_retrieval",
                "modeling",
                "knowledge retrieval ran but selected no card and did not record no_relevant_card_found",
            )

    def _check_modeling_application(self) -> None:
        if not self.metrics["modeling_plan_has_domain_table"]:
            self.fail(
                "knowledge_application",
                "modeling",
                "planning/modeling_plan.md lacks a Domain Knowledge Used table",
            )
        for card_path in self.metrics["retrieved_cards"]:
            card_name = Path(card_path).name
            if card_name and card_name not in self.modeling_plan and card_path not in self.modeling_plan:
                self.warn(
                    "knowledge_application",
                    "modeling",
                    f"retrieved card `{card_name}` is not traceably named in planning/modeling_plan.md",
                )
        required_terms = ["operators", "validation", "repair", "sensitivity", "baseline"]
        missing = [term for term in required_terms if term not in self.modeling_plan.lower()]
        if missing:
            self.warn(
                "knowledge_application",
                "modeling",
                "modeling plan does not visibly carry card obligations: " + ", ".join(missing),
            )

    def _check_validation_evidence(self) -> None:
        if self.metrics["retrieved_card_count"] == 0:
            return
        signals = self.metrics["validation_signals"]
        required = self._required_validation_groups()
        if not required:
            required = ["baseline"]
        if _has_any(self.project_text, ["heuristic", "local search", "simulated annealing", "sa", "ga", "pso"]):
            required.extend(["multi_seed", "convergence"])
        if _has_any(self.project_text, ["penalty", "coefficient", "alpha", "beta", "fixed_cost", "objective scale"]):
            required.append("sensitivity")
        missing = sorted({name for name in required if not signals.get(name)})
        if missing:
            self.fail(
                "knowledge_validation",
                "implementation",
                "retrieved knowledge cards require validation evidence, but these signal groups are missing: " + ", ".join(missing),
            )

    def _check_failure_repairs(self) -> None:
        failure_signs = self.metrics.get("failure_signs_detected", [])
        if not failure_signs:
            return
        repair_paths = self.metrics["validation_signals"].get("repair", [])
        waiver = _has_any(self.project_text, ["waived", "waiver", "鏀惧純", "豁免", "limitation accepted"])
        if not repair_paths and not waiver:
            self.fail(
                "knowledge_repair",
                "implementation",
                "knowledge-card failure signs are present but no repair-move evidence or waiver was found: " + ", ".join(failure_signs),
            )

    def _failure_signs_detected(self, context: str) -> list[str]:
        signs: list[str] = []
        lower = context.lower()
        if "penalty/travel" in lower or "scale-dominating" in lower or "objective/travel" in lower:
            signs.append("penalty/objective scale dominance")
        if "unstable" in lower or "vary by" in lower or "multi-run spread" in lower:
            signs.append("heuristic instability")
        if "time-window" in lower and ("violation" in lower or "infeasible" in lower):
            signs.append("time-window infeasibility")
        if "arbitrary" in lower and ("parameter" in lower or "weight" in lower):
            signs.append("arbitrary parameter")
        if self._has_discrete_extremum_risk(context):
            signs.append("discrete scan used for continuous extremum/peak")
        return signs

    def _required_validation_groups(self) -> list[str]:
        paths_text = "\n".join(self.metrics.get("retrieved_cards", [])).lower()
        card_text = "\n".join(self.metrics.get("retrieved_card_signals", [])).lower()
        context = "\n".join([paths_text, card_text, self.modeling_plan]).lower()
        required: list[str] = []
        if _has_any(paths_text + context, ["routing", "time-window", "vehicle", "vrp", "optimization", "genetic", "annealing", "pso", "heuristic"]):
            required.extend(["feasibility_audit", "baseline", "decomposition"])
        if _has_any(paths_text + context, ["regression", "ols", "ridge", "lasso", "回归"]):
            required.extend(["regression_diagnostics", "baseline"])
        if _has_any(paths_text + context, ["logistic", "logit", "binary-classification", "binary classification", "svm", "support-vector", "classification", "逻辑回归", "二分类", "支持向量机"]):
            required.extend(["classification_validation", "baseline"])
        if _has_any(paths_text + context, ["clustering", "cluster", "dbscan", "k-means", "聚类"]):
            required.extend(["cluster_validation", "baseline"])
        if _has_any(paths_text + context, ["pca", "factor-analysis", "factor analysis", "主成分", "因子分析"]):
            required.append("pca_factor_diagnostics")
        if _has_any(paths_text + context, ["ode", "differential", "continuous-system", "微分方程"]):
            required.append("ode_validation")
        if _has_any(paths_text + context, ["sensitivity", "sobol", "morris", "灵敏度", "敏感性"]):
            required.append("sensitivity")
        if _has_any(paths_text + context, ["multiobjective", "multi-objective", "nsga", "pareto", "多目标", "帕累托"]):
            required.extend(["pareto_validation", "baseline"])
        if _has_any(paths_text + context, ["queueing", "queue", "erlang", "排队"]):
            required.extend(["queue_validation", "baseline"])
        if _has_any(paths_text + context, ["miv", "mean-impact", "mean impact value", "feature-importance", "variable-screening", "变量筛选", "平均影响值", "特征重要性"]):
            required.append("feature_importance_validation")
        if _has_any(paths_text + context, ["traffic-cellular", "traffic-ca", "nasch", "traffic flow", "lane-changing", "random-slowdown", "交通流", "随机慢化", "换道"]):
            required.extend(["traffic_ca_validation", "multi_seed"])
        if _has_any(paths_text + context, ["m/m/s/k", "finite-capacity", "blocking", "loss-probability", "有限容量", "损失率", "阻塞概率"]):
            required.extend(["finite_queue_validation", "queue_validation"])
        if _has_any(paths_text + context, ["yalmip", "sdpvar", "binvar", "intvar", "solver-status", "sol.problem", "求解器状态", "优化建模"]):
            required.extend(["solver_status", "feasibility_audit"])
        if _has_any(paths_text + context, ["rigid-chain", "chain-kinematics", "rigid-segment", "linked-segment", "fixed-distance", "spiral", "刚性链", "刚性杆", "固定间距"]):
            required.append("geometry_audit")
        if _has_any(paths_text + context, ["collision", "separating-axis", "sat", "oriented-rectangle", "碰撞", "分离轴"]):
            required.append("collision_audit")
        if self.metrics.get("discrete_extremum_risk") or _has_any(paths_text + context, ["continuous-extremum", "extremum", "peak", "maximum", "minimum", "integer-second", "离散扫描", "峰值"]):
            required.append("continuous_refinement")
        return required

    def _card_signal_text(self, hits: Any) -> str:
        if not isinstance(hits, list):
            return ""
        parts: list[str] = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            parts.append(str(hit.get("path", "")))
            parts.append(str(hit.get("title", "")))
            matched = hit.get("matched_terms", [])
            if isinstance(matched, list):
                parts.extend(str(item) for item in matched)
            sections = hit.get("sections", {})
            if isinstance(sections, dict):
                for name in ["Tags", "Problem Patterns", "Validation Requirements", "Failure Signs", "Repair Moves"]:
                    parts.append(str(sections.get(name, ""))[:3000])
        return "\n".join(parts)

    def _has_discrete_extremum_risk(self, text: str) -> bool:
        lower = text.lower()
        scan_terms = [
            "coarse scan",
            "grid scan",
            "grid search",
            "discrete scan",
            "integer second",
            "integer-second",
            "integer time",
            "step=1",
            "dt=1",
            "one-second",
            "网格扫描",
            "网格搜索",
            "离散扫描",
            "整数秒",
            "秒级扫描",
        ]
        extremum_terms = [
            "maximum",
            "minimum",
            "max ",
            "min ",
            "peak",
            "extremum",
            "optimum",
            "threshold",
            "峰值",
            "极值",
            "最大值",
            "最小值",
            "最优",
            "临界",
        ]
        refined_terms = [
            "continuous refinement",
            "local refinement",
            "refined value",
            "refined time",
            "refined peak",
            "refinement log",
            "sub-second",
            "brent",
            "minimize_scalar",
            "root_scalar",
            "ternary",
            "golden",
            "bisection",
            "bounded local",
            "局部加密",
            "连续加密",
            "三分",
            "黄金分割",
        ]
        return _has_any(lower, scan_terms) and _has_any(lower, extremum_terms) and not _has_positive_refinement_evidence(lower, refined_terms)

    def _signal_paths(self, terms: list[str]) -> list[str]:
        out: list[str] = []
        for path in self._validation_files():
            text = self._read(path)
            if _has_any(text, terms):
                out.append(self.rel(path))
        return out[:12]

    def _collect_project_text(self) -> str:
        parts: list[str] = []
        for path in self._evidence_files():
            parts.append(self._read(path)[:40000])
        return "\n".join(parts)

    def _evidence_files(self) -> list[Path]:
        files: list[Path] = []
        for rel in ["planning", "results", "checks", "revisions", "code"]:
            folder = self.root / rel
            if not folder.exists():
                continue
            files.extend(
                path
                for path in folder.rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".md", ".txt", ".json", ".csv", ".py", ".tex", ".typ"}
                and not self._is_self_audit_output(path)
                and not self._is_retrieval_output(path)
            )
        return sorted(files)

    def _validation_files(self) -> list[Path]:
        files: list[Path] = []
        for rel in ["results", "code"]:
            folder = self.root / rel
            if folder.exists():
                files.extend(
                    path
                    for path in folder.rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in {".md", ".txt", ".json", ".csv", ".py"}
                    and not self._is_self_audit_output(path)
                )
        modeling_plan = self.planning / "modeling_plan.md"
        if modeling_plan.exists():
            files.append(modeling_plan)
        return sorted(files)

    def _is_self_audit_output(self, path: Path) -> bool:
        return path.name in {"knowledge_application_report.md", "knowledge_application_report.json"}

    def _is_retrieval_output(self, path: Path) -> bool:
        return path.name in {"knowledge_injection.md", "knowledge_injection.json"}

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
        verdict = self._verdict()
        lines = [
            "# Mira Knowledge Application Audit",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{verdict}**",
            f"- Root: `{self.root}`",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        for key, value in self.metrics.items():
            lines.append(f"| {key} | {_escape_table(json.dumps(value, ensure_ascii=False))} |")
        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        if self.findings:
            for item in self.findings:
                lines.append(f"| {item.level} | {item.axis} | {item.phase} | {_escape_table(item.message)} |")
        else:
            lines.append("| INFO | knowledge_application | - | knowledge loop has no blocking findings |")
        lines.extend(
            [
                "",
                "## Gate Use",
                "",
                "- Run after knowledge retrieval, code execution, and result analysis for risky contest-final models.",
                "- A card hit is an obligation: it must appear in modeling, code/result validation, or a visible waiver.",
                "- Failure signs from a card require repair-move evidence before final delivery.",
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
            _print(f"METRIC: {key}={_compact(value)}")
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

    def _read(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8-sig", errors="ignore")

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, phase, message))

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, phase, message))


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(_term_present(lower, term.lower()) for term in terms)


def extract_signal_terms(text: str) -> set[str]:
    lower = text.lower()
    ascii_terms = re.findall(r"[a-z0-9][a-z0-9+\-_/]{1,}", lower)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", lower)
    return {term.strip("-_/") for term in [*ascii_terms, *chinese_terms] if term.strip("-_/")}


def _term_present(lower: str, term: str) -> bool:
    if not term:
        return False
    # Method names must be lexical signals, not arbitrary substrings. Without
    # this boundary rule, `ridge` matched `bridge` and `ode` matched `model`,
    # creating unrelated validation obligations.
    if term.isascii() and term[0].isalnum() and term[-1].isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lower))
    return term in lower


def _has_positive_refinement_evidence(lower: str, terms: list[str]) -> bool:
    for term in terms:
        needle = term.lower()
        start = 0
        while True:
            idx = lower.find(needle, start)
            if idx < 0:
                break
            prefix = lower[max(0, idx - 40) : idx]
            if not _has_any(prefix, ["no", "not", "without", "lacks", "missing", "没有", "未", "无"]):
                return True
            start = idx + len(needle)
    return False


def _escape_table(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _compact(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 700 else text[:700] + " ..."


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
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return KnowledgeApplicationAudit(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
