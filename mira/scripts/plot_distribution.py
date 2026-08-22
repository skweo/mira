#!/usr/bin/env python3
"""Generate violin, box, and JoyPlot/ridgeline figures for Mira papers."""

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

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, mira_figure_size, save_mira_figure


PLOT_KINDS = ("violin", "box", "joy")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    df, source = load_source(args, root)
    long_df, meta = build_long_frame(df, args)
    outputs = prepare_outputs(args, root)

    written: dict[str, list[str]] = {"figures": [], "tables": []}
    summary = summarize(long_df)
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    long_df.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    written["tables"].extend([str(outputs["summary"]), str(outputs["plot_data"])])

    kinds = list(PLOT_KINDS) if args.kind == "all" else [args.kind]
    for kind in kinds:
        figure_paths = plot_kind(kind, long_df, args, outputs)
        written["figures"].extend(str(path) for path in figure_paths)

    params = {
        "source": source,
        "kind": args.kind,
        "value_column": args.value,
        "group_column": args.group,
        "hue_column": args.hue,
        "feature_columns": meta["feature_columns"],
        "n_input_rows": len(df),
        "n_plot_rows": len(long_df),
        "dropped_rows": meta["dropped_rows"],
        "orientation": args.orientation,
        "show_points": not args.no_points,
        "written": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, args, source, long_df, summary, written)

    print("INFO: distribution figures written:")
    for path in written["figures"]:
        print(f"  figure: {path}")
    print(f"  summary: {outputs['summary']}")
    print(f"  plot_data: {outputs['plot_data']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")
    if meta["dropped_rows"]:
        print(f"INFO: dropped rows with missing value/group fields: {meta['dropped_rows']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", choices=["iris", "scores"], help="Generate a built-in demo dataset.")
    parser.add_argument("--kind", choices=("violin", "box", "joy", "all"), default="all", help="Figure type.")
    parser.add_argument("--features", help="Comma-separated numeric columns for wide-format input.")
    parser.add_argument("--value", help="Numeric value column for long-format input.")
    parser.add_argument("--group", help="Category/group column.")
    parser.add_argument("--hue", help="Optional secondary category for violin/box plots.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="distribution", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--xlabel", default="", help="Override x-axis label.")
    parser.add_argument("--ylabel", default="", help="Override y-axis label.")
    parser.add_argument("--orientation", choices=("auto", "vertical", "horizontal"), default="auto", help="Violin/box orientation.")
    parser.add_argument("--order", help="Comma-separated category order for group/feature axis.")
    parser.add_argument("--no-points", action="store_true", help="Hide jittered sample points.")
    parser.add_argument("--max-points", type=int, default=600, help="Maximum rows for overlayed sample points.")
    parser.add_argument("--joy-overlap", type=float, default=1.0, help="JoyPlot overlap value.")
    parser.add_argument("--joy-alpha", type=float, default=0.82, help="JoyPlot fill alpha.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_source(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return load_demo(args.demo, args)
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo <iris|scores>.")
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
    if name == "iris":
        from sklearn.datasets import load_iris

        data = load_iris()
        df = pd.DataFrame(data.data, columns=["萼片长度", "萼片宽度", "花瓣长度", "花瓣宽度"])
        df["类别"] = [str(data.target_names[i]) for i in data.target]
        if not args.features and not args.value:
            args.features = "萼片长度,萼片宽度,花瓣长度,花瓣宽度"
        if not args.group:
            args.group = "类别"
        return df, "demo:iris"

    rng = np.random.default_rng(42)
    records: list[dict[str, Any]] = []
    groups = ["方案A", "方案B", "方案C", "方案D"]
    for i, group in enumerate(groups):
        base = rng.normal(loc=70 + i * 4, scale=5 + i * 0.7, size=120)
        if group in {"方案C", "方案D"}:
            base = np.concatenate([base, rng.normal(loc=83 + i * 2, scale=2.6, size=28)])
        for j, value in enumerate(base):
            records.append({"方案": group, "指标值": float(value), "批次": f"批次{j % 3 + 1}"})
    df = pd.DataFrame(records)
    if not args.value:
        args.value = "指标值"
    if not args.group:
        args.group = "方案"
    if not args.hue:
        args.hue = "批次"
    return df, "demo:scores"


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


def build_long_frame(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_cols = parse_columns(args.features)
    if feature_cols:
        missing = [col for col in feature_cols if col not in df.columns]
        if missing:
            raise SystemExit("ERROR: feature columns not found: " + ", ".join(missing))
        id_vars = [col for col in [args.group, args.hue] if col and col in df.columns]
        melted = df.melt(id_vars=id_vars, value_vars=feature_cols, var_name="指标", value_name="取值")
        long_df = melted.rename(columns={args.group: "组别"} if args.group else {})
        if not args.group:
            args.group = "指标"
        else:
            long_df["指标"] = long_df["指标"].astype(str)
        args.value = "取值"
        plot_group = args.group if args.group == "指标" else "组别"
        if args.group != "指标":
            long_df["组别"] = long_df["组别"].astype(str)
            long_df["显示组"] = long_df["组别"] + " | " + long_df["指标"].astype(str)
            args.group = "显示组"
        else:
            args.group = plot_group
    else:
        if not args.value:
            numeric_cols = infer_numeric_columns(df, {args.group, args.hue})
            if len(numeric_cols) != 1:
                raise SystemExit("ERROR: pass --value for long-format data, or --features for wide-format data.")
            args.value = numeric_cols[0]
        if args.value not in df.columns:
            raise SystemExit(f"ERROR: value column not found: {args.value}")
        if not args.group:
            args.group = "样本"
            long_df = df.copy()
            long_df[args.group] = "全部样本"
        else:
            if args.group not in df.columns:
                raise SystemExit(f"ERROR: group column not found: {args.group}")
            long_df = df.copy()

    if args.hue and args.hue not in long_df.columns:
        raise SystemExit(f"ERROR: hue column not found after reshaping: {args.hue}")

    long_df[args.value] = pd.to_numeric(long_df[args.value], errors="coerce")
    required = [args.value, args.group]
    if args.hue:
        required.append(args.hue)
    valid = long_df[required].notna().all(axis=1)
    dropped_rows = int((~valid).sum())
    long_df = long_df.loc[valid].copy()
    long_df[args.group] = long_df[args.group].astype(str)
    if args.hue:
        long_df[args.hue] = long_df[args.hue].astype(str)
    if len(long_df) < 5:
        raise SystemExit("ERROR: at least 5 complete numeric observations are required.")
    if long_df[args.group].nunique() > 40:
        raise SystemExit("ERROR: too many groups for a readable distribution plot; aggregate or filter first.")

    return long_df, {"feature_columns": feature_cols, "dropped_rows": dropped_rows}


def parse_columns(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，;；]", text) if part.strip()]


def infer_numeric_columns(df: pd.DataFrame, excluded: set[str | None]) -> list[str]:
    excluded_clean = {value for value in excluded if value}
    out: list[str] = []
    for col in df.columns:
        if col in excluded_clean:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() >= max(5, int(len(df) * 0.8)):
            out.append(col)
    return out


def summarize(long_df: pd.DataFrame) -> pd.DataFrame:
    group_col = current_group_column(long_df)
    value_col = current_value_column(long_df)
    grouped = long_df.groupby(group_col, observed=False)[value_col]
    summary = grouped.agg(
        样本量="count",
        均值="mean",
        标准差="std",
        最小值="min",
        下四分位数=lambda s: s.quantile(0.25),
        中位数="median",
        上四分位数=lambda s: s.quantile(0.75),
        最大值="max",
    ).reset_index()
    summary["四分位距"] = summary["上四分位数"] - summary["下四分位数"]
    return summary


def current_group_column(df: pd.DataFrame) -> str:
    for col in ["显示组", "指标", "组别", "方案", "类别", "样本"]:
        if col in df.columns:
            return col
    return df.columns[0]


def current_value_column(df: pd.DataFrame) -> str:
    for col in ["取值", "指标值", "value"]:
        if col in df.columns:
            return col
    numeric = infer_numeric_columns(df, set())
    if not numeric:
        raise SystemExit("ERROR: cannot identify numeric value column.")
    return numeric[0]


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Path]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "summary": data_dir / f"{prefix}_distribution_summary.csv",
        "plot_data": data_dir / f"{prefix}_distribution_plot_data.csv",
        "params": data_dir / f"{prefix}_distribution_params.json",
        "index": figures_dir / f"{prefix}_distribution_index.md",
        "prefix": Path(prefix),
    }


