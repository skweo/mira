#!/usr/bin/env python3
"""Render and audit Mira structured flowcharts with Matplotlib/NetworkX."""

from __future__ import annotations

import argparse
import json
import math
import platform
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

from visual_style import apply_mira_style


ROLE_STYLE = {
    "input": ("#E8EEF2", "#536875"),
    "method": ("#DCE9EE", "#3F6D7A"),
    "shared": ("#D8E4E1", "#47736A"),
    "decision": ("#EEE8D8", "#857648"),
    "output": ("#E4E7EB", "#5B6573"),
    "validation": ("#E9E3E8", "#756371"),
}
EDGE_STYLE = {
    "main": ("#344955", "-"),
    "dependency": ("#607D86", "-"),
    "validation": ("#756371", "--"),
    "feedback": ("#9A5E5E", "--"),
}


@dataclass
class Finding:
    level: str
    code: str
    message: str
    evidence: str = ""


class StructuredFlowchart:
    def __init__(self, spec: dict[str, Any], spec_path: Path, output_dir: Path) -> None:
        self.spec = spec
        self.spec_path = spec_path.resolve()
        self.output_dir = output_dir.resolve()
        self.findings: list[Finding] = []
        self.positions: dict[str, tuple[float, float]] = {}
        self.segments: list[tuple[str, str, tuple[float, float], tuple[float, float]]] = []
        self.truncated_nodes: list[str] = []
        self.metrics: dict[str, Any] = {}

    def run(self, audit_only: bool = False) -> dict[str, Any]:
        self._validate_schema()
        if not any(item.level == "FAIL" for item in self.findings):
            self._layout()
            self._audit_information_value()
            self._audit_layout()
            if not audit_only:
                self._render()
        verdict = "FAIL" if any(item.level == "FAIL" for item in self.findings) else "PASS"
        diagram_id = str(self.spec.get("diagram_id") or "flowchart")
        return {
            "schema_version": 1,
            "generated_at": now(),
            "verdict": verdict,
            "diagram_id": diagram_id,
            "spec": str(self.spec_path),
            "outputs": {
                "pdf": str(self.output_dir / f"{diagram_id}.pdf"),
                "png": str(self.output_dir / f"{diagram_id}.png"),
                "provenance": str(self.output_dir / f"{diagram_id}.provenance.json"),
            },
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }

    def fail(self, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("FAIL", code, message, evidence))

    def warn(self, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("WARN", code, message, evidence))

    def _validate_schema(self) -> None:
        required = ("version", "diagram_id", "title", "claim_ids", "lanes", "nodes", "edges")
        for key in required:
            if key not in self.spec:
                self.fail("schema", f"missing required field: {key}")
        if self.spec.get("version") != 1:
            self.fail("schema", "version must be 1")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(self.spec.get("diagram_id") or "")):
            self.fail("schema", "diagram_id must contain only letters, numbers, underscore, or hyphen")
        lanes = self.spec.get("lanes") if isinstance(self.spec.get("lanes"), list) else []
        nodes = self.spec.get("nodes") if isinstance(self.spec.get("nodes"), list) else []
        edges = self.spec.get("edges") if isinstance(self.spec.get("edges"), list) else []
        if not lanes:
            self.fail("schema", "at least one swimlane is required")
        if len(nodes) < 5:
            self.fail("information_value", "a main-paper flowchart requires at least five meaningful nodes")
        lane_ids = [str(item.get("id") or "") for item in lanes if isinstance(item, dict)]
        node_ids = [str(item.get("id") or "") for item in nodes if isinstance(item, dict)]
        if len(set(lane_ids)) != len(lane_ids):
            self.fail("schema", "lane ids must be unique")
        if len(set(node_ids)) != len(node_ids):
            self.fail("schema", "node ids must be unique")
        allowed_roles = set(ROLE_STYLE)
        claims = {str(item) for item in self.spec.get("claim_ids", [])}
        if not claims:
            self.fail("claim_binding", "flowchart must bind at least one claim_id")
        for item in nodes:
            if not isinstance(item, dict):
                self.fail("schema", "every node must be an object")
                continue
            node_id = str(item.get("id") or "")
            if item.get("lane") not in lane_ids:
                self.fail("schema", f"node {node_id} refers to an unknown lane")
            if item.get("role") not in allowed_roles:
                self.fail("schema", f"node {node_id} has invalid role")
            if len(str(item.get("label") or "").strip()) < 2:
                self.fail("schema", f"node {node_id} needs a meaningful label")
            for claim in item.get("claim_ids", []) if isinstance(item.get("claim_ids"), list) else []:
                if str(claim) not in claims:
                    self.fail("claim_binding", f"node {node_id} refers to undeclared claim {claim}")
        for item in edges:
            if not isinstance(item, dict):
                self.fail("schema", "every edge must be an object")
                continue
            if item.get("from") not in node_ids or item.get("to") not in node_ids:
                self.fail("schema", f"edge endpoint is missing: {item}")
            if item.get("kind", "main") not in EDGE_STYLE:
                self.fail("schema", f"edge kind is invalid: {item.get('kind')}")

    def _layout(self) -> None:
        nodes = self.spec["nodes"]
        edges = self.spec["edges"]
        orientation = str(self.spec.get("orientation") or "left_to_right")
        lanes = sorted(self.spec["lanes"], key=lambda item: (int(item.get("order", 0)), str(item.get("id"))))
        lane_index = {str(item["id"]): index for index, item in enumerate(lanes)}
        graph = nx.DiGraph()
        graph.add_nodes_from(str(item["id"]) for item in nodes)
        graph.add_edges_from((str(item["from"]), str(item["to"])) for item in edges if item.get("kind", "main") != "feedback")
        if nx.is_directed_acyclic_graph(graph):
            inferred: dict[str, int] = {}
            for node in nx.topological_sort(graph):
                predecessors = list(graph.predecessors(node))
                inferred[node] = max((inferred[parent] + 1 for parent in predecessors), default=0)
        else:
            self.fail("layout_graph", "non-feedback edges must form a directed acyclic graph")
            return
        layout = self.spec.get("layout") if isinstance(self.spec.get("layout"), dict) else {}
        width = float(layout.get("node_width", 2.25))
        height = float(layout.get("node_height", 0.92))
        level_gap = float(layout.get("level_gap", 1.25))
        lane_height = float(layout.get("lane_height", 2.45))
        lane_width = float(layout.get("lane_width", 3.0))
        groups: dict[tuple[int, int], list[str]] = {}
        node_map = {str(item["id"]): item for item in nodes}
        for node_id, item in node_map.items():
            level = int(item.get("level", inferred.get(node_id, 0)))
            lane = lane_index[str(item["lane"])]
            groups.setdefault((level, lane), []).append(node_id)
        for (level, lane), ids in sorted(groups.items()):
            ids.sort()
            for offset, node_id in enumerate(ids):
                if orientation == "top_to_bottom":
                    center_offset = (offset - (len(ids) - 1) / 2) * (width * 1.18)
                    x = 0.75 + lane * lane_width + lane_width / 2 + center_offset
                    y = -(1.25 + level * (height + level_gap))
                else:
                    center_offset = (offset - (len(ids) - 1) / 2) * (height * 1.18)
                    x = 1.65 + level * (width + level_gap)
                    y = -(lane * lane_height + lane_height / 2 + center_offset)
                self.positions[node_id] = (x, y)
        self.metrics.update(
            {
                "orientation": orientation,
                "lane_count": len(lanes),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "level_count": 1 + max((int(node_map[node].get("level", inferred.get(node, 0))) for node in node_map), default=0),
                "node_width": width,
                "node_height": height,
                "lane_height": lane_height,
                "lane_width": lane_width,
                "level_gap": level_gap,
            }
        )
        self._build_segments(width, height, lane_height, lane_width)

    def _build_segments(self, width: float, height: float, lane_height: float, lane_width: float) -> None:
        self.segments = []
        feedback_index = 0
        orientation = str(self.metrics.get("orientation") or "left_to_right")
        for edge in self.spec["edges"]:
            source = str(edge["from"])
            target = str(edge["to"])
            x1, y1 = self.positions[source]
            x2, y2 = self.positions[target]
            kind = str(edge.get("kind", "main"))
            if orientation == "top_to_bottom":
                start = (x1, y1 - height / 2)
                end = (x2, y2 + height / 2)
                if math.isclose(y1, y2, abs_tol=1e-9) and kind != "feedback":
                    direction = math.copysign(1.0, x2 - x1)
                    start = (x1 + direction * width / 2, y1)
                    end = (x2 - direction * width / 2, y2)
                    points = [start, end]
                elif kind == "feedback" or y2 > y1:
                    feedback_index += 1
                    route_x = 0.75 + len(self.spec["lanes"]) * lane_width + 0.25 * feedback_index
                    points = [start, (route_x, start[1] - 0.22), (route_x, end[1] + 0.22), end]
                else:
                    middle = (start[1] + end[1]) / 2
                    points = [start, (start[0], middle), (end[0], middle), end]
            else:
                start = (x1 + width / 2, y1)
                end = (x2 - width / 2, y2)
                if math.isclose(x1, x2, abs_tol=1e-9) and kind != "feedback":
                    start = (x1, y1 - math.copysign(height / 2, y1 - y2))
                    end = (x2, y2 + math.copysign(height / 2, y1 - y2))
                    points = [start, end]
                elif kind == "feedback" or x2 < x1:
                    feedback_index += 1
                    route_y = lane_height * (0.08 + 0.11 * feedback_index)
                    points = [start, (start[0] + 0.32, route_y), (end[0] - 0.32, route_y), end]
                else:
                    middle = (start[0] + end[0]) / 2
                    points = [start, (middle, start[1]), (middle, end[1]), end]
            for first, second in zip(points, points[1:]):
                self.segments.append((source, target, first, second))

    def _audit_information_value(self) -> None:
        nodes = self.spec["nodes"]
        roles = {str(item.get("role")) for item in nodes}
        required = {"input", "method", "output", "validation"}
        missing = sorted(required - roles)
        self.metrics["roles"] = sorted(roles)
        if missing:
            self.fail("information_value", "flowchart is missing reasoning roles", ", ".join(missing))
        if len(nodes) <= 5 and roles <= {"input", "method", "output"}:
            self.fail("generic_template", "generic input-model-result flowcharts are not accepted")
        claims = set(map(str, self.spec.get("claim_ids", [])))
        bound = {str(claim) for node in nodes for claim in node.get("claim_ids", [])}
        missing_claims = sorted(claims - bound)
        if missing_claims:
            self.fail("claim_binding", "declared claims are not represented by any node", ", ".join(missing_claims))
        if len(claims) >= 2 and "shared" not in roles:
            self.fail("shared_core", "multi-claim route requires an explicit shared mathematical core")
        has_validation_edge = any(edge.get("kind") == "validation" for edge in self.spec["edges"])
        if "validation" not in roles or not has_validation_edge:
            self.fail("validation_branch", "flowchart requires a visible validation branch")

    def _audit_layout(self) -> None:
        node_width = float(self.metrics.get("node_width", 2.25))
        node_height = float(self.metrics.get("node_height", 0.92))
        overlaps: list[str] = []
        node_ids = sorted(self.positions)
        for index, left in enumerate(node_ids):
            x1, y1 = self.positions[left]
            for right in node_ids[index + 1 :]:
                x2, y2 = self.positions[right]
                if abs(x1 - x2) < node_width * 0.96 and abs(y1 - y2) < node_height * 0.96:
                    overlaps.append(f"{left}/{right}")
        crossings: list[str] = []
        for index, first in enumerate(self.segments):
            for second in self.segments[index + 1 :]:
                if {first[0], first[1]} & {second[0], second[1]}:
                    continue
                if segment_intersects(first[2], first[3], second[2], second[3]):
                    crossings.append(f"{first[0]}->{first[1]} x {second[0]}->{second[1]}")
        self.metrics.update({"node_overlaps": overlaps, "edge_crossings": crossings})
        if overlaps:
            self.fail("node_crowding", "flowchart nodes overlap", ", ".join(overlaps))
        if crossings:
            self.fail("edge_crossing", "orthogonal connectors cross", "; ".join(crossings[:12]))

    def _render(self) -> None:
        apply_mira_style(font_size=10)
        diagram_id = str(self.spec["diagram_id"])
        lanes = sorted(self.spec["lanes"], key=lambda item: (int(item.get("order", 0)), str(item.get("id"))))
        node_map = {str(item["id"]): item for item in self.spec["nodes"]}
        orientation = str(self.metrics.get("orientation") or "left_to_right")
        width = float(self.metrics["node_width"])
        height = float(self.metrics["node_height"])
        lane_height = float(self.metrics["lane_height"])
        lane_width = float(self.metrics["lane_width"])
        if orientation == "top_to_bottom":
            max_x = 0.75 + len(lanes) * lane_width + 0.25
            min_y = min(y for _, y in self.positions.values()) - height / 2 - 0.65
            fig_width = max(7.2, len(lanes) * 2.05 + 0.9)
            fig_height = max(8.2, abs(min_y) * 0.65)
        else:
            max_x = max(x for x, _ in self.positions.values()) + width / 2 + 0.8
            min_y = -(len(lanes) * lane_height)
            fig_width = max(10.5, max_x * 0.68)
            fig_height = max(4.2, len(lanes) * 1.55 + 0.8)
        fig, axis = plt.subplots(figsize=(fig_width, fig_height), constrained_layout=False)
        fig.patch.set_facecolor("white")
        axis.set_facecolor("white")
        axis.set_xlim(0, max_x)
        axis.set_ylim(min_y - 0.1, 0.72 if orientation == "top_to_bottom" else lane_height * 0.48)
        axis.axis("off")
        fig.suptitle(self.spec["title"], x=0.025, y=0.97, ha="left", va="top", fontsize=15, fontweight="bold", color="#20262B")
        fig.subplots_adjust(left=0.02, right=0.995, bottom=0.04, top=0.87)
        for index, lane in enumerate(lanes):
            background = "#F7F8F9" if index % 2 == 0 else "#FCFCFC"
            if orientation == "top_to_bottom":
                left = 0.75 + index * lane_width
                axis.add_patch(Rectangle((left, min_y), lane_width, 0.48 - min_y, facecolor=background, edgecolor="#CCD2D7", linewidth=0.8, zorder=0))
                axis.text(left + lane_width / 2, 0.25, str(lane["label"]), ha="center", va="center", fontsize=9.5, color="#58636B", fontweight="bold")
            else:
                top = -index * lane_height
                axis.add_patch(Rectangle((0.75, top - lane_height), max_x - 1.0, lane_height, facecolor=background, edgecolor="#CCD2D7", linewidth=0.8, zorder=0))
                axis.text(0.18, top - lane_height / 2, str(lane["label"]), ha="center", va="center", rotation=90, fontsize=9.5, color="#58636B", fontweight="bold")
        edge_paths = self._edge_paths()
        for edge, points in edge_paths:
            kind = str(edge.get("kind", "main"))
            color, linestyle = EDGE_STYLE[kind]
            for first, second in zip(points[:-2], points[1:-1]):
                axis.plot([first[0], second[0]], [first[1], second[1]], color=color, linewidth=1.25, linestyle=linestyle, zorder=1)
            penultimate, end = points[-2], points[-1]
            axis.annotate("", xy=end, xytext=penultimate, arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.25, "linestyle": linestyle, "mutation_scale": 10}, zorder=2)
            label = str(edge.get("label") or "").strip()
            if label:
                middle = points[len(points) // 2]
                axis.text(middle[0], middle[1] + 0.13, label, fontsize=7.8, color=color, ha="center", va="bottom", bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.7}, zorder=4)
        for node_id, (x, y) in self.positions.items():
            node = node_map[node_id]
            role = str(node["role"])
            face, edge = ROLE_STYLE[role]
            if role == "decision":
                vertices = [(x, y + height * 0.58), (x + width * 0.55, y), (x, y - height * 0.58), (x - width * 0.55, y)]
                axis.add_patch(Polygon(vertices, closed=True, facecolor=face, edgecolor=edge, linewidth=1.1, zorder=3))
            else:
                axis.add_patch(FancyBboxPatch((x - width / 2, y - height / 2), width, height, boxstyle="round,pad=0.025,rounding_size=0.06", facecolor=face, edgecolor=edge, linewidth=1.1, zorder=3))
            label, truncated = wrap_label(str(node["label"]), max_chars=max(8, int(width * 6.0)), max_lines=3)
            if truncated:
                self.truncated_nodes.append(node_id)
            axis.text(x, y, label, ha="center", va="center", fontsize=8.8, color="#20262B", zorder=4, linespacing=1.15)
        self.metrics["truncated_node_labels"] = sorted(self.truncated_nodes)
        if self.truncated_nodes:
            self.fail("text_truncation", "node labels were truncated during rendering", ", ".join(self.truncated_nodes))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pdf = self.output_dir / f"{diagram_id}.pdf"
        png = self.output_dir / f"{diagram_id}.png"
        fig.savefig(pdf, bbox_inches="tight", facecolor="white")
        fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        provenance = {
            "schema_version": 1,
            "generated_at": now(),
            "diagram_id": diagram_id,
            "spec": str(self.spec_path),
            "claim_ids": self.spec.get("claim_ids", []),
            "backend": "python/matplotlib/networkx",
            "python": platform.python_version(),
            "matplotlib": matplotlib.__version__,
            "networkx": nx.__version__,
            "exports": {"pdf": str(pdf), "png": str(png), "png_dpi": 300},
            "metrics": self.metrics,
        }
        (self.output_dir / f"{diagram_id}.provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _edge_paths(self) -> list[tuple[dict[str, Any], list[tuple[float, float]]]]:
        width = float(self.metrics["node_width"])
        height = float(self.metrics["node_height"])
        lane_height = float(self.metrics["lane_height"])
        lane_width = float(self.metrics["lane_width"])
        orientation = str(self.metrics.get("orientation") or "left_to_right")
        feedback_index = 0
        result = []
        for edge in self.spec["edges"]:
            x1, y1 = self.positions[str(edge["from"])]
            x2, y2 = self.positions[str(edge["to"])]
            if orientation == "top_to_bottom":
                start = (x1, y1 - height / 2)
                end = (x2, y2 + height / 2)
                if math.isclose(y1, y2, abs_tol=1e-9) and edge.get("kind") != "feedback":
                    direction = math.copysign(1.0, x2 - x1)
                    start = (x1 + direction * width / 2, y1)
                    end = (x2 - direction * width / 2, y2)
                    points = [start, end]
                elif edge.get("kind") == "feedback" or y2 > y1:
                    feedback_index += 1
                    route_x = 0.75 + len(self.spec["lanes"]) * lane_width + 0.25 * feedback_index
                    points = [start, (route_x, start[1] - 0.22), (route_x, end[1] + 0.22), end]
                else:
                    middle = (start[1] + end[1]) / 2
                    points = [start, (start[0], middle), (end[0], middle), end]
            else:
                start = (x1 + width / 2, y1)
                end = (x2 - width / 2, y2)
                if math.isclose(x1, x2, abs_tol=1e-9) and edge.get("kind") != "feedback":
                    start = (x1, y1 - math.copysign(height / 2, y1 - y2))
                    end = (x2, y2 + math.copysign(height / 2, y1 - y2))
                    points = [start, end]
                elif edge.get("kind") == "feedback" or x2 < x1:
                    feedback_index += 1
                    route_y = lane_height * (0.08 + 0.11 * feedback_index)
                    points = [start, (start[0] + 0.32, route_y), (end[0] - 0.32, route_y), end]
                else:
                    middle = (start[0] + end[0]) / 2
                    points = [start, (middle, start[1]), (middle, end[1]), end]
            result.append((edge, points))
        return result


def wrap_label(text: str, max_chars: int, max_lines: int) -> tuple[str, bool]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return "", False
    lines: list[str] = []
    for manual_line in normalized.split("\n"):
        compact = re.sub(r"[^\S\n]+", " ", manual_line).strip()
        if not compact:
            continue
        current = ""
        for token in re.findall(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z]+(?:[A-Za-z0-9_./+-]*[A-Za-z0-9])?|.", compact):
            token_width = display_width(token)
            if current and display_width(current) + token_width > max_chars:
                lines.append(current.rstrip())
                current = token.lstrip()
            elif not current and token.isspace():
                continue
            else:
                current += token
        if current:
            lines.append(current.rstrip())
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        # Do not shorten the final token: it may be a decimal that must remain exact.
        lines[-1] = lines[-1].rstrip() + "…" if lines[-1] else "…"
    return "\n".join(lines), truncated


def display_width(text: str) -> int:
    return sum(1 if ord(char) < 128 else 2 for char in text)


def segment_intersects(a1: tuple[float, float], a2: tuple[float, float], b1: tuple[float, float], b2: tuple[float, float]) -> bool:
    def orientation(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> int:
        value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if math.isclose(value, 0.0, abs_tol=1e-9):
            return 0
        return 1 if value > 0 else 2

    def on_segment(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> bool:
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1, o2 = orientation(a1, a2, b1), orientation(a1, a2, b2)
    o3, o4 = orientation(b1, b2, a1), orientation(b1, b2, a2)
    if o1 != o2 and o3 != o4:
        return True
    return (o1 == 0 and on_segment(a1, b1, a2)) or (o2 == 0 and on_segment(a1, b2, a2)) or (o3 == 0 and on_segment(b1, a1, b2)) or (o4 == 0 and on_segment(b1, a2, b2))


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_spec(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("flowchart spec root must be a JSON object")
    return payload


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Mira Structured Flowchart Report",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Diagram: `{payload['diagram_id']}`",
        f"- Spec: `{payload['spec']}`",
        "",
        "## Findings",
        "",
        "| Level | Code | Message | Evidence |",
        "|---|---|---|---|",
    ]
    if payload["findings"]:
        for item in payload["findings"]:
            values = [str(item.get(key, "")).replace("|", "\\|").replace("\n", " ") for key in ("level", "code", "message", "evidence")]
            lines.append("| " + " | ".join(values) + " |")
    else:
        lines.append("| INFO | complete | no findings | - |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--spec", required=True, help="Structured flowchart JSON")
    parser.add_argument("--output-dir", default="diagrams")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--write-json", default="checks/structured_flowchart_report.json")
    parser.add_argument("--write-report", default="checks/structured_flowchart_report.md")
    return parser.parse_args()


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    spec_path = resolve(root, args.spec)
    try:
        spec = load_spec(spec_path)
        payload = StructuredFlowchart(spec, spec_path, resolve(root, args.output_dir)).run(args.audit_only)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "schema_version": 1,
            "generated_at": now(),
            "verdict": "FAIL",
            "diagram_id": "invalid",
            "spec": str(spec_path),
            "outputs": {},
            "metrics": {},
            "findings": [{"level": "FAIL", "code": "spec_read", "message": str(exc), "evidence": str(spec_path)}],
        }
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"diagram: {payload['diagram_id']}")
    print(f"findings: {len(payload['findings'])}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
