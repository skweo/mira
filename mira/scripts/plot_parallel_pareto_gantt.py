#!/usr/bin/env python3
"""Generate parallel-coordinate, Pareto-front, and Gantt/timeline figures."""

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

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, save_mira_figure


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    outputs = prepare_outputs(args, root)
    if args.kind == "parallel":
        write_parallel(args, root, outputs)
    elif args.kind == "pareto":
        write_pareto(args, root, outputs)
    elif args.kind == "gantt":
        write_gantt(args, root, outputs)
    else:
        raise SystemExit(f"ERROR: unsupported kind: {args.kind}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--kind", choices=("parallel", "pareto", "gantt"), required=True, help="Figure type.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", action="store_true", help="Use built-in demo data for the chosen kind.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")

    # Parallel coordinates.
    parser.add_argument("--item-col", default="", help="Parallel-coordinate item/scheme column.")
    parser.add_argument("--metrics", default="", help="Comma-separated metric columns.")
    parser.add_argument("--group-col", default="", help="Optional group/category column.")
    parser.add_argument("--normalize", choices=("minmax", "zscore", "none"), default="minmax", help="Metric normalization.")
    parser.add_argument("--lower-is-better", default="", help="Comma-separated metrics whose smaller value is better.")
    parser.add_argument("--max-lines", type=int, default=80, help="Maximum lines in a readable parallel-coordinate plot.")
    parser.add_argument("--label-top", type=int, default=0, help="Label top-N items by mean normalized score.")

    # Pareto front.
    parser.add_argument("--x", default="", help="Pareto x objective column.")
    parser.add_argument("--y", default="", help="Pareto y objective column.")
    parser.add_argument("--x-direction", choices=("min", "max"), default="min", help="Whether x objective should be minimized or maximized.")
    parser.add_argument("--y-direction", choices=("min", "max"), default="min", help="Whether y objective should be minimized or maximized.")
    parser.add_argument("--label-col", default="", help="Optional label column for Pareto points.")
    parser.add_argument("--front-labels", type=int, default=12, help="Maximum Pareto-front point labels.")

    # Gantt/timeline.
    parser.add_argument("--task-col", default="", help="Task name column.")
    parser.add_argument("--start-col", default="", help="Task start column.")
    parser.add_argument("--end-col", default="", help="Task end column.")
    parser.add_argument("--duration-col", default="", help="Task duration column when end is absent.")
    parser.add_argument("--resource-col", default="", help="Optional resource/stage/group column.")
    parser.add_argument("--milestone-col", default="", help="Optional boolean milestone column.")
    parser.add_argument("--date-format", default="", help="Optional date parsing format.")
    return parser.parse_args()


def write_parallel(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_parallel)
    item_col = args.item_col or first_text_col(df) or str(df.columns[0])
    metrics = parse_list(args.metrics) or [col for col in df.columns if col != item_col and pd.api.types.is_numeric_dtype(df[col])]
    if len(metrics) < 2:
        raise SystemExit("ERROR: parallel coordinates need at least two numeric metric columns.")
    missing = [col for col in [item_col, args.group_col] + metrics if col and col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing columns: " + ", ".join(missing))
    work = df[[item_col] + ([args.group_col] if args.group_col else []) + metrics].copy()
    for col in metrics:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=metrics).copy()
    if work.empty:
        raise SystemExit("ERROR: no complete metric rows for parallel coordinates.")
    if len(work) > args.max_lines:
        raise SystemExit(f"ERROR: {len(work)} lines would be unreadable; filter to <= {args.max_lines}.")
    lower = set(parse_list(args.lower_is_better))
    normalized, summary = normalize_parallel(work, metrics, lower, args.normalize)
    plot_df = pd.concat([work[[item_col] + ([args.group_col] if args.group_col else [])].reset_index(drop=True), normalized.reset_index(drop=True)], axis=1)
    plot_df["mean_normalized_score"] = normalized[metrics].mean(axis=1)
    plot_df.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    fig = plot_parallel(plot_df, item_col, metrics, args)
    written = save_kind_figures(fig, outputs, args, "parallel")
    params = {
        "kind": "parallel",
        "source": source,
        "item_col": item_col,
        "metrics": metrics,
        "group_col": args.group_col,
        "normalize": args.normalize,
        "lower_is_better": sorted(lower),
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "Parallel Coordinate Figure Index", written, parallel_caption(metrics, args), parallel_interpretation(), parallel_caveats(), source, len(plot_df))
    print_written("parallel", outputs, written)


