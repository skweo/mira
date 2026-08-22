#!/usr/bin/env python3
"""Generate a hexbin joint-distribution figure with marginal histograms."""

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

from visual_style import MIRA_COLORS, apply_mira_style, save_mira_figure


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    outputs = prepare_outputs(args, root)
    df, source = load_table_or_demo(args, root)
    x_col, y_col = infer_columns(df, args)
    work = prepare_data(df, x_col, y_col)
    if len(work) < args.min_samples:
        raise SystemExit(f"ERROR: hexbin joint plot needs at least {args.min_samples} complete samples; got {len(work)}.")

    work.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary = build_summary(work, x_col, y_col, args)
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    fig = plot_hexbin_joint(work, x_col, y_col, args)
    written = save_figures(fig, outputs, args)
    params = {
        "kind": "hexbin_joint",
        "source": source,
        "x": x_col,
        "y": y_col,
        "samples": int(len(work)),
        "gridsize": args.gridsize,
        "bins": args.bins,
        "marginal_bins": args.marginal_bins,
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, written, source, x_col, y_col, len(work), args)
    print_written(outputs, written)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", action="store_true", help="Use built-in demo data.")
    parser.add_argument("--x", default="", help="X numeric column.")
    parser.add_argument("--y", default="", help="Y numeric column.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="hexbin_joint", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional Chinese figure title.")
    parser.add_argument("--xlabel", default="", help="Optional x-axis label.")
    parser.add_argument("--ylabel", default="", help="Optional y-axis label.")
    parser.add_argument("--unit-note", default="", help="Optional unit note shown in the main panel.")
    parser.add_argument("--gridsize", type=int, default=34, help="Hexbin grid size.")
    parser.add_argument("--mincnt", type=int, default=1, help="Minimum count for a visible hexagon.")
    parser.add_argument("--bins", choices=("linear", "log"), default="linear", help="Color scaling for hexbin counts.")
    parser.add_argument("--marginal-bins", type=int, default=28, help="Histogram bins for marginal distributions.")
    parser.add_argument("--cmap", default="viridis", help="Matplotlib colormap.")
    parser.add_argument("--min-samples", type=int, default=120, help="Minimum complete samples before using this visual.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_table_or_demo(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return demo_data(), "demo:hexbin_joint"
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo.")
    path = resolve_path(root, args.input)
    if not path.exists():
        raise SystemExit(f"ERROR: input file does not exist: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        return pd.read_excel(path, sheet_name=sheet), str(path)
    if path.suffix.lower() in {".csv", ".txt", ".tsv"}:
        return read_csv_with_fallback(path), str(path)
    raise SystemExit("ERROR: supported input formats are CSV, TSV, TXT, XLSX, and XLS.")


def infer_columns(df: pd.DataFrame, args: argparse.Namespace) -> tuple[str, str]:
    if args.x and args.y:
        missing = [col for col in [args.x, args.y] if col not in df.columns]
        if missing:
            raise SystemExit("ERROR: missing columns: " + ", ".join(missing))
        return args.x, args.y
    numeric = [str(col) for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if len(numeric) < 2:
        coerced = []
        for col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            if values.notna().mean() >= 0.8:
                coerced.append(str(col))
        numeric = coerced
    if len(numeric) < 2:
        raise SystemExit("ERROR: pass --x --y, or provide at least two numeric columns.")
    return args.x or numeric[0], args.y or numeric[1]


def prepare_data(df: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    work = df[[x_col, y_col]].copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work = work.replace([np.inf, -np.inf], np.nan).dropna().copy()
    return work


def build_summary(work: pd.DataFrame, x_col: str, y_col: str, args: argparse.Namespace) -> pd.DataFrame:
    x = work[x_col]
    y = work[y_col]
    pearson = float(x.corr(y, method="pearson"))
    spearman = float(x.corr(y, method="spearman"))
    rows: list[dict[str, Any]] = [
        {"metric": "samples", "value": int(len(work))},
        {"metric": "x_min", "value": float(x.min())},
        {"metric": "x_max", "value": float(x.max())},
        {"metric": "x_mean", "value": float(x.mean())},
        {"metric": "x_std", "value": float(x.std(ddof=1))},
        {"metric": "y_min", "value": float(y.min())},
        {"metric": "y_max", "value": float(y.max())},
        {"metric": "y_mean", "value": float(y.mean())},
        {"metric": "y_std", "value": float(y.std(ddof=1))},
        {"metric": "pearson_corr", "value": pearson},
        {"metric": "spearman_corr", "value": spearman},
        {"metric": "gridsize", "value": int(args.gridsize)},
        {"metric": "color_bins", "value": args.bins},
    ]
    return pd.DataFrame(rows)


def plot_hexbin_joint(work: pd.DataFrame, x_col: str, y_col: str, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig = plt.figure(figsize=(6.4, 5.8))
    grid = fig.add_gridspec(
        4,
        4,
        left=0.11,
        right=0.88,
        bottom=0.10,
        top=0.90,
        hspace=0.06,
        wspace=0.06,
    )
    ax_joint = fig.add_subplot(grid[1:, :3])
    ax_x = fig.add_subplot(grid[0, :3], sharex=ax_joint)
    ax_y = fig.add_subplot(grid[1:, 3], sharey=ax_joint)

    x = work[x_col].to_numpy(float)
    y = work[y_col].to_numpy(float)
    hb = ax_joint.hexbin(
        x,
        y,
        gridsize=args.gridsize,
        mincnt=args.mincnt,
        cmap=args.cmap,
        bins="log" if args.bins == "log" else None,
        linewidths=0.0,
    )
    cbar = fig.colorbar(hb, ax=ax_joint, fraction=0.046, pad=0.035)
    cbar.set_label("样本数" if args.bins == "linear" else "样本数（对数色阶）")

    hist_color = MIRA_COLORS["teal"]
    ax_x.hist(x, bins=args.marginal_bins, color=hist_color, alpha=0.72, edgecolor="white", linewidth=0.4)
    ax_y.hist(y, bins=args.marginal_bins, orientation="horizontal", color=hist_color, alpha=0.72, edgecolor="white", linewidth=0.4)

    ax_joint.set_xlabel(args.xlabel or x_col)
    ax_joint.set_ylabel(args.ylabel or y_col)
    if args.title:
        fig.suptitle(args.title, fontsize=12, y=0.98)
    if args.unit_note:
        ax_joint.text(0.98, 0.02, args.unit_note, transform=ax_joint.transAxes, ha="right", va="bottom", fontsize=9, color=MIRA_COLORS["gray"])

    for ax in [ax_joint, ax_x, ax_y]:
        ax.grid(False)
        ax.set_facecolor("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax_x.spines["left"].set_visible(False)
    ax_y.spines["bottom"].set_visible(False)
    ax_x.tick_params(axis="x", labelbottom=False)
    ax_x.tick_params(axis="y", left=False, labelleft=False)
    ax_y.tick_params(axis="x", bottom=False, labelbottom=False)
    ax_y.tick_params(axis="y", labelleft=False)
    return fig


def save_figures(fig: Any, outputs: dict[str, Path], args: argparse.Namespace) -> list[str]:
    png = outputs["figures_dir"] / f"{outputs['prefix']}_hexbin_joint.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_hexbin_joint.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)
    return [str(png), str(pdf)]


def write_index(outputs: dict[str, Path], written: list[str], source: str, x_col: str, y_col: str, samples: int, args: argparse.Namespace) -> None:
    lines = [
        "# Hexbin Joint Distribution Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Plot data: `{outputs['plot_data']}`",
        f"- Summary: `{outputs['summary']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Sample count: {samples}",
        "- Role: `validate` / `compare`",
        "- Chart grammar: hexbin joint distribution with marginal histograms",
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
            f"图：`{x_col}` 与 `{y_col}` 的 Hexbin 联合分布图。主图用六边形颜色表示二维样本密度，上方和右侧分别给出两个变量的边际分布，用于识别相关方向、密集区域和异常尾部。",
            "",
            "## Nearby Interpretation Draft",
            "",
            "Hexbin 联合分布图适合样本量较大或散点严重重叠的情形。正文应结合相关系数、边际分布形态和高密度区域说明变量关系；若存在分组差异，应进一步分组作图或给出对比表。",
            "",
            "## Caveat",
            "",
            "- Hexbin 颜色表示落入六边形单元的样本数，不代表连续概率密度的精确估计。",
            "- `gridsize` 会影响视觉粒度，最终论文应记录参数并避免过粗或过细。",
            "- 边际分布只说明单变量形态，不能单独证明变量之间的因果关系。",
            "- 若结论依赖极端尾部，应补充分位数表、异常样本表或局部放大图。",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def demo_data() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    x = rng.gamma(2.0, size=1000)
    y = -0.5 * x + rng.normal(size=1000)
    return pd.DataFrame({"变量x": x, "变量y": y})


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Path]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "plot_data": data_dir / f"{prefix}_hexbin_joint_plot_data.csv",
        "summary": data_dir / f"{prefix}_hexbin_joint_summary.csv",
        "params": data_dir / f"{prefix}_hexbin_joint_params.json",
        "index": figures_dir / f"{prefix}_hexbin_joint_index.md",
        "prefix": prefix,
    }


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    last_error: Exception | None = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
        try:
            return pd.read_csv(path, encoding=encoding, sep=sep)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(path, sep=sep)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "hexbin_joint"


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


def print_written(outputs: dict[str, Path], written: list[str]) -> None:
    print("INFO: hexbin joint figures written:")
    for path in written:
        print(f"  figure: {path}")
    print(f"  plot_data: {outputs['plot_data']}")
    print(f"  summary: {outputs['summary']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")


if __name__ == "__main__":
    raise SystemExit(main())
