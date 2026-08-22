#!/usr/bin/env python3
"""Generate radar, Taylor, and 3D surface figures for Mira papers."""

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
    outputs = prepare_outputs(args, root)
    if args.kind == "radar":
        write_radar(args, root, outputs)
    elif args.kind == "taylor":
        write_taylor(args, root, outputs)
    elif args.kind == "surface":
        write_surface(args, root, outputs)
    else:
        raise SystemExit(f"ERROR: unsupported kind: {args.kind}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--kind", choices=("radar", "taylor", "surface"), required=True, help="Figure type.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", action="store_true", help="Use built-in demo data for the chosen kind.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Plot-data output directory.")
    parser.add_argument("--prefix", default="", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")

    # Radar.
    parser.add_argument("--item-col", default="", help="Radar series/item column.")
    parser.add_argument("--metrics", default="", help="Comma-separated radar metric columns.")
    parser.add_argument("--normalize", choices=("none", "minmax", "max", "zscore"), default="none", help="Radar metric normalization.")
    parser.add_argument("--max-items", type=int, default=6, help="Maximum radar series before raising an error.")
    parser.add_argument("--fill-alpha", type=float, default=0.12, help="Radar polygon fill alpha.")

    # Taylor.
    parser.add_argument("--obs", default="", help="Observation column for Taylor diagram.")
    parser.add_argument("--pred-cols", default="", help="Comma-separated model prediction columns.")
    parser.add_argument("--model-col", default="", help="Optional model column for precomputed Taylor stats.")
    parser.add_argument("--corr-col", default="", help="Optional correlation column for precomputed Taylor stats.")
    parser.add_argument("--std-col", default="", help="Optional standard deviation column for precomputed Taylor stats.")
    parser.add_argument("--rmse-col", default="", help="Optional centered RMSE column for precomputed Taylor stats.")
    parser.add_argument("--normalize-std", action="store_true", help="Normalize Taylor standard deviations by observed std.")

    # Surface.
    parser.add_argument("--x", default="", help="Surface x column.")
    parser.add_argument("--y", default="", help="Surface y column.")
    parser.add_argument("--z", default="", help="Surface z/response column.")
    parser.add_argument("--grid-size", type=int, default=80, help="Interpolation grid size for scattered surface data.")
    parser.add_argument("--surface-mode", choices=("surface", "wireframe", "surface-contour"), default="surface-contour", help="Surface rendering mode.")
    parser.add_argument("--cmap", default="viridis", help="Matplotlib colormap for surface/Taylor contours.")
    parser.add_argument("--elev", type=float, default=28.0, help="3D camera elevation.")
    parser.add_argument("--azim", type=float, default=-48.0, help="3D camera azimuth.")
    parser.add_argument("--contour", action="store_true", help="Also write 2D contour companion for surface.")
    return parser.parse_args()


def write_radar(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_radar)
    item_col = args.item_col or first_text_col(df) or str(df.columns[0])
    metrics = parse_list(args.metrics) or [col for col in df.columns if col != item_col and pd.api.types.is_numeric_dtype(df[col])]
    if not metrics:
        raise SystemExit("ERROR: radar needs metric columns; pass --metrics or provide numeric columns.")
    missing = [col for col in [item_col] + metrics if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing radar columns: " + ", ".join(missing))
    work = df[[item_col] + metrics].copy()
    for col in metrics:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    before = len(work)
    work = work.dropna(subset=metrics).copy()
    if work.empty:
        raise SystemExit("ERROR: radar has no complete metric rows.")
    if len(work) > args.max_items:
        raise SystemExit(f"ERROR: radar has {len(work)} series; reduce to <= {args.max_items} or use a table/bar chart.")
    norm = normalize_metrics(work, metrics, args.normalize)
    norm.insert(0, item_col, work[item_col].astype(str).to_list())
    stats = pd.DataFrame(
        {
            "metric": metrics,
            "raw_min": [float(work[col].min()) for col in metrics],
            "raw_max": [float(work[col].max()) for col in metrics],
            "raw_mean": [float(work[col].mean()) for col in metrics],
            "normalization": args.normalize,
        }
    )
    norm.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    stats.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    fig = plot_radar(norm, item_col, metrics, args)
    written = save_kind_figures(fig, outputs, args, "radar")
    params = {
        "kind": "radar",
        "source": source,
        "item_col": item_col,
        "metrics": metrics,
        "normalization": args.normalize,
        "n_input_rows": before,
        "n_plot_rows": len(norm),
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "Radar Figure Index", written, radar_caption(item_col, metrics, args), radar_interpretation(args), radar_caveats(), source, len(norm))
    print_written("radar", outputs, written)


def plot_radar(df: pd.DataFrame, item_col: str, metrics: list[str], args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    n = len(metrics)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    angles_closed = np.concatenate([angles, [angles[0]]])
    fig = plt.figure(figsize=(5.8, 5.2))
    ax = fig.add_subplot(111, polar=True)
    for idx, (_, row) in enumerate(df.iterrows()):
        values = row[metrics].to_numpy(dtype=float)
        values_closed = np.concatenate([values, [values[0]]])
        color = MIRA_PALETTE[idx % len(MIRA_PALETTE)]
        ax.plot(angles_closed, values_closed, color=color, linewidth=1.8, label=str(row[item_col]))
        ax.fill(angles_closed, values_closed, color=color, alpha=args.fill_alpha)
    ax.set_xticks(angles)
    ax.set_xticklabels(metrics)
    ax.set_ylim(*radar_ylim(df[metrics].to_numpy(dtype=float), args.normalize))
    ax.set_rlabel_position(90)
    ax.grid(True, alpha=0.12, linewidth=0.45)  # structural grid: radar axes, not a chart backdrop
    if args.title:
        ax.set_title(args.title, pad=18)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.05), frameon=False)
    return fig


def radar_ylim(values: np.ndarray, normalize: str) -> tuple[float, float]:
    if normalize in {"minmax", "max"}:
        return 0.0, 1.0
    lo = float(np.nanmin(values))
    hi = float(np.nanmax(values))
    pad = max((hi - lo) * 0.08, 0.05)
    if lo >= 0:
        return 0.0, hi + pad
    return lo - pad, hi + pad


def normalize_metrics(df: pd.DataFrame, metrics: list[str], method: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col in metrics:
        values = df[col].astype(float)
        if method == "minmax":
            span = values.max() - values.min()
            out[col] = 0.5 if abs(span) < 1e-12 else (values - values.min()) / span
        elif method == "max":
            max_abs = values.abs().max()
            out[col] = values if max_abs < 1e-12 else values / max_abs
        elif method == "zscore":
            std = values.std(ddof=1)
            out[col] = 0.0 if abs(std) < 1e-12 else (values - values.mean()) / std
        else:
            out[col] = values
    return out


def write_taylor(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_taylor)
    if args.model_col and args.corr_col and args.std_col:
        stats = build_taylor_from_stats(df, args)
        ref_std = 1.0 if args.normalize_std else float(stats["ref_std"].dropna().iloc[0] if "ref_std" in stats else 1.0)
    else:
        stats, ref_std = build_taylor_from_raw(df, args)
    if args.normalize_std:
        stats["std_plot"] = stats["std"] / max(ref_std, 1e-12)
        stats["rmse_plot"] = stats["centered_rmse"] / max(ref_std, 1e-12)
        ref_plot = 1.0
    else:
        stats["std_plot"] = stats["std"]
        stats["rmse_plot"] = stats["centered_rmse"]
        ref_plot = ref_std
    stats.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    stats.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    fig = plot_taylor(stats, ref_plot, args)
    written = save_kind_figures(fig, outputs, args, "taylor")
    params = {
        "kind": "taylor",
        "source": source,
        "obs": args.obs,
        "pred_cols": parse_list(args.pred_cols),
        "normalize_std": args.normalize_std,
        "reference_std": ref_std,
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "Taylor Diagram Index", written, taylor_caption(args), taylor_interpretation(args), taylor_caveats(), source, len(stats))
    print_written("taylor", outputs, written)


def build_taylor_from_raw(df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, float]:
    obs = args.obs or first_numeric_col(df)
    pred_cols = parse_list(args.pred_cols) or [col for col in df.columns if col != obs and pd.api.types.is_numeric_dtype(df[col])]
    if not obs or not pred_cols:
        raise SystemExit("ERROR: Taylor diagram needs --obs and --pred-cols, or numeric observation/model columns.")
    missing = [col for col in [obs] + pred_cols if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing Taylor columns: " + ", ".join(missing))
    work = df[[obs] + pred_cols].copy()
    for col in [obs] + pred_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    ref = work[obs].dropna()
    ref_std = float(ref.std(ddof=1))
    if not np.isfinite(ref_std) or ref_std <= 1e-12:
        raise SystemExit("ERROR: observation standard deviation is zero or invalid.")
    rows: list[dict[str, Any]] = []
    for col in pred_cols:
        pair = work[[obs, col]].dropna()
        if len(pair) < 3:
            continue
        obs_values = pair[obs].to_numpy(float)
        pred = pair[col].to_numpy(float)
        corr = float(np.corrcoef(obs_values, pred)[0, 1])
        std = float(np.std(pred, ddof=1))
        centered_rmse = float(np.sqrt(np.mean(((pred - pred.mean()) - (obs_values - obs_values.mean())) ** 2)))
        rows.append({"model": col, "corr": corr, "std": std, "centered_rmse": centered_rmse, "sample_size": len(pair)})
    if not rows:
        raise SystemExit("ERROR: no valid Taylor model pairs.")
    args.obs = obs
    args.pred_cols = ",".join(pred_cols)
    return pd.DataFrame(rows), ref_std


def build_taylor_from_stats(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    cols = [args.model_col, args.corr_col, args.std_col] + ([args.rmse_col] if args.rmse_col else [])
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise SystemExit("ERROR: missing precomputed Taylor columns: " + ", ".join(missing))
    stats = pd.DataFrame(
        {
            "model": df[args.model_col].astype(str),
            "corr": pd.to_numeric(df[args.corr_col], errors="coerce"),
            "std": pd.to_numeric(df[args.std_col], errors="coerce"),
            "centered_rmse": pd.to_numeric(df[args.rmse_col], errors="coerce") if args.rmse_col else np.nan,
            "sample_size": np.nan,
        }
    ).dropna(subset=["corr", "std"])
    if stats.empty:
        raise SystemExit("ERROR: no valid precomputed Taylor stats.")
    return stats


def plot_taylor(stats: pd.DataFrame, ref_std: float, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    corr_values = np.clip(stats["corr"].to_numpy(float), 0.0, 1.0)
    theta = np.arccos(corr_values)
    radius = stats["std_plot"].to_numpy(float)
    max_radius = max(float(np.nanmax(radius)) * 1.20, ref_std * 1.35, 1e-6)
    fig = plt.figure(figsize=(6.3, 5.0))
    ax = fig.add_subplot(111, polar=True)
    ax.set_thetamin(0)
    ax.set_thetamax(90)
    ax.set_ylim(0, max_radius)
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)

    corr_ticks = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99, 1.0])
    ax.set_xticks(np.arccos(corr_ticks))
    ax.set_xticklabels([f"{v:.2g}" for v in corr_ticks])
    ax.set_ylabel("标准差" + ("（归一化）" if args.normalize_std else ""), labelpad=18)
    ax.text(0.50, 1.06, "弧线刻度：相关系数", transform=ax.transAxes, ha="center", va="bottom", fontsize=9, color=MIRA_COLORS["gray"])
    draw_taylor_rmse_contours(ax, ref_std, max_radius)
    ax.plot([0], [ref_std], marker="*", markersize=12, color=MIRA_COLORS["red"], label="观测参考")
    for idx, row in stats.iterrows():
        color = MIRA_PALETTE[idx % len(MIRA_PALETTE)]
        ax.scatter([math.acos(float(np.clip(row["corr"], 0.0, 1.0)))], [float(row["std_plot"])], s=48, color=color, edgecolors="white", linewidths=0.6, label=str(row["model"]), zorder=4)
    if args.title:
        ax.set_title(args.title, pad=18)
    ax.legend(loc="upper left", bbox_to_anchor=(1.05, 1.05), frameon=False)
    return fig


def draw_taylor_rmse_contours(ax: Any, ref_std: float, max_radius: float) -> None:
    theta = np.linspace(0, np.pi / 2, 181)
    radius = np.linspace(0, max_radius, 181)
    tt, rr = np.meshgrid(theta, radius)
    rmse = np.sqrt(np.maximum(ref_std**2 + rr**2 - 2 * ref_std * rr * np.cos(tt), 0.0))
    levels = np.linspace(max_radius / 5, max_radius, 5)
    cs = ax.contour(tt, rr, rmse, levels=levels, colors="#9AA3AF", linewidths=0.65, linestyles="dashed", alpha=0.75)
    ax.clabel(cs, inline=True, fontsize=7, fmt="%.2g")


def write_surface(args: argparse.Namespace, root: Path, outputs: dict[str, Any]) -> None:
    df, source = load_table_or_demo(args, root, demo_surface)
    x_col, y_col, z_col = infer_surface_columns(df, args)
    work = df[[x_col, y_col, z_col]].copy()
    for col in [x_col, y_col, z_col]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna().copy()
    if len(work) < 9:
        raise SystemExit("ERROR: 3D surface needs at least 9 complete x/y/z rows.")
    grid_df, x_grid, y_grid, z_grid = build_surface_grid(work, x_col, y_col, z_col, args)
    grid_df.to_csv(outputs["plot_data"], index=False, encoding="utf-8-sig")
    summary = surface_summary(work, x_col, y_col, z_col)
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8-sig")

    fig = plot_surface(x_grid, y_grid, z_grid, x_col, y_col, z_col, args)
    written = save_kind_figures(fig, outputs, args, "surface")
    if args.contour or args.surface_mode == "surface-contour":
        written.extend(save_contour_companion(x_grid, y_grid, z_grid, x_col, y_col, z_col, outputs, args))
    params = {
        "kind": "surface",
        "source": source,
        "x": x_col,
        "y": y_col,
        "z": z_col,
        "grid_size": args.grid_size,
        "surface_mode": args.surface_mode,
        "view": {"elev": args.elev, "azim": args.azim},
        "written_figures": written,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(outputs, "3D Surface Figure Index", written, surface_caption(x_col, y_col, z_col, args), surface_interpretation(args), surface_caveats(), source, len(grid_df))
    print_written("surface", outputs, written)


def infer_surface_columns(df: pd.DataFrame, args: argparse.Namespace) -> tuple[str, str, str]:
    if args.x and args.y and args.z:
        return args.x, args.y, args.z
    numeric = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if len(numeric) < 3:
        raise SystemExit("ERROR: pass --x --y --z, or provide at least three numeric columns.")
    return args.x or numeric[0], args.y or numeric[1], args.z or numeric[2]


def build_surface_grid(df: pd.DataFrame, x_col: str, y_col: str, z_col: str, args: argparse.Namespace) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    x_unique = np.sort(df[x_col].unique())
    y_unique = np.sort(df[y_col].unique())
    complete_grid = len(x_unique) * len(y_unique) == len(df.drop_duplicates([x_col, y_col]))
    if complete_grid and len(x_unique) >= 2 and len(y_unique) >= 2:
        pivot = df.pivot_table(index=y_col, columns=x_col, values=z_col, aggfunc="mean").sort_index().sort_index(axis=1)
        x_grid, y_grid = np.meshgrid(pivot.columns.to_numpy(float), pivot.index.to_numpy(float))
        z_grid = pivot.to_numpy(float)
    else:
        from scipy.interpolate import griddata

        xi = np.linspace(float(df[x_col].min()), float(df[x_col].max()), args.grid_size)
        yi = np.linspace(float(df[y_col].min()), float(df[y_col].max()), args.grid_size)
        x_grid, y_grid = np.meshgrid(xi, yi)
        points = df[[x_col, y_col]].to_numpy(float)
        values = df[z_col].to_numpy(float)
        z_grid = griddata(points, values, (x_grid, y_grid), method="cubic")
        if np.isnan(z_grid).any():
            nearest = griddata(points, values, (x_grid, y_grid), method="nearest")
            z_grid = np.where(np.isnan(z_grid), nearest, z_grid)
    grid_df = pd.DataFrame({"x": x_grid.ravel(), "y": y_grid.ravel(), "z": z_grid.ravel()})
    return grid_df, x_grid, y_grid, z_grid


def plot_surface(x_grid: np.ndarray, y_grid: np.ndarray, z_grid: np.ndarray, x_col: str, y_col: str, z_col: str, args: argparse.Namespace) -> Any:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig = plt.figure(figsize=(6.8, 5.2))
    ax = fig.add_subplot(111, projection="3d")
    if args.surface_mode == "wireframe":
        ax.plot_wireframe(x_grid, y_grid, z_grid, rstride=3, cstride=3, color=MIRA_COLORS["blue"], linewidth=0.7, alpha=0.85)
    else:
        surf = ax.plot_surface(x_grid, y_grid, z_grid, cmap=args.cmap, linewidth=0, antialiased=True, alpha=0.92)
        cbar = fig.colorbar(surf, ax=ax, shrink=0.66, pad=0.14)
        cbar.ax.set_title(z_col, pad=8)
        if args.surface_mode == "surface-contour":
            ax.contour(x_grid, y_grid, z_grid, zdir="z", offset=float(np.nanmin(z_grid)), cmap=args.cmap, linewidths=0.7, alpha=0.85)
    z_axis_label = z_col if args.surface_mode == "wireframe" else ""
    apply_3d_style(ax, xlabel=x_col, ylabel=y_col, zlabel=z_axis_label, elev=args.elev, azim=args.azim)
    soften_3d_panes(ax)
    try:
        ax.set_box_aspect((np.ptp(x_grid), np.ptp(y_grid), np.ptp(z_grid)))
    except Exception:
        pass
    if args.title:
        ax.set_title(args.title, pad=14)
    return fig


def save_contour_companion(x_grid: np.ndarray, y_grid: np.ndarray, z_grid: np.ndarray, x_col: str, y_col: str, z_col: str, outputs: dict[str, Any], args: argparse.Namespace) -> list[str]:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=10)
    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    cf = ax.contourf(x_grid, y_grid, z_grid, levels=18, cmap=args.cmap)
    cs = ax.contour(x_grid, y_grid, z_grid, levels=9, colors="white", linewidths=0.45, alpha=0.65)
    ax.clabel(cs, inline=True, fontsize=7, fmt="%.2g")
    cbar = fig.colorbar(cf, ax=ax)
    cbar.ax.set_title(z_col, pad=8)
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title((args.title + "二维等值线") if args.title else "二维等值线投影")
    png = outputs["figures_dir"] / f"{outputs['prefix']}_surface_contour.png"
    pdf = outputs["figures_dir"] / f"{outputs['prefix']}_surface_contour.pdf"
    save_mira_figure(fig, png, dpi=args.dpi)
    save_mira_figure(fig, pdf, dpi=args.dpi)
    close_figure(fig)
    return [str(png), str(pdf)]


def soften_3d_panes(ax: Any) -> None:
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.set_facecolor((0.97, 0.98, 1.0, 0.35))
        pane.set_edgecolor((0.82, 0.84, 0.88, 0.65))


def surface_summary(df: pd.DataFrame, x_col: str, y_col: str, z_col: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"field": x_col, "min": float(df[x_col].min()), "max": float(df[x_col].max()), "mean": float(df[x_col].mean()), "std": float(df[x_col].std(ddof=1))},
            {"field": y_col, "min": float(df[y_col].min()), "max": float(df[y_col].max()), "mean": float(df[y_col].mean()), "std": float(df[y_col].std(ddof=1))},
            {"field": z_col, "min": float(df[z_col].min()), "max": float(df[z_col].max()), "mean": float(df[z_col].mean()), "std": float(df[z_col].std(ddof=1))},
        ]
    )


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


