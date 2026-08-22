#!/usr/bin/env python3
"""Create or refresh Mira's adaptive contest-paper strategy artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ARCHITECTURES = {
    "mechanism-first": {
        "explanation_mode": "causal-mechanistic",
        "sections": [
            ("S1", "问题边界与关键现象", "foundation", []),
            ("S2", "机制假设与状态演化", "mechanism", ["S1"]),
            ("S3", "数学模型与可识别参数", "model", ["S2"]),
            ("S4", "求解结果与机制检验", "evidence", ["S3"]),
            ("S5", "阈值、边界与反例", "validation", ["S4"]),
            ("S6", "决策含义与适用范围", "synthesis", ["S5"]),
        ],
    },
    "decision-first": {
        "explanation_mode": "optimization-tradeoff",
        "sections": [
            ("S1", "决策对象与评价准则", "decision", []),
            ("S2", "约束结构与可行域", "foundation", ["S1"]),
            ("S3", "候选策略与求解模型", "model", ["S2"]),
            ("S4", "方案比较与权衡证据", "evidence", ["S3"]),
            ("S5", "情景扰动与稳健决策", "scenario", ["S4"]),
            ("S6", "最终策略及执行边界", "synthesis", ["S5"]),
        ],
    },
    "evidence-first": {
        "explanation_mode": "empirical-identification",
        "sections": [
            ("S1", "数据质量与可辨识信息", "evidence", []),
            ("S2", "特征结构与问题转化", "foundation", ["S1"]),
            ("S3", "统计模型与估计方法", "model", ["S2"]),
            ("S4", "结果证据与误差分解", "evidence", ["S3"]),
            ("S5", "机制解释与外推边界", "mechanism", ["S4"]),
            ("S6", "决策结论与适用范围", "synthesis", ["S5"]),
        ],
    },
    "theorem-first": {
        "explanation_mode": "deductive-proof",
        "sections": [
            ("S1", "定义、条件与目标命题", "foundation", []),
            ("S2", "核心性质与关键引理", "theorem", ["S1"]),
            ("S3", "证明链与边界条件", "proof", ["S2"]),
            ("S4", "可计算形式与算法", "model", ["S3"]),
            ("S5", "数值验证与反例检查", "evidence", ["S4"]),
            ("S6", "结论范围与应用", "synthesis", ["S5"]),
        ],
    },
    "scenario-first": {
        "explanation_mode": "scenario-contrast",
        "sections": [
            ("S1", "情景空间与评价指标", "scenario", []),
            ("S2", "系统机制与状态转移", "mechanism", ["S1"]),
            ("S3", "仿真设计与参数方案", "model", ["S2"]),
            ("S4", "情景对照与关键结果", "evidence", ["S3"]),
            ("S5", "阈值、风险与反事实", "validation", ["S4"]),
            ("S6", "策略建议与适用条件", "decision", ["S5"]),
        ],
    },
}


SIGNALS = {
    "mechanism-first": ("机理", "机制", "动力学", "微分方程", "传热", "守恒", "状态空间", "物理过程", "控制系统"),
    "decision-first": ("优化", "决策", "调度", "路径", "分配", "目标函数", "约束", "选址", "策略组合"),
    "evidence-first": ("数据", "回归", "预测", "分类", "聚类", "统计", "识别", "观测", "指标评价", "残差"),
    "theorem-first": ("证明", "定理", "命题", "引理", "上界", "下界", "收敛性", "解析解", "充分条件", "必要条件"),
    "scenario-first": ("情景", "场景", "仿真", "蒙特卡洛", "政策", "干预", "风险", "反事实", "演化实验"),
}


DEFAULT_PROHIBITED = [
    "Mira/Codex/其他 agent 或模型名称",
    "planning/、checks/、scripts/ 等内部路径",
    "PASS、FAIL、gate、audit、workflow 等审计状态",
    "本轮优化、结果冻结、通过门槛等内部流程叙述",
]

ARCHITECTURE_OWNED_FIELDS = {
    "status",
    "primary_architecture",
    "supporting_architectures",
    "hybrid_reason",
    "architecture_rationale",
    "argument_dependency_order",
    "section_plan",
    "dominant_explanation_mode",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), help="Explicit primary architecture override")
    parser.add_argument("--write-report", default="planning/paper_strategy.md")
    parser.add_argument("--write-json", default="planning/paper_strategy.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    json_path = resolve(root, args.write_json)
    existing = load_json(json_path)
    source_text, sources = collect_sources(root)
    scores = score_architectures(source_text)
    recommended = max(ARCHITECTURES, key=lambda name: (scores[name], -list(ARCHITECTURES).index(name)))
    current = str(existing.get("primary_architecture", "")).strip()
    selected = args.architecture or (current if current in ARCHITECTURES else recommended)

    payload = build_strategy(selected, recommended, scores, sources)
    architecture_changed = current in ARCHITECTURES and current != selected
    payload = merge_existing(payload, existing, architecture_changed=architecture_changed)
    payload["primary_architecture"] = selected
    payload["architecture_recommendation"] = {
        "recommended": recommended,
        "scores": scores,
        "note": "This is a drafting recommendation from project signals, not a quality verdict or a substitute for modeler judgment.",
    }
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = resolve(root, args.write_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown(payload), encoding="utf-8")

    print(f"PRIMARY_ARCHITECTURE: {selected}")
    print(f"RECOMMENDED_ARCHITECTURE: {recommended}")
    print(f"WROTE: {rel(root, json_path)}")
    print(f"WROTE: {rel(root, report_path)}")
    return 0


def build_strategy(selected: str, recommended: str, scores: dict[str, int], sources: list[str]) -> dict[str, Any]:
    template = ARCHITECTURES[selected]
    sections = [
        {
            "id": section_id,
            "title": title,
            "role": role,
            "claim": "",
            "depends_on": dependencies,
            "evidence": [],
            "keep_reason": "",
        }
        for section_id, title, role, dependencies in template["sections"]
    ]
    return {
        "version": 1,
        "status": "draft",
        "updated_at": "",
        "source_artifacts": sources,
        "primary_architecture": selected,
        "supporting_architectures": [],
        "hybrid_reason": "",
        "architecture_rationale": "",
        "architecture_recommendation": {"recommended": recommended, "scores": scores},
        "one_sentence_thesis": "",
        "core_contributions": [],
        "argument_dependency_order": [row[0] for row in template["sections"]],
        "section_plan": sections,
        "deleted_or_merged_sections": [],
        "dominant_explanation_mode": template["explanation_mode"],
        "paragraph_rhythm": {
            "default_pattern": ["claim", "mathematical reason or mechanism", "evidence", "scope or decision implication"],
            "variation_rules": [],
        },
        "terminology_boundaries": [],
        "prohibited_internal_language": DEFAULT_PROHIBITED,
    }


def collect_sources(root: Path) -> tuple[str, list[str]]:
    candidates = [
        "planning/delivery_brief.md",
        "planning/problem_analysis.md",
        "planning/modeling_plan.md",
        "planning/validation_plan.md",
        "results/result_report.md",
    ]
    parts: list[str] = []
    sources: list[str] = []
    for item in candidates:
        path = root / item
        if not path.is_file():
            continue
        text = read_text(path)
        if text.strip():
            parts.append(text[:50000])
            sources.append(item)
    return "\n".join(parts).lower(), sources


def score_architectures(text: str) -> dict[str, int]:
    return {
        architecture: sum(text.count(term.lower()) for term in terms)
        for architecture, terms in SIGNALS.items()
    }


def merge_existing(
    base: dict[str, Any],
    existing: dict[str, Any],
    *,
    architecture_changed: bool = False,
) -> dict[str, Any]:
    if not existing:
        return base
    merged = dict(base)
    for key, value in existing.items():
        if key in {"architecture_recommendation", "updated_at"}:
            continue
        if architecture_changed and key in ARCHITECTURE_OWNED_FIELDS:
            continue
        if value not in (None, "", [], {}):
            merged[key] = value
    if architecture_changed:
        preserve_section_annotations(merged, existing)
    return merged


def preserve_section_annotations(merged: dict[str, Any], existing: dict[str, Any]) -> None:
    new_sections = [item for item in merged.get("section_plan", []) if isinstance(item, dict)]
    old_sections = [item for item in existing.get("section_plan", []) if isinstance(item, dict)]
    available_by_role: dict[str, list[dict[str, Any]]] = {}
    for section in new_sections:
        available_by_role.setdefault(str(section.get("role", "")), []).append(section)

    carried: list[dict[str, str]] = []
    unmapped: list[dict[str, Any]] = []
    for old in old_sections:
        annotations = {
            key: old.get(key)
            for key in ("claim", "evidence", "keep_reason")
            if old.get(key) not in (None, "", [], {})
        }
        if not annotations:
            continue
        candidates = available_by_role.get(str(old.get("role", "")), [])
        target = candidates.pop(0) if candidates else None
        if target is None:
            unmapped.append(dict(old))
            continue
        target.update(annotations)
        carried.append(
            {
                "from_id": str(old.get("id", "")),
                "to_id": str(target.get("id", "")),
                "role": str(old.get("role", "")),
            }
        )

    previous_fields = {
        key: existing.get(key)
        for key in (
            "status",
            "supporting_architectures",
            "hybrid_reason",
            "architecture_rationale",
            "dominant_explanation_mode",
        )
        if existing.get(key) not in (None, "", [], {})
    }
    transition = {
        "from_architecture": str(existing.get("primary_architecture", "")),
        "to_architecture": str(merged.get("primary_architecture", "")),
        "previous_architecture_fields": previous_fields,
        "carried_sections": carried,
        "unmapped_annotated_sections": unmapped,
    }
    history = existing.get("architecture_transition_history", [])
    merged["architecture_transition_history"] = list(history) + [transition] if isinstance(history, list) else [transition]


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Paper Strategy",
        "",
        f"- Status: **{data.get('status', 'draft')}**",
        f"- Primary architecture: **{data.get('primary_architecture', '')}**",
        f"- Supporting architectures: {', '.join(data.get('supporting_architectures', [])) or 'none'}",
        f"- Dominant explanation mode: {data.get('dominant_explanation_mode', '')}",
        f"- Recommendation only: {data.get('architecture_recommendation', {}).get('recommended', '')}",
        "",
        "## Thesis",
        "",
        str(data.get("one_sentence_thesis", "") or "to_be_filled"),
        "",
        "## Architecture Rationale",
        "",
        str(data.get("architecture_rationale", "") or "to_be_filled"),
        "",
        "## Core Contributions",
        "",
        "| ID | Claim | Evidence | Boundary |",
        "|---|---|---|---|",
    ]
    for item in data.get("core_contributions", []):
        if isinstance(item, dict):
            lines.append(f"| {item.get('id', '')} | {item.get('claim', '')} | {join_value(item.get('evidence'))} | {item.get('boundary', '')} |")
    if not data.get("core_contributions"):
        lines.append("| to_be_filled | | | |")
    lines.extend(["", "## Argument And Section Plan", "", "| Order | ID | Title | Role | Depends on | Claim | Evidence | Keep reason |", "|---|---|---|---|---|---|---|---|"])
    order = {item: index + 1 for index, item in enumerate(data.get("argument_dependency_order", []))}
    for item in data.get("section_plan", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| {order.get(item.get('id'), '')} | {item.get('id', '')} | {item.get('title', '')} | {item.get('role', '')} | "
            f"{join_value(item.get('depends_on'))} | {item.get('claim', '')} | {join_value(item.get('evidence'))} | {item.get('keep_reason', '')} |"
        )
    lines.extend(["", "## Deleted Or Merged Sections", "", "| Section | Decision | Reason |", "|---|---|---|"])
    for item in data.get("deleted_or_merged_sections", []):
        if isinstance(item, dict):
            lines.append(f"| {item.get('section', '')} | {item.get('decision', '')} | {item.get('reason', '')} |")
    if not data.get("deleted_or_merged_sections"):
        lines.append("| to_be_filled | | |")
    lines.extend(["", "## Paragraph Rhythm", "", f"- Default: {' -> '.join(data.get('paragraph_rhythm', {}).get('default_pattern', []))}"])
    for rule in data.get("paragraph_rhythm", {}).get("variation_rules", []):
        lines.append(f"- Variation: {rule}")
    lines.extend(["", "## Terminology Boundaries", "", "| Term | Use | Avoid |", "|---|---|---|"])
    for item in data.get("terminology_boundaries", []):
        if isinstance(item, dict):
            lines.append(f"| {item.get('term', '')} | {item.get('use', '')} | {item.get('avoid', '')} |")
    if not data.get("terminology_boundaries"):
        lines.append("| to_be_filled | | |")
    lines.extend(["", "## Prohibited Internal Language", ""])
    lines.extend(f"- {item}" for item in data.get("prohibited_internal_language", []))
    lines.extend(["", "The JSON file is authoritative; regenerate this Markdown view after editing it.", ""])
    return "\n".join(lines)


def join_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
