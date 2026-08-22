#!/usr/bin/env python3
"""Audit workflow, idea, architecture, and process diagrams in a Mira project."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from delivery_contract import collect_source_files, manifest_path, source_fingerprint


@dataclass
class Finding:
    level: str
    axis: str
    message: str


FLOW_TERMS = [
    "flow",
    "workflow",
    "pipeline",
    "process",
    "state transition",
    "decision flow",
    "system link",
    "sequence diagram",
    "sequenceDiagram",
    "call chain",
    "interaction order",
    "mechanism",
    "时序图",
    "调用链",
    "交互顺序",
    "流程",
    "链路",
    "过程",
    "阶段",
    "状态转移",
    "决策流",
    "系统框图",
    "机制图",
]

BRANCH_TERMS = [
    "switch",
    "branch",
    "merge",
    "couple",
    "feedback",
    "loop",
    "split",
    "recycle",
    "return",
    "切换",
    "分支",
    "合流",
    "耦合",
    "反馈",
    "循环",
    "拆解",
    "回收",
    "返回",
]

DOMAIN_TERMS = [
    "domain",
    "lane",
    "layer",
    "stage",
    "input",
    "output",
    "data",
    "model",
    "decision",
    "platform",
    "application",
    "泳道",
    "层",
    "阶段",
    "输入",
    "输出",
    "数据",
    "模型",
    "决策",
    "平台",
    "应用",
]

ABBREVIATION_TERMS = [
    "abbreviation",
    "legend",
    "note",
    "caption",
    "callout",
    "缩写",
    "注",
    "说明",
    "图注",
    "含义",
    "标注",
]

FLOW_FILE_TOKENS = [
    "flow",
    "workflow",
    "pipeline",
    "process",
    "state",
    "transition",
    "decision",
    "mechanism",
    "system",
    "tree",
    "route",
    "idea",
    "architecture",
    "sequence",
    "mermaid",
    "mmd",
    "call",
    "interaction",
    "swimlane",
    "lane",
    "ppt",
]

LANE_CONTAINER_TERMS = [
    "lane",
    "layer",
    "stage",
    "container",
    "group",
    "swimlane",
    "architecture",
    "platform",
    "module",
    "input layer",
    "output layer",
    "数据层",
    "模型层",
    "执行层",
    "应用层",
    "管理层",
    "阶段",
    "泳道",
    "分区",
    "容器",
    "架构",
    "平台",
    "模块",
]

DECISION_TERMS = [
    "decision",
    "threshold",
    "approve",
    "reject",
    "yes",
    "no",
    "judge",
    "diamond",
    "判断",
    "阈值",
    "是否",
    "通过",
    "不通过",
    "批准",
    "拒绝",
    "返回",
]

REPEATED_TERMS = [
    "batch",
    "split",
    "partition",
    "parallel",
    "vehicle",
    "route",
    "sample",
    "scenario",
    "agent",
    "task",
    "worker",
    "particle",
    "population",
    "multi-seed",
    "多车",
    "多智能体",
    "多任务",
    "多场景",
    "样本",
    "批量",
    "分区",
    "并行",
    "重复",
    "车辆",
    "路线",
    "粒子",
    "种群",
]

TOOLCHAIN_TERMS = [
    "pptx",
    "powerpoint",
    "python",
    "matplotlib",
    "mermaid",
    "sequenceDiagram",
    "mmd",
    "svg",
    "visio",
    "toolchain",
    "source",
    "spec",
    "工具链",
    "源文件",
    "可编辑",
]

GRAMMAR_TERMS = [
    "compact route",
    "platform architecture",
    "decision swimlane",
    "approval swimlane",
    "technical swimlane",
    "workflow",
    "idea map",
    "architecture map",
    "route map",
    "复杂技术泳道",
    "平台架构",
    "决策泳道",
    "审批泳道",
    "思路图",
    "结构图",
    "流程图",
    "路线图",
]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    metrics = collect_metrics(root, args)
    findings = review(metrics)
    entry = paper_entry(root, args.paper)
    fingerprint = source_fingerprint(root, entry) if entry else {
        "canonical_source": "",
        "source_files": [],
        "source_sha256": "",
    }
    payload = {
        "generated_at": now(),
        "root": str(root),
        **fingerprint,
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
    emit(payload, args, root)
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    files = paper_files(root, args.paper)
    paper_text = "\n".join(read_text(path) for path in files)
    diagram_index = read_text(root / "diagrams" / "diagram_index.md")
    figure_index = read_text(root / "figures" / "figure_index.md")
    storyboard = read_text(root / "planning" / "figure_storyboard.md")
    modeling_plan = read_text(root / "planning" / "modeling_plan.md")
    problem_analysis = read_text(root / "planning" / "problem_analysis.md")
    spec_profiles = collect_spec_profiles(root)
    spec_text = "\n".join(profile.get("raw_text", "") for profile in spec_profiles)
    combined = "\n".join([paper_text, diagram_index, figure_index, storyboard, modeling_plan, problem_analysis, spec_text])
    diagrams = media_files(root / "diagrams")
    figures = media_files(root / "figures")
    mermaid_files = sorted((root / "diagrams").glob("*.mmd")) if (root / "diagrams").exists() else []
    flow_diagrams = [path for path in diagrams + figures + mermaid_files if has_token(path.name, FLOW_FILE_TOKENS)]
    pptx_files = sorted((root / "diagrams").glob("*.pptx")) if (root / "diagrams").exists() else []
    include_paths = re.findall(r"\\(?:includegraphics|figinc)(?:\[[^\]]*\])?\s*\{([^}]+)\}", paper_text)
    diagram_includes = [path for path in include_paths if "diagram" in path.lower() or has_token(path, FLOW_FILE_TOKENS)]
    spec_metrics = summarize_specs(spec_profiles)
    return {
        "paper_files": [rel(root, path) for path in files],
        "diagram_file_count": len(diagrams),
        "figure_file_count": len(figures),
        "pptx_file_count": len(pptx_files),
        "pptx_files": [rel(root, path) for path in pptx_files],
        "mermaid_source_count": len(mermaid_files),
        "mermaid_source_files": [rel(root, path) for path in mermaid_files],
        "flow_diagram_files": [rel(root, path) for path in flow_diagrams],
        "included_flow_diagrams": diagram_includes,
        "diagram_index_rows": count_index_rows(diagram_index),
        "flow_terms": count_terms(combined, FLOW_TERMS),
        "branch_terms": count_terms(combined, BRANCH_TERMS),
        "domain_terms": count_terms(combined, DOMAIN_TERMS),
        "abbreviation_terms": count_terms(combined, ABBREVIATION_TERMS),
        "lane_container_terms": count_terms(combined, LANE_CONTAINER_TERMS),
        "decision_terms": count_terms(combined, DECISION_TERMS),
        "repeated_instance_terms": count_terms(combined, REPEATED_TERMS),
        "toolchain_terms": count_terms(combined, TOOLCHAIN_TERMS),
        "grammar_terms": count_terms(combined, GRAMMAR_TERMS),
        "process_need_terms": count_terms(
            combined,
            [
                "stage",
                "phase",
                "process",
                "workflow",
                "state",
                "DP",
                "recursion",
                "feedback",
                "loop",
                "decision",
                "pipeline",
                "sequenceDiagram",
                "sequence diagram",
                "call chain",
                "interaction order",
                "architecture",
                "platform",
                "route",
                "mechanism",
                "阶段",
                "流程",
                "状态",
                "递归",
                "动态规划",
                "装配",
                "链路",
                "切换",
                "反馈",
                "循环",
                "决策",
                "架构",
                "平台",
                "路线",
                "机制",
                "时序图",
                "调用链",
                "交互顺序",
            ],
        ),
        "spec_files": [profile["path"] for profile in spec_profiles],
        **spec_metrics,
        "has_storyboard": bool(storyboard.strip()),
        "has_svg_or_pdf_diagram": any(path.suffix.lower() in {".svg", ".pdf"} for path in diagrams),
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not metrics["paper_files"]:
        return [Finding("FAIL", "paper_source", "no paper source was found")]

    needs_flow = metrics["process_need_terms"] >= 8
    needs_architecture = metrics["lane_container_terms"] >= 4 or metrics["grammar_terms"] >= 2
    needs_decision = metrics["decision_terms"] >= 3
    needs_repeated = metrics["repeated_instance_terms"] >= 4
    has_flow = (
        bool(metrics["flow_diagram_files"])
        or bool(metrics["included_flow_diagrams"])
        or metrics["pptx_file_count"] > 0
        or metrics["spec_count"] > 0
    )

    if needs_flow and not has_flow:
        findings.append(Finding("WARN", "flowchart_presence", "process/state/stage language is strong but no flowchart/system-link diagram was detected"))
    if has_flow and not metrics["included_flow_diagrams"]:
        findings.append(Finding("WARN", "paper_inclusion", "flowchart-like diagram files exist but are not clearly included in the paper"))
    if has_flow and metrics["diagram_index_rows"] == 0:
        findings.append(Finding("WARN", "diagram_index", "diagrams exist but diagrams/diagram_index.md has no clear rows"))
    if has_flow and metrics["branch_terms"] < 2 and metrics["process_need_terms"] >= 12:
        findings.append(Finding("WARN", "branch_logic", "flowchart exists but branch/merge/feedback/cycle logic is weakly documented"))
    if has_flow and metrics["domain_terms"] < 3 and metrics["lane_container_terms"] < 3 and metrics["spec_group_count"] < 2:
        findings.append(Finding("WARN", "domain_lanes", "flowchart exists but domain/lane/stage labels are weak"))
    if has_flow and needs_architecture and metrics["spec_group_count"] < 2 and metrics["lane_container_terms"] < 5:
        findings.append(Finding("WARN", "stage_container_grammar", "architecture or idea-map language is present, but stage containers/lanes are weak"))
    if has_flow and needs_decision and metrics["spec_decision_node_count"] == 0 and metrics["decision_terms"] < 6:
        findings.append(Finding("WARN", "decision_node_grammar", "decision or approval language is present, but no decision-node/yes-no branch grammar is recorded"))
    if has_flow and needs_repeated and metrics["spec_repeated_instance_count"] == 0 and not any("repeat" in path.lower() or "batch" in path.lower() or "parallel" in path.lower() for path in metrics["flow_diagram_files"]):
        findings.append(Finding("WARN", "repeated_instance_grammar", "batch/parallel/multi-instance language is present, but repeated-instance diagram grammar is weak"))
    if has_flow and metrics["spec_feedback_edge_count"] == 0 and metrics["branch_terms"] >= 3 and not re.search(r"feedback|loop|return|反馈|循环|返回", " ".join(metrics["flow_diagram_files"]), re.I):
        findings.append(Finding("WARN", "feedback_loop_grammar", "branch/feedback language is present, but feedback or return-loop arrows are not clearly recorded"))
    if has_flow and metrics["abbreviation_terms"] < 2:
        findings.append(Finding("WARN", "abbreviation_caption", "flowchart captions or notes should decode compact module labels and abbreviations"))
    if has_flow and metrics["toolchain_terms"] < 2:
        findings.append(Finding("WARN", "diagram_toolchain", "diagram source/toolchain is weakly recorded; keep PPTX/spec/SVG or generation command provenance"))
    if has_flow and not metrics["has_storyboard"]:
        findings.append(Finding("WARN", "storyboard", "flowchart should be planned in figure_storyboard with role, source, and takeaway"))
    return findings


def collect_spec_profiles(root: Path) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for folder in [root / "planning" / "flowcharts", root / "diagrams", root / "results" / "figures_data"]:
        if folder.exists():
            candidates.extend(sorted(folder.glob("*.json")))
    profiles: list[dict[str, Any]] = []
    for path in candidates:
        text = read_text(path)
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if not any(key in data for key in ["nodes", "edges", "groups", "callouts", "source", "export"]):
            continue
        profiles.append(profile_spec(root, path, data, text))
    return profiles


def profile_spec(root: Path, path: Path, data: dict[str, Any], raw_text: str) -> dict[str, Any]:
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    groups = data.get("groups", [])
    callouts = data.get("callouts", [])
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []
    if not isinstance(groups, list):
        groups = []
    if not isinstance(callouts, list):
        callouts = []
    node_text = " ".join(str(node.get("label", "")) + " " + str(node.get("type", "")) + " " + str(node.get("shape", "")) for node in nodes if isinstance(node, dict))
    edge_text = " ".join(str(edge.get("label", "")) + " " + str(edge.get("style", "")) for edge in edges if isinstance(edge, dict))
    group_text = " ".join(str(group.get("label", "")) for group in groups if isinstance(group, dict))
    explicit_repeated_instances = sum(
        max(0, int(node.get("repeat_count", 0)))
        for node in nodes
        if isinstance(node, dict) and str(node.get("repeat_count", "")).isdigit()
    )
    return {
        "path": rel(root, path),
        "raw_text": raw_text,
        "nodes": len(nodes),
        "edges": len(edges),
        "groups": len(groups),
        "callouts": len(callouts),
        "decision_nodes": sum(1 for node in nodes if isinstance(node, dict) and re.search(r"decision|diamond|判断|是否|阈值", str(node), re.I)),
        "feedback_edges": sum(1 for edge in edges if isinstance(edge, dict) and re.search(r"feedback|loop|return|修正|反馈|返回|循环", str(edge), re.I)),
        "dashed_groups": sum(1 for group in groups if isinstance(group, dict) and bool(group.get("dashed", False))),
        "repeated_instances": count_repeated_labels(node_text) + explicit_repeated_instances,
        "lane_terms": count_terms(group_text + " " + node_text, LANE_CONTAINER_TERMS),
        "branch_terms": count_terms(edge_text + " " + node_text, BRANCH_TERMS),
    }


def summarize_specs(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "spec_count": len(profiles),
        "spec_node_count": sum(int(profile.get("nodes", 0)) for profile in profiles),
        "spec_edge_count": sum(int(profile.get("edges", 0)) for profile in profiles),
        "spec_group_count": sum(int(profile.get("groups", 0)) for profile in profiles),
        "spec_callout_count": sum(int(profile.get("callouts", 0)) for profile in profiles),
        "spec_decision_node_count": sum(int(profile.get("decision_nodes", 0)) for profile in profiles),
        "spec_feedback_edge_count": sum(int(profile.get("feedback_edges", 0)) for profile in profiles),
        "spec_dashed_group_count": sum(int(profile.get("dashed_groups", 0)) for profile in profiles),
        "spec_repeated_instance_count": sum(int(profile.get("repeated_instances", 0)) for profile in profiles),
        "spec_lane_term_count": sum(int(profile.get("lane_terms", 0)) for profile in profiles),
        "spec_branch_term_count": sum(int(profile.get("branch_terms", 0)) for profile in profiles),
    }


def count_repeated_labels(text: str) -> int:
    lower = text.lower()
    patterns = [
        r"\btask\s*\d+",
        r"\bworker\s*\d+",
        r"\bvehicle\s*\d+",
        r"\broute\s*\d+",
        r"\bscenario\s*\d+",
        r"\bcase\s*\d+",
        r"\bs\d+",
        r"\bq\d+",
        r"[0-9]+[ ]*(?:tasks|routes|vehicles|samples|scenarios)",
        r"多[个组车任务场景样本]",
    ]
    return sum(len(re.findall(pattern, lower)) for pattern in patterns)


def media_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in suffixes)


def paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    entry = paper_entry(root, paper_arg)
    if not entry:
        return []
    if entry.suffix.lower() == ".tex":
        return [path for path in collect_source_files(root, entry) if path.suffix.lower() == ".tex"]
    if paper_arg:
        return [entry]
    paper_dir = root / "paper"
    files = [entry]
    for pattern in ["*.tex", "*.typ", "*.md"]:
        files.extend(sorted((paper_dir / "sections").glob(pattern)) if (paper_dir / "sections").exists() else [])
    return dedupe(files)


def paper_entry(root: Path, paper_arg: str | None) -> Path | None:
    if paper_arg:
        path = resolve(root, paper_arg)
        return path if path.is_file() else None
    if manifest_path(root).is_file():
        path = root / "paper" / "main.tex"
        return path if path.is_file() else None
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_final.tex",
        paper_dir / "main.tex",
        paper_dir / "main.typ",
        paper_dir / "main.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


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


def count_index_rows(text: str) -> int:
    return len([line for line in text.splitlines() if "|" in line and not re.match(r"\s*\|?\s*-+\s*\|", line)])


def has_token(text: str, tokens: list[str]) -> bool:
    lower = text.lower()
    return any(token.lower() in lower for token in tokens)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira 0.8.3 Flowchart Diagram Gate",
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
        lines.append("| INFO | flowchart_diagram | no findings |")
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


def emit(payload: dict[str, Any], args: argparse.Namespace, root: Path) -> None:
    _print(f"VERDICT: {payload['verdict']}")
    _print("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
    for finding in payload["findings"]:
        _print(f"{finding['level']}: [{finding['axis']}] {finding['message']}")
    if args.write_report:
        _print(f"wrote: {resolve(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve(root, args.write_json)}")


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