def demo_radar() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "方案": ["方案A", "方案B", "方案C", "方案D"],
            "准确性": [0.86, 0.78, 0.91, 0.83],
            "稳定性": [0.74, 0.88, 0.80, 0.84],
            "效率": [0.82, 0.90, 0.68, 0.79],
            "成本优势": [0.70, 0.76, 0.64, 0.91],
            "鲁棒性": [0.81, 0.72, 0.87, 0.78],
        }
    )


def demo_taylor() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    x = np.linspace(0, 8, 120)
    obs = np.sin(x) + 0.12 * x + rng.normal(0, 0.08, len(x))
    return pd.DataFrame(
        {
            "观测值": obs,
            "模型A": obs * 0.96 + rng.normal(0, 0.12, len(x)),
            "模型B": np.sin(x + 0.18) + 0.11 * x + rng.normal(0, 0.16, len(x)),
            "模型C": obs * 1.12 + rng.normal(0, 0.20, len(x)),
            "模型D": 0.85 * np.sin(x) + 0.15 * x + rng.normal(0, 0.18, len(x)),
        }
    )


def demo_surface() -> pd.DataFrame:
    x = np.linspace(-3.0, 3.0, 45)
    y = np.linspace(-2.5, 2.5, 42)
    xx, yy = np.meshgrid(x, y)
    zz = np.sin(xx) * np.cos(yy) + 0.16 * xx**2 - 0.08 * yy
    return pd.DataFrame({"参数x": xx.ravel(), "参数y": yy.ravel(), "响应z": zz.ravel()})


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


