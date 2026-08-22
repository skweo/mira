#!/usr/bin/env python3
"""Route Mira references by public stage, lane, and active risk.

This keeps Mira from loading a long mandatory reference chain on startup. The
script writes a small stage-local reading list; references not on that list are
optional unless a finding or expansion trigger names them.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from command_profiles import commands_for_phase
from reference_trigger_coverage import (
    TRIGGER_RULES,
    TriggerHit,
    evaluate_reference_triggers,
    route_trigger_hits,
)
from stage_gate import normalize_stage


@dataclass(frozen=True)
class VisualLeafRule:
    category: str
    path: str
    reason: str
    pattern: re.Pattern[str]
    priority: int
    owner_stages: frozenset[str] = frozenset({"implementation", "paper"})


MATERIAL_REFS = {
    "batch": "references/batch-learning-protocol.md",
    "math_model": "references/math-model-corpus-protocol.md",
}
MATERIAL_REF_OWNER_STAGES = {
    "batch": frozenset({"analysis", "modeling"}),
    "math_model": frozenset({"analysis", "modeling"}),
}
CONDITIONAL_REF_OWNER_STAGES = {
    "references/anti-paper-tiger-rules.md": frozenset(
        {"analysis", "modeling", "implementation", "paper"}
    ),
    "references/skill-compaction.md": frozenset(
        {"analysis", "modeling", "implementation", "paper", "maintenance"}
    ),
}

# Public routing uses four bounded stage lists; deeper rules are added only by
# current evidence. Maintenance modes are normalized into their owning stage.
PUBLIC_STAGE_REFS = {
    "analysis": [
        "references/workflow-orchestration.md",
        "references/phase-contracts.md",
        "references/attachment-mapping-guard-rules.md",
        "references/data-quality-gate-rules.md",
        "references/evidence-authenticity-rules.md",
    ],
    "modeling": [
        "references/workflow-orchestration.md",
        "references/phase-contracts.md",
        "references/model-depth-rules.md",
        "references/model-knowledge-routing.md",
        "references/validation-patterns.md",
        "references/evidence-authenticity-rules.md",
    ],
    "implementation": [
        "references/workflow-orchestration.md",
        "references/phase-contracts.md",
        "references/computation-backends.md",
        "references/result-quality-evaluation.md",
        "references/model-solver-consistency.md",
        "references/visual-backend-rules.md",
        "references/figure-table-rules.md",
    ],
    "paper": [
        "references/workflow-orchestration.md",
        "references/phase-contracts.md",
        "references/contest-final-writing-contract.md",
        "references/paper-template-zh.md",
        "references/verification-gates.md",
        "references/evidence-authenticity-rules.md",
    ],
}

MAINTENANCE_REFS = {
    "benchmark": "references/benchmark-regression-rules.md",
}

# Visual routing has two levels: the stage keeps its small base contract, then
# one concrete leaf is selected from the current visual intent. The registry
# includes the 24 previously unrouted visual references plus the existing
# system-flowchart leaf so competing diagram intents follow the same rule.
VISUAL_LEAF_RULES = [
    VisualLeafRule(
        "special_visual",
        "references/pseudo-3d-ppt-diagram-rules.md",
        "pseudo-3D or 2.5D editable schematic",
        re.compile(r"\b(?:pseudo[- ]?3d|2\.5d)\b|伪三维|伪3D", re.I),
        120,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/cnn-architecture-diagram-rules.md",
        "CNN architecture diagram",
        re.compile(r"\bCNN\b|convolutional neural|卷积神经(?:网络)?(?:架构|结构|示意)?图?", re.I),
        118,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/multimodal-fusion-architecture-rules.md",
        "multimodal or multi-branch fusion architecture",
        re.compile(r"multimodal fusion|multi[- ]branch fusion|多模态融合|多分支融合", re.I),
        116,
    ),
    VisualLeafRule(
        "data_chart",
        "references/3d-bar-visualization-rules.md",
        "3D bar chart",
        re.compile(r"\b(?:3d bar|bar3d|3-d bar)\b|三维柱(?:状)?图|立体柱(?:状)?图", re.I),
        114,
    ),
    VisualLeafRule(
        "data_chart",
        "references/3d-scatter-visualization-rules.md",
        "3D scatter or point-cloud chart",
        re.compile(r"\b(?:3d scatter|scatter3d|point cloud)\b|三维散点图?|点云图?", re.I),
        112,
    ),
    VisualLeafRule(
        "data_chart",
        "references/tsne-visualization-rules.md",
        "t-SNE embedding chart",
        re.compile(r"\bt-?SNE\b|embedding plot|嵌入可视化|流形可视化", re.I),
        110,
    ),
    VisualLeafRule(
        "data_chart",
        "references/flow-visualization-rules.md",
        "Sankey, chord, or directed-flow chart",
        re.compile(r"\b(?:sankey|chord diagram|alluvial|OD flow)\b|桑基图|弦图|河流图|流向图", re.I),
        108,
    ),
    VisualLeafRule(
        "data_chart",
        "references/radar-taylor-surface-visualization-rules.md",
        "radar, Taylor, or 3D response-surface chart",
        re.compile(r"\b(?:radar chart|taylor diagram|response surface|3d surface|surface plot)\b|雷达图|泰勒图|响应面|三维曲面|目标函数曲面", re.I),
        106,
    ),
    VisualLeafRule(
        "data_chart",
        "references/parallel-pareto-gantt-visualization-rules.md",
        "parallel coordinates, Pareto front, or Gantt chart",
        re.compile(r"\b(?:parallel coordinates?|pareto front|gantt|timeline chart)\b|平行坐标|帕累托前沿|甘特图|时间线图", re.I),
        104,
    ),
    VisualLeafRule(
        "data_chart",
        "references/distribution-visualization-rules.md",
        "distribution, violin, box, or ridgeline chart",
        re.compile(r"\b(?:distribution plot|violin plot|box plot|boxplot|ridgeline|joyplot|histogram)\b|分布图|小提琴图|箱线图|山峦图|脊线图|直方图", re.I),
        102,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/mermaid-diagram-templates.md",
        "Mermaid sequence or compact structural diagram",
        re.compile(r"\b(?:mermaid|sequenceDiagram|sequence diagram)\b|时序图", re.I),
        100,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/structure-schematic-rules.md",
        "structure, geometry, or model-relationship schematic",
        re.compile(r"\b(?:structure schematic|model relationship diagram|geometry schematic)\b|结构示意图|模型关系图|变量关系图|几何示意图|对象结构图", re.I),
        98,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/system-flowchart-diagram-rules.md",
        "system flowchart or state-transition diagram",
        re.compile(r"\b(?:system flowchart|flowchart|process diagram|state[- ]transition diagram)\b|系统流程图|流程图|状态转移图|决策流程图", re.I),
        96,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/neural-network-diagram-rules.md",
        "neural-network or learned-surrogate architecture",
        re.compile(r"\b(?:neural network diagram|MLP architecture|BP network diagram|learned surrogate architecture)\b|神经网络(?:架构|结构)图|代理模型架构图", re.I),
        94,
    ),
    VisualLeafRule(
        "special_visual",
        "references/image-generation-visual-rules.md",
        "traceable AI-generated explanatory illustration",
        re.compile(r"\b(?:AI image|image generation|generated illustration|concept illustration)\b|AI\s*插图|生成式图片|概念插图|生成图片", re.I),
        92,
    ),
    VisualLeafRule(
        "structural_diagram",
        "references/ppt-reasoning-diagram-rules.md",
        "editable PPT reasoning diagram",
        re.compile(r"\b(?:PPT reasoning|PowerPoint reasoning|PPT diagram|PowerPoint diagram)\b|PPT\s*(?:推理图|流程图|架构图)", re.I),
        90,
    ),
    VisualLeafRule(
        "style_spec",
        "references/color-palette-rules.md",
        "semantic color palette",
        re.compile(r"\b(?:color palette|colour palette|colorblind palette|semantic color)\b|配色方案|色盲配色|颜色编码|语义配色", re.I),
        80,
    ),
    VisualLeafRule(
        "style_spec",
        "references/three-line-table-rules.md",
        "three-line table typography",
        re.compile(r"\b(?:three-line table|booktabs)\b|三线表", re.I),
        78,
        frozenset({"paper"}),
    ),
    VisualLeafRule(
        "style_spec",
        "references/abstract-layout-rules.md",
        "abstract and first-page layout",
        re.compile(r"\babstract layout\b|摘要版式|摘要排版|首页版式", re.I),
        76,
        frozenset({"paper"}),
    ),
    VisualLeafRule(
        "special_visual",
        "references/chart-gallery-index.md",
        "curated chart-gallery lookup",
        re.compile(r"\b(?:chart gallery|plot gallery|chart examples?)\b|图表图库|图表画廊|图表示例库|选图参考", re.I),
        70,
    ),
    VisualLeafRule(
        "style_spec",
        "references/figure-claim-ownership-rules.md",
        "figure-to-claim ownership",
        re.compile(r"\b(?:figure claim ownership|figure-to-claim|claim-bound figure)\b|图表论点归属|图证据归属|图表支撑结论", re.I),
        68,
    ),
    VisualLeafRule(
        "style_spec",
        "references/figure-narrative-rules.md",
        "figure-text narrative loop",
        re.compile(r"\b(?:figure narrative|figure-text narrative)\b|图文叙事|图前说明|图后解读", re.I),
        66,
        frozenset({"paper"}),
    ),
    VisualLeafRule(
        "style_spec",
        "references/figure-diversity-portfolio-rules.md",
        "visual diversity portfolio",
        re.compile(r"\b(?:figure diversity|visual diversity|visual portfolio)\b|图表多样性|视觉组合|图形重复", re.I),
        64,
    ),
    VisualLeafRule(
        "style_spec",
        "references/journal-grade-figure-rules.md",
        "journal-grade core figure",
        re.compile(r"\b(?:journal-grade figure|publication-quality figure|multi-panel core figure)\b|期刊级图表|高水平图表|多面板核心图", re.I),
        62,
    ),
    VisualLeafRule(
        "style_spec",
        "references/visual-expression-rules.md",
        "general visual expression and readability",
        re.compile(r"\b(?:visual expression|figure readability|visual polish)\b|视觉表达|图表美化|图形可读性|图表规范", re.I),
        50,
    ),
]

# Compatibility view used by the registry audit. Matching is owned by the
# shared trigger contract so routing and stage-end coverage use one rule set.
PUBLIC_RISK_REFS = [
    (rule.keyword_pattern, rule.reference, rule.reason, set(rule.owner_stages))
    for rule in TRIGGER_RULES[:4]
]


@dataclass
class ReferenceItem:
    path: str
    reason: str


@dataclass
class Route:
    schema_version: int
    generated_at: str
    stage: str
    phase: str
    lane: str
    output_level: str
    load_now: list[ReferenceItem]
    optional_later: list[ReferenceItem]
    commands: list[str]
    notes: list[str]
    trigger_hits: list[TriggerHit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--stage", help="analysis, modeling, implementation, or paper")
    parser.add_argument("--phase", help="Legacy phase or gate alias")
    parser.add_argument("--request", default="", help="Current user request text")
    parser.add_argument("--write-report", help="Write markdown route, default planning/reference_route.md when --write is used")
    parser.add_argument("--write-json", help="Write JSON route")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    parser.add_argument("--write", action="store_true", help="Write planning/reference_route.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    route = build_route(root, args.stage or args.phase or "analysis", args.request)
    if args.json:
        print(json.dumps(asdict(route), ensure_ascii=False, indent=2))
    else:
        print(markdown(route))

    report_path = Path(args.write_report) if args.write_report else root / "planning" / "reference_route.md"
    if args.write or args.write_report:
        report_path = report_path if report_path.is_absolute() else root / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown(route), encoding="utf-8")
        print(f"INFO: wrote {rel(root, report_path)}")
    if args.write or args.write_json:
        json_path = Path(args.write_json) if args.write_json else root / "planning" / "reference_route.json"
        json_path = json_path if json_path.is_absolute() else root / json_path
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(asdict(route), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"INFO: wrote {rel(root, json_path)}")
    return 0


def build_route(root: Path, phase_value: str, request: str) -> Route:
    requested_mode = str(phase_value or "analysis").strip().lower()
    phase = normalize_phase(phase_value)
    lane = detect_lane(root)
    output_level = detect_output_level(root, request)
    context = collect_context(root, request)

    refs: dict[str, str] = {}
    for path in PUBLIC_STAGE_REFS.get(phase, PUBLIC_STAGE_REFS["analysis"]):
        refs[path] = f"required for {phase}"
    if requested_mode in MAINTENANCE_REFS:
        refs[MAINTENANCE_REFS[requested_mode]] = f"{requested_mode} maintenance inside {phase}"

    if lane == "compact":
        trim_for_compact(refs, phase)
    elif lane == "deep":
        refs["references/skill-compaction.md"] = "deep lane still uses compaction before loading granular skills"
        if phase == "modeling":
            refs["references/validation-patterns.md"] = "deep lane validation pattern"

    if output_level == "contest_final" and phase in CONDITIONAL_REF_OWNER_STAGES["references/anti-paper-tiger-rules.md"]:
        refs["references/anti-paper-tiger-rules.md"] = "contest_final evidence gate"

    trigger_hits = route_trigger_hits(evaluate_reference_triggers(root, request), phase)
    risk_hits: list[str] = []
    deferred_risk_hits: list[str] = []
    for hit in trigger_hits:
        if hit.disposition == "load_now":
            risk_hits.append(hit.reason)
            refs[hit.reference] = hit.reason
        else:
            deferred_risk_hits.append(hit.reason)

    visual_leaf, deferred_visual_leaves = select_visual_leaf(request, context, phase)
    if visual_leaf is not None:
        refs[visual_leaf.path] = (
            f"visual leaf [{visual_leaf.category}]: {visual_leaf.reason}"
        )

    commands = commands_for_phase(requested_mode, output_level=output_level)
    optional = optional_references(refs, phase)
    notes = [
        "Load only `load_now` references before acting on this stage.",
        "Treat other references as optional until a finding, command output, or expansion trigger names them.",
        "Granular external SKILL.md files are not authority in compact/standard lanes.",
    ]
    if risk_hits:
        notes.append("Risk-triggered additions: " + "; ".join(sorted(set(risk_hits))))
    if deferred_risk_hits:
        notes.append("Risk triggers were detected but deferred until the owning stage: " + "; ".join(sorted(set(deferred_risk_hits))))
    if visual_leaf is not None:
        notes.append(
            "Secondary visual route selected exactly one leaf: "
            f"[{visual_leaf.category}] `{visual_leaf.path}`."
        )
    if deferred_visual_leaves:
        notes.append(
            "Other visual leaves matched but were not loaded; reroute the concrete "
            "figure intent to select one of: "
            + "; ".join(item.path for item in deferred_visual_leaves[:5])
        )
    if requested_mode in MAINTENANCE_REFS:
        notes.append(f"Maintenance mode `{requested_mode}` is owned by the `{phase}` stage; it is not a fifth public stage.")

    return Route(
        schema_version=2,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        stage=phase,
        phase=phase,
        lane=lane,
        output_level=output_level,
        load_now=[ReferenceItem(path=path, reason=reason) for path, reason in sorted(refs.items())],
        optional_later=optional,
        commands=commands,
        notes=notes,
        trigger_hits=trigger_hits,
    )


def normalize_phase(value: str) -> str:
    """Compatibility name retained for callers; output is always a public stage."""
    return normalize_stage(str(value or "analysis").strip().lower())


def select_visual_leaf(
    request: str, context: str, phase: str
) -> tuple[VisualLeafRule | None, list[VisualLeafRule]]:
    """Select one specific visual rule without widening the stage route.

    An explicit current request takes precedence over saved project context.
    Remaining matches are reported as deferred candidates rather than loaded
    together, which keeps visual guidance bounded and makes conflicts visible.
    """
    eligible = [item for item in VISUAL_LEAF_RULES if phase in item.owner_stages]
    explicit = matched_visual_leaves(request, eligible)
    matches = explicit or matched_visual_leaves(context, eligible)
    if not matches:
        return None, []
    return matches[0], matches[1:]


def matched_visual_leaves(
    text: str, rules: list[VisualLeafRule] | None = None
) -> list[VisualLeafRule]:
    candidates = rules if rules is not None else VISUAL_LEAF_RULES
    return sorted(
        (item for item in candidates if item.pattern.search(text or "")),
        key=lambda item: (-item.priority, item.path),
    )


def detect_lane(root: Path) -> str:
    text = read_text(root / "planning" / "workflow_lane.md")
    patterns = [
        r"Selected lane:\s*\*\*(compact|standard|deep)\*\*",
        r"Selected lane:\s*(compact|standard|deep)",
        r"Workflow lane\s*\|\s*(compact|standard|deep)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).lower()
    return "standard"


def detect_output_level(root: Path, request: str) -> str:
    text = request + "\n" + read_text(root / "planning" / "delivery_brief.md")
    match = re.search(r"Output level\s*\|\s*([^|\n]+)", text, flags=re.I)
    if match:
        value = match.group(1).strip()
        if value in {"quick_draft", "reproducible_draft", "contest_final"}:
            return value
    if re.search(r"\b(contest_final|PDF|MathorCup|提交|正式|完整论文|对比|上一版|不如)\b", text, flags=re.I):
        return "contest_final"
    return "reproducible_draft"


def collect_context(root: Path, request: str) -> str:
    # Route from project facts and explicit decisions only. Generated templates,
    # audit reports, and prior route output contain Mira's own vocabulary and can
    # otherwise create self-reinforcing false risk hits.
    parts = [request]
    for rel_path in [
        "planning/delivery_brief.md",
        "planning/workflow_lane.md",
        "planning/problem_analysis.md",
        "planning/attachment_mapping.md",
        "planning/attachment_mapping.json",
        "planning/data_quality_template.json",
        "planning/data_quality_overrides.json",
        "planning/data_cleaning_log.json",
        "planning/modeling_plan.md",
        "planning/figure_claims.json",
        "planning/diagram_intent_pack.json",
    ]:
        parts.append(read_text(root / rel_path)[:8000])
    return "\n".join(parts)


def trim_for_compact(refs: dict[str, str], phase: str) -> None:
    keep = set(PUBLIC_STAGE_REFS.get(phase, [])[:3])
    for path in list(refs):
        if path not in keep and not path.endswith("material-feeding-guidelines.md"):
            refs.pop(path, None)


def optional_references(refs: dict[str, str], phase: str) -> list[ReferenceItem]:
    all_refs = {ref for values in PUBLIC_STAGE_REFS.values() for ref in values}
    all_refs.update(ref for _, ref, _, _ in PUBLIC_RISK_REFS)
    all_refs.update(MATERIAL_REFS.values())
    all_refs.update(item.path for item in VISUAL_LEAF_RULES if phase in item.owner_stages)
    out = []
    for ref in sorted(all_refs - set(refs)):
        if should_list_optional(ref, phase):
            out.append(ReferenceItem(path=ref, reason="load only if a finding or expansion trigger names it"))
    return out[:12]


def should_list_optional(ref: str, phase: str) -> bool:
    if phase == "analysis" and any(term in ref for term in ["writing", "solver", "iteration"]):
        return False
    return True


def markdown(route: Route) -> str:
    lines = [
        "# Mira Reference Route",
        "",
        f"- Generated: {route.generated_at}",
        f"- Stage: **{route.stage}**",
        f"- Lane: **{route.lane}**",
        f"- Output level: **{route.output_level}**",
        "",
        "## Load Now",
        "",
        "| Reference | Reason |",
        "|---|---|",
    ]
    for item in route.load_now:
        lines.append(f"| `{item.path}` | {escape(item.reason)} |")
    if route.trigger_hits:
        lines.extend(["", "## Trigger Evidence", "", "| Rule | Disposition | Evidence |", "|---|---|---|"])
        for hit in route.trigger_hits:
            sources = "; ".join(
                f"{item.source_type}: {item.location}" for item in hit.evidence[:3]
            )
            lines.append(f"| `{hit.rule_id}` | {hit.disposition} | {escape(sources)} |")
    lines.extend(["", "## Commands", ""])
    if route.commands:
        for command in route.commands:
            lines.append(f"- `{command}`")
    else:
        lines.append("- No mandatory command from reference routing.")
    lines.extend(["", "## Optional Later", "", "| Reference | Reason |", "|---|---|"])
    for item in route.optional_later:
        lines.append(f"| `{item.path}` | {escape(item.reason)} |")
    lines.extend(["", "## Notes", ""])
    for note in route.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


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


if __name__ == "__main__":
    raise SystemExit(main())
