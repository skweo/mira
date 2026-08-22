#!/usr/bin/env python3
"""Generate reproducible 3D scatter figures for Mira papers."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_3d_style, apply_mira_style, save_mira_figure


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    df, source = load_source(args, root)
    plot_df, meta = build_plot_frame(df, args)
    outputs = prepare_outputs(args, root)

    plot_df.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary = summarize(plot_df, args)
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    fig = plot_3d_scatter(plot_df, args)
    png = outputs["figures_dir"] / f"{outputs['prefix']}_3d_scatter.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_3d_scatter.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)

    projection_paths: list[str] = []
    if args.projections:
        projection_paths = [str(path) for path in plot_projections(plot_df, args, outputs)]

    params = {
        "source": source,
        "x_column": args.x,
        "y_column": args.y,
        "z_column": args.z,
        "color_column": args.color,
        "size_column": args.size,
        "label_column": args.label,
        "unit": args.unit,
        "n_input_rows": len(df),
        "n_plot_rows": len(plot_df),
        "dropped_rows": meta["dropped_rows"],
        "downsampled": meta["downsampled"],
        "max_points": args.max_points,
        "view": {"elev": args.elev, "azim": args.azim},
        "written_figures": [str(png), str(pdf)] + projection_paths,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, plot_df, [str(png), str(pdf)] + projection_paths)

    print("INFO: 3D scatter figures written:")
    print(f"  figure: {png}")
    print(f"  figure: {pdf}")
    for path in projection_paths:
        print(f"  figure: {path}")
    print(f"  plot_data: {outputs['plot_data']}")
    print(f"  summary: {outputs['summary']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    if meta["dropped_rows"]:
        print(f"INFO: dropped rows with missing x/y/z/color/size fields: {meta['dropped_rows']}")
    if meta["downsampled"]:
        print(f"INFO: downsampled to {len(plot_df)} points for readability.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX point table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", choices=("clusters", "response"), help="Generate built-in demo point data.")
    parser.add_argument("--x", help="X-axis numeric column.")
    parser.add_argument("--y", help="Y-axis numeric column.")
    parser.add_argument("--z", help="Z-axis numeric column.")
    parser.add_argument("--color", help="Optional categorical or numeric color column.")
    parser.add_argument("--size", help="Optional numeric marker-size column.")
    parser.add_argument("--label", help="Optional point label column for top labeled points.")
    parser.add_argument("--label-top", type=int, default=0, help="Label top-N points by z value.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="scatter3d", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--xlabel", default="", help="Override x-axis label.")
    parser.add_argument("--ylabel", default="", help="Override y-axis label.")
    parser.add_argument("--zlabel", default="", help="Override z-axis label.")
    parser.add_argument("--unit", default="", help="Optional unit note.")
    parser.add_argument("--elev", type=float, default=24.0, help="3D camera elevation.")
    parser.add_argument("--azim", type=float, default=-55.0, help="3D camera azimuth.")
    parser.add_argument("--alpha", type=float, default=0.78, help="Marker alpha.")
    parser.add_argument("--marker-size", type=float, default=34.0, help="Base marker size.")
    parser.add_argument("--max-points", type=int, default=2500, help="Maximum plotted points before deterministic downsampling.")
    parser.add_argument("--seed", type=int, default=42, help="Downsampling seed.")
    parser.add_argument("--projections", action="store_true", help="Also write XY/XZ/YZ projection panels.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_source(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return load_demo(args.demo, args)
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo <clusters|response>.")
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
    rng = np.random.default_rng(42)
    if name == "response":
        n = 900
        x = rng.uniform(-3.0, 3.0, n)
        y = rng.uniform(-2.4, 2.4, n)
        z = np.sin(x) * np.cos(y) + 0.18 * x - 0.12 * y + rng.normal(0, 0.08, n)
        df = pd.DataFrame({"参数x": x, "参数y": y, "响应z": z, "响应等级": pd.cut(z, 4, labels=["低", "中低", "中高", "高"])})
        args.x = args.x or "参数x"
        args.y = args.y or "参数y"
        args.z = args.z or "响应z"
        args.color = args.color or "响应等级"
        return df, "demo:response"

    centers = np.array([[-1.8, -0.8, 0.2], [0.5, 1.4, 1.2], [1.9, -0.4, -0.8], [-0.4, 0.1, 2.0]])
    records: list[dict[str, Any]] = []
    for idx, center in enumerate(centers):
        cov = np.diag([0.22 + idx * 0.04, 0.16 + idx * 0.03, 0.20 + idx * 0.05])
        points = rng.multivariate_normal(center, cov, size=180)
        for j, point in enumerate(points):
            records.append({"特征1": point[0], "特征2": point[1], "特征3": point[2], "类别": f"簇{idx + 1}", "样本": f"S{idx + 1}-{j + 1}"})
    df = pd.DataFrame(records)
    args.x = args.x or "特征1"
    args.y = args.y or "特征2"
    args.z = args.z or "特征3"
    args.color = args.color or "类别"
    args.label = args.label or "样本"
    return df, "demo:clusters"


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


def build_plot_frame(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    infer_xyz(df, args)
    required = [args.x, args.y, args.z]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: required x/y/z columns not found: " + ", ".join(missing))
    if args.color and args.color not in df.columns:
        raise SystemExit(f"ERROR: color column not found: {args.color}")
    if args.size and args.size not in df.columns:
        raise SystemExit(f"ERROR: size column not found: {args.size}")
    if args.label and args.label not in df.columns:
        raise SystemExit(f"ERROR: label column not found: {args.label}")

    keep = [args.x, args.y, args.z] + [col for col in [args.color, args.size, args.label] if col]
    work = df[keep].copy()
    for col in [args.x, args.y, args.z]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    if args.size:
        work[args.size] = pd.to_numeric(work[args.size], errors="coerce")
    valid_cols = [args.x, args.y, args.z] + ([args.size] if args.size else [])
    valid = work[valid_cols].notna().all(axis=1)
    if args.color:
        valid &= work[args.color].notna()
    dropped_rows = int((~valid).sum())
    work = work.loc[valid].copy()
    if len(work) < 3:
        raise SystemExit("ERROR: at least 3 complete points are required for a 3D scatter plot.")
    for col in [args.color, args.label]:
        if col:
            work[col] = work[col].astype(str)

    downsampled = False
    if args.max_points > 0 and len(work) > args.max_points:
        work = work.sample(n=args.max_points, random_state=args.seed).sort_index().copy()
        downsampled = True
    return work.reset_index(drop=True), {"dropped_rows": dropped_rows, "downsampled": downsampled}


def infer_xyz(df: pd.DataFrame, args: argparse.Namespace) -> None:
    if args.x and args.y and args.z:
        return
    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if len(numeric_cols) < 3:
        raise SystemExit("ERROR: pass --x --y --z, or provide at least three numeric columns.")
    args.x = args.x or numeric_cols[0]
    args.y = args.y or numeric_cols[1]
    args.z = args.z or numeric_cols[2]


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "plot_data": data_dir / f"{prefix}_3d_scatter_points.csv",
        "summary": data_dir / f"{prefix}_3d_scatter_summary.csv",
        "params": data_dir / f"{prefix}_3d_scatter_params.json",
        "index": figures_dir / f"{prefix}_3d_scatter_index.md",
        "prefix": prefix,
    }


def summarize(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    axes = [args.x, args.y, args.z]
    if args.color and not pd.api.types.is_numeric_dtype(df[args.color]) and df[args.color].nunique() <= 40:
        grouped = df.groupby(args.color, observed=False)[axes].agg(["count", "mean", "std", "min", "max"])
        grouped.columns = ["_".join(col).strip("_") for col in grouped.columns.to_flat_index()]
        return grouped.reset_index()
    return df[axes].agg(["count", "mean", "std", "min", "max"]).reset_index().rename(columns={"index": "stat"})


def plot_3d_scatter(df: pd.DataFrame, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig = plt.figure(figsize=(6.8, 5.2))
    ax = fig.add_subplot(111, projection="3d")
    x = df[args.x].to_numpy(float)
    y = df[args.y].to_numpy(float)
    z = df[args.z].to_numpy(float)
    sizes = marker_sizes(df, args)
    color_info = color_values(df, args)

    if color_info["kind"] == "numeric":
        scatter = ax.scatter(x, y, z, c=color_info["values"], cmap="viridis", s=sizes, alpha=args.alpha, edgecolors="white", linewidths=0.25, depthshade=True)
        cbar = fig.colorbar(scatter, ax=ax, shrink=0.68, pad=0.08)
        cbar.set_label(args.color)
    elif color_info["kind"] == "categorical":
        for label, color in color_info["colors"].items():
            part = df[args.color] == label
            ax.scatter(
                df.loc[part, args.x],
                df.loc[part, args.y],
                df.loc[part, args.z],
                s=sizes[part.to_numpy()],
                color=color,
                label=label,
                alpha=args.alpha,
                edgecolors="white",
                linewidths=0.25,
                depthshade=True,
            )
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 0.98), borderaxespad=0)
    else:
        ax.scatter(x, y, z, s=sizes, color=MIRA_COLORS["blue"], alpha=args.alpha, edgecolors="white", linewidths=0.25, depthshade=True)

    label_top_points(ax, df, args)
    apply_3d_style(
        ax,
        xlabel=args.xlabel or args.x,
        ylabel=args.ylabel or args.y,
        zlabel=args.zlabel or args.z,
        elev=args.elev,
        azim=args.azim,
    )
    set_box_aspect(ax, x, y, z)
    soften_3d_panes(ax)
    if args.title:
        ax.set_title(args.title, pad=14)
    if args.unit:
        ax.text2D(0.02, 0.02, f"单位：{args.unit}", transform=ax.transAxes, fontsize=9, color=MIRA_COLORS["gray"])
    return fig


def marker_sizes(df: pd.DataFrame, args: argparse.Namespace) -> np.ndarray:
    if not args.size:
        return np.full(len(df), args.marker_size)
    values = df[args.size].to_numpy(float)
    lo, hi = np.nanpercentile(values, [5, 95])
    scaled = (np.clip(values, lo, hi) - lo) / max(hi - lo, 1e-9)
    return args.marker_size * (0.55 + 1.65 * scaled)


def color_values(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    if not args.color:
        return {"kind": "single"}
    series = df[args.color]
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all() and series.nunique() > 8:
        return {"kind": "numeric", "values": numeric.to_numpy(float)}
    labels = sorted(series.astype(str).unique(), key=natural_key)
    if len(labels) > 16:
        raise SystemExit("ERROR: too many color categories for a readable 3D scatter plot; aggregate or use a numeric color scale.")
    palette = MIRA_PALETTE
    if len(labels) > len(palette):
        import matplotlib.pyplot as plt

        cmap = plt.get_cmap("tab20")
        palette = [cmap(i / max(len(labels) - 1, 1)) for i in range(len(labels))]
    return {"kind": "categorical", "colors": {label: palette[i % len(palette)] for i, label in enumerate(labels)}}


def label_top_points(ax: Any, df: pd.DataFrame, args: argparse.Namespace) -> None:
    if args.label_top <= 0 or not args.label:
        return
    subset = df.nlargest(min(args.label_top, len(df)), args.z)
    for _, row in subset.iterrows():
        ax.text(float(row[args.x]), float(row[args.y]), float(row[args.z]), str(row[args.label]), fontsize=8, color="#222222")


def set_box_aspect(ax: Any, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
    ranges = np.array([np.ptp(x), np.ptp(y), np.ptp(z)], dtype=float)
    ranges = np.where(ranges <= 1e-9, 1.0, ranges)
    try:
        ax.set_box_aspect(tuple(ranges / ranges.max()))
    except Exception:
        return


def soften_3d_panes(ax: Any) -> None:
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.set_facecolor((0.97, 0.98, 1.0, 0.35))
        pane.set_edgecolor((0.82, 0.84, 0.88, 0.65))


def plot_projections(df: pd.DataFrame, args: argparse.Namespace, outputs: dict[str, Any]) -> list[Path]:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 2.8))
    pairs = [(args.x, args.y, "XY"), (args.x, args.z, "XZ"), (args.y, args.z, "YZ")]
    colors = projection_colors(df, args)
    sizes = marker_sizes(df, args) * 0.72
    for ax, (a, b, title) in zip(axes, pairs):
        ax.scatter(df[a], df[b], s=sizes, c=colors, alpha=min(args.alpha + 0.08, 0.92), edgecolors="white", linewidths=0.2)
        ax.set_title(title)
        ax.set_xlabel(a)
        ax.set_ylabel(b)
        ax.grid(False)
    fig.subplots_adjust(wspace=0.34)
    png = outputs["figures_dir"] / f"{outputs['prefix']}_3d_scatter_projections.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_3d_scatter_projections.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)
    return [png, pdf]


def projection_colors(df: pd.DataFrame, args: argparse.Namespace) -> Any:
    info = color_values(df, args)
    if info["kind"] == "numeric":
        return info["values"]
    if info["kind"] == "categorical":
        return [info["colors"][value] for value in df[args.color].astype(str)]
    return MIRA_COLORS["blue"]


def write_index(outputs: dict[str, Any], args: argparse.Namespace, source: str, df: pd.DataFrame, written: list[str]) -> None:
    ranges = {
        args.x: [float(df[args.x].min()), float(df[args.x].max())],
        args.y: [float(df[args.y].min()), float(df[args.y].max())],
        args.z: [float(df[args.z].min()), float(df[args.z].max())],
    }
    color_note = f"，颜色表示 `{args.color}`" if args.color else ""
    size_note = f"，点大小表示 `{args.size}`" if args.size else ""
    caption = f"图：`{args.x}`、`{args.y}` 与 `{args.z}` 的三维散点分布{color_note}{size_note}。"
    interpretation = "三维散点图用于观察空间分布、分群、极端点或三变量耦合关系；精确比较应结合投影图、表格或统计量。"
    lines = [
        "# 3D Scatter Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Plot data: `{outputs['plot_data']}`",
        f"- Summary: `{outputs['summary']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Point count: {len(df)}",
        f"- Axis ranges: `{json.dumps(ranges, ensure_ascii=False)}`",
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
            "- 3D scatter can hide occluded points; rotate/view choice must be recorded.",
            "- When exact threshold, ranking, or dominance matters, add a 2D projection, contour, or numeric table.",
            "- Do not use 3D scatter for two-variable data or tiny tables.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "scatter3d"


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