def radar_caption(item_col: str, metrics: list[str], args: argparse.Namespace) -> str:
    norm = "，各指标已归一化" if args.normalize != "none" else ""
    return f"图：基于 `{item_col}` 的多指标雷达图{norm}，比较 {len(metrics)} 个评价维度下不同方案的综合表现。"


def radar_interpretation(args: argparse.Namespace) -> str:
    return "雷达图用于快速识别方案的长板和短板；若需要给出最终排序，应在正文中配合权重、综合得分表或敏感性分析，而不是只根据图形面积判断优劣。"


def radar_caveats() -> list[str]:
    return [
        "不同量纲指标必须先说明归一化或同向化方法。",
        "雷达图适合少量方案和少量指标；方案过多时改用表格、热力图或分组柱状图。",
        "不要把多边形面积直接当成严格综合得分，除非正文给出对应公式。",
    ]


def taylor_caption(args: argparse.Namespace) -> str:
    scale = "归一化标准差" if args.normalize_std else "标准差"
    return f"图：泰勒图同时比较各模型的相关系数、{scale}和中心化均方根误差，用于检验预测或仿真结果与观测值的一致性。"


def taylor_interpretation(args: argparse.Namespace) -> str:
    return "泰勒图中越靠近观测参考点的模型，通常同时具有更高相关性、更接近的波动幅度和更小的中心化误差；最终模型选择仍应结合偏差、业务约束和独立测试误差。"


