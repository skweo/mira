#!/usr/bin/env python3
"""Audit Mira's scenario-experiment and showcase-presentation layer."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


RULE_REFERENCE = "references/showcase-scenario-rules.md"


@dataclass
class Finding:
    level: str
    axis: str
    message: str


PROCESS_TERMS = [
    "流程",
    "阶段",
    "步骤",
    "链路",
    "状态转移",
    "决策流程",
    "生产流程",
    "求解流程",
    "装配树",
    "循环",
    "process",
    "workflow",
    "pipeline",
    "state transition",
    "decision flow",
]

SCENARIO_TERMS = [
    "仿真",
    "模拟",
    "场景",
    "案例",
    "批量",
    "批次",
    "样本",
    "扰动",
    "抽样",
    "蒙特卡洛",
    "随机",
    "后验",
    "稳健",
    "敏感性",
    "压力测试",
    "极端情形",
    "simulation",
    "scenario",
    "case study",
    "batch",
    "Monte Carlo",
    "posterior",
    "perturbation",
    "stress test",
    "sensitivity",
]

SEARCH_TERMS = [
    "收敛",
    "迭代",
    "运行时间",
    "耗时",
    "搜索",
    "枚举",
    "遍历",
    "策略空间",
    "候选",
    "退火",
    "遗传",
    "粒子群",
    "动态规划",
    "convergence",
    "iteration",
    "runtime",
    "search",
    "enumeration",
    "simulated annealing",
    "GA",
    "PSO",
    "DP",
]

BATCH_TERMS = [
    "批量",
    "批次",
    "企业",
    "工厂",
    "生产线",
    "元/件",
    "件",
    "万元",
    "一万",
    "10000",
    "执行",
    "管理",
    "KPI",
    "batch",
    "factory",
    "enterprise",
    "per unit",
]

VISUAL_ROLE_TERMS = [
    "define",
    "derive",
    "compare",
    "validate",
    "explain",
    "decide",
    "定义",
    "推导",
    "比较",
    "对比",
    "验证",
    "解释",
    "决策",
]

PROCESS_FILE_TOKENS = [
    "flow",
    "process",
    "pipeline",
    "decision",
    "state",
    "tree",
    "cycle",
    "workflow",
    "route",
    "framework",
    "solution",
]

SCENARIO_FILE_TOKENS = [
    "scenario",
    "simulation",
    "simulate",
    "monte",
    "posterior",
    "sampling",
    "stability",
    "sensitivity",
    "threshold",
    "convergence",
    "iteration",
    "runtime",
    "trace",
    "stress",
    "batch",
    "policy_gap",
    "top_policy",
    "oc",
]


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
        path = resolve(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for key, value in metrics.items():
        _print(f"METRIC: {key}={value}")
    for finding in findings:
        _print(f"{finding.level}: [{finding.axis}] {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve(root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    files = paper_files(root, args.paper)
    paper_text = "\n".join(read_text(path) for path in files)
    checked_text = read_text(root / "paper" / "main_final_checked.txt")
    figure_index = read_text(root / "figures" / "figure_index.md")
    diagram_index = read_text(root / "diagrams" / "diagram_index.md")
    storyboard_text = read_text(root / "planning" / "figure_storyboard.md")
    evidence_text = read_text(root / "planning" / "evidence_plan.md")
    result_report = read_text(root / "results" / "result_report.md")
    combined = "\n".join([paper_text, checked_text, figure_index, diagram_index, storyboard_text, evidence_text, result_report])

    figure_files = media_files(root / "figures")
    diagram_files = media_files(root / "diagrams")
    scenario_artifacts = scenario_files(root)
    algorithm_need = count_terms(combined, SEARCH_TERMS)

    return {
        "paper_files": [rel(root, path) for path in files],
        "paper_chars": len(strip_tex(paper_text)),
        "includegraphics_count": len(re.findall(r"\\includegraphics", paper_text)),
        "figure_file_count": len(figure_files),
        "diagram_file_count": len(diagram_files),
        "figure_index_rows": count_index_rows(figure_index),
        "diagram_index_rows": count_index_rows(diagram_index),
        "storyboard_exists": bool(storyboard_text.strip()),
        "storyboard_role_terms": count_terms(storyboard_text + "\n" + figure_index + "\n" + diagram_index, VISUAL_ROLE_TERMS),
        "process_diagram_files": [rel(root, path) for path in diagram_files if has_token(path.name, PROCESS_FILE_TOKENS)],
        "process_terms": count_terms(combined, PROCESS_TERMS),
        "scenario_terms": count_terms(combined, SCENARIO_TERMS),
        "scenario_artifacts": scenario_artifacts["files"],
        "scenario_artifact_rows": scenario_artifacts["rows"],
        "search_terms": algorithm_need,
        "search_process_terms": count_terms(combined, SEARCH_TERMS),
        "batch_terms": count_terms(combined, BATCH_TERMS),
        "has_artifact_manifest": (root / "checks" / "artifact_manifest.json").exists(),
        "has_result_ledger": (root / "planning" / "result_ledger.md").exists() or (root / "planning" / "result_ledger.json").exists(),
        "has_frozen_numbers": (root / "results" / "frozen_numbers.json").exists(),
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not metrics["paper_files"]:
        findings.append(Finding("FAIL", "paper_source", "no final paper source file was found"))
        return findings

    process_signal = metrics["process_terms"] + len(metrics["process_diagram_files"]) * 3 + metrics["diagram_index_rows"]
    if process_signal < 4:
        findings.append(Finding("WARN", "stage_storyboard", "weak stage/process storyboard; add flow, state, or decision-process diagrams for the model chain"))

    scenario_signal = metrics["scenario_terms"] + metrics["scenario_artifact_rows"] + len(metrics["scenario_artifacts"]) * 2
    if scenario_signal < 6:
        findings.append(Finding("WARN", "scenario_experiments", "weak scenario/simulation/perturbation evidence; add validation or batch-case experiments when feasible"))

    if metrics["search_terms"] >= 4 and metrics["scenario_artifact_rows"] == 0 and metrics["search_process_terms"] < 8:
        findings.append(Finding("WARN", "search_process", "algorithm/search language appears without enough convergence, iteration, top-candidate, or runtime evidence"))

    if metrics["batch_terms"] < 3 and metrics["scenario_terms"] >= 3:
        findings.append(Finding("WARN", "batch_scale", "scenario results are present but batch-scale or enterprise interpretation is weak"))

    if metrics["includegraphics_count"] >= 6 and not metrics["storyboard_exists"]:
        findings.append(Finding("WARN", "figure_storyboard", "many figures are included but planning/figure_storyboard.md was not found"))
    elif metrics["includegraphics_count"] >= 6 and metrics["storyboard_role_terms"] < 4:
        findings.append(Finding("WARN", "figure_roles", "figure storyboard/index lacks enough define/derive/compare/validate/explain/decide roles"))

    if not (metrics["has_artifact_manifest"] or metrics["has_result_ledger"] or metrics["has_frozen_numbers"]):
        findings.append(Finding("WARN", "reproducibility_support", "weak reproducibility support; add an artifact manifest, result ledger, or frozen-number record"))

    return findings


def scenario_files(root: Path) -> dict[str, Any]:
    rows = 0
    files: list[str] = []
    for folder in [root / "results" / "tables", root / "figures", root / "diagrams", root / "planning"]:
        if not folder.exists():
            continue
        for path in folder.glob("*"):
            if path.is_file() and has_token(path.name, SCENARIO_FILE_TOKENS):
                files.append(rel(root, path))
                if path.suffix.lower() == ".csv":
                    rows += count_csv_rows(path)
                elif path.suffix.lower() in {".md", ".txt"}:
                    rows += max(1, count_index_rows(read_text(path)))
    return {"files": sorted(files), "rows": rows}


def media_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in suffixes)


def paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    if paper_arg:
        path = resolve(root, paper_arg)
        return [path] if path.exists() else []
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_final.tex",
        paper_dir / "main.tex",
        paper_dir / "main.typ",
        paper_dir / "main.md",
    ]
    for path in candidates:
        if path.exists():
            files = [path]
            for pattern in ["*.tex", "*.typ", "*.md"]:
                files.extend(sorted((paper_dir / "sections").glob(pattern)) if (paper_dir / "sections").exists() else [])
            return dedupe(files)
    return []


def dedupe(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def has_token(name: str, tokens: list[str]) -> bool:
    lower = name.lower()
    return any(token.lower() in lower for token in tokens)


def count_csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
            return max(0, sum(1 for _ in csv.reader(handle)) - 1)
    except OSError:
        return 0


def count_index_rows(text: str) -> int:
    return len([line for line in text.splitlines() if "|" in line and not re.match(r"\s*\|?\s*-+\s*\|", line)])


def strip_tex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"[{}\\$&_^~]", " ", text)
    return re.sub(r"\s+", "", text)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Scenario Showcase Gate",
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
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    else:
        lines.append("| INFO | scenario_showcase | no findings |")
    lines.append("")
    return "\n".join(lines)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve(root: Path, value: str | Path) -> Path:
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