def plot_kind(kind: str, long_df: pd.DataFrame, args: argparse.Namespace, outputs: dict[str, Path]) -> list[Path]:
    import matplotlib.pyplot as plt
    import seaborn as sns

    apply_mira_style(font_size=11)
    prefix = str(outputs["prefix"])
    png = outputs["figures_dir"] / f"{prefix}_{kind}.png"
    pdf = outputs["figures_dir"] / f"{prefix}_{kind}.pdf"

    if kind == "joy":
        fig = plot_joy(long_df, args)
    else:
        fig, ax = plt.subplots(figsize=figure_size_for(long_df, args))
        order = category_order(long_df, args)
        orient = choose_orientation(long_df, args)
        x_col, y_col = axes_for(orient, args)
        plot_hue = args.hue or args.group
        show_legend: bool | str = "auto" if args.hue else False
        common = {
            "data": long_df,
            "x": x_col,
            "y": y_col,
            "order": order,
            "hue": plot_hue,
            "hue_order": order if plot_hue == args.group else None,
            "palette": palette_for(long_df, plot_hue),
            "legend": show_legend,
            "ax": ax,
        }
        if kind == "violin":
            sns.violinplot(**common, inner="quartile", cut=0, linewidth=0.9, density_norm="width")
        else:
            sns.boxplot(**common, width=0.58, linewidth=1.1, fliersize=3)
        if not args.no_points and len(long_df) <= args.max_points:
            point_common = {
                "data": long_df,
                "x": x_col,
                "y": y_col,
                "order": order,
                "hue": plot_hue,
                "hue_order": order if plot_hue == args.group else None,
                "palette": palette_for(long_df, plot_hue),
                "legend": show_legend,
                "ax": ax,
                "dodge": bool(args.hue),
                "alpha": 0.42,
                "size": 2.4,
                "linewidth": 0,
            }
            sns.stripplot(**point_common)
            if args.hue:
                deduplicate_legend(ax)
        style_distribution_axis(ax, args, kind, orient)
        fig.tight_layout()

    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    plt.close(fig)
    return [png, pdf]


