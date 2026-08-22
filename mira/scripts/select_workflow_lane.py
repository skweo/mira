#!/usr/bin/env python3
"""Select Mira's workflow lane before loading granular skills.

The lane selector keeps Mira's interface small: callers only need to know the
selected lane, while the implementation hides skip rules, expansion triggers,
and artifact budgeting.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


COMPLEX_METHOD_TERMS = [
    "PDE",
    "偏微分",
    "微分方程",
    "逆问题",
    "参数识别",
    "校准",
    "神经网络",
    "深度学习",
    "强化学习",
    "图像",
    "视频",
    "传感器",
    "QUBO",
    "VRPTW",
    "多目标",
    "随机",
    "启发式",
    "模拟退火",
    "遗传算法",
]

COMPARISON_TERMS = [
    "对比",
    "比较",
    "上一版",
    "之前版本",
    "不如",
    "升级",
    "优化mira",
    "优化 mira",
    "deepseek",
    "claude",
    "agent",
]

FINAL_TERMS = [
    "contest_final",
    "完整论文",
    "正式",
    "提交",
    "终稿",
    "PDF",
    "pdf",
    "MathorCup",
    "数学建模",
]


@dataclass
class LaneDecision:
    lane: str
    reasons: list[str]
    skipped_granular_skills: list[str]
    references_to_load_now: list[str]
    expansion_triggers: list[str]
    artifact_budget: list[str]
    metrics: dict[str, object]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def detect_output_level(text: str) -> str:
    match = re.search(r"\|\s*Output level\s*\|\s*([^|\n]+)\|", text, flags=re.I)
    if match:
        value = match.group(1).strip()
        if value and value not in {"to_be_decided", "unknown"}:
            return value
    if has_any(text, FINAL_TERMS):
        return "contest_final"
    return "to_be_decided"


def detect_subquestions(text: str) -> int:
    explicit = re.search(r"\|\s*Subquestion count\s*\|\s*([^|\n]+)\|", text, flags=re.I)
    if explicit:
        raw = explicit.group(1).strip()
        if raw.isdigit():
            return int(raw)
    cn = "一二三四五六七八九"
    seen = [cn.index(item) + 1 for item in re.findall(r"问题([一二三四五六七八九])", text)]
    qn = [int(item) for item in re.findall(r"\bQ([1-9])\b", text, flags=re.I)]
    values = seen + qn
    return max(values) if values else 0


def collect_metrics(root: Path, request: str) -> dict[str, object]:
    planning = root / "planning"
    checks = root / "checks"
    materials = root / "materials"
    problem = root / "problem"
    data_raw = root / "data_raw"
    text_parts = [
        request,
        read_text(planning / "delivery_brief.md"),
        read_text(planning / "problem_analysis.md"),
        read_text(planning / "modeling_plan.md"),
        read_text(checks / "compliance_report.md"),
        read_text(checks / "quality_balance_report.md"),
        read_text(root / "revisions" / "iteration_report.md"),
    ]
    text = "\n".join(text_parts)
    source_count = sum(1 for folder in (problem, data_raw) if folder.exists() for path in folder.rglob("*") if path.is_file() and path.name != ".gitkeep")
    material_count = sum(1 for path in materials.rglob("*") if path.is_file() and path.name != ".gitkeep") if materials.exists() else 0
    failed_gates = len(re.findall(r"\bFAIL\b|失败|不通过|blocker|阻塞", text, flags=re.I))
    warnings = len(re.findall(r"\bWARN\b|警告|warning", text, flags=re.I))
    output_level = detect_output_level(text)
    subquestions = detect_subquestions(text)
    complex_terms = [term for term in COMPLEX_METHOD_TERMS if term.lower() in text.lower()]
    comparison = has_any(text, COMPARISON_TERMS)
    existing_phase_artifacts = {
        "problem_analysis": (planning / "problem_analysis.md").exists(),
        "modeling_plan": (planning / "modeling_plan.md").exists(),
        "result_report": (root / "results" / "result_report.md").exists(),
        "paper": any((root / "paper").glob("main.*")) if (root / "paper").exists() else False,
    }
    return {
        "output_level": output_level,
        "subquestions": subquestions,
        "source_count": source_count,
        "material_count": material_count,
        "failed_gates": failed_gates,
        "warnings": warnings,
        "complex_terms": complex_terms[:12],
        "comparison_or_upgrade_request": comparison,
        "existing_phase_artifacts": existing_phase_artifacts,
    }


def decide_lane(metrics: dict[str, object], forced: str | None) -> LaneDecision:
    if forced:
        lane = forced
        reasons = [f"lane forced by caller: {forced}"]
    else:
        output_level = str(metrics["output_level"])
        subquestions = int(metrics["subquestions"] or 0)
        failed_gates = int(metrics["failed_gates"] or 0)
        complex_terms = list(metrics["complex_terms"])
        comparison = bool(metrics["comparison_or_upgrade_request"])
        source_count = int(metrics["source_count"] or 0)
        material_count = int(metrics["material_count"] or 0)

        reasons: list[str] = []
        if failed_gates:
            reasons.append(f"existing checks contain {failed_gates} failure/blocker signals")
        if len(complex_terms) >= 3:
            reasons.append("multiple complex method/data terms detected: " + ", ".join(complex_terms[:6]))
        if material_count > 20:
            reasons.append(f"large learning/material corpus detected: {material_count} files")
        if comparison and failed_gates:
            reasons.append("comparison/upgrade request with unresolved quality failures")

        if reasons:
            lane = "deep"
        elif output_level == "contest_final" or comparison or subquestions >= 3 or source_count > 0:
            lane = "standard"
            if output_level == "contest_final":
                reasons.append("contest_final requires strong gates but not automatic granular expansion")
            if comparison:
                reasons.append("comparison/upgrade request should use standard lane plus targeted expansion")
            if subquestions >= 3:
                reasons.append(f"multi-question contest detected: {subquestions} subquestions")
            if source_count > 0:
                reasons.append(f"problem/data sources detected: {source_count} files")
        else:
            lane = "compact"
            reasons.append("no final-paper or high-risk trigger detected")

    skipped = skipped_for_lane(lane)
    refs = references_for_lane(lane)
    triggers = expansion_triggers()
    budget = artifact_budget_for_lane(lane)
    return LaneDecision(
        lane=lane,
        reasons=reasons,
        skipped_granular_skills=skipped,
        references_to_load_now=refs,
        expansion_triggers=triggers,
        artifact_budget=budget,
        metrics=metrics,
    )


def skipped_for_lane(lane: str) -> list[str]:
    if lane == "compact":
        return [
            "problem-classifier as separate JSON+MD",
            "long granular SKILL.md files when canonical stage artifacts are sufficient",
            "related-paper-analyzer when no papers/citations are needed",
            "separate method-selector report when modeling_plan can carry the decision",
            "standalone figure/diagram planning if no paper figure is requested",
        ]
    if lane == "standard":
        return [
            "empty related-paper reports",
            "duplicate JSON artifacts whose fields are already in canonical Markdown",
            "granular parser/classifier skills when problem_analysis satisfies the gate",
            "long parser/classifier/method-selector SKILL.md files without a deep trigger",
            "global deep audit for stages that have not failed",
        ]
    return [
        "empty reports only; deep mode still skips artifacts with no downstream consumer",
    ]


def references_for_lane(lane: str) -> list[str]:
    base = [
        "references/workflow-orchestration.md",
        "references/adaptive-workflow-lanes.md",
        "references/phase-contracts.md",
    ]
    if lane == "compact":
        return base
    if lane == "standard":
        return base + [
            "references/anti-paper-tiger-rules.md",
            "references/model-depth-rules.md",
        ]
    return base + [
        "references/anti-paper-tiger-rules.md",
        "references/model-depth-rules.md",
        "references/validation-patterns.md",
        "references/dual-quality-loop.md",
    ]


def expansion_triggers() -> list[str]:
    return [
        "a stage check fails",
        "model choice materially changes numerical answers",
        "data fields, units, or extraction rules are unclear",
        "heuristic results lack baseline, seed, convergence, or sensitivity evidence",
        "paper comparison exposes a non-local quality regression",
        "a compact contract is insufficient for a failed stage and the granular skill has unique executable assets",
    ]


def artifact_budget_for_lane(lane: str) -> list[str]:
    if lane == "compact":
        return [
            "planning/delivery_brief.md",
            "planning/workflow_lane.md",
            "only the canonical stage artifact needed by the user request",
        ]
    if lane == "standard":
        return [
            "canonical four-stage artifacts only",
            "machine JSON only when a script consumes it",
            "skip empty reports and duplicate JSON+MD pairs",
        ]
    return [
        "canonical four-stage artifacts",
        "granular artifacts only for expanded risky stages",
        "extra audits tied to concrete failure or risk triggers",
    ]


def markdown(decision: LaneDecision) -> str:
    lines = [
        "# Workflow Lane",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Selected lane: **{decision.lane}**",
        "",
        "## Reasons",
        "",
    ]
    lines.extend(f"- {item}" for item in decision.reasons)
    lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---|"])
    for key, value in decision.metrics.items():
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(str(item) for item in value) if value else "-"
        elif isinstance(value, dict):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"| {key} | {rendered} |")

    sections = [
        ("Skipped Granular Skills", decision.skipped_granular_skills),
        ("References To Load Now", decision.references_to_load_now),
        ("Expansion Triggers", decision.expansion_triggers),
        ("Artifact Budget", decision.artifact_budget),
    ]
    for title, items in sections:
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {item}" for item in items)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--request", default="", help="User request text, if available")
    parser.add_argument("--force", choices=["compact", "standard", "deep"], help="Force a lane")
    parser.add_argument("--write", action="store_true", help="Write planning/workflow_lane.md")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    decision = decide_lane(collect_metrics(root, args.request), args.force)
    if args.json:
        print(json.dumps(decision.__dict__, ensure_ascii=False, indent=2))
    else:
        print(markdown(decision))

    if args.write:
        out = root / "planning" / "workflow_lane.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(decision), encoding="utf-8")
        print(f"INFO: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