def normalize_parallel(df: pd.DataFrame, metrics: list[str], lower: set[str], method: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = pd.DataFrame(index=df.index)
    rows: list[dict[str, Any]] = []
    for col in metrics:
        values = df[col].astype(float)
        if method == "zscore":
            std = values.std(ddof=1)
            norm = pd.Series(0.0, index=df.index) if abs(std) < 1e-12 else (values - values.mean()) / std
        elif method == "none":
            norm = values.copy()
        else:
            span = values.max() - values.min()
            norm = pd.Series(0.5, index=df.index) if abs(span) < 1e-12 else (values - values.min()) / span
        if col in lower and method == "minmax":
            norm = 1.0 - norm
        out[col] = norm
        rows.append(
            {
                "metric": col,
                "raw_min": float(values.min()),
                "raw_max": float(values.max()),
                "raw_mean": float(values.mean()),
                "direction": "lower_is_better" if col in lower else "higher_is_better",
                "normalization": method,
            }
        )
    return out, pd.DataFrame(rows)


def plot_parallel(df: pd.DataFrame, item_col: str, metrics: list[str], args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    x = np.arange(len(metrics))
    groups = color_groups(df, args.group_col)
    for idx, (_, row) in enumerate(df.iterrows()):
        color = groups["colors"].get(str(row[args.group_col]), MIRA_PALETTE[idx % len(MIRA_PALETTE)]) if args.group_col else MIRA_PALETTE[idx % len(MIRA_PALETTE)]
        alpha = 0.45 if len(df) > 18 else 0.72
        ax.plot(x, row[metrics].to_numpy(float), color=color, alpha=alpha, linewidth=1.35)
    for xpos in x:
        ax.axvline(xpos, color="#D7DDE5", linewidth=0.7, zorder=0)
    label_parallel_items(ax, df, item_col, metrics, args)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=0)
    ax.set_xlim(x[0], x[-1])
    if args.normalize == "minmax":
        ax.set_ylim(-0.04, 1.04)
        ax.set_ylabel("归一化表现（越高越优）")
    else:
        ax.set_ylabel("指标值" if args.normalize == "none" else "标准化值")
    if args.group_col:
        handles = [plt.Line2D([0], [0], color=color, lw=2, label=label) for label, color in groups["colors"].items()]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    elif len(df) <= 8:
        handles = [plt.Line2D([0], [0], color=MIRA_PALETTE[i % len(MIRA_PALETTE)], lw=2, label=str(name)) for i, name in enumerate(df[item_col])]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    ax.grid(False)
    if args.title:
        ax.set_title(args.title)
    return fig


def label_parallel_items(ax: Any, df: pd.DataFrame, item_col: str, metrics: list[str], args: argparse.Namespace) -> None:
    if args.label_top <= 0:
        return
    top = df.nlargest(min(args.label_top, len(df)), "mean_normalized_score")
    last_x = len(metrics) - 1
    for _, row in top.iterrows():
        ax.text(last_x + 0.03, float(row[metrics[-1]]), str(row[item_col]), fontsize=8, va="center", color="#222222")


def write_pareto(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_pareto)
    x_col, y_col = infer_pareto_columns(df, args)
    keep = [x_col, y_col] + [col for col in [args.group_col, args.label_col] if col]
    missing = [col for col in keep if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing Pareto columns: " + ", ".join(missing))
    work = df[keep].copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work = work.dropna(subset=[x_col, y_col]).copy()
    if len(work) < 2:
        raise SystemExit("ERROR: Pareto plot needs at least two complete points.")
    work["pareto_front"] = pareto_mask(work[x_col].to_numpy(float), work[y_col].to_numpy(float), args.x_direction, args.y_direction)
    work.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary = pd.DataFrame(
        [
            {"metric": "points", "value": int(len(work))},
            {"metric": "pareto_front_points", "value": int(work["pareto_front"].sum())},
            {"metric": "x_direction", "value": args.x_direction},
            {"metric": "y_direction", "value": args.y_direction},
        ]
    )
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    fig = plot_pareto(work, x_col, y_col, args)
    written = save_kind_figures(fig, outputs, args, "pareto")
    params = {
        "kind": "pareto",
        "source": source,
        "x": x_col,
        "y": y_col,
        "x_direction": args.x_direction,
        "y_direction": args.y_direction,
        "group_col": args.group_col,
        "label_col": args.label_col,
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "Pareto Front Figure Index", written, pareto_caption(x_col, y_col, args), pareto_interpretation(), pareto_caveats(), source, len(work))
    print_written("pareto", outputs, written)


def infer_pareto_columns(df: pd.DataFrame, args: argparse.Namespace) -> tuple[str, str]:
    if args.x and args.y:
        return args.x, args.y
    numeric = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if len(numeric) < 2:
        raise SystemExit("ERROR: pass --x --y, or provide at least two numeric objective columns.")
    return args.x or numeric[0], args.y or numeric[1]


def pareto_mask(x: np.ndarray, y: np.ndarray, x_direction: str, y_direction: str) -> np.ndarray:
    x_eff = x if x_direction == "min" else -x
    y_eff = y if y_direction == "min" else -y
    mask = np.ones(len(x_eff), dtype=bool)
    for i in range(len(x_eff)):
        dominated = (x_eff <= x_eff[i]) & (y_eff <= y_eff[i]) & ((x_eff < x_eff[i]) | (y_eff < y_eff[i]))
        if dominated.any():
            mask[i] = False
    return mask


def plot_pareto(df: pd.DataFrame, x_col: str, y_col: str, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    front = df[df["pareto_front"]].copy()
    dominated = df[~df["pareto_front"]].copy()
    if args.group_col:
        groups = color_groups(df, args.group_col)
        for label, color in groups["colors"].items():
            part = dominated[dominated[args.group_col].astype(str) == label]
            ax.scatter(part[x_col], part[y_col], s=32, color=color, alpha=0.28, edgecolors="white", linewidths=0.4)
            part_front = front[front[args.group_col].astype(str) == label]
            ax.scatter(part_front[x_col], part_front[y_col], s=54, color=color, edgecolors="#222222", linewidths=0.5, label=label)
        ax.legend(loc="best", frameon=False)
    else:
        ax.scatter(dominated[x_col], dominated[y_col], s=34, color=MIRA_COLORS["gray"], alpha=0.35, edgecolors="white", linewidths=0.4, label="被支配方案")
        ax.scatter(front[x_col], front[y_col], s=58, color=MIRA_COLORS["red"], edgecolors="white", linewidths=0.6, label="Pareto 前沿")
        ax.legend(loc="best", frameon=False)
    front_sorted = front.sort_values(x_col)
    if len(front_sorted) >= 2:
        ax.plot(front_sorted[x_col], front_sorted[y_col], color=MIRA_COLORS["red"], linewidth=1.4, alpha=0.82)
    label_pareto_front(ax, front_sorted, x_col, y_col, args)
    x_arrow = "越小越优" if args.x_direction == "min" else "越大越优"
    y_arrow = "越小越优" if args.y_direction == "min" else "越大越优"
    ax.set_xlabel(f"{x_col}（{x_arrow}）")
    ax.set_ylabel(f"{y_col}（{y_arrow}）")
    ax.grid(False)
    if args.title:
        ax.set_title(args.title)
    return fig


def label_pareto_front(ax: Any, front: pd.DataFrame, x_col: str, y_col: str, args: argparse.Namespace) -> None:
    label_col = args.label_col
    if not label_col or label_col not in front.columns or args.front_labels <= 0:
        return
    for _, row in front.head(args.front_labels).iterrows():
        ax.annotate(str(row[label_col]), (float(row[x_col]), float(row[y_col])), xytext=(5, 5), textcoords="offset points", fontsize=8)


def write_gantt(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_gantt)
    task_col = args.task_col or first_text_col(df) or str(df.columns[0])
    start_col = args.start_col or infer_column(df, ["start", "开始", "开始时间"])
    end_col = args.end_col or infer_column(df, ["end", "结束", "结束时间"])
    duration_col = args.duration_col or infer_column(df, ["duration", "工期", "持续时间"])
    if not start_col:
        raise SystemExit("ERROR: Gantt chart needs a start column.")
    keep = [task_col, start_col] + [col for col in [end_col, duration_col, args.resource_col, args.milestone_col] if col]
    missing = [col for col in keep if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing Gantt columns: " + ", ".join(missing))
    work, is_datetime = normalize_gantt_frame(df[keep].copy(), task_col, start_col, end_col, duration_col, args)
    work.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary = gantt_summary(work, args.resource_col)
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")
    fig = plot_gantt(work, task_col, args.resource_col, args.milestone_col, is_datetime, args)
    written = save_kind_figures(fig, outputs, args, "gantt")
    params = {
        "kind": "gantt",
        "source": source,
        "task_col": task_col,
        "start_col": start_col,
        "end_col": end_col,
        "duration_col": duration_col,
        "resource_col": args.resource_col,
        "milestone_col": args.milestone_col,
        "is_datetime": is_datetime,
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "Gantt Timeline Figure Index", written, gantt_caption(args), gantt_interpretation(), gantt_caveats(), source, len(work))
    print_written("gantt", outputs, written)


def normalize_gantt_frame(df: pd.DataFrame, task_col: str, start_col: str, end_col: str, duration_col: str, args: argparse.Namespace) -> tuple[pd.DataFrame, bool]:
    start_dt = parse_datetime_series(df[start_col], args.date_format)
    if start_dt.notna().mean() >= 0.8:
        is_datetime = True
        df["start_plot"] = start_dt
        if end_col:
            df["end_plot"] = parse_datetime_series(df[end_col], args.date_format)
        elif duration_col:
            df["end_plot"] = df["start_plot"] + pd.to_timedelta(pd.to_numeric(df[duration_col], errors="coerce"), unit="D")
        else:
            raise SystemExit("ERROR: Gantt chart needs --end-col or --duration-col.")
        df["duration_plot"] = (df["end_plot"] - df["start_plot"]).dt.total_seconds() / 86400.0
    else:
        is_datetime = False
        df["start_plot"] = pd.to_numeric(df[start_col], errors="coerce")
        if end_col:
            df["end_plot"] = pd.to_numeric(df[end_col], errors="coerce")
        elif duration_col:
            df["end_plot"] = df["start_plot"] + pd.to_numeric(df[duration_col], errors="coerce")
        else:
            raise SystemExit("ERROR: Gantt chart needs --end-col or --duration-col.")
        df["duration_plot"] = df["end_plot"] - df["start_plot"]
    df = df.dropna(subset=["start_plot", "end_plot", "duration_plot"]).copy()
    df = df[df["duration_plot"] >= 0].copy()
    if df.empty:
        raise SystemExit("ERROR: no valid Gantt tasks after parsing start/end.")
    df = df.sort_values("start_plot").reset_index(drop=True)
    df[task_col] = df[task_col].astype(str)
    return df, is_datetime


def plot_gantt(df: pd.DataFrame, task_col: str, resource_col: str, milestone_col: str, is_datetime: bool, args: argparse.Namespace) -> Any:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    height = max(3.6, 0.34 * len(df) + 1.2)
    fig, ax = plt.subplots(figsize=(7.4, height))
    y = np.arange(len(df))
    colors = resource_colors(df, resource_col)
    if is_datetime:
        starts = mdates.date2num(pd.to_datetime(df["start_plot"]).dt.to_pydatetime())
        widths = df["duration_plot"].to_numpy(float)
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    else:
        starts = df["start_plot"].to_numpy(float)
        widths = df["duration_plot"].to_numpy(float)
    for i, (_, row) in enumerate(df.iterrows()):
        color = colors.get(str(row[resource_col]), MIRA_COLORS["blue"]) if resource_col else MIRA_PALETTE[i % len(MIRA_PALETTE)]
        if milestone_col and bool(row.get(milestone_col, False)):
            ax.scatter(starts[i], y[i], marker="D", s=46, color=color, edgecolors="white", linewidths=0.6, zorder=4)
        else:
            ax.barh(y[i], widths[i], left=starts[i], height=0.62, color=color, alpha=0.86, edgecolor="white", linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(df[task_col])
    ax.invert_yaxis()
    ax.set_xlabel("时间")
    ax.grid(False)
    if resource_col:
        handles = [plt.Line2D([0], [0], color=color, lw=6, label=label) for label, color in colors.items()]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    if args.title:
        ax.set_title(args.title)
    fig.autofmt_xdate(rotation=25 if is_datetime else 0)
    return fig


def parse_datetime_series(series: pd.Series, fmt: str) -> pd.Series:
    if fmt:
        return pd.to_datetime(series, format=fmt, errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def gantt_summary(df: pd.DataFrame, resource_col: str) -> pd.DataFrame:
    rows = [
        {"metric": "task_count", "value": int(len(df))},
        {"metric": "total_duration", "value": float(df["duration_plot"].sum())},
        {"metric": "makespan", "value": float((df["end_plot"].max() - df["start_plot"].min()).days if hasattr(df["end_plot"].max() - df["start_plot"].min(), "days") else df["end_plot"].max() - df["start_plot"].min())},
    ]
    if resource_col and resource_col in df.columns:
        for label, part in df.groupby(resource_col, observed=False):
            rows.append({"metric": f"duration_{label}", "value": float(part["duration_plot"].sum())})
    return pd.DataFrame(rows)


def load_table_or_demo(args: argparse.Namespace, root: Path, demo_fn: Any) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return demo_fn(), f"demo:{args.kind}"
    if not args.input:
        raise SystemExit(f"ERROR: provide --input <csv/xlsx> or --demo for {args.kind}.")
    path = resolve_path(root, args.input)
    if not path.exists():
        raise SystemExit(f"ERROR: input file does not exist: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheet: str | int = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        return pd.read_excel(path, sheet_name=sheet), str(path)
    if path.suffix.lower() in {".csv", ".txt"}:
        return read_csv_with_fallback(path), str(path)
    raise SystemExit("ERROR: supported input formats are CSV, TXT, XLSX, and XLS.")


def demo_parallel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "方案": ["A", "B", "C", "D", "E", "F"],
            "类型": ["精度型", "均衡型", "成本型", "精度型", "均衡型", "成本型"],
            "成本": [82, 74, 61, 95, 70, 58],
            "时间": [44, 38, 53, 40, 35, 60],
            "准确性": [0.88, 0.82, 0.74, 0.93, 0.84, 0.70],
            "稳定性": [0.81, 0.86, 0.72, 0.79, 0.88, 0.76],
            "鲁棒性": [0.83, 0.80, 0.77, 0.90, 0.84, 0.71],
        }
    )


def demo_pareto() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 42
    cost = rng.uniform(35, 105, n)
    quality = 0.55 + 0.38 * (1 - np.exp(-(cost - 30) / 42)) + rng.normal(0, 0.035, n)
    time = 70 - 0.22 * cost + rng.normal(0, 4, n)
    return pd.DataFrame({"方案": [f"S{i+1}" for i in range(n)], "成本": cost, "质量收益": quality, "完成时间": time, "类型": rng.choice(["A类", "B类", "C类"], n)})


def demo_gantt() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "任务": ["数据整理", "参数估计", "模型求解", "稳健性检验", "图表生成", "论文撰写", "格式检查", "提交材料"],
            "开始": ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-05", "2026-07-06", "2026-07-07", "2026-07-09", "2026-07-10"],
            "结束": ["2026-07-02", "2026-07-04", "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-10", "2026-07-10", "2026-07-10"],
            "阶段": ["准备", "建模", "建模", "验证", "写作", "写作", "交付", "交付"],
            "里程碑": [False, False, False, False, False, False, False, True],
        }
    )


def prepare_outputs(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_prefix(args.prefix or args.kind)
    return {
        "figures_dir": figures_dir,
        "data_dir": data_dir,
        "plot_data": data_dir / f"{prefix}_{args.kind}_plot_data.csv",
        "summary": data_dir / f"{prefix}_{args.kind}_summary.csv",
        "params": data_dir / f"{prefix}_{args.kind}_params.json",
        "index": figures_dir / f"{prefix}_{args.kind}_index.md",
        "prefix": prefix,
    }


def save_kind_figures(fig: Any, outputs: dict[str, Any], args: argparse.Namespace, suffix: str) -> list[str]:
    png = outputs["figures_dir"] / f"{outputs['prefix']}_{suffix}.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_{suffix}.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)
    return [str(png), str(pdf)]


def write_index(outputs: dict[str, Any], title: str, written: list[str], caption: str, interpretation: str, caveats: list[str], source: str, row_count: int) -> None:
    lines = [
        f"# {title}",
        "",
        f"- Source: `{source}`",
        f"- Plot data: `{outputs['plot_data']}`",
        f"- Summary: `{outputs['summary']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Record count: {row_count}",
        "",
        "## Figures",
        "",
    ]
    for path in written:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Caption Draft", "", caption, "", "## Nearby Interpretation Draft", "", interpretation, "", "## Caveat", ""])
    for caveat in caveats:
        lines.append(f"- {caveat}")
    lines.append("")
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def parallel_caption(metrics: list[str], args: argparse.Namespace) -> str:
    return f"图：平行坐标图展示 {len(metrics)} 个指标下不同方案的相对表现，低成本或低时间类指标已按方向要求进行同向化处理。"


def parallel_interpretation() -> str:
    return "平行坐标图用于筛选多指标下表现稳定或存在明显短板的方案；最终排序仍需结合权重、约束和综合评分表。"


def parallel_caveats() -> list[str]:
    return [
        "不同量纲指标应归一化，并记录低值优先指标的方向变换。",
        "线条过多会降低可读性，应先筛选候选方案或按类别分面。",
        "平行坐标图显示模式，不等价于严格最优性证明。",
    ]


def pareto_caption(x_col: str, y_col: str, args: argparse.Namespace) -> str:
    return f"图：以 `{x_col}` 与 `{y_col}` 为双目标的 Pareto 前沿，突出不可被同时改进的候选方案。"


def pareto_interpretation() -> str:
    return "Pareto 前沿用于解释多目标权衡：前沿方案不能在所有目标上被另一个方案同时改进，最终选择应结合偏好权重、约束和管理可执行性。"


def pareto_caveats() -> list[str]:
    return [
        "必须明确每个目标是最小化还是最大化。",
        "Pareto 前沿不是唯一推荐方案，只给出不可支配候选集合。",
        "若有三目标以上，应补充表格、平行坐标或分层筛选规则。",
    ]


def gantt_caption(args: argparse.Namespace) -> str:
    return "图：甘特图展示任务、阶段和时间窗口之间的执行关系，用于说明方案落地过程和关键节点。"


def gantt_interpretation() -> str:
    return "甘特图用于把数学结果转化为可执行计划，重点解释任务先后关系、资源分工和里程碑，而不是代替约束或调度模型。"


def gantt_caveats() -> list[str]:
    return [
        "甘特图中的任务时间必须来自模型结果、工程假设或明确人工安排。",
        "若存在资源冲突或前后依赖，应在正文中配合约束表或流程图说明。",
        "不要把甘特图作为求解证明；它是执行层表达。",
    ]


def print_written(kind: str, outputs: dict[str, Any], written: list[str]) -> None:
    print(f"INFO: {kind} figures written:")
    for path in written:
        print(f"  figure: {path}")
    print(f"  plot_data: {outputs['plot_data']}")
    print(f"  summary: {outputs['summary']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")


def color_groups(df: pd.DataFrame, group_col: str) -> dict[str, Any]:
    if not group_col or group_col not in df.columns:
        return {"colors": {}}
    labels = sorted(df[group_col].astype(str).unique(), key=natural_key)
    return {"colors": {label: MIRA_PALETTE[i % len(MIRA_PALETTE)] for i, label in enumerate(labels)}}


def resource_colors(df: pd.DataFrame, resource_col: str) -> dict[str, str]:
    if not resource_col or resource_col not in df.columns:
        return {}
    labels = sorted(df[resource_col].astype(str).unique(), key=natural_key)
    return {label: MIRA_PALETTE[i % len(MIRA_PALETTE)] for i, label in enumerate(labels)}


def first_text_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            return str(col)
    return ""


def parse_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，]", value or "") if part.strip()]


def infer_column(df: pd.DataFrame, names: list[str]) -> str:
    lowered = {str(col).lower(): str(col) for col in df.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    for col in df.columns:
        if any(name.lower() in str(col).lower() for name in names):
            return str(col)
    return ""


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


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "figure"


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