def taylor_caveats() -> list[str]:
    return [
        "泰勒图只表达相关系数、标准差和中心化 RMSE，不能替代 MAE、偏差或极值误差分析。",
        "样本必须一一配对，缺失值处理和样本量需要记录。",
        "相关性高不等于预测无偏；必要时补充残差图和误差统计表。",
    ]


def surface_caption(x_col: str, y_col: str, z_col: str, args: argparse.Namespace) -> str:
    return f"图：`{z_col}` 随 `{x_col}` 与 `{y_col}` 变化的三维响应曲面，用于展示双参数耦合关系和局部峰谷结构。"


def surface_interpretation(args: argparse.Namespace) -> str:
    return "三维曲面图用于观察连续响应面、参数耦合和局部极值；若结论涉及最优点、阈值或边界，应在正文中给出二维等值线、局部放大或数值优化结果。"


def surface_caveats() -> list[str]:
    return [
        "三维视角可能遮挡局部细节；关键比较要配合二维等值线或表格。",
        "若原始数据不是规则网格，插值得到的曲面只能作为可视化近似，不能替代真实求解。",
        "不要用曲面图展示离散方案矩阵；离散矩阵更适合热力图、表格或 3D 柱状图。",
    ]


def print_written(kind: str, outputs: dict[str, Any], written: list[str]) -> None:
    print(f"INFO: {kind} figures written:")
    for path in written:
        print(f"  figure: {path}")
    print(f"  plot_data: {outputs['plot_data']}")
    print(f"  summary: {outputs['summary']}")
    print(f"  params: {outputs['params']}")
    print(f"  index: {outputs['index']}")


def first_text_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            return str(col)
    return ""


def first_numeric_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            return str(col)
    return ""


def parse_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，]", value or "") if part.strip()]


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


def close_figure(fig: Any) -> None:
    import matplotlib.pyplot as plt

    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
