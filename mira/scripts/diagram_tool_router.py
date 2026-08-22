#!/usr/bin/env python3
"""Route and audit structural diagram intents for Mira.

This gate keeps implementation focused: Mira first records what each structural diagram
must prove, then selects a truthful, reproducible source. Python/matplotlib is
the default final lane; MATLAB and Mermaid are scoped alternatives.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


STRUCTURAL_TYPES = {
    "flowchart",
    "process",
    "workflow",
    "architecture",
    "roadmap",
    "state_transition",
    "decision_flow",
    "sequence",
    "variable_relation",
    "mechanism",
    "system_link",
    "model_route",
}

DATA_TYPES = {
    "data_chart",
    "bar",
    "line",
    "scatter",
    "heatmap",
    "surface",
    "boxplot",
    "radar",
    "distribution",
}

LEGACY_DRAWIO_ROUTES = {"drawio_mcp", "drawio_xml", "drawio_manual", "next_ai_drawio_mcp"}
MERMAID_ROUTES = {"mermaid", "mermaid_draft", "mermaid_sequence"}
PPT_ROUTES = {"ppt", "pptx", "ppt_pseudo3d", "powerpoint"}
STRUCTURE_ROUTES = {"python_matplotlib", "python_structure", "matlab_structure"}
DATA_ROUTES = {"python", "matplotlib", "seaborn", "pyecharts", "echarts", "echarts_gl", "matlab"}
IMAGE_ROUTES = {"imagegen", "ai_image", "generated_image"}
WAIVER_ROUTES = {"waived", "none"}

EDITABLE_SUFFIXES = {".py", ".m", ".mmd", ".pptx", ".json", ".svg"}
EXPORT_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".webp"}

DIAGRAM_TERMS = re.compile(
    r"\b(flowchart|workflow|process|pipeline|architecture|roadmap|sequence|"
    r"state transition|decision flow|variable relation|mechanism|system link|"
    r"model route|swimlane|drawio|draw\.io|next-ai-draw)\b|"
    r"流程图|结构图|架构图|路线图|思路图|时序图|状态转移|变量关系|机制图|泳道",
    re.I,
)

DATA_CHART_TERMS = re.compile(
    r"\b(bar chart|line chart|scatter|heatmap|surface|boxplot|violin|radar|"
    r"distribution|histogram|3d bar|3d scatter)\b|"
    r"柱状图|折线图|散点图|热力图|曲面图|箱线图|小提琴图|雷达图|分布图",
    re.I,
)

ENGLISH_LABEL_RE = re.compile(r"\b(Start|End|Input|Output|Process|Decision|Model|Result|Data|Server|Client|Database|Yes|No)\b")


@dataclass
class Finding:
    level: str
    axis: str
    artifact: str
    message: str


@dataclass
class Candidate:
    diagram_id: str
    title: str
    reason: str
    recommended_type: str
    recommended_route: str
    source: str


class DiagramToolRouter:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.output_level = args.output_level
        self.intent_path = self._resolve(args.intent_pack or "planning/diagram_intent_pack.json")
        self.template_path = self._resolve(args.write_template) if args.write_template else self.root / "planning" / "diagram_intent_pack_template.json"
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "checks" / "diagram_tool_route_report.md"
        self.json_path = self._resolve(args.write_json) if args.write_json else self.root / "checks" / "diagram_tool_route_report.json"
        self.findings: list[Finding] = []
        self.candidates = collect_candidates(self.root)
        self.intents = load_intents(self.intent_path)
        self.tooling = detect_tooling()

    def run(self) -> int:
        self._check()
        self._write_template()
        self._write_report()
        self._write_json()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _check(self) -> None:
        existing_diagrams = existing_diagram_assets(self.root)
        paper_refs = paper_diagram_refs(self.root)
        if not self.intents:
            if existing_diagrams or paper_refs:
                level = "FAIL" if self.output_level == "contest_final" else "WARN"
                self._add(level, "intent_pack", "planning/diagram_intent_pack.json", "diagram assets or paper references exist but no diagram intent pack is recorded")
            elif self.candidates:
                self._add("WARN", "opportunity", "planning/diagram_intent_pack.json", "structural diagram opportunities detected; fill the generated intent-pack template or record a waiver")
            else:
                self._add("INFO", "opportunity", "-", "no structural diagram opportunity detected")
            return

        seen_ids: set[str] = set()
        for intent in self.intents:
            diagram_id = str(intent.get("diagram_id") or intent.get("id") or "").strip()
            artifact = diagram_id or str(intent.get("export_file") or intent.get("source_file") or "-")
            if not diagram_id:
                self._add("FAIL", "identity", artifact, "diagram_id is missing")
            elif diagram_id in seen_ids:
                self._add("WARN", "identity", artifact, "duplicate diagram_id; keep stable unique ids")
            seen_ids.add(diagram_id)
            self._check_intent(intent, artifact)

    def _check_intent(self, intent: dict[str, Any], artifact: str) -> None:
        diagram_type = normalize_token(intent.get("diagram_type") or intent.get("type"))
        route = normalize_token(intent.get("tool_route") or intent.get("route") or intent.get("tool"))
        paper_use = normalize_token(intent.get("paper_use") or intent.get("use") or ("main" if intent.get("main_paper") is True else ""))
        source_file = str(intent.get("source_file") or intent.get("editable_source") or intent.get("diagram_source") or "").strip()
        export_file = str(intent.get("export_file") or intent.get("image_file") or intent.get("asset") or "").strip()
        core_claim = str(intent.get("core_claim") or intent.get("claim") or "").strip()
        paper_section = str(intent.get("paper_section") or intent.get("section") or "").strip()
        labels_language = normalize_token(intent.get("labels_language") or intent.get("language"))
        nodes = as_list(intent.get("nodes"))
        edges = as_list(intent.get("edges"))
        source_artifacts = as_list(intent.get("source_artifacts") or intent.get("evidence_sources"))
        waiver = str(intent.get("waiver") or intent.get("waiver_reason") or "").strip()

        if route in WAIVER_ROUTES:
            if len(waiver) < 8:
                self._add("WARN", "waiver", artifact, "diagram is waived but waiver_reason is missing or too short")
            return

        if not diagram_type:
            self._add("FAIL", "diagram_type", artifact, "diagram_type is missing")
        if not route:
            self._add("FAIL", "tool_route", artifact, "tool_route is missing")
        if diagram_type in DATA_TYPES or DATA_CHART_TERMS.search(" ".join(map(str, [diagram_type, route, intent]))):
            self._add("FAIL", "stage_boundary", artifact, "data charts and structural diagrams belong to implementation; route them through their specialized renderers")

        is_structural = diagram_type in STRUCTURAL_TYPES or DIAGRAM_TERMS.search(str(intent))
        if is_structural:
            self._check_structural_route(intent, artifact, diagram_type, route, source_file, export_file)
        if route in IMAGE_ROUTES and is_structural:
            self._add("FAIL", "tool_route", artifact, "AI image generation is not an editable source for precise structural diagrams")

        main_paper = paper_use in {"", "main", "body", "paper", "main_paper"}
        required_level = "FAIL" if self.output_level == "contest_final" and main_paper else "WARN"
        if main_paper and len(core_claim) < 8:
            self._add(required_level, "core_claim", artifact, "main-paper diagram needs a concrete core_claim before drawing")
        if main_paper and not paper_section:
            self._add("WARN", "placement", artifact, "paper_section is missing; the diagram may drift away from its explanation")
        if not source_artifacts:
            self._add("WARN", "traceability", artifact, "source_artifacts are missing; map the diagram to model/code/result evidence")
        if is_structural and len(nodes) < 3:
            self._add("WARN", "spec", artifact, "structural diagram spec has fewer than 3 nodes")
        if is_structural and len(edges) < 2:
            self._add("WARN", "spec", artifact, "structural diagram spec has fewer than 2 edges")
        if self.output_level == "contest_final" and main_paper and labels_language not in {"zh", "chinese", "zh-cn", "cn"}:
            self._add("FAIL", "language", artifact, "main-paper diagram labels must be Chinese; set labels_language=zh after checking labels")
        if source_file and has_english_labels(self.root / source_file):
            self._add("WARN", "language", source_file, "editable source may contain English default labels such as Start/Input/Process/Decision")

        if self.output_level == "contest_final" and main_paper:
            self._require_file(source_file, "source_file", artifact, EDITABLE_SUFFIXES)
            self._require_file(export_file, "export_file", artifact, EXPORT_SUFFIXES)
        elif source_file:
            self._check_optional_file(source_file, "source_file", artifact, EDITABLE_SUFFIXES)
        elif export_file:
            self._check_optional_file(export_file, "export_file", artifact, EXPORT_SUFFIXES)

        if route in LEGACY_DRAWIO_ROUTES:
            self._add("FAIL", "retired_backend", artifact, "draw.io is retired from Mira's active workflow; use python_matplotlib or a justified MATLAB/Mermaid route")
    def _check_structural_route(self, intent: dict[str, Any], artifact: str, diagram_type: str, route: str, source_file: str, export_file: str) -> None:
        if diagram_type != "sequence" and route not in STRUCTURE_ROUTES:
            if route in MERMAID_ROUTES:
                self._add("WARN", "tool_route", artifact, "Mermaid is acceptable as a draft; use a Python source for a polished nontrivial structural diagram")
            elif route in PPT_ROUTES:
                self._add("WARN", "tool_route", artifact, "PPT remains useful for special editable layouts; prefer Python for ordinary structural diagrams")
            elif route not in DATA_ROUTES and route not in IMAGE_ROUTES:
                self._add("WARN", "tool_route", artifact, "structural diagram route is unusual; record why Python/MATLAB was not selected")
        if diagram_type == "sequence" and route in MERMAID_ROUTES and self.output_level == "contest_final":
            if not export_file:
                self._add("WARN", "sequence", artifact, "Mermaid sequence diagrams used in final papers need an exported SVG/PDF/PNG")

    def _require_file(self, rel_path: str, axis: str, artifact: str, suffixes: set[str]) -> None:
        if not rel_path:
            self._add("FAIL", axis, artifact, f"{axis} is missing")
            return
        path = self.root / rel_path
        if not path.exists():
            self._add("FAIL", axis, rel_path, f"{axis} file does not exist")
            return
        if path.suffix.lower() not in suffixes:
            self._add("WARN", axis, rel_path, f"{axis} has an unusual suffix for this diagram route")
        if path.stat().st_size < 80:
            self._add("WARN", axis, rel_path, f"{axis} file is very small; check for placeholder output")

    def _check_optional_file(self, rel_path: str, axis: str, artifact: str, suffixes: set[str]) -> None:
        path = self.root / rel_path
        if not path.exists():
            self._add("WARN", axis, rel_path, f"{axis} is recorded but the file does not exist yet")
        elif path.suffix.lower() not in suffixes:
            self._add("WARN", axis, rel_path, f"{axis} has an unusual suffix")

    def payload(self) -> dict[str, Any]:
        return {
            "generated_at": now(),
            "root": str(self.root),
            "output_level": self.output_level,
            "verdict": verdict(self.findings),
            "tooling": self.tooling,
            "intent_pack": rel(self.root, self.intent_path),
            "template": rel(self.root, self.template_path),
            "metrics": {
                "candidate_opportunities": len(self.candidates),
                "recorded_intents": len(self.intents),
                "warnings": sum(1 for item in self.findings if item.level == "WARN"),
                "failures": sum(1 for item in self.findings if item.level == "FAIL"),
            },
            "candidates": [asdict(item) for item in self.candidates],
            "intents": self.intents,
            "findings": [asdict(item) for item in self.findings],
        }

    def _write_template(self) -> None:
        payload = {
            "version": 1,
            "generated_at": now(),
            "instructions": [
                "Copy resolved records into planning/diagram_intent_pack.json.",
                "Use python_matplotlib as the default final route for structural diagrams.",
                "Keep data charts in implementation and AI-generated images only for non-structural illustrations.",
                "For main-paper visuals, add a concrete, evidence-linked core claim to planning/figure_claims.json.",
            ],
            "intents": [candidate_template(item) for item in self.candidates],
        }
        self.template_path.parent.mkdir(parents=True, exist_ok=True)
        self.template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(markdown(self.payload()), encoding="utf-8")

    def _write_json(self) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.write_text(json.dumps(self.payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _emit(self) -> None:
        payload = self.payload()
        print_utf8(f"VERDICT: {payload['verdict']}")
        print_utf8("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
        for item in self.findings:
            print_utf8(f"{item.level}: {item.axis}: {item.artifact}: {item.message}")
        print_utf8(f"INFO: wrote {rel(self.root, self.template_path)}")
        print_utf8(f"INFO: wrote {rel(self.root, self.report_path)}")
        print_utf8(f"INFO: wrote {rel(self.root, self.json_path)}")

    def _add(self, level: str, axis: str, artifact: str, message: str) -> None:
        self.findings.append(Finding(level, axis, artifact, message))

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


def collect_candidates(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    seen: set[str] = set()
    for candidate in collect_from_storyboard(root) + collect_from_diagram_index(root) + collect_from_paper_refs(root) + collect_from_context(root):
        if candidate.diagram_id in seen:
            continue
        seen.add(candidate.diagram_id)
        rows.append(candidate)
    return rows


def collect_from_storyboard(root: Path) -> list[Candidate]:
    data = load_json(root / "planning" / "figure_storyboard.json", {})
    rows: list[Candidate] = []
    for index, item in enumerate(data.get("items", []) if isinstance(data, dict) else [], start=1):
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(key) or "") for key in ["role", "proposed_visual", "nearby_claim", "callout", "source_artifact"])
        if not DIAGRAM_TERMS.search(text):
            continue
        title = str(item.get("proposed_visual") or item.get("role") or f"结构图 {index}").strip()
        rows.append(
            Candidate(
                diagram_id=slugify(title, f"storyboard_diagram_{index}"),
                title=title,
                reason="figure_storyboard mentions a structural diagram",
                recommended_type=infer_diagram_type(text),
                recommended_route=recommend_route(text),
                source="planning/figure_storyboard.json",
            )
        )
    return rows


def collect_from_diagram_index(root: Path) -> list[Candidate]:
    text = read_text(root / "diagrams" / "diagram_index.md")
    rows: list[Candidate] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in {"diagram", "artifact", "file", "source"}:
            continue
        joined = " ".join(cells)
        if not DIAGRAM_TERMS.search(joined) and not looks_like_diagram_path(cells[0]):
            continue
        title = cells[0] or f"indexed_diagram_{index}"
        rows.append(
            Candidate(
                diagram_id=slugify(Path(title).stem, f"diagram_index_{index}"),
                title=title,
                reason="diagram_index has a structural diagram row",
                recommended_type=infer_diagram_type(joined),
                recommended_route=recommend_route(joined),
                source="diagrams/diagram_index.md",
            )
        )
    return rows


def collect_from_paper_refs(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    for path in sorted((root / "paper").rglob("*")) if (root / "paper").exists() else []:
        if path.suffix.lower() not in {".tex", ".typ", ".md"}:
            continue
        text = read_text(path)
        for match in re.finditer(r"(?:includegraphics|image|figure|#figure)\{?([^{}\s]+diagrams/[^{}\s]+)", text, re.I):
            asset = match.group(1).strip().strip("{}")
            rows.append(
                Candidate(
                    diagram_id=slugify(Path(asset).stem, "paper_diagram_ref"),
                    title=asset,
                    reason=f"paper references {asset}",
                    recommended_type=infer_diagram_type(asset),
                    recommended_route=recommend_route(asset),
                    source=rel(root, path),
                )
            )
    return rows


def collect_from_context(root: Path) -> list[Candidate]:
    context = "\n".join(
        read_text(root / path)
        for path in [
            "planning/modeling_plan.md",
            "planning/problem_analysis.md",
            "results/result_report.md",
        ]
    )
    rows: list[Candidate] = []
    if DIAGRAM_TERMS.search(context):
        rows.append(
            Candidate(
                diagram_id="overall_model_route",
                title="整体建模路线图",
                reason="modeling/result context mentions process, route, architecture, or mechanism structure",
                recommended_type=infer_diagram_type(context),
                recommended_route="python_matplotlib",
                source="planning/modeling_plan.md",
            )
        )
    return rows


def candidate_template(candidate: Candidate) -> dict[str, Any]:
    return {
        "diagram_id": candidate.diagram_id,
        "title": candidate.title,
        "paper_use": "main",
        "paper_section": "",
        "diagram_type": candidate.recommended_type,
        "tool_route": candidate.recommended_route,
        "execution_mode": "offline_reproducible_source",
        "core_claim": "",
        "claim_ids": [],
        "source_artifacts": [],
        "lanes": [
            {"id": "shared", "label": "共享数学核心", "order": 0},
            {"id": "questions", "label": "分问题求解", "order": 1},
            {"id": "verification", "label": "验证与回退", "order": 2},
        ],
        "nodes": [
            {"id": "input", "label": "题目数据与约束", "lane": "shared", "role": "input", "level": 0, "claim_ids": []},
            {"id": "core", "label": "共享数学核心", "lane": "shared", "role": "shared", "level": 1, "claim_ids": []},
            {"id": "method", "label": "分问题方法链", "lane": "questions", "role": "method", "level": 2, "claim_ids": []},
            {"id": "result", "label": "关键结果", "lane": "questions", "role": "output", "level": 3, "claim_ids": []},
            {"id": "verify", "label": "残差与边界核验", "lane": "verification", "role": "validation", "level": 3, "claim_ids": []},
            {"id": "decision", "label": "证据是否支持主张", "lane": "verification", "role": "decision", "level": 4, "claim_ids": []},
            {"id": "publish", "label": "冻结结果并写入论文", "lane": "shared", "role": "output", "level": 5, "claim_ids": []},
        ],
        "edges": [
            {"from": "input", "to": "core", "kind": "main"},
            {"from": "core", "to": "method", "kind": "dependency"},
            {"from": "method", "to": "result", "kind": "main"},
            {"from": "result", "to": "verify", "kind": "validation"},
            {"from": "verify", "to": "decision", "kind": "validation"},
            {"from": "decision", "to": "publish", "label": "通过", "kind": "main"},
            {"from": "decision", "to": "core", "label": "不通过", "kind": "feedback"},
        ],
        "layout": {"node_width": 2.25, "node_height": 0.92, "level_gap": 1.25, "lane_height": 2.45},
        "generation_guidance": generation_guidance(candidate),
        "source_file": f"planning/flowcharts/{candidate.diagram_id}.json" if candidate.recommended_route == "python_matplotlib" else "",
        "export_file": f"diagrams/{candidate.diagram_id}.pdf",
        "png_file": f"diagrams/{candidate.diagram_id}.png",
        "labels_language": "zh",
        "waiver_reason": "",
    }


def generation_guidance(candidate: Candidate) -> str:
    return (
        f"请用可复现的 Python/MATLAB 源码生成中文论文结构图《{candidate.title}》。"
        "要求：白色背景、无网格背景、2-4 种语义颜色、从左到右或从上到下单一主阅读方向；"
        "包含真实的输入、模型、算法、结果、验证或反馈节点；每条箭头标注传递对象；"
        "不要使用英文默认标签，不要画装饰性图标；按 flowchart.schema.json 记录泳道、层级、主张与验证分支，"
        "使用 render_structured_flowchart.py 导出矢量 PDF 和 300 DPI PNG，并保留 JSON 规范与 provenance。"
    )


def load_intents(path: Path) -> list[dict[str, Any]]:
    data = load_json(path, {})
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        records = data.get("intents") or data.get("diagrams") or data.get("items") or []
        return [item for item in records if isinstance(item, dict)]
    return []


def existing_diagram_assets(root: Path) -> list[Path]:
    base = root / "diagrams"
    if not base.exists():
        return []
    return [
        path
        for path in base.rglob("*")
        if path.is_file()
        and path.name.lower() != "diagram_index.md"
        and path.suffix.lower() in EDITABLE_SUFFIXES | EXPORT_SUFFIXES
    ]


def paper_diagram_refs(root: Path) -> list[str]:
    refs: list[str] = []
    for path in sorted((root / "paper").rglob("*")) if (root / "paper").exists() else []:
        if path.suffix.lower() not in {".tex", ".typ", ".md"}:
            continue
        text = read_text(path)
        refs.extend(re.findall(r"diagrams[/\\][^{}\s)]+", text, re.I))
    return refs


def detect_tooling() -> dict[str, Any]:
    return {
        "python_available": bool(shutil.which("python")),
        "matlab_installed": bool(shutil.which("matlab")),
        "mermaid_cli_available": bool(shutil.which("mmdc")),
        "note": "Python is the default structural route; MATLAB requires verified batch execution; Mermaid is scoped to sequence diagrams.",
    }


def infer_diagram_type(text: str) -> str:
    lower = text.lower()
    if re.search(r"sequence|sequencediagram|时序|交互顺序|调用", lower):
        return "sequence"
    if re.search(r"architecture|framework|架构|结构|框架", lower):
        return "architecture"
    if re.search(r"state|markov|dp|transition|状态|转移", lower):
        return "state_transition"
    if re.search(r"decision|approve|reject|判断|决策|审批|是?否", lower):
        return "decision_flow"
    if re.search(r"roadmap|route|路线|技术路线|思路", lower):
        return "model_route"
    if re.search(r"variable|relation|变量|关系", lower):
        return "variable_relation"
    if re.search(r"mechanism|机制|原理", lower):
        return "mechanism"
    return "flowchart"


def recommend_route(text: str) -> str:
    lower = text.lower()
    if DATA_CHART_TERMS.search(text):
        return "phase_5_chart_router"
    if re.search(r"pseudo|2\.5d|3d|ppt|立体|伪3d", lower):
        return "python_matplotlib"
    if re.search(r"sequence|sequencediagram|时序|交互顺序|调用", lower):
        return "mermaid_sequence"
    return "python_matplotlib"


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value in {None, ""}:
        return []
    return [value]


def normalize_token(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(value or "").strip().lower())


def looks_like_diagram_path(value: str) -> bool:
    suffix = Path(value).suffix.lower()
    return suffix in EDITABLE_SUFFIXES | EXPORT_SUFFIXES or DIAGRAM_TERMS.search(value) is not None


def has_english_labels(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.suffix.lower() not in {".py", ".m", ".mmd", ".svg", ".json"}:
        return False
    text = read_text(path)[:40000]
    return ENGLISH_LABEL_RE.search(text) is not None


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore") if path.exists() else ""
    except OSError:
        return ""


def rel(root: Path, path: Path | str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


def slugify(text: str, fallback: str) -> str:
    text = Path(text).stem if text else ""
    slug = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff-]+", "_", text).strip("_").lower()
    return slug or fallback


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Diagram Tool Route Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Output level: `{payload['output_level']}`",
        f"- Intent pack: `{payload['intent_pack']}`",
        f"- Template: `{payload['template']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Tooling", "", "| Key | Value |", "|---|---|"])
    for key, value in payload["tooling"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Candidates", "", "| Diagram | Type | Route | Reason | Source |", "|---|---|---|---|---|"])
    if payload["candidates"]:
        for item in payload["candidates"]:
            lines.append(f"| `{escape(item['diagram_id'])}` | {escape(item['recommended_type'])} | {escape(item['recommended_route'])} | {escape(item['reason'])} | `{escape(item['source'])}` |")
    else:
        lines.append("| - | - | - | no candidates detected | - |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Artifact | Message |", "|---|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {escape(item['axis'])} | `{escape(item['artifact'])}` | {escape(item['message'])} |")
    else:
        lines.append("| INFO | - | - | no findings |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Structural diagrams default to reproducible Python sources; use MATLAB only when its computed engineering semantics are material.",
            "- Mermaid remains useful for sequence diagrams; PPT is a scoped exception for special editable layouts.",
            "- Data charts belong to implementation and should use the visual backend router.",
        ]
    )
    return "\n".join(lines) + "\n"


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def print_utf8(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--output-level", default="reproducible_draft", help="quick_draft, reproducible_draft, or contest_final")
    parser.add_argument("--intent-pack", help="Existing diagram intent pack, default planning/diagram_intent_pack.json")
    parser.add_argument("--write-template", help="Write fill-in template, default planning/diagram_intent_pack_template.json")
    parser.add_argument("--write-report", help="Write markdown report, default checks/diagram_tool_route_report.md")
    parser.add_argument("--write-json", help="Write JSON report, default checks/diagram_tool_route_report.json")
    return parser.parse_args()


def main() -> int:
    return DiagramToolRouter(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
