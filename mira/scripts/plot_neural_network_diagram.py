#!/usr/bin/env python3
"""Generate reproducible neural-network-like diagrams for Mira papers."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, save_mira_figure


LAYER_STYLES = {
    "input": {"face": "#E8F2FB", "edge": MIRA_COLORS["blue"]},
    "hidden": {"face": "#F1ECF7", "edge": MIRA_COLORS["purple"]},
    "feature": {"face": "#F4EFE8", "edge": MIRA_COLORS["orange"]},
    "conv": {"face": "#EAF4EF", "edge": MIRA_COLORS["teal"]},
    "fusion": {"face": "#FFF6D8", "edge": MIRA_COLORS["gold"]},
    "attention": {"face": "#FCEEEF", "edge": MIRA_COLORS["red"]},
    "output": {"face": "#E9F5E6", "edge": MIRA_COLORS["green"]},
    "default": {"face": "#FFFFFF", "edge": MIRA_COLORS["gray"]},
}


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    spec, source = load_spec(args, root)
    spec = normalize_spec(spec, args)
    outputs = prepare_outputs(args, root)

    layers_df = pd.DataFrame(spec["layers"])
    connections_df = pd.DataFrame(spec["connections"])
    layers_df.to_csv(outputs["layers"], index=False, encoding="utf-8-sig")
    connections_df.to_csv(outputs["connections"], index=False, encoding="utf-8-sig")
    outputs["spec"].write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fig = plot_network(spec, args)
    png = outputs["figures_dir"] / f"{outputs['prefix']}_neural_network.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_neural_network.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)

    params = {
        "source": source,
        "orientation": args.orientation,
        "max_visible_units": args.max_visible_units,
        "max_connection_lines": args.max_connection_lines,
        "n_layers": len(spec["layers"]),
        "n_connections": len(spec["connections"]),
        "written_figures": [str(png), str(pdf)],
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, spec, [str(png), str(pdf)])

    print("INFO: neural-network diagram written:")
    print(f"  figure: {png}")
    print(f"  figure: {pdf}")
    print(f"  spec: {outputs['spec']}")
    print(f"  layers: {outputs['layers']}")
    print(f"  connections: {outputs['connections']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--spec", help="JSON neural-network diagram specification.")
    parser.add_argument("--demo", choices=("mlp", "cnn", "fusion"), help="Generate a built-in demo specification.")
    parser.add_argument("--orientation", choices=("horizontal", "vertical"), default="horizontal", help="Layer direction.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Diagram-data output directory.")
    parser.add_argument("--prefix", default="neural_network", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title override.")
    parser.add_argument("--max-visible-units", type=int, default=7, help="Maximum visible neurons per layer.")
    parser.add_argument("--max-connection-lines", type=int, default=70, help="Maximum explicit lines per connection pair.")
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
    raise SystemExit("ERROR: provide --spec <json> or --demo <mlp|cnn|fusion>.")


def demo_spec(name: str) -> dict[str, Any]:
    if name == "cnn":
        return {
            "title": "卷积神经网络结构示意",
            "caption": "结构图展示输入图像、卷积特征提取、池化压缩、全连接映射和输出分类之间的层级关系。",
            "layers": [
                {"id": "input", "label": "输入矩阵\n64x64", "type": "input", "kind": "block", "units": 1},
                {"id": "conv1", "label": "Conv 3x3\n16通道", "type": "conv", "kind": "block", "depth": 4},
                {"id": "pool1", "label": "MaxPool\n32x32", "type": "feature", "kind": "block", "depth": 3},
                {"id": "conv2", "label": "Conv 3x3\n32通道", "type": "conv", "kind": "block", "depth": 4},
                {"id": "fc", "label": "全连接\n128", "type": "hidden", "kind": "neurons", "units": 128},
                {"id": "output", "label": "输出层\n类别概率", "type": "output", "kind": "neurons", "units": 3},
            ],
            "connections": [
                {"source": "input", "target": "conv1", "label": "卷积"},
                {"source": "conv1", "target": "pool1", "label": "池化"},
                {"source": "pool1", "target": "conv2", "label": "卷积"},
                {"source": "conv2", "target": "fc", "label": "Flatten"},
                {"source": "fc", "target": "output", "style": "dense", "label": "Softmax"},
            ],
        }
    if name == "fusion":
        return {
            "title": "多源特征融合网络示意",
            "caption": "类神经网络结构图展示多源特征经编码、融合、非线性映射后输出预测值的过程。",
            "layers": [
                {"id": "raw", "label": "原始数据\n多源指标", "type": "input", "kind": "block"},
                {"id": "stat", "label": "统计特征\n均值/方差", "type": "feature", "kind": "block"},
                {"id": "embed", "label": "特征嵌入\nz", "type": "hidden", "kind": "neurons", "units": 6},
                {"id": "fusion", "label": "融合层\nconcat+权重", "type": "fusion", "kind": "block"},
                {"id": "hidden", "label": "非线性映射\nMLP", "type": "hidden", "kind": "neurons", "units": 7},
                {"id": "output", "label": "预测输出\n风险/评分", "type": "output", "kind": "neurons", "units": 2},
            ],
            "connections": [
                {"source": "raw", "target": "stat", "label": "提取"},
                {"source": "stat", "target": "embed", "label": "编码"},
                {"source": "embed", "target": "fusion", "label": "表示"},
                {"source": "raw", "target": "fusion", "style": "skip", "label": "原始分支"},
                {"source": "fusion", "target": "hidden", "label": "融合"},
                {"source": "hidden", "target": "output", "style": "dense", "label": "回归/分类"},
            ],
            "callouts": [{"target": "fusion", "text": "融合层必须对应真实特征组合或权重机制"}],
        }
    return {
        "title": "BP/MLP神经网络结构示意",
        "caption": "结构图展示输入指标、隐藏层非线性映射和输出预测之间的层级连接关系。",
        "layers": [
            {"id": "input", "label": "输入层\n指标向量", "type": "input", "kind": "neurons", "units": 6},
            {"id": "hidden1", "label": "隐藏层1\nReLU", "type": "hidden", "kind": "neurons", "units": 8},
            {"id": "hidden2", "label": "隐藏层2\nReLU", "type": "hidden", "kind": "neurons", "units": 5},
            {"id": "output", "label": "输出层\n预测值", "type": "output", "kind": "neurons", "units": 2},
        ],
        "connections": [
            {"source": "input", "target": "hidden1", "style": "dense", "label": "W1,b1"},
            {"source": "hidden1", "target": "hidden2", "style": "dense", "label": "W2,b2"},
            {"source": "hidden2", "target": "output", "style": "dense", "label": "W3,b3"},
        ],
    }


def normalize_spec(spec: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    layers = spec.get("layers", [])
    connections = spec.get("connections", [])
    if len(layers) < 2:
        raise SystemExit("ERROR: neural-network diagram requires at least two layers.")
    ids = []
    for idx, layer in enumerate(layers):
        if "id" not in layer:
            raise SystemExit("ERROR: every layer requires an id.")
        layer["id"] = str(layer["id"])
        layer["label"] = str(layer.get("label", layer["id"]))
        layer["type"] = str(layer.get("type", "default"))
        layer["kind"] = str(layer.get("kind", "neurons"))
        layer["units"] = int(layer.get("units", 1 if layer["kind"] == "block" else 4))
        layer["order"] = int(layer.get("order", idx))
        ids.append(layer["id"])
    if len(set(ids)) != len(ids):
        raise SystemExit("ERROR: duplicated layer ids in neural-network spec.")
    known = set(ids)
    for conn in connections:
        conn["source"] = str(conn.get("source", ""))
        conn["target"] = str(conn.get("target", ""))
        if conn["source"] not in known or conn["target"] not in known:
            raise SystemExit(f"ERROR: connection references unknown layer: {conn}")
        conn["style"] = str(conn.get("style", "forward"))
        conn["label"] = str(conn.get("label", ""))
    spec.setdefault("title", "")
    spec.setdefault("caption", "")
    spec.setdefault("callouts", [])
    if args.title:
        spec["title"] = args.title
    assign_positions(layers, args.orientation)
    return spec


def assign_positions(layers: list[dict[str, Any]], orientation: str) -> None:
    layers.sort(key=lambda layer: layer["order"])
    n = len(layers)
    for i, layer in enumerate(layers):
        primary = 0.10 + 0.80 * (i / max(n - 1, 1))
        if orientation == "vertical":
            layer["x"] = float(layer.get("x", 0.50))
            layer["y"] = float(layer.get("y", 0.90 - 0.80 * (i / max(n - 1, 1))))
        else:
            layer["x"] = float(layer.get("x", primary))
            layer["y"] = float(layer.get("y", 0.50))


def plot_network(spec: dict[str, Any], args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    layer_artifacts: dict[str, dict[str, Any]] = {}
    for layer in spec["layers"]:
        layer_artifacts[layer["id"]] = draw_layer(ax, layer, args)
    for conn in spec["connections"]:
        draw_connection(ax, conn, layer_artifacts, args)
    for callout in spec.get("callouts", []):
        draw_callout(ax, callout, layer_artifacts)
    title = spec.get("title", "")
    if title:
        ax.set_title(str(title), pad=10)
    return fig


def draw_layer(ax: Any, layer: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if layer.get("kind") == "block":
        return draw_block_layer(ax, layer)
    return draw_neuron_layer(ax, layer, args.max_visible_units)


def draw_neuron_layer(ax: Any, layer: dict[str, Any], max_visible: int) -> dict[str, Any]:
    style = LAYER_STYLES.get(layer["type"], LAYER_STYLES["default"])
    x = float(layer["x"])
    units = int(layer["units"])
    visible = visible_unit_slots(units, max_visible)
    y_values = unit_y_positions(len(visible))
    points = []
    for y, marker in zip(y_values, visible):
        if marker == "...":
            ax.text(x, y, "...", ha="center", va="center", fontsize=12, color=MIRA_COLORS["gray"], zorder=4)
            continue
        circ = Circle((x, y), 0.025, facecolor=style["face"], edgecolor=style["edge"], linewidth=1.1, zorder=4)
        ax.add_patch(circ)
        points.append((x, y))
    label_y = 0.10
    ax.text(x, label_y, wrap_label(str(layer["label"]), 8), ha="center", va="top", fontsize=9, color="#222222")
    if units > max_visible:
        ax.text(x, 0.17, f"{units}个单元", ha="center", va="center", fontsize=8, color=MIRA_COLORS["gray"])
    return {"kind": "neurons", "center": (x, 0.50), "points": points, "layer": layer}


def draw_block_layer(ax: Any, layer: dict[str, Any]) -> dict[str, Any]:
    style = LAYER_STYLES.get(layer["type"], LAYER_STYLES["default"])
    x = float(layer["x"])
    y = float(layer.get("y", 0.50))
    w = float(layer.get("w", 0.13))
    h = float(layer.get("h", 0.30))
    depth = int(layer.get("depth", 1))
    for i in reversed(range(depth)):
        dx = i * 0.010
        dy = i * 0.012
        rect = FancyBboxPatch(
            (x - w / 2 + dx, y - h / 2 + dy),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            facecolor=style["face"],
            edgecolor=style["edge"],
            linewidth=1.0,
            alpha=0.88,
            zorder=3 + i * 0.01,
        )
        ax.add_patch(rect)
    ax.text(x + depth * 0.005, y + depth * 0.006, wrap_label(str(layer["label"]), 9), ha="center", va="center", fontsize=9, color="#222222", zorder=5)
    return {"kind": "block", "center": (x, y), "points": [(x + w / 2, y), (x, y), (x - w / 2, y)], "layer": layer, "w": w, "h": h}


def draw_connection(ax: Any, conn: dict[str, Any], artifacts: dict[str, dict[str, Any]], args: argparse.Namespace) -> None:
    source = artifacts[conn["source"]]
    target = artifacts[conn["target"]]
    style = conn.get("style", "forward")
    color = MIRA_COLORS["gray"]
    linestyle = "-"
    rad = 0.0
    if style == "skip":
        color = MIRA_COLORS["orange"]
        linestyle = "--"
        rad = 0.16
    elif style == "attention":
        color = MIRA_COLORS["red"]
    elif style == "dense":
        color = "#8A94A3"
    source_points = source["points"]
    target_points = target["points"]
    n_lines = len(source_points) * len(target_points)
    if style == "dense" and source["kind"] == "neurons" and target["kind"] == "neurons" and n_lines <= args.max_connection_lines:
        for x0, y0 in source_points:
            for x1, y1 in target_points:
                ax.plot([x0 + 0.026, x1 - 0.026], [y0, y1], color=color, linewidth=0.55, alpha=0.30, zorder=1)
    else:
        x0, y0 = source["center"]
        x1, y1 = target["center"]
        arrow = FancyArrowPatch(
            (x0, y0),
            (x1, y1),
            arrowstyle="-|>",
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=12,
            linewidth=1.2,
            linestyle=linestyle,
            color=color,
            shrinkA=28,
            shrinkB=28,
            alpha=0.80,
            zorder=2,
        )
        ax.add_patch(arrow)
    label = str(conn.get("label", ""))
    if label:
        x0, y0 = source["center"]
        x1, y1 = target["center"]
        ax.text(
            (x0 + x1) / 2,
            (y0 + y1) / 2 + 0.07 + rad * 0.12,
            wrap_label(label, 8),
            ha="center",
            va="bottom",
            fontsize=8,
            color=color,
            bbox={"boxstyle": "round,pad=0.14", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            zorder=6,
        )


def draw_callout(ax: Any, callout: dict[str, Any], artifacts: dict[str, dict[str, Any]]) -> None:
    target = artifacts.get(str(callout.get("target", "")))
    if not target:
        return
    tx, ty = target["center"]
    x = float(callout.get("x", min(max(tx, 0.12), 0.88)))
    y = float(callout.get("y", 0.88))
    ax.annotate(
        wrap_label(str(callout.get("text", "")), 14),
        xy=(tx, ty),
        xytext=(x, y),
        ha="center",
        va="center",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": MIRA_COLORS["gray"], "linewidth": 0.7, "alpha": 0.94},
        arrowprops={"arrowstyle": "->", "linewidth": 0.8, "color": MIRA_COLORS["gray"], "shrinkA": 4, "shrinkB": 8},
        zorder=8,
    )


def visible_unit_slots(units: int, max_visible: int) -> list[int | str]:
    if units <= max_visible:
        return list(range(units))
    top = max_visible // 2
    bottom = max_visible - top - 1
    return list(range(top)) + ["..."] + list(range(units - bottom, units))


def unit_y_positions(n: int) -> list[float]:
    if n == 1:
        return [0.50]
    span = min(0.68, 0.075 * (n - 1))
    start = 0.50 + span / 2
    return [start - i * span / max(n - 1, 1) for i in range(n)]


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


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "spec": data_dir / f"{prefix}_neural_network_spec.json",
        "layers": data_dir / f"{prefix}_neural_network_layers.csv",
        "connections": data_dir / f"{prefix}_neural_network_connections.csv",
        "params": data_dir / f"{prefix}_neural_network_params.json",
        "index": figures_dir / f"{prefix}_neural_network_index.md",
        "prefix": prefix,
    }


def write_index(outputs: dict[str, Any], args: argparse.Namespace, source: str, spec: dict[str, Any], written: list[str]) -> None:
    caption = spec.get("caption") or "图：类神经网络结构图展示输入、隐藏表示、模块连接和输出之间的层级映射。"
    interpretation = "该图用于解释层级映射和模块关系；若论文声称使用神经网络，仍需给出训练数据、结构参数、损失函数、验证指标和可复现代码。"
    lines = [
        "# Neural Network Diagram Index",
        "",
        f"- Source: `{source}`",
        f"- Normalized spec: `{outputs['spec']}`",
        f"- Layer table: `{outputs['layers']}`",
        f"- Connection table: `{outputs['connections']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Layer count: {len(spec.get('layers', []))}",
        f"- Connection count: {len(spec.get('connections', []))}",
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
            "- Do not draw a neural-network diagram unless the model actually uses neural layers, learned mappings, feature embeddings, or an explicitly analogous layered mapping.",
            "- The diagram explains architecture; it does not prove predictive accuracy.",
            "- Dense connections may be visually abbreviated; keep exact layer sizes and training settings in the text or tables.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "neural_network"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
