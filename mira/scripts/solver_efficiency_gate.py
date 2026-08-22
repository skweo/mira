#!/usr/bin/env python3
"""Check algorithm-complexity and solver-efficiency evidence for Mira papers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Finding:
    level: str
    axis: str
    message: str


ALGORITHM_TERMS = [
    "算法",
    "动态规划",
    "DP",
    "Bellman",
    "递推",
    "枚举",
    "穷举",
    "遍历",
    "全枚举",
    "启发式",
    "模拟退火",
    "遗传算法",
    "粒子群",
    "局部搜索",
    "蒙特卡洛",
    "Monte Carlo",
    "MILP",
    "整数规划",
    "YALMIP",
    "sdpvar",
    "求解器",
    "Gurobi",
    "CPLEX",
    "linprog",
    "grid search",
    "网格搜索",
]

ENUMERATION_TERMS = ["枚举", "穷举", "全枚举", "遍历", "2^", "2^{", "65536", "策略空间", "状态空间"]
DP_TERMS = ["动态规划", "DP", "Bellman", "状态转移", "递推", "边界条件", "回溯", "traceback"]
HEURISTIC_TERMS = ["启发式", "模拟退火", "遗传算法", "粒子群", "蚁群", "局部搜索", "SA", "GA", "PSO"]
SOLVER_TERMS = ["YALMIP", "sdpvar", "Gurobi", "CPLEX", "求解器", "solver", "MILP", "整数规划", "linprog", "intlinprog"]

COMPLEXITY_TERMS = [
    "时间复杂度",
    "空间复杂度",
    "复杂度",
    "O(",
    "O（",
    "Big-O",
    "operation count",
    "计算量",
    "状态数",
    "策略数",
    "变量数",
    "约束数",
]

SCALE_TERMS = [
    "规模",
    "状态数",
    "策略数",
    "变量数",
    "约束数",
    "样本数",
    "网格数",
    "2^",
    "65536",
    "n=",
    "N=",
    "m=",
    "维度",
]

RUNTIME_TERMS = [
    "运行时间",
    "耗时",
    "秒",
    "runtime",
    "seconds",
    "time.perf_counter",
    "tic",
    "toc",
    "CPU",
    "内存",
    "memory",
    "日志",
]

EFFICIENCY_TERMS = [
    "剪枝",
    "分层",
    "分解",
    "记忆化",
    "缓存",
    "状态压缩",
    "滚动数组",
    "向量化",
    "并行",
    "上界",
    "下界",
    "分支定界",
    "prune",
    "memo",
    "decomposition",
    "layered DP",
]

SOLVER_STATUS_TERMS = ["status", "gap", "MIPGap", "optimal", "feasible", "infeasible", "求解状态", "最优间隙", "容差", "可行解"]
CLAIM_STRENGTH_TERMS = ["全局最优", "严格最优", "最优解", "最优性", "best-found", "较优", "当前最优", "实验中最优"]
BOUND_PROOF_TERMS = ["证明", "上界", "下界", "gap", "完整枚举", "全枚举", "穷举", "solver status", "optimality", "证书"]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    metrics = collect_metrics(root, args)
    findings = review(metrics)
    payload = {
        "generated_at": now(),
        "root": str(root),
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for key, value in metrics.items():
        _print(f"METRIC: {key}={value}")
    for finding in findings:
        _print(f"{finding.level}: [{finding.axis}] {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    paper = resolve_paper(root, args.paper)
    evidence = efficiency_evidence(root)
    text = "\n".join(
        [
            read_text(paper),
            read_text(root / "paper" / "main_final_checked.txt"),
            read_text(root / "planning" / "modeling_plan.md"),
            read_text(root / "planning" / "method_route.md"),
            read_text(root / "planning" / "validation_plan.md"),
            read_text(root / "results" / "result_report.md"),
            read_text(root / "results" / "frozen_numbers.json"),
            read_text(root / "checks" / "model_solver_consistency_report.md"),
            collect_code_text(root),
        ]
    )
    return {
        "paper": rel(root, paper) if paper.exists() else str(paper),
        "algorithm_terms": count_terms(text, ALGORITHM_TERMS),
        "enumeration_terms": count_terms(text, ENUMERATION_TERMS),
        "dp_terms": count_terms(text, DP_TERMS),
        "heuristic_terms": count_terms(text, HEURISTIC_TERMS),
        "solver_terms": count_terms(text, SOLVER_TERMS),
        "complexity_terms": count_terms(text, COMPLEXITY_TERMS),
        "scale_terms": count_terms(text, SCALE_TERMS),
        "runtime_terms": count_terms(text, RUNTIME_TERMS),
        "efficiency_terms": count_terms(text, EFFICIENCY_TERMS),
        "solver_status_terms": count_terms(text, SOLVER_STATUS_TERMS),
        "claim_strength_terms": count_terms(text, CLAIM_STRENGTH_TERMS),
        "bound_or_proof_terms": count_terms(text, BOUND_PROOF_TERMS),
        "efficiency_artifacts": evidence["files"],
        "efficiency_rows": evidence["rows"],
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    has_artifact = metrics["efficiency_rows"] > 0 or bool(metrics["efficiency_artifacts"])
    has_complexity = metrics["complexity_terms"] >= 2 or has_artifact
    has_scale = metrics["scale_terms"] >= 2 or has_artifact
    has_runtime = metrics["runtime_terms"] >= 1 or metrics["solver_status_terms"] >= 1 or has_artifact

    if metrics["algorithm_terms"] < 3:
        findings.append(Finding("INFO", "solver_efficiency", "no substantial algorithm-efficiency trigger detected"))
        return findings

    if not has_complexity:
        findings.append(Finding("FAIL", "algorithm_complexity", "nontrivial algorithms appear without time/space complexity, operation count, or complexity artifact"))
    if not has_scale:
        findings.append(Finding("WARN", "algorithm_scale", "algorithm route appears without state/strategy/variable/constraint/sample scale evidence"))
    if not has_runtime:
        findings.append(Finding("WARN", "runtime_evidence", "algorithm route appears without runtime, memory, solver-status, or feasibility evidence"))

    if metrics["enumeration_terms"] >= 2:
        if not has_scale:
            findings.append(Finding("FAIL", "enumeration_feasibility", "enumeration/exhaustive search is used without search-space size"))
        if not has_complexity:
            findings.append(Finding("FAIL", "enumeration_feasibility", "enumeration/exhaustive search is used without per-candidate cost, operation count, or complexity explanation"))
        if metrics["efficiency_terms"] == 0 and not has_artifact:
            findings.append(Finding("WARN", "enumeration_efficiency", "enumeration is used without pruning, layered DP, decomposition, or explicit small-scale waiver"))

    if metrics["dp_terms"] >= 3:
        if not has_scale:
            findings.append(Finding("FAIL", "dp_complexity", "dynamic-programming language appears without state-space size"))
        if not has_complexity:
            findings.append(Finding("FAIL", "dp_complexity", "dynamic-programming language appears without transition complexity or memory-cost explanation"))

    if metrics["heuristic_terms"] >= 2 and not has_runtime:
        findings.append(Finding("WARN", "heuristic_efficiency", "heuristic search appears without iteration budget, stopping rule, runtime, or stability evidence"))

    if metrics["solver_terms"] >= 2 and metrics["solver_status_terms"] == 0 and not has_artifact:
        findings.append(Finding("WARN", "solver_status", "solver-backed optimization appears without status, gap/tolerance, variable/constraint scale, or runtime evidence"))

    if metrics["claim_strength_terms"] >= 2 and metrics["heuristic_terms"] >= 2 and metrics["bound_or_proof_terms"] < 2:
        findings.append(Finding("FAIL", "claim_strength", "strong optimality language appears near heuristic/search terms without proof, bound, solver gap, or full enumeration evidence"))

    return findings


def efficiency_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    names = [
        "solver_efficiency.csv",
        "algorithm_complexity.csv",
        "complexity_analysis.csv",
        "runtime_profile.csv",
        "enumeration_feasibility.csv",
    ]
    seen: set[str] = set()
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(f"results/tables/{name}")
            rows += count
            seen.add(name)
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in seen:
                continue
            if any(token in lower for token in ["complexity", "efficiency", "runtime", "profile", "solver"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(f"results/tables/{path.name}")
                    rows += count
    for rel_path in ["planning/algorithm_complexity.md", "planning/solver_efficiency.md"]:
        path = root / rel_path
        if path.exists() and read_text(path).strip():
            files.append(rel_path)
    return {"rows": rows, "files": sorted(set(files))}


def collect_code_text(root: Path) -> str:
    code_dir = root / "code"
    if not code_dir.exists():
        return ""
    chunks: list[str] = []
    suffixes = {".py", ".m", ".jl", ".r", ".cpp", ".c", ".h", ".md", ".txt", ".log"}
    for path in sorted(code_dir.rglob("*"))[:120]:
        if path.is_file() and path.suffix.lower() in suffixes and path.stat().st_size <= 200_000:
            chunks.append(read_text(path)[:12000])
        if sum(len(item) for item in chunks) > 300_000:
            break
    return "\n".join(chunks)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Solver Efficiency Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(value)} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    if not payload["findings"]:
        lines.append("| INFO | solver_efficiency | no findings |")
    lines.append("")
    return "\n".join(lines)


def resolve_paper(root: Path, paper_arg: str | None) -> Path:
    candidates = []
    if paper_arg:
        candidates.append(resolve_path(root, paper_arg))
    candidates.extend([root / "paper" / "main_final.tex", root / "paper" / "main.tex", root / "paper" / "main.md"])
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def count_terms(text: str, terms: Iterable[str]) -> int:
    lower = text.lower()
    total = 0
    for term in terms:
        term_lower = term.lower()
        if re.fullmatch(r"[a-z0-9_]+", term_lower):
            total += len(re.findall(rf"\b{re.escape(term_lower)}\b", lower))
        else:
            total += lower.count(term_lower)
    return total


def count_data_rows(text: str) -> int:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0
    return max(0, len(lines) - 1)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    parser.add_argument("--paper", help="Paper tex/typ/md path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
