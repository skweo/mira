#!/usr/bin/env python3
"""Generate Sankey and circular chord flow figures for Mira papers."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle, Wedge


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, save_mira_figure


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    df, source = load_source(args, root)
    edges, meta = build_edges(df, args)
    nodes = build_node_summary(edges)
    outputs = prepare_outputs(args, root)

    edges.to_csv(outputs["edges"], index=False, encoding="utf-8-sig")
    nodes.to_csv(outputs["nodes"], index=False, encoding="utf-8-sig")

    written: list[str] = []
    kinds = ["sankey", "chord"] if args.kind == "all" else [args.kind]
    for kind in kinds:
        fig = plot_sankey(edges, nodes, args) if kind == "sankey" else plot_chord(edges, nodes, args)
        png = outputs["figures_dir"] / f"{outputs['prefix']}_{kind}.png"
        pdf = outputs["figures_dir"] / f"{outputs['prefix']}_{kind}.pdf"
        save_mira_figure(fig, png, dpi=args.dpi)
        save_mira_figure(fig, pdf, dpi=args.dpi)
        written.extend([str(png), str(pdf)])
        close_figure(fig)

    params = {
        "source": source,
        "kind": args.kind,
        "source_column": args.source,
        "target_column": args.target,
        "value_column": args.value,
        "category_column": args.category,
        "unit": args.unit,
        "n_input_rows": len(df),
        "n_edges": len(edges),
        "n_nodes": len(nodes),
        "dropped_rows": meta["dropped_rows"],
        "dropped_nonpositive_rows": meta["dropped_nonpositive_rows"],
        "dropped_self_loops": meta["dropped_self_loops"],
        "node_order": args.node_order,
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, edges, nodes, written)

    print("INFO: flow figures written:")
    for path in written:
        print(f"  figure: {path}")
    print(f"  edges: {outputs['edges']}")
    print(f"  nodes: {outputs['nodes']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX edge table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", choices=["supply", "od"], help="Generate built-in demo edge data.")
    parser.add_argument("--kind", choices=("sankey", "chord", "all"), default="all", help="Figure type.")
    parser.add_argument("--source", default="source", help="Source node column.")
    parser.add_argument("--target", default="target", help="Target node column.")
    parser.add_argument("--value", default="value", help="Positive flow value column.")
    parser.add_argument("--category", help="Optional edge category column for color grouping.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Flow-data output directory.")
    parser.add_argument("--prefix", default="flow", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--unit", default="", help="Optional flow unit for captions and labels.")
    parser.add_argument("--node-order", help="Comma-separated node order. For Sankey, also helps layer reading.")
    parser.add_argument("--label-top", type=int, default=5, help="Label top-N edges by value in Sankey.")
    parser.add_argument("--min-flow", type=float, default=0.0, help="Drop rows with value <= min-flow.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_source(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return load_demo(args.demo, args)
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo <supply|od>.")
    input_path = resolve_path(root, args.input)
    if not input_path.exists():
        raise SystemExit(f"ERROR: input file does not exist: {input_path}")
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        df = pd.read_excel(input_path, sheet_name=sheet)
    elif suffix in {".csv", ".txt"}:
        df = read_csv_with_fallback(input_path)
    else:
        raise SystemExit("ERROR: supported input formats are CSV, TXT, XLSX, and XLS.")
    return df, str(input_path)


def load_demo(name: str, args: argparse.Namespace) -> tuple[pd.DataFrame, str]:
    args.source = "来源"
    args.target = "去向"
    args.value = "流量"
    args.category = "类型"
    args.unit = args.unit or "单位"
    if name == "od":
        rows = [
            ("居住区A", "商业区", 180, "通勤"),
            ("居住区A", "学校", 64, "教育"),
            ("居住区B", "商业区", 135, "通勤"),
            ("居住区B", "医院", 42, "医疗"),
            ("居住区C", "产业园", 155, "通勤"),
            ("产业园", "商业区", 48, "换乘"),
            ("商业区", "居住区A", 72, "返程"),
            ("商业区", "居住区B", 68, "返程"),
            ("学校", "居住区A", 51, "返程"),
            ("医院", "居住区B", 32, "返程"),
        ]
        return pd.DataFrame(rows, columns=[args.source, args.target, args.value, args.category]), "demo:od"

    rows = [
        ("原料采购", "预处理", 120, "物料"),
        ("原料采购", "质检", 35, "检验"),
        ("预处理", "部件加工", 98, "物料"),
        ("质检", "部件加工", 29, "合格件"),
        ("部件加工", "半成品装配", 86, "物料"),
        ("部件加工", "返工", 18, "返工"),
        ("返工", "半成品装配", 13, "物料"),
        ("半成品装配", "成品检测", 82, "物料"),
        ("成品检测", "合格入库", 69, "合格品"),
        ("成品检测", "拆解回收", 11, "回收"),
        ("拆解回收", "部件加工", 7, "回收"),
        ("合格入库", "线上渠道", 41, "销售"),
        ("合格入库", "线下渠道", 28, "销售"),
    ]
    return pd.DataFrame(rows, columns=[args.source, args.target, args.value, args.category]), "demo:supply"


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


def build_edges(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, int]]:
    required = [args.source, args.target, args.value]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: required columns not found: " + ", ".join(missing))
    if args.category and args.category not in df.columns:
        raise SystemExit(f"ERROR: category column not found: {args.category}")

    work = df.copy()
    work[args.value] = pd.to_numeric(work[args.value], errors="coerce")
    valid = work[required].notna().all(axis=1)
    dropped_rows = int((~valid).sum())
    work = work.loc[valid].copy()
    work[args.source] = work[args.source].astype(str).str.strip()
    work[args.target] = work[args.target].astype(str).str.strip()
    if args.category:
        work[args.category] = work[args.category].astype(str).str.strip()
    else:
        work["类别"] = work[args.source]
        args.category = "类别"

    positive = work[args.value] > args.min_flow
    dropped_nonpositive = int((~positive).sum())
    work = work.loc[positive].copy()
    not_loop = work[args.source] != work[args.target]
    dropped_self_loops = int((~not_loop).sum())
    work = work.loc[not_loop].copy()
    if work.empty:
        raise SystemExit("ERROR: no positive non-self-loop flows remain after cleaning.")

    grouped = (
        work.groupby([args.source, args.target, args.category], as_index=False, observed=False)[args.value]
        .sum()
        .rename(columns={args.source: "source", args.target: "target", args.value: "value", args.category: "category"})
    )
    grouped = grouped.sort_values("value", ascending=False).reset_index(drop=True)
    return grouped, {
        "dropped_rows": dropped_rows,
        "dropped_nonpositive_rows": dropped_nonpositive,
        "dropped_self_loops": dropped_self_loops,
    }


def build_node_summary(edges: pd.DataFrame) -> pd.DataFrame:
    outflow = edges.groupby("source", observed=False)["value"].sum()
    inflow = edges.groupby("target", observed=False)["value"].sum()
    nodes = sorted(set(outflow.index).union(inflow.index))
    rows = []
    for node in nodes:
        in_value = float(inflow.get(node, 0.0))
        out_value = float(outflow.get(node, 0.0))
        rows.append({"node": node, "inflow": in_value, "outflow": out_value, "throughput": max(in_value, out_value)})
    return pd.DataFrame(rows).sort_values("throughput", ascending=False).reset_index(drop=True)


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "edges": data_dir / f"{prefix}_flow_edges.csv",
        "nodes": data_dir / f"{prefix}_flow_nodes.csv",
        "params": data_dir / f"{prefix}_flow_params.json",
        "index": figures_dir / f"{prefix}_flow_index.md",
        "prefix": prefix,
    }


def plot_sankey(edges: pd.DataFrame, nodes: pd.DataFrame, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    layers = infer_layers(edges, nodes, args)
    positions = layout_sankey_nodes(layers, nodes)
    colors = node_colors(nodes["node"].tolist())
    max_value = float(edges["value"].max())

    for _, row in edges.sort_values("value").iterrows():
        source = str(row["source"])
        target = str(row["target"])
        value = float(row["value"])
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        color = colors.get(source, MIRA_COLORS["gray"])
        draw_flow_curve(ax, x0 + 0.035, y0, x1 - 0.035, y1, value, max_value, color)

    for node, (x, y) in positions.items():
        throughput = float(nodes.loc[nodes["node"] == node, "throughput"].iloc[0])
        height = 0.035 + 0.08 * math.sqrt(throughput / max(float(nodes["throughput"].max()), 1e-9))
        rect = Rectangle((x - 0.025, y - height / 2), 0.05, height, facecolor=colors[node], edgecolor="white", linewidth=1.0, zorder=5)
        ax.add_patch(rect)
        ax.text(
            x + 0.035,
            y,
            node,
            va="center",
            ha="left",
            fontsize=9,
            color="#222222",
            zorder=6,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "none", "alpha": 0.72},
        )

    label_top_edges(ax, edges, positions, args)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    if args.title:
        ax.set_title(args.title)
    return fig


def infer_layers(edges: pd.DataFrame, nodes: pd.DataFrame, args: argparse.Namespace) -> list[list[str]]:
    ordered = parse_columns(args.node_order)
    graph = nx.DiGraph()
    graph.add_weighted_edges_from((str(r.source), str(r.target), float(r.value)) for r in edges.itertuples())
    dag = graph.copy()
    while not nx.is_directed_acyclic_graph(dag):
        cycle = nx.find_cycle(dag, orientation="original")
        weakest = min(cycle, key=lambda item: float(dag[item[0]][item[1]].get("weight", 1.0)))
        dag.remove_edge(weakest[0], weakest[1])

    level: dict[str, int] = {}
    for node in nx.topological_sort(dag):
        preds = list(dag.predecessors(node))
        level[node] = 0 if not preds else max(level[pred] + 1 for pred in preds)
    for node in graph.nodes:
        level.setdefault(node, 0)
    max_level = max(level.values(), default=0)
    layers = [[] for _ in range(max_level + 1)]
    throughput = dict(zip(nodes["node"], nodes["throughput"]))
    order_rank = {node: i for i, node in enumerate(ordered)}
    for node, lev in level.items():
        layers[lev].append(node)
    for layer in layers:
        layer.sort(key=lambda n: (order_rank.get(n, 10_000), -float(throughput.get(n, 0))))
    return [layer for layer in layers if layer]


def layout_sankey_nodes(layers: list[list[str]], nodes: pd.DataFrame) -> dict[str, tuple[float, float]]:
    throughput = dict(zip(nodes["node"], nodes["throughput"]))
    positions: dict[str, tuple[float, float]] = {}
    n_layers = max(len(layers), 1)
    for i, layer in enumerate(layers):
        x = 0.08 + 0.84 * (i / max(n_layers - 1, 1))
        total = sum(math.sqrt(max(float(throughput.get(node, 1.0)), 1e-9)) for node in layer)
        if len(layer) == 1:
            positions[layer[0]] = (x, 0.5)
            continue
        gap = 0.78 / max(total, 1e-9)
        current = 0.89
        for node in layer:
            weight = math.sqrt(max(float(throughput.get(node, 1.0)), 1e-9))
            y = current - weight * gap / 2
            positions[node] = (x, y)
            current -= weight * gap
    return positions


def draw_flow_curve(ax: Any, x0: float, y0: float, x1: float, y1: float, value: float, max_value: float, color: str) -> None:
    dx = max(abs(x1 - x0), 0.12)
    verts = [(x0, y0), (x0 + 0.45 * dx, y0), (x1 - 0.45 * dx, y1), (x1, y1)]
    path = MplPath(verts, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    lw = 1.2 + 13.0 * math.sqrt(value / max(max_value, 1e-9))
    patch = PathPatch(path, facecolor="none", edgecolor=color, linewidth=lw, alpha=0.34, capstyle="round", joinstyle="round", zorder=2)
    ax.add_patch(patch)


def label_top_edges(ax: Any, edges: pd.DataFrame, positions: dict[str, tuple[float, float]], args: argparse.Namespace) -> None:
    if args.label_top <= 0:
        return
    for _, row in edges.nlargest(args.label_top, "value").iterrows():
        source, target, value = str(row["source"]), str(row["target"]), float(row["value"])
        if source not in positions or target not in positions:
            continue
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        x, y = (x0 + x1) / 2, (y0 + y1) / 2
        label = f"{value:g}{args.unit}" if args.unit else f"{value:g}"
        ax.text(
            x,
            y + 0.018,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
            color=MIRA_COLORS["gray"],
            zorder=7,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.68},
        )


def plot_chord(edges: pd.DataFrame, nodes: pd.DataFrame, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    ax.set_aspect("equal")
    ax.axis("off")
    order = complete_node_order(parse_columns(args.node_order), nodes)
    node_values = dict(zip(nodes["node"], nodes["throughput"]))
    angles = circular_node_angles(order, node_values)
    colors = node_colors(order)
    max_value = float(edges["value"].max())

    for node in order:
        if node not in angles:
            continue
        start, end, mid = angles[node]
        wedge = Wedge((0, 0), 1.0, math.degrees(start), math.degrees(end), width=0.075, facecolor=colors[node], edgecolor="white", linewidth=1.0, alpha=0.95)
        ax.add_patch(wedge)
        lx, ly = 1.13 * math.cos(mid), 1.13 * math.sin(mid)
        ha = "left" if lx >= 0 else "right"
        rotation = math.degrees(mid)
        if 90 < rotation < 270:
            rotation += 180
        ax.text(lx, ly, node, ha=ha, va="center", rotation=rotation, rotation_mode="anchor", fontsize=9)

    edge_angles = allocate_edge_angles(edges, angles, order)
    for _, row in edges.sort_values("value").iterrows():
        source, target, value = str(row["source"]), str(row["target"]), float(row["value"])
        if source not in edge_angles or target not in edge_angles[source]:
            continue
        a0 = edge_angles[source][target]
        a1 = edge_angles[target].get(source, angles[target][2])
        color = colors.get(source, MIRA_COLORS["gray"])
        draw_chord(ax, a0, a1, value, max_value, color)

    if args.title:
        ax.set_title(args.title)
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    return fig


def circular_node_angles(order: list[str], node_values: dict[str, float]) -> dict[str, tuple[float, float, float]]:
    values = np.array([max(float(node_values.get(node, 0.0)), 1e-6) for node in order], dtype=float)
    total = float(values.sum())
    gap = math.radians(2.4)
    usable = 2 * math.pi - gap * len(order)
    start = math.radians(90)
    out: dict[str, tuple[float, float, float]] = {}
    for node, value in zip(order, values):
        span = usable * value / total
        end = start + span
        out[node] = (start, end, (start + end) / 2)
        start = end + gap
    return out


def allocate_edge_angles(edges: pd.DataFrame, angles: dict[str, tuple[float, float, float]], order: list[str]) -> dict[str, dict[str, float]]:
    neighbors: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in edges.itertuples():
        source, target, value = str(row.source), str(row.target), float(row.value)
        neighbors[source].append((target, value))
        neighbors[target].append((source, value))
    out: dict[str, dict[str, float]] = defaultdict(dict)
    rank = {node: i for i, node in enumerate(order)}
    for node, items in neighbors.items():
        if node not in angles:
            continue
        start, end, _ = angles[node]
        total = sum(value for _, value in items)
        cursor = start
        for target, value in sorted(items, key=lambda item: rank.get(item[0], 10_000)):
            span = (end - start) * value / max(total, 1e-9)
            out[node][target] = cursor + span / 2
            cursor += span
    return out


def draw_chord(ax: Any, a0: float, a1: float, value: float, max_value: float, color: str) -> None:
    r = 0.93
    p0 = np.array([r * math.cos(a0), r * math.sin(a0)])
    p1 = np.array([r * math.cos(a1), r * math.sin(a1)])
    c0 = p0 * 0.18
    c1 = p1 * 0.18
    path = MplPath([tuple(p0), tuple(c0), tuple(c1), tuple(p1)], [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    lw = 0.7 + 8.5 * math.sqrt(value / max(max_value, 1e-9))
    patch = PathPatch(path, facecolor="none", edgecolor=color, linewidth=lw, alpha=0.32, capstyle="round", zorder=1)
    ax.add_patch(patch)


def node_colors(nodes: list[str]) -> dict[str, str]:
    palette = MIRA_PALETTE
    if len(nodes) > len(palette):
        try:
            import seaborn as sns

            palette = list(sns.color_palette("tab20", len(nodes)).as_hex())
        except Exception:
            palette = [f"C{i}" for i in range(len(nodes))]
    return {node: palette[i % len(palette)] for i, node in enumerate(nodes)}


def write_index(outputs: dict[str, Any], args: argparse.Namespace, source: str, edges: pd.DataFrame, nodes: pd.DataFrame, written: list[str]) -> None:
    top = edges.nlargest(1, "value").iloc[0]
    unit = args.unit or ""
    caption = (
        "图：节点之间的流量关系。桑基图强调从来源到去向的层级转移，"
        "圆形弦图强调多节点之间的整体关联强度；线宽按流量大小缩放。"
    )
    interpretation = f"最大流向为 `{top['source']} -> {top['target']}`，流量为 {float(top['value']):g}{unit}。"
    lines = [
        "# Flow Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Plot kind: `{args.kind}`",
        f"- Edge table: `{outputs['edges']}`",
        f"- Node table: `{outputs['nodes']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Edge count: {len(edges)}",
        f"- Node count: {len(nodes)}",
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
            caption,
            "",
            "## Nearby Interpretation Draft",
            "",
            interpretation,
            "",
            "## Caveat",
            "",
            "- Use Sankey when the flow has a readable stage/layer direction.",
            "- Use circular chord when the claim is about mutual association among many nodes.",
            "- Do not use a chord diagram as a substitute for exact flow values; keep the edge table or summary table nearby.",
            "- If direction matters in a circular chart, state that color indicates the source node and keep directional values in the table.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def parse_columns(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，;；]", text) if part.strip()]


def complete_node_order(order: list[str], nodes: pd.DataFrame) -> list[str]:
    all_nodes = nodes.sort_values("throughput", ascending=False)["node"].astype(str).tolist()
    if not order:
        return all_nodes
    seen = set(order)
    return order + [node for node in all_nodes if node not in seen]


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "flow"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    raise SystemExit(main())
