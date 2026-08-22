#!/usr/bin/env python3
"""Generate reproducible t-SNE figures for Mira contest papers."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_style import MIRA_COLORS, MIRA_PALETTE, apply_mira_style, mira_figure_size, save_mira_figure


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    df, source = load_source(args, root)
    feature_cols = select_feature_columns(df, args.features, {args.label, args.id})
    prepared = prepare_features(df, feature_cols, args)
    label_values = prepared["frame"][args.label] if args.label and args.label in prepared["frame"].columns else None

    x_model, transform_meta = preprocess_matrix(prepared["x"], args)
    perplexity, perplexity_note = choose_perplexity(args.perplexity, x_model.shape[0])
    coords = run_tsne(x_model, perplexity, args)

    coord_df = build_coordinate_frame(coords, prepared["frame"], args, feature_cols)
    outputs = write_outputs(coord_df, prepared, transform_meta, perplexity, perplexity_note, args, root, source)
    plot_figure(coord_df, label_values, args, outputs)
    write_index(outputs, args, source, feature_cols, prepared, transform_meta, perplexity, perplexity_note)

    print("INFO: t-SNE figure written:")
    for key in ["png", "pdf", "coordinates", "params", "index"]:
        print(f"  {key}: {outputs[key]}")
    if perplexity_note:
        print(f"INFO: {perplexity_note}")
    if prepared["dropped_rows"]:
        print(f"INFO: dropped rows with missing feature values: {prepared['dropped_rows']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root for relative paths.")
    parser.add_argument("--input", help="CSV/XLSX input table. Omit when using --demo.")
    parser.add_argument("--sheet", default=0, help="Excel sheet name or index.")
    parser.add_argument("--demo", choices=["iris", "wine", "digits"], help="Generate a built-in demo dataset.")
    parser.add_argument("--features", help="Comma-separated feature columns. Defaults to inferred numeric columns.")
    parser.add_argument("--label", help="Optional class/cluster label column.")
    parser.add_argument("--id", help="Optional sample identifier column.")
    parser.add_argument("--figures-dir", "--out-dir", dest="figures_dir", default="figures", help="Figure output directory.")
    parser.add_argument("--data-dir", default="results/figures_data", help="Coordinate/parameter output directory.")
    parser.add_argument("--prefix", default="tsne", help="Output filename prefix.")
    parser.add_argument("--title", default="", help="Optional figure title.")
    parser.add_argument("--label-title", default="", help="Legend/colorbar title.")
    parser.add_argument("--perplexity", default="auto", help="t-SNE perplexity, or auto.")
    parser.add_argument("--pca-dim", type=int, default=50, help="PCA pre-reduction dimension for wide feature matrices.")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed.")
    parser.add_argument("--learning-rate", default="auto", help="TSNE learning_rate value.")
    parser.add_argument("--max-iter", type=int, default=1000, help="TSNE max_iter/n_iter value.")
    parser.add_argument("--metric", default="euclidean", help="TSNE distance metric.")
    parser.add_argument("--n-jobs", type=int, default=None, help="TSNE parallel jobs when supported.")
    parser.add_argument("--no-standardize", action="store_true", help="Disable StandardScaler preprocessing.")
    parser.add_argument("--no-ellipses", action="store_true", help="Disable class covariance ellipses.")
    parser.add_argument("--free-aspect", action="store_true", help="Do not force equal aspect ratio.")
    parser.add_argument("--dpi", type=int, default=300, help="PNG output dpi.")
    return parser.parse_args()


def load_source(args: argparse.Namespace, root: Path) -> tuple[pd.DataFrame, str]:
    if args.demo:
        return load_demo(args.demo, args)
    if not args.input:
        raise SystemExit("ERROR: provide --input <csv/xlsx> or --demo <iris|wine|digits>.")
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
    from sklearn.datasets import load_digits, load_iris, load_wine

    loaders = {
        "iris": load_iris,
        "wine": load_wine,
        "digits": load_digits,
    }
    data = loaders[name]()
    df = pd.DataFrame(data.data, columns=[sanitize_column(c) for c in data.feature_names])
    df["类别"] = [str(data.target_names[i]) for i in data.target]
    df["样本编号"] = [f"{name}_{i:03d}" for i in range(len(df))]
    if not args.label:
        args.label = "类别"
    if not args.id:
        args.id = "样本编号"
    return df, f"demo:{name}"


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


def sanitize_column(name: str) -> str:
    return re.sub(r"\s+", "_", str(name).strip())


def select_feature_columns(df: pd.DataFrame, feature_text: str | None, excluded: set[str | None]) -> list[str]:
    excluded_clean = {value for value in excluded if value}
    if feature_text:
        cols = [part.strip() for part in re.split(r"[,，;；]", feature_text) if part.strip()]
        missing = [col for col in cols if col not in df.columns]
        if missing:
            raise SystemExit("ERROR: feature columns not found: " + ", ".join(missing))
        return cols

    candidates: list[str] = []
    min_valid = max(3, int(math.ceil(len(df) * 0.8)))
    for col in df.columns:
        if col in excluded_clean:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() >= min_valid:
            candidates.append(col)
    if not candidates:
        raise SystemExit("ERROR: no numeric feature columns inferred; pass --features explicitly.")
    return candidates


def prepare_features(df: pd.DataFrame, feature_cols: list[str], args: argparse.Namespace) -> dict[str, Any]:
    frame_cols = list(dict.fromkeys([*(col for col in [args.id, args.label] if col), *feature_cols]))
    frame = df[frame_cols].copy()

    x_frame = pd.DataFrame(index=frame.index)
    dropped_constants: list[str] = []
    for col in feature_cols:
        numeric = pd.to_numeric(frame[col], errors="coerce")
        if numeric.nunique(dropna=True) <= 1:
            dropped_constants.append(col)
            continue
        x_frame[col] = numeric

    if x_frame.empty:
        raise SystemExit("ERROR: all selected feature columns are constant or nonnumeric.")

    valid_mask = x_frame.notna().all(axis=1)
    dropped_rows = int((~valid_mask).sum())
    x_frame = x_frame.loc[valid_mask].reset_index(drop=True)
    frame = frame.loc[valid_mask].reset_index(drop=True)
    if len(x_frame) < 5:
        raise SystemExit("ERROR: at least 5 complete samples are required for a useful t-SNE plot.")

    return {
        "frame": frame,
        "x": x_frame.to_numpy(dtype=float),
        "feature_cols": list(x_frame.columns),
        "dropped_constants": dropped_constants,
        "dropped_rows": dropped_rows,
        "n_input": len(df),
        "n_used": len(frame),
    }


def preprocess_matrix(x: np.ndarray, args: argparse.Namespace) -> tuple[np.ndarray, dict[str, Any]]:
    meta: dict[str, Any] = {
        "standardized": not args.no_standardize,
        "pca_applied": False,
        "pca_dim": None,
        "pca_explained_variance_ratio": None,
    }
    x_model = x
    if not args.no_standardize:
        x_model = StandardScaler().fit_transform(x_model)

    n_samples, n_features = x_model.shape
    if args.pca_dim and n_features > args.pca_dim and min(n_samples - 1, n_features) >= 2:
        n_components = min(args.pca_dim, n_samples - 1, n_features)
        pca = PCA(n_components=n_components, random_state=args.random_state)
        x_model = pca.fit_transform(x_model)
        meta.update(
            {
                "pca_applied": True,
                "pca_dim": int(n_components),
                "pca_explained_variance_ratio": float(np.sum(pca.explained_variance_ratio_)),
            }
        )
    return x_model, meta


def choose_perplexity(value: str, n_samples: int) -> tuple[float, str]:
    note = ""
    if str(value).strip().lower() == "auto":
        if n_samples < 8:
            perplexity = max(2.0, float(n_samples - 2))
        else:
            perplexity = float(max(5, min(30, (n_samples - 1) // 3)))
        return perplexity, note

    try:
        perplexity = float(value)
    except ValueError as exc:
        raise SystemExit("ERROR: --perplexity must be a number or auto.") from exc
    if perplexity <= 0:
        raise SystemExit("ERROR: --perplexity must be positive.")
    if perplexity >= n_samples:
        adjusted = max(1.0, float(n_samples - 1))
        note = f"perplexity adjusted from {perplexity:g} to {adjusted:g} because it must be smaller than sample count."
        perplexity = adjusted
    return perplexity, note


def run_tsne(x_model: np.ndarray, perplexity: float, args: argparse.Namespace) -> np.ndarray:
    kwargs: dict[str, Any] = {
        "n_components": 2,
        "perplexity": perplexity,
        "learning_rate": parse_number_or_string(args.learning_rate),
        "init": "pca",
        "metric": args.metric,
        "random_state": args.random_state,
    }
    signature = inspect.signature(TSNE)
    if "max_iter" in signature.parameters:
        kwargs["max_iter"] = args.max_iter
    else:
        kwargs["n_iter"] = args.max_iter
    if "n_jobs" in signature.parameters and args.n_jobs is not None:
        kwargs["n_jobs"] = args.n_jobs
    return TSNE(**kwargs).fit_transform(x_model)


def parse_number_or_string(value: str) -> str | float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def build_coordinate_frame(coords: np.ndarray, frame: pd.DataFrame, args: argparse.Namespace, feature_cols: list[str]) -> pd.DataFrame:
    out = pd.DataFrame({"tsne_1": coords[:, 0], "tsne_2": coords[:, 1]})
    if args.id and args.id in frame.columns:
        out.insert(0, args.id, frame[args.id].to_numpy())
    if args.label and args.label in frame.columns:
        out[args.label] = frame[args.label].to_numpy()
    out["feature_count"] = len(feature_cols)
    return out


def write_outputs(
    coord_df: pd.DataFrame,
    prepared: dict[str, Any],
    transform_meta: dict[str, Any],
    perplexity: float,
    perplexity_note: str,
    args: argparse.Namespace,
    root: Path,
    source: str,
) -> dict[str, Path]:
    figures_dir = resolve_path(root, args.figures_dir)
    data_dir = resolve_path(root, args.data_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    prefix = safe_prefix(args.prefix)
    outputs = {
        "png": figures_dir / f"{prefix}_tsne.png",
        "pdf": figures_dir / f"{prefix}_tsne.pdf",
        "coordinates": data_dir / f"{prefix}_tsne_coordinates.csv",
        "params": data_dir / f"{prefix}_tsne_params.json",
        "index": figures_dir / f"{prefix}_tsne_index.md",
    }
    coord_df.to_csv(outputs["coordinates"], index=False, encoding="utf-8-sig")

    params = {
        "source": source,
        "n_input": prepared["n_input"],
        "n_used": prepared["n_used"],
        "dropped_rows": prepared["dropped_rows"],
        "feature_columns": prepared["feature_cols"],
        "dropped_constant_columns": prepared["dropped_constants"],
        "standardized": transform_meta["standardized"],
        "pca": transform_meta,
        "perplexity": perplexity,
        "perplexity_note": perplexity_note,
        "random_state": args.random_state,
        "learning_rate": args.learning_rate,
        "max_iter": args.max_iter,
        "metric": args.metric,
        "label_column": args.label,
        "id_column": args.id,
    }
    outputs["params"].write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return outputs


def plot_figure(coord_df: pd.DataFrame, label_values: pd.Series | None, args: argparse.Namespace, outputs: dict[str, Path]) -> None:
    import matplotlib.pyplot as plt

    apply_mira_style(font_size=11)
    fig, ax = plt.subplots(figsize=mira_figure_size("square"))
    labels = label_values.reset_index(drop=True) if label_values is not None else None

    if labels is None:
        ax.scatter(coord_df["tsne_1"], coord_df["tsne_2"], s=40, alpha=0.86, color=MIRA_COLORS["blue"], edgecolor="white", linewidth=0.35)
    elif is_continuous_label(labels):
        values = pd.to_numeric(labels, errors="coerce")
        scatter = ax.scatter(
            coord_df["tsne_1"],
            coord_df["tsne_2"],
            c=values,
            cmap="viridis",
            s=42,
            alpha=0.88,
            edgecolor="white",
            linewidth=0.35,
        )
        cbar = fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(args.label_title or args.label or "标签")
    else:
        labels_str = labels.fillna("未标注").astype(str)
        categories = list(labels_str.value_counts().index)
        palette = palette_for(len(categories))
        for category, color in zip(categories, palette):
            mask = labels_str == category
            xy = coord_df.loc[mask, ["tsne_1", "tsne_2"]].to_numpy()
            if not args.no_ellipses:
                add_covariance_ellipse(ax, xy, color)
            ax.scatter(
                xy[:, 0],
                xy[:, 1],
                s=42,
                alpha=0.88,
                label=category,
                color=color,
                edgecolor="white",
                linewidth=0.35,
            )
            if len(categories) <= 12 and len(xy) >= 3:
                cx, cy = np.median(xy, axis=0)
                ax.text(
                    cx,
                    cy,
                    category,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="#222222",
                    bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": color, "linewidth": 0.8, "alpha": 0.88},
                )
        legend_cols = 1 if len(categories) <= 8 else 2
        ax.legend(title=args.label_title or args.label or "类别", loc="best", ncol=legend_cols)

    ax.set_xlabel("t-SNE 维度 1")
    ax.set_ylabel("t-SNE 维度 2")
    if args.title:
        ax.set_title(args.title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.margins(0.08)
    if not args.free_aspect:
        ax.set_aspect("equal", adjustable="datalim")

    save_mira_figure(fig, outputs["png"], dpi=args.dpi)
    save_mira_figure(fig, outputs["pdf"], dpi=args.dpi)
    plt.close(fig)


def is_continuous_label(labels: pd.Series) -> bool:
    numeric = pd.to_numeric(labels, errors="coerce")
    return numeric.notna().mean() >= 0.95 and numeric.nunique(dropna=True) > 12


def palette_for(n: int) -> list[Any]:
    if n <= len(MIRA_PALETTE):
        return MIRA_PALETTE[:n]
    try:
        import seaborn as sns

        return list(sns.color_palette("tab20", n))
    except Exception:
        return [f"C{i}" for i in range(n)]


def add_covariance_ellipse(ax: Any, xy: np.ndarray, color: Any, n_std: float = 1.45) -> None:
    if len(xy) < 5:
        return
    cov = np.cov(xy, rowvar=False)
    if cov.shape != (2, 2) or not np.all(np.isfinite(cov)):
        return
    vals, vecs = np.linalg.eigh(cov)
    if np.any(vals <= 1e-12):
        return
    order = vals.argsort()[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    angle = math.degrees(math.atan2(vecs[1, 0], vecs[0, 0]))
    width, height = 2 * n_std * np.sqrt(vals)
    from matplotlib.patches import Ellipse

    ellipse = Ellipse(
        xy=np.mean(xy, axis=0),
        width=width,
        height=height,
        angle=angle,
        facecolor=color,
        edgecolor=color,
        linewidth=1.0,
        alpha=0.12,
        zorder=0,
    )
    ax.add_patch(ellipse)


def write_index(
    outputs: dict[str, Path],
    args: argparse.Namespace,
    source: str,
    feature_cols: list[str],
    prepared: dict[str, Any],
    transform_meta: dict[str, Any],
    perplexity: float,
    perplexity_note: str,
) -> None:
    caption = (
        "图：高维特征样本的 t-SNE 二维嵌入。图中颜色表示样本类别或聚类标签，"
        "仅用于展示局部邻域分离趋势；分类、聚类或机理结论仍需结合指标、表格或稳健性检验。"
    )
    lines = [
        "# t-SNE Figure Index",
        "",
        f"- Source: `{source}`",
        f"- Figure PNG: `{outputs['png']}`",
        f"- Figure PDF: `{outputs['pdf']}`",
        f"- Coordinates: `{outputs['coordinates']}`",
        f"- Parameters: `{outputs['params']}`",
        f"- Samples used: {prepared['n_used']} / {prepared['n_input']}",
        f"- Feature count: {len(prepared['feature_cols'])}",
        f"- Perplexity: {perplexity:g}",
        f"- Random state: {args.random_state}",
        f"- Standardized: {not args.no_standardize}",
        f"- PCA pre-reduction: {transform_meta['pca_applied']}",
        "",
        "## Caption Draft",
        "",
        caption,
        "",
        "## Caveat",
        "",
        "- Do not interpret t-SNE axes as physical units.",
        "- Do not use t-SNE alone to prove global distance, cluster count, or classifier accuracy.",
        "- If the paper's conclusion depends on this plot, compare at least two perplexities or random seeds.",
        "",
    ]
    if perplexity_note:
        lines.insert(10, f"- Perplexity note: {perplexity_note}")
    if prepared["dropped_constants"]:
        lines.extend(["## Dropped Constant Features", "", ", ".join(prepared["dropped_constants"]), ""])
    if len(feature_cols) <= 40:
        lines.extend(["## Feature Columns", "", ", ".join(feature_cols), ""])
    outputs["index"].write_text("\n".join(lines), encoding="utf-8")


def safe_prefix(value: str) -> str:
    prefix = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value.strip())
    return prefix or "tsne"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    raise SystemExit(main())
