#!/usr/bin/env python3
"""Generate reproducible 3D bar/bar3D figures for Mira papers."""

from __future__ import annotations

import argparse
import json
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


AGG_FUNCS = {"sum": "sum", "mean": "mean", "median": "median", "max": "max", "min": "min"}


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    df, source = load_source(args, root)
    bars, matrix, meta = build_bar_data(df, args)
    outputs = prepare_outputs(args, root)

    bars.to_csv(outputs["bars"], index=False, encoding="utf-8-sig")
    matrix.to_csv(outputs["matrix"], encoding="utf-8-sig")

    fig = plot_3d_bar(bars, args)
    png = outputs["figures_dir"] / f"{outputs['prefix']}_3d_bar.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_3d_bar.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)

    companion_paths: list[str] = []
    if args.heatmap:
        companion_paths = [str(path) for path in plot_heatmap(matrix, args, outputs)]

    params = {
        "source": source,
        "input_mode": "matrix" if args.matrix else "long",
        "x_column": args.x,
        "y_column": args.y,
        "value_column": args.value,
        "aggregation": args.agg,
        "color_by": args.color_by,
        "unit": args.unit,
        "n_input_rows": len(df),
        "n_bars": len(bars),
        "dropped_rows": meta["dropped_rows"],
        "duplicate_cells": meta["duplicate_cells"],
        "view": {"elev": args.elev, "azim": args.azim},
        "written_figures": [str(png), str(pdf)] + companion_paths,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, bars, matrix, [str(png), str(pdf)] + companion_paths)

    print("INFO: 3D bar figures written:")
    print(f"  figure: {png}")
    print(f"  figure: {pdf}")
    for path in companion_paths:
        print(f"  figure: {path}")
    print(f"  bars: {outputs['bars']}")
    print(f"  matrix: {outputs['matrix']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    if meta["dropped_rows"]:
        print(f"INFO: dropped rows with missing x/y/value fields: {meta['dropped_rows']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", choices=("scenarios", "grid"), help="Generate built-in demo data.")
    parser.add_argument("--matrix", action="store_true", help="Treat input as matrix data instead of long x/y/value rows.")
    parser.add_argument("--index-col", help="Row-category column for matrix input.")
    parser.add_argument("--x", help="X category column for long input.")
    parser.add_argument("--y", help="Y category column for long input.")
    parser.add_argument("--value", help="Numeric height/value column for long input.")
    parser.add_argument("--agg", choices=tuple(AGG_FUNCS), default="sum", help="Aggregation for duplicate x-y cells.")
    parser.add_argument("--x-order", help="Comma-separated x category order.")
    parser.add_argument("--y-order", help="Comma-separated y category order.")
    parser.add_argument("--color-by", choices=("height", "x", "y"), default="height", help="Color mapping.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="bar3d", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--xlabel", default="", help="Override x-axis label.")
    parser.add_argument("--ylabel", default="", help="Override y-axis label.")
    parser.add_argument("--zlabel", default="", help="Override z-axis label.")
    parser.add_argument("--unit", default="", help="Optional value unit.")
    parser.add_argument("--elev", type=float, default=28.0, help="3D camera elevation.")
    parser.add_argument("--azim", type=float, default=-48.0, help="3D camera azimuth.")
    parser.add_argument("--bar-alpha", type=float, default=0.86, help="Bar alpha.")
    parser.add_argument("--bar-width", type=float, default=0.72, help="Bar width/depth in category cells.")
    parser.add_argument("--label-top", type=int, default=0, help="Label top-N bars by value.")
    parser.add_argument("--max-bars", type=int, default=120, help="Maximum bars for readability.")
    parser.add_argument("--allow-negative", action="store_true", help="Allow negative values using downward bars.")
    parser.add_argument("--heatmap", action="store_true", help="Also write a 2D heatmap companion.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_source(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return load_demo(args.demo, args)
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo <scenarios|grid>.")
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
    if name == "grid":
        rows = []
        for p1 in ["低", "中低", "中高", "高"]:
            for p2 in ["短", "中", "长", "超长"]:
                base = {"低": 0.4, "中低": 0.8, "中高": 1.1, "高": 1.35}[p1]
                adjust = {"短": 0.15, "中": 0.35, "长": 0.48, "超长": 0.42}[p2]
                rows.append({"参数A": p1, "参数B": p2, "目标值": round(10 + 8 * base + 6 * adjust - 3 * base * adjust, 3)})
        args.x = args.x or "参数A"
        args.y = args.y or "参数B"
        args.value = args.value or "目标值"
        args.heatmap = True if not args.heatmap else args.heatmap
        return pd.DataFrame(rows), "demo:grid"

    rows = []
    schemes = ["方案A", "方案B", "方案C", "方案D"]
    metrics = ["收益", "稳定性", "效率", "公平性", "鲁棒性"]
    values = np.array(
        [
            [82, 74, 88, 69, 76],
            [78, 82, 80, 73, 84],
            [86, 70, 83, 78, 72],
            [74, 88, 76, 85, 81],
        ],
        dtype=float,
    )
    for i, scheme in enumerate(schemes):
        for j, metric in enumerate(metrics):
            rows.append({"方案": scheme, "指标": metric, "评分": values[i, j]})
    args.x = args.x or "指标"
    args.y = args.y or "方案"
    args.value = args.value or "评分"
    return pd.DataFrame(rows), "demo:scenarios"


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


def build_bar_data(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    if args.matrix:
        bars = melt_matrix(df, args)
        dropped_rows = 0
        duplicate_cells = 0
    else:
        bars, dropped_rows, duplicate_cells = build_long_bars(df, args)

    if not args.allow_negative and (bars["value"] < 0).any():
        raise SystemExit("ERROR: negative values found. Use --allow-negative or choose a 2D/diverging chart.")
    if len(bars) > args.max_bars:
        raise SystemExit(f"ERROR: {len(bars)} bars exceed --max-bars {args.max_bars}; filter data or use heatmap/table.")

    x_order = complete_order(parse_columns(args.x_order), bars["x"].astype(str).tolist())
    y_order = complete_order(parse_columns(args.y_order), bars["y"].astype(str).tolist())
    bars["x"] = pd.Categorical(bars["x"].astype(str), categories=x_order, ordered=True)
    bars["y"] = pd.Categorical(bars["y"].astype(str), categories=y_order, ordered=True)
    bars = bars.sort_values(["y", "x"]).reset_index(drop=True)
    bars["x"] = bars["x"].astype(str)
    bars["y"] = bars["y"].astype(str)
    matrix = bars.pivot(index="y", columns="x", values="value").reindex(index=y_order, columns=x_order)
    return bars, matrix, {"dropped_rows": dropped_rows, "duplicate_cells": duplicate_cells}


def melt_matrix(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    work = df.copy()
    index_col = args.index_col
    if not index_col:
        nonnumeric = [col for col in work.columns if not pd.api.types.is_numeric_dtype(work[col])]
        index_col = nonnumeric[0] if nonnumeric else None
    if index_col:
        if index_col not in work.columns:
            raise SystemExit(f"ERROR: index column not found: {index_col}")
        value_cols = [col for col in work.columns if col != index_col]
        melted = work.melt(id_vars=[index_col], value_vars=value_cols, var_name="x", value_name="value")
        melted = melted.rename(columns={index_col: "y"})
    else:
        melted = work.copy()
        melted.insert(0, "y", [f"行{i + 1}" for i in range(len(work))])
        melted = melted.melt(id_vars=["y"], var_name="x", value_name="value")
    melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
    valid = melted[["x", "y", "value"]].notna().all(axis=1)
    out = melted.loc[valid, ["x", "y", "value"]].copy()
    if out.empty:
        raise SystemExit("ERROR: no numeric matrix cells found.")
    args.x = args.x or "列变量"
    args.y = args.y or "行变量"
    args.value = args.value or "数值"
    return out


def build_long_bars(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, int, int]:
    if not args.x or not args.y:
        raise SystemExit("ERROR: long input requires --x and --y category columns.")
    if not args.value:
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col not in {args.x, args.y}]
        if len(numeric_cols) != 1:
            raise SystemExit("ERROR: pass --value for long input, or use --matrix.")
        args.value = numeric_cols[0]
    missing = [col for col in [args.x, args.y, args.value] if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: required columns not found: " + ", ".join(missing))
    work = df[[args.x, args.y, args.value]].copy()
    work[args.value] = pd.to_numeric(work[args.value], errors="coerce")
    valid = work[[args.x, args.y, args.value]].notna().all(axis=1)
    dropped_rows = int((~valid).sum())
    work = work.loc[valid].copy()
    work[args.x] = work[args.x].astype(str).str.strip()
    work[args.y] = work[args.y].astype(str).str.strip()
    cell_counts = work.groupby([args.x, args.y], observed=False).size()
    duplicate_cells = int((cell_counts > 1).sum())
    grouped = (
        work.groupby([args.x, args.y], as_index=False, observed=False)[args.value]
        .agg(AGG_FUNCS[args.agg])
        .rename(columns={args.x: "x", args.y: "y", args.value: "value"})
    )
    if grouped.empty:
        raise SystemExit("ERROR: no complete x-y-value rows remain after cleaning.")
    return grouped, dropped_rows, duplicate_cells


def plot_3d_bar(bars: pd.DataFrame, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt
    from matplotlib import cm, colors as mcolors

    apply_mira_style(font_size=10)
    fig = plt.figure(figsize=(7.0, 5.2))
    ax = fig.add_subplot(111, projection="3d")
    x_order = list(dict.fromkeys(bars["x"].tolist()))
    y_order = list(dict.fromkeys(bars["y"].tolist()))
    x_rank = {name: i for i, name in enumerate(x_order)}
    y_rank = {name: i for i, name in enumerate(y_order)}
    xpos = np.array([x_rank[x] for x in bars["x"]], dtype=float)
    ypos = np.array([y_rank[y] for y in bars["y"]], dtype=float)
    values = bars["value"].to_numpy(float)
    zbase = np.where(values >= 0, 0.0, values)
    heights = np.abs(values)
    dx = np.full(len(bars), args.bar_width)
    dy = np.full(len(bars), args.bar_width)
    colors = bar_colors(bars, values, args)
    ax.bar3d(xpos, ypos, zbase, dx, dy, heights, color=colors, alpha=args.bar_alpha, edgecolor="white", linewidth=0.45, shade=True)

    ax.set_xticks(np.arange(len(x_order)) + args.bar_width / 2)
    ax.set_yticks(np.arange(len(y_order)) + args.bar_width / 2)
    ax.set_xticklabels(x_order, rotation=18, ha="right")
    ax.set_yticklabels(y_order, rotation=-12, ha="left")
    zlabel = args.zlabel or args.value or "数值"
    if args.unit:
        zlabel = f"{zlabel}（{args.unit}）"
    apply_3d_style(
        ax,
        xlabel=args.xlabel or args.x or "X",
        ylabel=args.ylabel or args.y or "Y",
        zlabel=zlabel,
        elev=args.elev,
        azim=args.azim,
    )
    ax.xaxis.labelpad = 18
    ax.yaxis.labelpad = 16
    ax.zaxis.labelpad = 12
    ax.set_xlim(0, max(len(x_order), 1))
    ax.set_ylim(0, max(len(y_order), 1))
    if not args.allow_negative:
        ax.set_zlim(bottom=0)
    if args.color_by == "height":
        norm = mcolors.Normalize(vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
        sm = cm.ScalarMappable(norm=norm, cmap="viridis")
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.66, pad=0.08)
        cbar.set_label(args.value or "数值")
    elif args.color_by in {"x", "y"}:
        add_category_legend(ax, bars, args.color_by)
    label_top_bars(ax, bars, xpos, ypos, values, args)
    soften_3d_panes(ax)
    if args.title:
        ax.set_title(args.title, pad=14)
    return fig


def bar_colors(bars: pd.DataFrame, values: np.ndarray, args: argparse.Namespace) -> list[Any]:
    from matplotlib import cm, colors as mcolors

    if args.color_by == "height":
        norm = mcolors.Normalize(vmin=float(np.nanmin(values)), vmax=float(np.nanmax(values)))
        return [cm.viridis(norm(value)) for value in values]
    categories = list(dict.fromkeys(bars[args.color_by].tolist()))
    palette = MIRA_PALETTE
    if len(categories) > len(palette):
        import matplotlib.pyplot as plt

        cmap = plt.get_cmap("tab20")
        palette = [cmap(i / max(len(categories) - 1, 1)) for i in range(len(categories))]
    mapping = {category: palette[i % len(palette)] for i, category in enumerate(categories)}
    return [mapping[value] for value in bars[args.color_by]]


def add_category_legend(ax: Any, bars: pd.DataFrame, category: str) -> None:
    import matplotlib.patches as mpatches

    categories = list(dict.fromkeys(bars[category].tolist()))
    palette = MIRA_PALETTE
    handles = [mpatches.Patch(color=palette[i % len(palette)], label=str(value)) for i, value in enumerate(categories)]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 0.98), borderaxespad=0)


def label_top_bars(ax: Any, bars: pd.DataFrame, xpos: np.ndarray, ypos: np.ndarray, values: np.ndarray, args: argparse.Namespace) -> None:
    if args.label_top <= 0:
        return
    top = bars.assign(_abs=np.abs(values)).nlargest(min(args.label_top, len(bars)), "_abs")
    for idx, row in top.iterrows():
        value = float(row["value"])
        label = f"{value:g}{args.unit}" if args.unit else f"{value:g}"
        z = value if value >= 0 else value
        ax.text(float(xpos[idx]) + args.bar_width / 2, float(ypos[idx]) + args.bar_width / 2, z, label, fontsize=8, ha="center", va="bottom")


def plot_heatmap(matrix: pd.DataFrame, args: argparse.Namespace, outputs: dict[str, Any]) -> list[Path]:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    data = matrix.to_numpy(float)
    im = ax.imshow(data, cmap="viridis", aspect="auto")
    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_xticklabels(matrix.columns.astype(str), rotation=30, ha="right")
    ax.set_yticklabels(matrix.index.astype(str))
    ax.set_xlabel(args.xlabel or args.x or "X")
    ax.set_ylabel(args.ylabel or args.y or "Y")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(args.zlabel or args.value or "数值")
    if matrix.shape[0] * matrix.shape[1] <= 80:
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                value = data[i, j]
                if np.isfinite(value):
                    ax.text(j, i, f"{value:.3g}", ha="center", va="center", fontsize=8, color="white" if value > np.nanmean(data) else "#222222")
    if args.title:
        ax.set_title(args.title + "（二维投影）")
    png = outputs["figures_dir"] / f"{outputs['prefix']}_3d_bar_heatmap.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_3d_bar_heatmap.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)
    return [png, pdf]


def write_index(outputs: dict[str, Any], args: argparse.Namespace, source: str, bars: pd.DataFrame, matrix: pd.DataFrame, written: list[str]) -> None:
    top = bars.nlargest(1, "value").iloc[0]
    unit = args.unit or ""
    caption = f"图：`{args.x}` 与 `{args.y}` 构成的二维类别矩阵三维柱状图，柱高表示 `{args.value}`{('（' + args.unit + '）') if args.unit else ''}。"
    interpretation = f"最大单元为 `{top['x']} - {top['y']}`，取值为 {float(top['value']):g}{unit}。"
    lines = [
        "# 3D Bar Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Bar table: `{outputs['bars']}`",
        f"- Matrix table: `{outputs['matrix']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Bar count: {len(bars)}",
        f"- Matrix shape: {matrix.shape[0]} x {matrix.shape[1]}",
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
            "- Use 3D bars for structured two-way category or parameter-grid comparisons, not for simple one-dimensional rankings.",
            "- If exact comparison or dense cells matter, place the saved matrix table or heatmap near the 3D bar figure.",
            "- Record the camera view because changing view angle can change perceived height and occlusion.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def soften_3d_panes(ax: Any) -> None:
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.set_facecolor((0.97, 0.98, 1.0, 0.35))
        pane.set_edgecolor((0.82, 0.84, 0.88, 0.65))


def parse_columns(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，;；]", text) if part.strip()]


def complete_order(preferred: list[str], values: list[str]) -> list[str]:
    out = list(preferred)
    seen = set(out)
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "bars": data_dir / f"{prefix}_3d_bar_cells.csv",
        "matrix": data_dir / f"{prefix}_3d_bar_matrix.csv",
        "params": data_dir / f"{prefix}_3d_bar_params.json",
        "index": figures_dir / f"{prefix}_3d_bar_index.md",
        "prefix": prefix,
    }


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "bar3d"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
