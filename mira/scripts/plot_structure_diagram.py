#!/usr/bin/env python3
"""Generate reproducible structure-schematic diagrams for Mira papers."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, save_mira_figure


NODE_STYLES = {
    "data": {"face": "#E8F2FB", "edge": MIRA_COLORS["blue"], "shape": "round"},
    "process": {"face": "#F4EFE8", "edge": MIRA_COLORS["orange"], "shape": "round"},
    "model": {"face": "#EAF4EF", "edge": MIRA_COLORS["teal"], "shape": "round"},
    "decision": {"face": "#FFF6D8", "edge": MIRA_COLORS["gold"], "shape": "diamond"},
    "state": {"face": "#F1ECF7", "edge": MIRA_COLORS["purple"], "shape": "hex"},
    "equation": {"face": "#FFFFFF", "edge": MIRA_COLORS["gray"], "shape": "square"},
    "result": {"face": "#E9F5E6", "edge": MIRA_COLORS["green"], "shape": "round"},
    "geometry": {"face": "#EFF6FF", "edge": MIRA_COLORS["blue"], "shape": "ellipse"},
    "default": {"face": "#FFFFFF", "edge": MIRA_COLORS["gray"], "shape": "round"},
}


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    spec, source = load_spec(args, root)
    spec = normalize_spec(spec, args)
    outputs = prepare_outputs(args, root)

    nodes_df, edges_df, groups_df, callouts_df = spec_tables(spec)
    nodes_df.to_csv(outputs["nodes"], index=False, encoding="utf-8-sig")
    edges_df.to_csv(outputs["edges"], index=False, encoding="utf-8-sig")
    groups_df.to_csv(outputs["groups"], index=False, encoding="utf-8-sig")
    callouts_df.to_csv(outputs["callouts"], index=False, encoding="utf-8-sig")
    outputs["spec"].write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fig = plot_structure(spec, args)
    png = outputs["figures_dir"] / f"{outputs['prefix']}_structure_diagram.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_structure_diagram.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)

    params = {
        "source": source,
        "layout": args.layout,
        "orientation": args.orientation,
        "n_nodes": len(spec["nodes"]),
        "n_edges": len(spec["edges"]),
        "n_groups": len(spec.get("groups", [])),
        "n_callouts": len(spec.get("callouts", [])),
        "written_figures": [str(png), str(pdf)],
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, spec, [str(png), str(pdf)])

    print("INFO: structure diagram written:")
    print(f"  figure: {png}")
    print(f"  figure: {pdf}")
    print(f"  spec: {outputs['spec']}")
    print(f"  nodes: {outputs['nodes']}")
    print(f"  edges: {outputs['edges']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--spec", help="JSON structure-diagram specification.")
    parser.add_argument("--nodes", help="CSV/XLSX nodes table with id,label columns.")
    parser.add_argument("--edges", help="CSV/XLSX edges table with source,target columns.")
    parser.add_argument("--demo", choices=("model", "system", "geometry"), help="Generate a built-in demo specification.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index for CSV/XLSX inputs.")
    parser.add_argument("--layout", choices=("auto", "manual"), default="auto", help="Use manual x/y when available, otherwise layered layout.")
    parser.add_argument("--orientation", choices=("horizontal", "vertical"), default="horizontal", help="Layer direction for auto layout.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Diagram-data output directory.")
    parser.add_argument("--prefix", default="structure", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title override.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_spec(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], str]:
    if args.demo:
        return demo_spec(args.demo), f"demo:{args.demo}"
    if args.spec:
        path = resolve_path(root, args.spec)
        if not path.exists():
            raise SystemExit(f"ERROR: spec file does not exist: {path}")
        return json.loads(path.read_text(encoding="utf-8")), str(path)
    if args.nodes and args.edges:
        nodes_path = resolve_path(root, args.nodes)
        edges_path = resolve_path(root, args.edges)
        nodes_df = read_table(nodes_path, args.sheet)
        edges_df = read_table(edges_path, args.sheet)
        return spec_from_tables(nodes_df, edges_df), f"nodes:{nodes_path}; edges:{edges_path}"
    raise SystemExit("ERROR: provide --spec <json>, --nodes <table> --edges <table>, or --demo.")


def demo_spec(name: str) -> dict[str, Any]:
    if name == "system":
        return {
            "title": "生产检测与拆解决策系统结构",
            "caption": "结构示意图将来料、检测、装配、调换与拆解回收连接为可递推的决策系统。",
            "nodes": [
                {"id": "input", "label": "来料批次\n次品率先验", "kind": "data", "x": 0.10, "y": 0.52, "w": 0.15},
                {"id": "sample", "label": "抽样检验\n置信判定", "kind": "process", "x": 0.28, "y": 0.52, "w": 0.15},
                {"id": "parts", "label": "零配件状态\nB/U/K", "kind": "state", "x": 0.43, "y": 0.73, "w": 0.15},
                {"id": "assembly", "label": "装配树递推\n成本-合格率", "kind": "model", "x": 0.61, "y": 0.73, "w": 0.17},
                {"id": "recover", "label": "拆解回收\n信息保留", "kind": "state", "x": 0.43, "y": 0.31, "w": 0.15},
                {"id": "exchange", "label": "调换损失\n售后约束", "kind": "process", "x": 0.61, "y": 0.31, "w": 0.16},
                {"id": "decision", "label": "检测/拆解\n组合策略", "kind": "decision", "x": 0.78, "y": 0.52, "w": 0.15, "h": 0.13},
                {"id": "output", "label": "期望利润\n稳健策略", "kind": "result", "x": 0.94, "y": 0.52, "w": 0.15},
            ],
            "edges": [
                {"source": "input", "target": "sample", "label": "样本"},
                {"source": "sample", "target": "parts", "label": "后验"},
                {"source": "parts", "target": "assembly", "label": "转移"},
                {"source": "assembly", "target": "decision", "label": "目标"},
                {"source": "exchange", "target": "decision", "label": "损失"},
                {"source": "decision", "target": "output", "label": "策略"},
                {"source": "assembly", "target": "recover", "label": "拆解", "style": "dashed"},
                {"source": "recover", "target": "parts", "label": "回流", "style": "feedback"},
            ],
            "groups": [
                {"label": "统计判定层", "nodes": ["input", "sample"]},
                {"label": "递推建模层", "nodes": ["parts", "assembly", "exchange", "recover"]},
                {"label": "决策输出层", "nodes": ["decision", "output"]},
            ],
            "callouts": [
                {"target": "parts", "text": "拆解后仍需保留状态信息", "x": 0.48, "y": 0.92},
            ],
        }
    if name == "geometry":
        return {
            "title": "空间几何约束结构示意",
            "caption": "结构示意图展示坐标、距离、角度、碰撞边界和局部放大之间的关系。",
            "nodes": [
                {"id": "coord", "label": "坐标系\nO-XYZ", "kind": "geometry", "x": 0.16, "y": 0.50, "w": 0.16, "h": 0.13},
                {"id": "object", "label": "运动对象\n位置 r(t)", "kind": "state", "x": 0.40, "y": 0.62, "w": 0.18, "h": 0.12},
                {"id": "boundary", "label": "约束边界\nD(r)<=0", "kind": "equation", "x": 0.64, "y": 0.62, "w": 0.18, "h": 0.12},
                {"id": "collision", "label": "临界接触\nD(r*)=0", "kind": "decision", "x": 0.82, "y": 0.50, "w": 0.16, "h": 0.13},
                {"id": "zoom", "label": "局部放大\n阈值区间", "kind": "result", "x": 0.54, "y": 0.30, "w": 0.20, "h": 0.12},
            ],
            "edges": [
                {"source": "coord", "target": "object", "label": "参数化"},
                {"source": "object", "target": "boundary", "label": "代入约束"},
                {"source": "boundary", "target": "collision", "label": "求根/极值"},
                {"source": "boundary", "target": "zoom", "label": "局部细化", "style": "dashed"},
                {"source": "zoom", "target": "collision", "label": "确认阈值"},
            ],
            "callouts": [{"target": "zoom", "text": "全局图给结构，局部图给精度", "x": 0.28, "y": 0.25}],
        }
    return {
        "title": "模型变量关系结构示意",
        "caption": "结构示意图展示输入数据、状态变量、目标函数、约束和输出结论之间的对应关系。",
        "nodes": [
            {"id": "data", "label": "题目数据\n观测量", "kind": "data", "layer": 0},
            {"id": "variables", "label": "决策变量\nx, y, s", "kind": "state", "layer": 1},
            {"id": "objective", "label": "目标函数\nmax F(x)", "kind": "equation", "layer": 2},
            {"id": "constraints", "label": "约束集合\ng_i(x)<=0", "kind": "equation", "layer": 2},
            {"id": "solver", "label": "求解器/枚举\n可行性审计", "kind": "model", "layer": 3},
            {"id": "validation", "label": "稳健性\n灵敏度", "kind": "process", "layer": 4},
            {"id": "result", "label": "推荐方案\n关键阈值", "kind": "result", "layer": 5},
        ],
        "edges": [
            {"source": "data", "target": "variables", "label": "定义"},
            {"source": "variables", "target": "objective", "label": "收益/成本"},
            {"source": "variables", "target": "constraints", "label": "边界"},
            {"source": "objective", "target": "solver", "label": "优化"},
            {"source": "constraints", "target": "solver", "label": "筛选"},
            {"source": "solver", "target": "validation", "label": "候选解"},
            {"source": "validation", "target": "result", "label": "可信结论"},
        ],
        "groups": [
            {"label": "建模对象", "nodes": ["data", "variables"]},
            {"label": "数学模型", "nodes": ["objective", "constraints", "solver"]},
            {"label": "结果解释", "nodes": ["validation", "result"]},
        ],
    }


def read_table(path: Path, sheet: str | int = 0) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"ERROR: table file does not exist: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheet_arg: str | int = int(sheet) if str(sheet).isdigit() else sheet
        return pd.read_excel(path, sheet_name=sheet_arg)
    return read_csv_with_fallback(path)


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(path)


def spec_from_tables(nodes: pd.DataFrame, edges: pd.DataFrame) -> dict[str, Any]:
    if not {"id", "label"}.issubset(nodes.columns):
        raise SystemExit("ERROR: nodes table requires id and label columns.")
    if not {"source", "target"}.issubset(edges.columns):
        raise SystemExit("ERROR: edges table requires source and target columns.")
    return {
        "title": "",
        "nodes": clean_records(nodes),
        "edges": clean_records(edges),
        "groups": [],
        "callouts": [],
    }


def clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.to_dict("records"):
        out = {}
        for key, value in row.items():
            if pd.isna(value):
                continue
            if key in {"x", "y", "w", "h", "layer"}:
                try:
                    out[key] = float(value) if key != "layer" else int(value)
                    continue
                except Exception:
                    pass
            out[key] = value
        records.append(out)
    return records


def normalize_spec(spec: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])
    if not nodes:
        raise SystemExit("ERROR: structure spec requires at least one node.")
    node_ids = []
    for node in nodes:
        if "id" not in node:
            raise SystemExit("ERROR: every node requires an id.")
        node["id"] = str(node["id"])
        node["label"] = str(node.get("label", node["id"]))
        node["kind"] = str(node.get("kind", "default"))
        node["w"] = float(node.get("w", 0.16))
        node["h"] = float(node.get("h", 0.10))
        node_ids.append(node["id"])
    seen = set()
    duplicated = [node_id for node_id in node_ids if node_id in seen or seen.add(node_id)]
    if duplicated:
        raise SystemExit("ERROR: duplicated node ids: " + ", ".join(sorted(set(duplicated))))
    known = set(node_ids)
    for edge in edges:
        edge["source"] = str(edge.get("source", ""))
        edge["target"] = str(edge.get("target", ""))
        if edge["source"] not in known or edge["target"] not in known:
            raise SystemExit(f"ERROR: edge references unknown node: {edge}")
        edge["label"] = str(edge.get("label", ""))
        edge["style"] = str(edge.get("style", "solid"))
    if args.title:
        spec["title"] = args.title
    spec.setdefault("title", "")
    spec.setdefault("caption", "")
    spec.setdefault("groups", [])
    spec.setdefault("callouts", [])
    needs_layout = args.layout == "auto" or any("x" not in node or "y" not in node for node in nodes)
    if needs_layout:
        apply_layered_layout(spec, args.orientation)
    for group in spec.get("groups", []):
        group.setdefault("label", "")
        group.setdefault("nodes", [])
    for callout in spec.get("callouts", []):
        callout.setdefault("text", "")
    return spec


def apply_layered_layout(spec: dict[str, Any], orientation: str) -> None:
    nodes = spec["nodes"]
    node_by_id = {node["id"]: node for node in nodes}
    layers = infer_layers(nodes, spec.get("edges", []))
    max_layer = max(layers.values(), default=0)
    by_layer: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_layer.setdefault(layers[node["id"]], []).append(node)
    for layer, layer_nodes in by_layer.items():
        layer_nodes.sort(key=lambda item: item["id"])
        n = len(layer_nodes)
        for i, node in enumerate(layer_nodes):
            if "x" in node and "y" in node:
                continue
            primary = 0.10 + 0.80 * (layer / max(max_layer, 1))
            secondary = 0.50 if n == 1 else 0.84 - 0.68 * (i / max(n - 1, 1))
            if orientation == "vertical":
                node["x"] = secondary
                node["y"] = 0.90 - 0.80 * (layer / max(max_layer, 1))
            else:
                node["x"] = primary
                node["y"] = secondary
    # Preserve explicit manual positions for nodes already placed.
    for node in nodes:
        node["x"] = float(node.get("x", node_by_id[node["id"]].get("x", 0.5)))
        node["y"] = float(node.get("y", node_by_id[node["id"]].get("y", 0.5)))


def infer_layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    explicit = {node["id"]: int(node["layer"]) for node in nodes if "layer" in node}
    ids = [node["id"] for node in nodes]
    incoming: dict[str, list[str]] = {node_id: [] for node_id in ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        outgoing[source].append(target)
        incoming[target].append(source)
    layers = dict(explicit)
    roots = [node_id for node_id in ids if not incoming[node_id]]
    queue = roots or ids[:1]
    for root in queue:
        layers.setdefault(root, 0)
    changed = True
    for _ in range(len(ids) + len(edges) + 1):
        if not changed:
            break
        changed = False
        for source, targets in outgoing.items():
            if source not in layers:
                continue
            for target in targets:
                candidate = layers[source] + 1
                if target not in layers or candidate > layers[target]:
                    if target in explicit:
                        continue
                    layers[target] = candidate
                    changed = True
    for node_id in ids:
        layers.setdefault(node_id, 0)
    return layers


def plot_structure(spec: dict[str, Any], args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.03, 1.03)
    ax.axis("off")
    node_by_id = {node["id"]: node for node in spec["nodes"]}
    draw_groups(ax, spec.get("groups", []), node_by_id)
    for edge in spec.get("edges", []):
        draw_edge(ax, edge, node_by_id)
    for node in spec["nodes"]:
        draw_node(ax, node)
    for callout in spec.get("callouts", []):
        draw_callout(ax, callout, node_by_id)
    title = spec.get("title", "")
    if title:
        ax.set_title(str(title), pad=10)
    return fig


def draw_groups(ax: Any, groups: list[dict[str, Any]], node_by_id: dict[str, dict[str, Any]]) -> None:
    palette = ["#F7F9FB", "#F9F7F2", "#F4F8F4", "#F7F4FA"]
    for i, group in enumerate(groups):
        nodes = [node_by_id[node_id] for node_id in group.get("nodes", []) if node_id in node_by_id]
        if not nodes and not all(key in group for key in ["x", "y", "w", "h"]):
            continue
        if nodes:
            left = min(node["x"] - node["w"] / 2 for node in nodes) - 0.035
            right = max(node["x"] + node["w"] / 2 for node in nodes) + 0.035
            bottom = min(node["y"] - node["h"] / 2 for node in nodes) - 0.04
            top = max(node["y"] + node["h"] / 2 for node in nodes) + 0.05
        else:
            left = float(group["x"] - group["w"] / 2)
            right = float(group["x"] + group["w"] / 2)
            bottom = float(group["y"] - group["h"] / 2)
            top = float(group["y"] + group["h"] / 2)
        rect = FancyBboxPatch(
            (left, bottom),
            right - left,
            top - bottom,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor=palette[i % len(palette)],
            edgecolor="#D0D7DE",
            linewidth=0.8,
            alpha=0.72,
            zorder=0,
        )
        ax.add_patch(rect)
        label = str(group.get("label", ""))
        if label:
            ax.text(left + 0.012, top - 0.018, label, ha="left", va="top", fontsize=9, color=MIRA_COLORS["gray"], zorder=1)


def draw_node(ax: Any, node: dict[str, Any]) -> None:
    style = NODE_STYLES.get(node.get("kind", "default"), NODE_STYLES["default"])
    x = float(node["x"])
    y = float(node["y"])
    w = float(node.get("w", 0.16))
    h = float(node.get("h", 0.10))
    shape = str(node.get("shape", style["shape"]))
    face = str(node.get("facecolor", style["face"]))
    edge = str(node.get("edgecolor", style["edge"]))
    if shape == "diamond":
        patch = Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True, facecolor=face, edgecolor=edge, linewidth=1.2, zorder=3)
    elif shape == "hex":
        patch = Polygon(
            [
                (x - w * 0.40, y + h / 2),
                (x + w * 0.40, y + h / 2),
                (x + w / 2, y),
                (x + w * 0.40, y - h / 2),
                (x - w * 0.40, y - h / 2),
                (x - w / 2, y),
            ],
            closed=True,
            facecolor=face,
            edgecolor=edge,
            linewidth=1.2,
            zorder=3,
        )
    elif shape == "ellipse":
        patch = Ellipse((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=1.2, zorder=3)
    elif shape == "square":
        patch = Rectangle((x - w / 2, y - h / 2), w, h, facecolor=face, edgecolor=edge, linewidth=1.2, zorder=3)
    else:
        patch = FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor=face,
            edgecolor=edge,
            linewidth=1.2,
            zorder=3,
        )
    ax.add_patch(patch)
    ax.text(x, y, wrap_label(str(node["label"]), max_chars=max(5, int(w * 70))), ha="center", va="center", fontsize=9, color="#222222", linespacing=1.18, zorder=4)


def draw_edge(ax: Any, edge: dict[str, Any], node_by_id: dict[str, dict[str, Any]]) -> None:
    source = node_by_id[edge["source"]]
    target = node_by_id[edge["target"]]
    sx, sy = float(source["x"]), float(source["y"])
    tx, ty = float(target["x"]), float(target["y"])
    style = str(edge.get("style", "solid"))
    color = MIRA_COLORS["gray"]
    linestyle = "-"
    rad = 0.0
    if style == "dashed":
        linestyle = "--"
        color = MIRA_COLORS["purple"]
    elif style == "feedback":
        linestyle = "--"
        color = MIRA_COLORS["red"]
        rad = -0.22 if tx < sx else 0.22
    elif style == "weak":
        color = "#A0A8B0"
    arrow = FancyArrowPatch(
        (sx, sy),
        (tx, ty),
        arrowstyle="-|>",
        connectionstyle=f"arc3,rad={float(edge.get('rad', rad))}",
        mutation_scale=12,
        linewidth=1.2,
        linestyle=linestyle,
        color=color,
        shrinkA=18,
        shrinkB=18,
        zorder=2,
    )
    ax.add_patch(arrow)
    label = str(edge.get("label", ""))
    if label:
        mx, my = (sx + tx) / 2, (sy + ty) / 2
        if rad:
            my += rad * 0.12
        ax.text(
            mx,
            my + 0.016,
            wrap_label(label, 8),
            ha="center",
            va="bottom",
            fontsize=8,
            color=color,
            zorder=5,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
        )


def draw_callout(ax: Any, callout: dict[str, Any], node_by_id: dict[str, dict[str, Any]]) -> None:
    text = wrap_label(str(callout.get("text", "")), int(callout.get("wrap", 14)))
    if not text:
        return
    target_id = str(callout.get("target", ""))
    target = node_by_id.get(target_id)
    if target:
        tx, ty = float(target["x"]), float(target["y"])
        x = float(callout.get("x", min(max(tx + 0.12, 0.08), 0.92)))
        y = float(callout.get("y", min(max(ty + 0.12, 0.08), 0.92)))
        ax.annotate(
            text,
            xy=(tx, ty),
            xytext=(x, y),
            ha="center",
            va="center",
            fontsize=8,
            color="#222222",
            bbox={"boxstyle": "round,pad=0.28", "facecolor": "white", "edgecolor": MIRA_COLORS["gray"], "linewidth": 0.7, "alpha": 0.94},
            arrowprops={"arrowstyle": "->", "linewidth": 0.8, "color": MIRA_COLORS["gray"], "shrinkA": 4, "shrinkB": 8},
            zorder=6,
        )
    else:
        ax.text(
            float(callout.get("x", 0.5)),
            float(callout.get("y", 0.1)),
            text,
            ha="center",
            va="center",
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.28", "facecolor": "white", "edgecolor": MIRA_COLORS["gray"], "linewidth": 0.7, "alpha": 0.94},
            zorder=6,
        )


def wrap_label(text: str, max_chars: int = 10) -> str:
    parts: list[str] = []
    for line in re.split(r"\n|\\n", text):
        line = line.strip()
        if not line:
            continue
        if " " in line:
            current = ""
            for word in line.split():
                if len(current) + len(word) + 1 > max_chars and current:
                    parts.append(current)
                    current = word
                else:
                    current = word if not current else current + " " + word
            if current:
                parts.append(current)
        else:
            parts.extend(line[i : i + max_chars] for i in range(0, len(line), max_chars))
    return "\n".join(parts)


def spec_tables(spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.DataFrame(spec.get("nodes", [])),
        pd.DataFrame(spec.get("edges", [])),
        pd.DataFrame(spec.get("groups", [])),
        pd.DataFrame(spec.get("callouts", [])),
    )


def write_index(outputs: dict[str, Any], args: argparse.Namespace, source: str, spec: dict[str, Any], written: list[str]) -> None:
    caption = spec.get("caption") or "图：结构示意图展示问题对象、变量、模型模块与结果输出之间的连接关系。"
    interpretation = "该图用于解释模型结构和推理链条，不能替代数值结果；关键节点、变量和箭头含义应在正文中逐一对应。"
    lines = [
        "# Structure Diagram Index",
        "",
        f"- Source: `{source}`",
        f"- Normalized spec: `{outputs['spec']}`",
        f"- Node table: `{outputs['nodes']}`",
        f"- Edge table: `{outputs['edges']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Node count: {len(spec.get('nodes', []))}",
        f"- Edge count: {len(spec.get('edges', []))}",
        "",
        "## Figures",
        "",
    ]
    for path in written:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Caption Draft",
            "",
            str(caption),
            "",
            "## Nearby Interpretation Draft",
            "",
            interpretation,
            "",
            "## Caveat",
            "",
            "- Draw only structures that correspond to the actual model, variables, equations, data, or geometry.",
            "- Do not use decorative structure diagrams without nearby reasoning value.",
            "- If a geometric scale or threshold is important, pair the schematic with a quantitative figure or table.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "spec": data_dir / f"{prefix}_structure_spec.json",
        "nodes": data_dir / f"{prefix}_structure_nodes.csv",
        "edges": data_dir / f"{prefix}_structure_edges.csv",
        "groups": data_dir / f"{prefix}_structure_groups.csv",
        "callouts": data_dir / f"{prefix}_structure_callouts.csv",
        "params": data_dir / f"{prefix}_structure_params.json",
        "index": figures_dir / f"{prefix}_structure_index.md",
        "prefix": prefix,
    }


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "structure"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