def plot_joy(long_df: pd.DataFrame, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt
    from scipy.stats import gaussian_kde

    order = category_order(long_df, args)
    groups = order or sorted(long_df[args.group].dropna().astype(str).unique())
    n_groups = len(groups)
    fig_height = max(3.8, min(8.8, 0.42 * n_groups + 2.2))
    fig, ax = plt.subplots(figsize=(7.2, fig_height))
    values_all = long_df[args.value].to_numpy(dtype=float)
    xmin, xmax = float(np.nanmin(values_all)), float(np.nanmax(values_all))
    pad = max((xmax - xmin) * 0.08, 1e-6)
    x_grid = np.linspace(xmin - pad, xmax + pad, 360)
    gap = 0.82
    scale = max(0.35, min(1.25, args.joy_overlap)) * 0.82
    palette = palette_for_groups(n_groups)

    for i, group in enumerate(groups):
        group_values = long_df.loc[long_df[args.group].astype(str) == str(group), args.value].to_numpy(dtype=float)
        group_values = group_values[np.isfinite(group_values)]
        baseline = i * gap
        if len(group_values) >= 3 and np.unique(group_values).size >= 2:
            density = gaussian_kde(group_values)(x_grid)
            if density.max() > 0:
                density = density / density.max() * scale
        else:
            density = np.zeros_like(x_grid)
        color = palette[i % len(palette)]
        ax.fill_between(x_grid, baseline, baseline + density, color=color, alpha=args.joy_alpha, linewidth=0)
        ax.plot(x_grid, baseline + density, color=color, linewidth=1.0)
        median = float(np.median(group_values)) if len(group_values) else np.nan
        if np.isfinite(median):
            ax.plot([median, median], [baseline, baseline + scale * 0.18], color=MIRA_COLORS["gray"], linewidth=0.9)

    ax.set_yticks([i * gap for i in range(n_groups)])
    ax.set_yticklabels(groups)
    ax.set_ylim(-0.15, max(0.6, (n_groups - 1) * gap + scale + 0.15))
    ax.set_xlim(float(x_grid.min()), float(x_grid.max()))
    if args.title:
        ax.set_title(args.title)
    ax.set_xlabel(args.xlabel or args.value)
    ax.set_ylabel(args.ylabel or args.group)
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    return fig


def figure_size_for(long_df: pd.DataFrame, args: argparse.Namespace) -> tuple[float, float]:
    n_groups = long_df[args.group].nunique()
    if choose_orientation(long_df, args) == "horizontal":
        return (7.2, max(3.8, min(8.5, 0.38 * n_groups + 1.8)))
    return (max(6.4, min(9.0, 0.45 * n_groups + 3.2)), 4.4)


def choose_orientation(long_df: pd.DataFrame, args: argparse.Namespace) -> str:
    if args.orientation != "auto":
        return args.orientation
    groups = [str(item) for item in long_df[args.group].dropna().unique()]
    if len(groups) > 8 or max((len(item) for item in groups), default=0) > 10:
        return "horizontal"
    return "vertical"


def axes_for(orientation: str, args: argparse.Namespace) -> tuple[str, str]:
    if orientation == "horizontal":
        return args.value, args.group
    return args.group, args.value


def category_order(long_df: pd.DataFrame, args: argparse.Namespace) -> list[str] | None:
    if args.order:
        return parse_columns(args.order)
    medians = long_df.groupby(args.group, observed=False)[args.value].median().sort_values()
    return [str(item) for item in medians.index]


def palette_for(long_df: pd.DataFrame, field: str) -> list[str]:
    if field not in long_df.columns:
        return MIRA_PALETTE
    return palette_for_groups(long_df[field].nunique())


def palette_for_groups(n_groups: int) -> list[str]:
    if n_groups <= len(MIRA_PALETTE):
        return MIRA_PALETTE[: max(1, n_groups)]
    try:
        import seaborn as sns

        return list(sns.color_palette("tab20", n_groups).as_hex())
    except Exception:
        return [f"C{i}" for i in range(n_groups)]


def style_distribution_axis(ax: Any, args: argparse.Namespace, kind: str, orientation: str) -> None:
    title_map = {
        "violin": "分布形态与四分位结构",
        "box": "中位数、四分位距与异常值",
    }
    if args.title:
        ax.set_title(args.title)
    else:
        ax.set_title(title_map.get(kind, "分布比较"))
    if orientation == "horizontal":
        ax.set_xlabel(args.xlabel or args.value)
        ax.set_ylabel(args.ylabel or args.group)
    else:
        ax.set_xlabel(args.xlabel or args.group)
        ax.set_ylabel(args.ylabel or args.value)
        ax.tick_params(axis="x", rotation=25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(False)


def deduplicate_legend(ax: Any) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    seen: dict[str, Any] = {}
    for handle, label in zip(handles, labels):
        if label and label not in seen:
            seen[label] = handle
    ax.legend(seen.values(), seen.keys(), frameon=False, title=ax.get_legend().get_title().get_text() if ax.get_legend() else None)


def write_index(
    outputs: dict[str, Path],
    args: argparse.Namespace,
    source: str,
    long_df: pd.DataFrame,
    summary: pd.DataFrame,
    written: dict[str, list[str]],
) -> None:
    strongest = summary.sort_values("中位数", ascending=False).head(1)
    strongest_text = ""
    if not strongest.empty:
        strongest_text = f"中位数最高的组为 `{strongest.iloc[0][args.group]}`，中位数约为 {strongest.iloc[0]['中位数']:.4g}。"
    caption = (
        "图：不同组别的指标分布比较。小提琴图强调分布形态和多峰特征，箱式图强调中位数、四分位距和异常值，"
        "JoyPlot 山峦图强调多组分布的层叠比较；最终结论需结合摘要统计表和问题背景解释。"
    )
    lines = [
        "# Distribution Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Plot kind: `{args.kind}`",
        f"- Value column: `{args.value}`",
        f"- Group column: `{args.group}`",
        f"- Hue column: `{args.hue or ''}`",
        f"- Plot rows: {len(long_df)}",
        f"- Group count: {long_df[args.group].nunique()}",
        f"- Summary table: `{outputs['summary']}`",
        f"- Plot data: `{outputs['plot_data']}`",
        f"- Parameters: `{outputs['params']}`",
        "",
        "## Figures",
        "",
    ]
    for path in written["figures"]:
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
            strongest_text or "结合中位数、四分位距和分布形态判断不同组别的稳定性与差异。",
            "",
            "## Caveat",
            "",
            "- Violin/JoyPlot show kernel-density estimates; small samples can create unstable shapes.",
            "- Box plots hide multimodality; use violin or JoyPlot when distribution shape matters.",
            "- Do not claim a statistical difference from the figure alone; use tests, confidence intervals, or domain thresholds when needed.",
            "",
        ]
    )
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "distribution"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    raise SystemExit(main())
