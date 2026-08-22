#!/usr/bin/env python3
"""Generate a claim-oriented Python figure with a justified local inset."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from figure_provenance import write_figure_provenance
from visual_backend_router import route_visual
from visual_style import (JOURNAL_COLORS, annotate_key_point, apply_mira_style,
                          mira_figure_size, save_mira_figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--data", help="CSV matching the selected visual kind.")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--visual-kind", choices=("trajectory", "distribution"), default="trajectory")
    parser.add_argument("--request-json", default="", help="Structured request consumed by route_visual(request).")
    parser.add_argument("--prefix", default="core_evidence")
    parser.add_argument("--claim-id", default="UNBOUND")
    parser.add_argument("--title", default="")
    parser.add_argument("--claim", default="模型能够跟踪主要趋势，并在决策边界附近保持稳定。")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260714)
    parser.add_argument("--estimator", choices=("mean",), default="mean")
    parser.add_argument("--errorbar-level", type=int, default=95)
    return parser.parse_args()


def main() -> int:
    args = parse_args(); root = Path(args.root).resolve()
    route = resolve_route(root, args)
    if route.get("status") != "READY":
        print(json.dumps(route, ensure_ascii=False, indent=2))
        return 2
    if route.get("backend") != "python":
        print("ERROR: plot_claim_figure.py only implements the Python adapter; use run_matlab_visual.py for MATLAB routes.")
        return 2
    data = load_data(root, args)
    figures = root / "figures"; evidence = root / "results" / "figures_data"
    figures.mkdir(parents=True, exist_ok=True); evidence.mkdir(parents=True, exist_ok=True)
    csv_path = evidence / f"{args.prefix}.csv"; data.to_csv(csv_path, index=False, encoding="utf-8-sig")
    source_path = preserve_source(root, args.prefix)
    summary = plot(data, figures, args, route)
    backend = f"python/{route['library']}"
    summary.update({"claim_id": args.claim_id, "figure": f"figures/{args.prefix}.pdf", "source_data": f"results/figures_data/{args.prefix}.csv", "supported_claim": args.claim, "backend": backend})
    summary_path = evidence / f"{args.prefix}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path = write_render_log(root, args, summary, route)
    png_path = figures / f"{args.prefix}.png"
    pdf_path = figures / f"{args.prefix}.pdf"
    provenance_path, provenance = write_figure_provenance(
        root,
        figure_id=f"fig_{args.prefix}",
        claim_id=args.claim_id,
        route={**route, "route_mode": "structured_confirmed"},
        source_code=source_path,
        input_data=csv_path,
        png=png_path,
        pdf=pdf_path,
        statistics=summary["statistics"],
        transformations=summary["transformations"],
        dpi=args.dpi,
        seed=args.seed,
        warnings=summary.get("warnings", []),
    )
    update_index(root, args, summary, route)
    update_evidence_manifest(root, args, summary, source_path, log_path, route, provenance_path, provenance)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def resolve_route(root: Path, args: argparse.Namespace) -> dict:
    if args.request_json:
        path = Path(args.request_json)
        path = path if path.is_absolute() else root / path
        try:
            request = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"ERROR: invalid visual request: {exc}")
        if not isinstance(request, dict):
            raise SystemExit("ERROR: visual request must be a JSON object")
    else:
        request = {
            "data_shape": "tidy_long_table" if args.visual_kind == "distribution" else "precomputed_array",
            "statistical_goal": "compare grouped distributions" if args.visual_kind == "distribution" else "local inset paper layout",
            "evidence_role": "uncertainty" if args.visual_kind == "distribution" else "validation",
            "upstream_runtime": "python",
            "provenance_present": True,
            "units_present": True,
            "statistics_explicit": True,
            "offline_reproducible": True,
            "static_evidence_available": True,
            "interaction_required": False,
            "output_contract": ["png_300dpi", "vector_pdf"],
        }
    return route_visual(request)


def load_data(root: Path, args: argparse.Namespace) -> pd.DataFrame:
    if args.data:
        path = Path(args.data); path = path if path.is_absolute() else root / path
        df = pd.read_csv(path)
        required = {"group", "value"} if args.visual_kind == "distribution" else {"x", "observed", "predicted"}
        missing = required - set(df.columns)
        if missing:
            raise SystemExit("ERROR: missing columns: " + ", ".join(sorted(missing)))
        if args.visual_kind == "trajectory":
            if "lower" not in df: df["lower"] = df["predicted"]
            if "upper" not in df: df["upper"] = df["predicted"]
        return df
    if not args.demo:
        raise SystemExit("ERROR: provide --data or --demo")
    rng = np.random.default_rng(args.seed)
    if args.visual_kind == "distribution":
        groups = ("方案 A", "方案 B", "方案 C")
        centers = (5.2, 5.8, 6.1)
        rows = [
            {"group": group, "value": float(rng.normal(center, 0.42)), "unit": "m"}
            for group, center in zip(groups, centers)
            for _ in range(36)
        ]
        return pd.DataFrame(rows)
    x = np.linspace(0, 12, 96)
    truth = 2.2 + 0.32*x + 1.25*np.sin(x/1.7)
    observed = truth + rng.normal(0, 0.28, len(x))
    predicted = 2.15 + 0.33*x + 1.18*np.sin((x+0.08)/1.72)
    width = 0.40 + 0.025*x
    return pd.DataFrame({"x": x, "observed": observed, "predicted": predicted, "lower": predicted-width, "upper": predicted+width})


def plot(df: pd.DataFrame, figures: Path, args: argparse.Namespace, route: dict) -> dict:
    if route.get("library") == "seaborn":
        if args.visual_kind != "distribution":
            raise SystemExit("ERROR: the Seaborn adapter currently requires --visual-kind distribution")
        return plot_distribution(df, figures, args)
    return plot_trajectory(df, figures, args)


def plot_trajectory(df: pd.DataFrame, figures: Path, args: argparse.Namespace) -> dict:
    import matplotlib.pyplot as plt
    apply_mira_style(10)
    fig, ax = plt.subplots(figsize=mira_figure_size("wide"))
    x = df["x"].to_numpy(); obs = df["observed"].to_numpy(); pred = df["predicted"].to_numpy()
    residual = obs - pred; rmse = float(np.sqrt(np.mean(residual**2))); mae = float(np.mean(np.abs(residual)))

    ax.plot(x, obs, color=JOURNAL_COLORS["muted"], lw=1.1, label="观测值")
    ax.plot(x, pred, color=JOURNAL_COLORS["blue"], lw=2.0, label="预测值")
    ax.fill_between(x, df["lower"], df["upper"], color=JOURNAL_COLORS["blue"], alpha=.14, label="预测区间")
    ax.set(xlabel="自变量", ylabel="响应值", title="拟合轨迹及最大误差局部核验")
    ax.legend(ncol=3, loc="upper left")
    peak = int(np.argmax(np.abs(residual)))
    annotate_key_point(ax, x[peak], obs[peak], f"最大误差 {abs(residual[peak]):.3f}")

    half_window = max((float(x.max()) - float(x.min())) * 0.09, 0.5)
    mask = (x >= x[peak] - half_window) & (x <= x[peak] + half_window)
    inset = ax.inset_axes([0.60, 0.48, 0.36, 0.38])
    inset.plot(x[mask], obs[mask], color=JOURNAL_COLORS["muted"], lw=1.0)
    inset.plot(x[mask], pred[mask], color=JOURNAL_COLORS["blue"], lw=1.6)
    inset.fill_between(x[mask], df.loc[mask, "lower"], df.loc[mask, "upper"], color=JOURNAL_COLORS["blue"], alpha=.14)
    inset.scatter([x[peak]], [obs[peak]], s=22, color=JOURNAL_COLORS["coral"], zorder=4)
    inset.set_title("局部放大：最大误差邻域", fontsize=9)
    inset.tick_params(labelsize=8)
    ax.indicate_inset_zoom(inset, edgecolor=JOURNAL_COLORS["muted"], alpha=.75)
    ax.text(0.02, 0.03, f"RMSE = {rmse:.3f}；MAE = {mae:.3f}", transform=ax.transAxes, color=JOURNAL_COLORS["ink"], fontsize=9)

    if args.title:
        fig.suptitle(args.title, fontsize=12, y=.995)
        fig.subplots_adjust(top=.91)
    png = figures / f"{args.prefix}.png"; pdf = figures / f"{args.prefix}.pdf"
    save_mira_figure(fig, png, dpi=args.dpi); save_mira_figure(fig, pdf, dpi=args.dpi); plt.close(fig)
    return {
        "type": "claim_oriented_single_with_inset",
        "layout": "inset",
        "metrics": {"rmse": rmse, "mae": mae, "largest_error_x": float(x[peak]), "largest_abs_error": float(abs(residual[peak]))},
        "statistics": {"estimator": None, "errorbar": None, "raw_observations_overlaid": True, "missing_values": "pandas/numpy default; no imputation"},
        "transformations": {"data": [], "display_only": ["local inset around largest absolute error"]},
        "outputs": [str(png), str(pdf)],
        "warnings": [],
    }


def plot_distribution(df: pd.DataFrame, figures: Path, args: argparse.Namespace) -> dict:
    import matplotlib.pyplot as plt
    import seaborn as sns

    apply_mira_style(10)
    fig, ax = plt.subplots(figsize=mira_figure_size("wide"))
    order = list(dict.fromkeys(df["group"].astype(str)))
    sns.stripplot(
        data=df,
        x="group",
        y="value",
        order=order,
        color=JOURNAL_COLORS["muted"],
        alpha=0.42,
        jitter=0.18,
        size=3.2,
        ax=ax,
    )
    sns.pointplot(
        data=df,
        x="group",
        y="value",
        order=order,
        estimator="mean",
        errorbar=("ci", args.errorbar_level),
        n_boot=1000,
        seed=args.seed,
        color=JOURNAL_COLORS["blue"],
        markers="D",
        linestyles="none",
        capsize=0.12,
        ax=ax,
    )
    unit = str(df["unit"].dropna().iloc[0]) if "unit" in df and not df["unit"].dropna().empty else ""
    ylabel = f"响应值（{unit}）" if unit else "响应值"
    ax.set(xlabel="方案", ylabel=ylabel, title="分组观测、均值与 95% 置信区间")
    ax.text(0.01, 0.98, "灰点为原始观测；蓝色菱形和误差线为均值及 bootstrap 置信区间。", transform=ax.transAxes, va="top", color=JOURNAL_COLORS["ink"], fontsize=9)
    if args.title:
        fig.suptitle(args.title, fontsize=12, y=.995)
        fig.subplots_adjust(top=.91)
    png = figures / f"{args.prefix}.png"; pdf = figures / f"{args.prefix}.pdf"
    save_mira_figure(fig, png, dpi=args.dpi); save_mira_figure(fig, pdf, dpi=args.dpi); plt.close(fig)
    means = df.groupby("group", sort=False)["value"].mean().to_dict()
    return {
        "type": "grouped_observations_with_estimate",
        "layout": "single",
        "metrics": {"group_means": {str(key): float(value) for key, value in means.items()}, "observation_count": int(len(df))},
        "statistics": {
            "estimator": args.estimator,
            "errorbar": {"method": "ci", "level": args.errorbar_level},
            "bootstrap_samples": 1000,
            "raw_observations_overlaid": True,
            "raw_overlay_reason": "Show sample size, spread, and outliers behind the aggregate estimate.",
            "category_order": order,
            "missing_values": "rows with missing plotted values are omitted by Seaborn; no imputation",
        },
        "transformations": {"data": [], "display_only": ["horizontal jitter for overlapping raw observations"]},
        "outputs": [str(png), str(pdf)],
        "warnings": [],
    }


def preserve_source(root: Path, prefix: str) -> Path:
    target = root / "code" / "python" / f"plot_{prefix}.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve()
    if source != target.resolve():
        shutil.copyfile(source, target)
    return target


def write_render_log(root: Path, args: argparse.Namespace, summary: dict, route: dict) -> Path:
    import matplotlib

    path = root / "results" / "logs" / f"plot_{args.prefix}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "success",
        "backend": f"Python {platform.python_version()} / {route['library']} / Matplotlib {matplotlib.__version__}",
        "route_id": route["route_id"],
        "library": route["library"],
        "claim_id": args.claim_id,
        "source": f"code/python/plot_{args.prefix}.py",
        "data": f"results/figures_data/{args.prefix}.csv",
        "vector": f"figures/{args.prefix}.pdf",
        "png": f"figures/{args.prefix}.png",
        "metrics": summary["metrics"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_evidence_manifest(
    root: Path,
    args: argparse.Namespace,
    summary: dict,
    source: Path,
    log: Path,
    route: dict,
    provenance_path: Path,
    provenance: dict,
) -> None:
    match = re.search(r"Q\s*([0-9]+)", args.claim_id, flags=re.I)
    question_id = f"Q{match.group(1)}" if match else "Q1"
    is_distribution = args.visual_kind == "distribution"
    key_values = (
        [
            {"metric": f"mean_{group}", "value": value, "tolerance": 1e-9}
            for group, value in summary["metrics"]["group_means"].items()
        ]
        if is_distribution
        else [
            {"metric": "rmse", "value": summary["metrics"]["rmse"], "tolerance": 1e-9},
            {"metric": "mae", "value": summary["metrics"]["mae"], "tolerance": 1e-9},
        ]
    )
    record = {
        "figure_id": f"fig_{args.prefix}",
        "claim_id": args.claim_id,
        "question_id": question_id,
        "evidence_role": "uncertainty" if is_distribution else "validation",
        "reader_question": "不同方案的原始观测分布、均值和估计不确定性是否存在可解释差异？" if is_distribution else "模型是否跟踪主要响应趋势，并在最大误差位置保持可解释的偏差范围？",
        "expected_inference": "原始观测揭示组内离散程度，均值与置信区间支持对方案差异及不确定性的审慎比较。" if is_distribution else "预测轨迹覆盖主要趋势，最大误差邻域的局部放大能够直接核验偏差与区间关系。",
        "data_source": f"results/figures_data/{args.prefix}.csv",
        "backend": f"python/{route['library']}",
        "library": route["library"],
        "route_id": route["route_id"],
        "route_mode": "structured_confirmed",
        "recommended_route": route.get("recommended") or {"backend": route["backend"], "library": route["library"], "route_id": route["route_id"]},
        "route_override": route.get("override"),
        "backend_reason": route.get("rationale") or "Python provides the declared reproducible evidence route.",
        "source_file": source.relative_to(root).as_posix(),
        "log_file": log.relative_to(root).as_posix(),
        "provenance_file": provenance_path.relative_to(root).as_posix(),
        "provenance_sha256": provenance["record_sha256"],
        "vector_file": f"figures/{args.prefix}.pdf",
        "png_file": f"figures/{args.prefix}.png",
        "png_dpi": args.dpi,
        "layout": summary["layout"],
        "shared_scale": not is_distribution,
        "comparison_reason": "",
        "has_local_inset": not is_distribution,
        "legend_strategy": "原始观测使用低透明度中性色，均值与置信区间使用单一强调色并在图内直接说明。" if is_distribution else "图例只区分观测、预测和预测区间，最大误差点采用直接标注。",
        "palette": ["#7A869A", "#1F77B4"] if is_distribution else ["#1F2933", "#7A869A", "#1F77B4", "#D65F5F"],
        "prelude": "为比较各方案的中心水平与估计不确定性，图中同时保留原始观测、均值和置信区间。" if is_distribution else "为核验模型对主要趋势和最大误差位置的解释能力，图中给出完整轨迹及关键邻域局部放大。",
        "conclusion": "各方案的组内离散程度和均值差异均可见，置信区间给出了比较结论所需的不确定性边界。" if is_distribution else "模型捕捉了主要响应变化，局部放大明确展示了最大误差点及其与预测区间的关系。",
        "paper_section": "问题一不确定性分析" if is_distribution else "问题一模型验证",
        "statistics": summary["statistics"],
        "transformations": summary["transformations"],
        "key_values": key_values,
    }
    path = root / "planning" / "figure_evidence.json"
    payload = {"version": 1, "figures": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict) and isinstance(loaded.get("figures"), list):
                payload = loaded
        except json.JSONDecodeError:
            pass
    payload["version"] = 1
    payload["figures"] = [
        item for item in payload["figures"]
        if not isinstance(item, dict) or item.get("figure_id") != record["figure_id"]
    ] + [record]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_index(root: Path, args: argparse.Namespace, summary: dict, route: dict) -> None:
    path = root / "figures" / "figure_index.md"
    if not path.exists(): path.write_text("# Figure Index\n\n| Figure | Backend | Source data | Supported claim |\n|---|---|---|---|\n", encoding="utf-8")
    row = f"| figures/{args.prefix}.pdf | Python/{route['library']} | results/figures_data/{args.prefix}.csv | {args.claim.replace('|','/')} |\n"
    text = path.read_text(encoding="utf-8-sig")
    if f"figures/{args.prefix}.pdf" not in text: path.write_text(text + row, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
