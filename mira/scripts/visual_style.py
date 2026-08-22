#!/usr/bin/env python3
"""Reusable Mira plotting style for Chinese contest-final figures.

Import this module from project plotting scripts before creating matplotlib
figures:

    from visual_style import apply_mira_style, save_mira_figure
    apply_mira_style()

``save_mira_figure`` runs nonblocking live-layout QA by default.  Use
``layout_qa="strict"`` in regression tests, or ``layout_qa="off"`` when a
figure intentionally uses overlapping artists and is checked another way.

The style is intentionally conservative: clear Chinese labels, readable axes,
print-safe colors, stable output dimensions, and clean white backgrounds without
default grid backdrops.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


MIRA_COLORS = {
    "blue": "#2F6B9A",
    "teal": "#2A9D8F",
    "orange": "#E76F51",
    "gold": "#E9C46A",
    "green": "#5E8C61",
    "red": "#B23A48",
    "purple": "#6D597A",
    "gray": "#6C757D",
}

MIRA_PALETTE = [
    MIRA_COLORS["blue"],
    MIRA_COLORS["orange"],
    MIRA_COLORS["teal"],
    MIRA_COLORS["gold"],
    MIRA_COLORS["green"],
    MIRA_COLORS["red"],
    MIRA_COLORS["purple"],
    MIRA_COLORS["gray"],
]

JOURNAL_COLORS = {
    "ink": "#1F2933",
    "muted": "#7A869A",
    "panel_bg": "#F7F9FB",
    "blue": "#1F77B4",
    "cyan": "#17A2B8",
    "green": "#2E8B57",
    "gold": "#D9A441",
    "coral": "#D65F5F",
    "violet": "#6F4E9B",
}

JOURNAL_PALETTE = [
    JOURNAL_COLORS["blue"],
    JOURNAL_COLORS["coral"],
    JOURNAL_COLORS["green"],
    JOURNAL_COLORS["gold"],
    JOURNAL_COLORS["cyan"],
    JOURNAL_COLORS["violet"],
]

COLORBLIND_PALETTE = [
    "#0173B2",
    "#DE8F05",
    "#029E73",
    "#D55E00",
    "#CC78BC",
    "#CA9161",
    "#FBAFE4",
    "#949494",
    "#ECE133",
    "#56B4E9",
]

_SEABORN_DEFAULTS = {
    "categorical": "colorblind",
    "qualitative": "colorblind",
    "colorblind": "colorblind",
    "muted": "muted",
    "deep": "deep",
    "ordered": "crest",
    "sequential": "mako",
    "sequential_points": "flare",
    "numeric": "mako",
    "diverging": "vlag",
}

_MPL_CMAP_FALLBACKS = {
    "ordered": "viridis",
    "sequential": "viridis",
    "sequential_points": "plasma",
    "numeric": "viridis",
    "diverging": "coolwarm",
}


def mira_palette(
    kind: str = "categorical",
    n: int = 6,
    *,
    name: str | None = None,
    desaturate: float | None = None,
    accent: str | None = None,
) -> list[str]:
    """Return a print-safe palette chosen by color semantics.

    `kind` should describe what color encodes: `categorical`, `ordered`,
    `sequential`, `sequential_points`, `diverging`, or `highlight`.
    Seaborn is used when available; otherwise Mira falls back to local colors
    and matplotlib colormaps.
    """

    key = normalize_palette_kind(kind)
    count = max(int(n), 0)
    if count == 0:
        return []
    if key == "highlight":
        if count == 1:
            return [accent or MIRA_COLORS["red"]]
        base = _cycle(["#CED4DA", "#ADB5BD", "#868E96", "#6C757D"], count - 1)
        return base + [accent or MIRA_COLORS["red"]]

    palette_name = name or _SEABORN_DEFAULTS.get(key, "colorblind")
    sns = _try_seaborn()
    if sns is not None:
        try:
            return _as_hex_list(sns.color_palette(palette_name, n_colors=count, desat=desaturate))
        except Exception:
            pass

    if key in {"categorical", "qualitative", "colorblind"}:
        return _cycle(COLORBLIND_PALETTE, count)
    if key in {"muted", "deep"}:
        return _cycle(MIRA_PALETTE, count)
    if key in {"ordered", "sequential", "sequential_points", "numeric", "diverging"}:
        cmap_name = name or _MPL_CMAP_FALLBACKS.get(key, "viridis")
        return _sample_mpl_cmap(cmap_name, count, fallback=_MPL_CMAP_FALLBACKS.get(key, "viridis"))
    return _cycle(MIRA_PALETTE, count)


def mira_cmap(
    kind: str = "sequential",
    *,
    name: str | None = None,
    as_cmap: bool = True,
    n: int = 256,
) -> Any:
    """Return a matplotlib colormap or a discrete Mira palette.

    Use sequential colormaps for nonnegative magnitudes and diverging colormaps
    for signed residuals, deviations, correlations, or values around a
    meaningful midpoint.
    """

    if not as_cmap:
        return mira_palette(kind, n=n, name=name)

    key = normalize_palette_kind(kind)
    palette_name = name or _SEABORN_DEFAULTS.get(key, "mako")
    sns = _try_seaborn()
    if sns is not None:
        try:
            return sns.color_palette(palette_name, as_cmap=True)
        except Exception:
            pass

    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    if key in {"categorical", "qualitative", "colorblind", "muted", "deep", "highlight"}:
        return ListedColormap(mira_palette(key, n=min(max(n, 1), 20), name=name))

    fallback = _MPL_CMAP_FALLBACKS.get(key, "viridis")
    try:
        return plt.get_cmap(name or fallback)
    except ValueError:
        return plt.get_cmap(fallback)


def choose_palette_for_encoding(
    data_role: str,
    n: int = 6,
    *,
    visual_role: str = "",
    midpoint: float | None = None,
    accessibility: str = "colorblind",
) -> dict[str, Any]:
    """Choose a palette route from a data/visual role description.

    The return value is intentionally manifest-friendly so plotting scripts can
    write it into `figures/figure_index.md` or a JSON artifact.
    """

    role = f"{data_role} {visual_role}".lower()
    if midpoint is not None or _contains_any(role, ["residual", "signed", "deviation", "baseline", "zero", "midpoint", "correlation", "残差", "正负", "偏差", "基线", "零", "中点", "相关"]):
        palette_class = "diverging"
        palette_name = "vlag"
        color_meaning = "color shows values below/above a meaningful midpoint"
    elif _contains_any(role, ["highlight", "threshold", "winner", "selected", "critical", "risk", "高亮", "阈值", "选中", "临界", "风险"]):
        palette_class = "highlight"
        palette_name = "neutral-highlight"
        color_meaning = "neutral colors provide context; accent color marks the key claim"
    elif _contains_any(role, ["ordered", "rank", "stage", "level", "序", "排序", "阶段", "等级", "层级"]):
        palette_class = "ordered"
        palette_name = "crest"
        color_meaning = "color order follows the ordered category"
    elif _contains_any(role, ["numeric", "value", "density", "heatmap", "hexbin", "count", "surface", "magnitude", "数值", "密度", "热力", "计数", "强度", "大小", "曲面"]):
        palette_class = "sequential_points" if _contains_any(role, ["point", "line", "scatter", "trajectory", "点", "线", "散点", "轨迹"]) else "sequential"
        palette_name = "flare" if palette_class == "sequential_points" else "mako"
        color_meaning = "luminance represents numeric magnitude"
    else:
        palette_class = "categorical"
        palette_name = "colorblind" if accessibility == "colorblind" else "deep"
        color_meaning = "hue identifies a category"

    colors = mira_palette(palette_class, n=n, name=None if palette_name == "neutral-highlight" else palette_name)
    return {
        "palette_class": palette_class,
        "palette": palette_name,
        "colors": colors,
        "cmap": None if palette_class in {"categorical", "highlight"} else palette_name,
        "midpoint": midpoint,
        "color_meaning": color_meaning,
        "accessibility": "pair color with marker/line style when categories are close or printed in grayscale",
    }


def normalize_palette_kind(kind: str) -> str:
    key = (kind or "categorical").strip().lower().replace("-", "_")
    aliases = {
        "category": "categorical",
        "categories": "categorical",
        "qual": "qualitative",
        "seq": "sequential",
        "sequential_point": "sequential_points",
        "number": "numeric",
        "numbers": "numeric",
        "residual": "diverging",
        "signed": "diverging",
        "accent": "highlight",
        "neutral_highlight": "highlight",
    }
    return aliases.get(key, key)


def _try_seaborn() -> Any | None:
    try:
        import seaborn as sns

        return sns
    except Exception:
        return None


def _as_hex_list(colors: Any) -> list[str]:
    try:
        return list(colors.as_hex())
    except AttributeError:
        pass
    try:
        import matplotlib.colors as mcolors

        return [mcolors.to_hex(color) for color in colors]
    except Exception:
        return [str(color) for color in colors]


def _sample_mpl_cmap(name: str, n: int, *, fallback: str = "viridis") -> list[str]:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        try:
            cmap = plt.get_cmap(name)
        except ValueError:
            cmap = plt.get_cmap(fallback)
        if n == 1:
            samples = [0.65]
        else:
            samples = [0.08 + 0.84 * i / (n - 1) for i in range(n)]
        return [mcolors.to_hex(cmap(value)) for value in samples]
    except Exception:
        return _cycle(MIRA_PALETTE, n)


def _cycle(colors: list[str], n: int) -> list[str]:
    if n <= 0:
        return []
    return [colors[i % len(colors)] for i in range(n)]


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def apply_mira_style(font_size: int = 11) -> None:
    """Apply Mira's default matplotlib rcParams.

    The function imports matplotlib lazily so this module can still be imported
    on machines where plotting dependencies are installed later.
    """

    import matplotlib as mpl
    from cycler import cycler

    mpl.rcParams.update(
        {
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.06,
            "figure.figsize": (6.4, 4.0),
            "axes.prop_cycle": cycler(color=MIRA_PALETTE),
            "axes.titlesize": font_size + 1,
            "axes.labelsize": font_size,
            "xtick.labelsize": max(font_size - 1, 8),
            "ytick.labelsize": max(font_size - 1, 8),
            "legend.fontsize": max(font_size - 1, 8),
            "lines.linewidth": 1.8,
            "lines.markersize": 5.0,
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "grid.alpha": 0.0,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def mira_figure_size(kind: str = "single") -> tuple[float, float]:
    """Return stable figure dimensions by paper role."""

    sizes = {
        "single": (6.4, 4.0),
        "wide": (7.2, 3.8),
        "half": (4.8, 3.4),
        "square": (4.8, 4.8),
        "route": (6.8, 5.0),
        "matrix": (5.8, 4.8),
        "timeline": (7.2, 3.6),
        "journal_2x2": (7.2, 6.2),
        "journal_1x3": (7.4, 3.0),
        "journal_story": (7.4, 5.2),
    }
    return sizes.get(kind, sizes["single"])


def save_mira_figure(
    fig: Any,
    path: str | Path,
    *,
    dpi: int = 300,
    layout_qa: str = "warn",
) -> Path:
    """Save a figure with contest-paper defaults and live layout QA.

    ``layout_qa`` accepts ``warn`` (default, nonblocking), ``strict`` (raise
    before export), or ``off``.  Results are cached while the figure is not
    stale, so exporting the same live figure to PNG and PDF does not repeat the
    collision analysis or warning.
    """

    mode = str(layout_qa).strip().lower()
    if mode not in {"off", "warn", "strict"}:
        raise ValueError("layout_qa must be one of: off, warn, strict")
    if mode != "off":
        findings = _cached_layout_findings(fig)
        if findings:
            from matplotlib_layout_qa import FigureLayoutError, format_findings

            message = format_findings(findings)
            if mode == "strict":
                raise FigureLayoutError(message)
            fingerprint = tuple(
                (item.code, item.axes, item.primary, item.secondary)
                for item in findings
            )
            if getattr(fig, "_mira_layout_qa_warned", None) != fingerprint:
                import warnings

                warnings.warn(message, RuntimeWarning, stacklevel=2)
                setattr(fig, "_mira_layout_qa_warned", fingerprint)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight", pad_inches=0.06)
    return out


def inspect_mira_figure_layout(fig: Any, *, use_cache: bool = True) -> list[Any]:
    """Return live-layout findings without saving or changing failure policy."""

    if use_cache:
        return list(_cached_layout_findings(fig))
    from matplotlib_layout_qa import inspect_figure

    findings = inspect_figure(fig)
    setattr(fig, "_mira_layout_qa_cache", findings)
    return list(findings)


def _cached_layout_findings(fig: Any) -> list[Any]:
    cached = getattr(fig, "_mira_layout_qa_cache", None)
    if cached is not None and not bool(getattr(fig, "stale", True)):
        return list(cached)
    from matplotlib_layout_qa import inspect_figure

    findings = inspect_figure(fig)
    setattr(fig, "_mira_layout_qa_cache", findings)
    return list(findings)


def create_journal_multipanel(
    layout: str = "2x2",
    *,
    figsize: tuple[float, float] | None = None,
    labels: tuple[str, ...] = ("a", "b", "c", "d"),
) -> tuple[Any, list[Any]]:
    """Create a polished multi-panel figure with stable panel labels.

    Use this for a core figure that needs to connect mechanism, data, result,
    and validation. The caller still owns the actual plots and must keep every
    panel evidence-bearing.
    """

    import matplotlib.pyplot as plt

    if layout == "1x3":
        nrows, ncols, default_size = 1, 3, mira_figure_size("journal_1x3")
    elif layout == "story":
        nrows, ncols, default_size = 2, 3, mira_figure_size("journal_story")
    else:
        nrows, ncols, default_size = 2, 2, mira_figure_size("journal_2x2")

    fig, axes_grid = plt.subplots(nrows, ncols, figsize=figsize or default_size, squeeze=False)
    axes = [ax for row in axes_grid for ax in row]
    for ax, label in zip(axes, labels):
        label_panel(ax, f"({label})")
    fig.subplots_adjust(wspace=0.28, hspace=0.34)
    return fig, axes


def add_panel_takeaway(ax: Any, text: str, *, color: str | None = None) -> Any:
    """Add a short journal-style takeaway label inside a panel."""

    return ax.text(
        0.02,
        0.02,
        text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        color=color or JOURNAL_COLORS["ink"],
        linespacing=1.2,
        bbox={
            "boxstyle": "round,pad=0.28",
            "facecolor": "white",
            "edgecolor": JOURNAL_COLORS["muted"],
            "linewidth": 0.7,
            "alpha": 0.92,
        },
    )


def set_axis_labels(ax: Any, *, title: str = "", xlabel: str = "", ylabel: str = "", unit_note: str = "") -> None:
    """Apply standard title and axis labels, with optional unit note."""

    if title:
        ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if unit_note:
        ax.text(
            0.99,
            0.01,
            unit_note,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color=MIRA_COLORS["gray"],
        )


def annotate_key_point(ax: Any, x: float, y: float, text: str, *, color: str | None = None) -> None:
    """Annotate an important value without crowding the chart."""

    ax.scatter([x], [y], s=28, color=color or MIRA_COLORS["red"], zorder=4)
    ax.annotate(
        text,
        xy=(x, y),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=9,
        arrowprops={"arrowstyle": "->", "linewidth": 0.8, "color": color or MIRA_COLORS["red"]},
    )


def emphasize_window(ax: Any, xmin: float, xmax: float, *, label: str = "", color: str | None = None) -> None:
    """Shade a critical interval such as a collision, threshold, or peak zone."""

    span = ax.axvspan(xmin, xmax, color=color or MIRA_COLORS["gold"], alpha=0.18, linewidth=0)
    if label:
        ymax = ax.get_ylim()[1]
        ax.text((xmin + xmax) / 2, ymax, label, ha="center", va="top", fontsize=9, color=MIRA_COLORS["gray"])
    return span


def add_callout_box(
    ax: Any,
    text: str,
    *,
    xy: tuple[float, float] = (0.98, 0.98),
    loc: str = "axes fraction",
    ha: str = "right",
    va: str = "top",
    fontsize: int = 9,
    color: str | None = None,
) -> Any:
    """Add a readable explanatory callout box.

    Use this for figure interpretation, not for long paragraphs. The callout
    should explain the highlighted object and the next reasoning step.
    """

    transform = ax.transAxes if loc == "axes fraction" else ax.transData
    return ax.text(
        xy[0],
        xy[1],
        text,
        transform=transform,
        ha=ha,
        va=va,
        fontsize=fontsize,
        color=color or "#222222",
        linespacing=1.25,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": MIRA_COLORS["gray"],
            "linewidth": 0.8,
            "alpha": 0.92,
        },
    )


def annotate_bracket(
    ax: Any,
    start: float,
    end: float,
    y: float,
    text: str = "",
    *,
    color: str | None = None,
) -> None:
    """Draw a horizontal bracket for a search interval or feasible window."""

    c = color or MIRA_COLORS["red"]
    ax.plot([start, end], [y, y], color=c, linewidth=1.4)
    ax.plot([start, start], [y, y], marker="|", color=c, markersize=10)
    ax.plot([end, end], [y, y], marker="|", color=c, markersize=10)
    if text:
        ax.text((start + end) / 2, y, text, ha="center", va="bottom", fontsize=9, color=c)


def add_zoom_inset(ax: Any, xlim: tuple[float, float], ylim: tuple[float, float], *, loc: str = "upper right") -> Any:
    """Create a standard inset axis for local magnification.

    This helper requires matplotlib's inset toolkit and returns the inset axes so
    callers can replot the same data on the zoomed scale.
    """

    from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

    inset = inset_axes(ax, width="38%", height="38%", loc=loc)
    inset.set_xlim(*xlim)
    inset.set_ylim(*ylim)
    inset.grid(False)
    mark_inset(ax, inset, loc1=2, loc2=4, fc="none", ec=MIRA_COLORS["gray"], lw=0.8)
    return inset


def connect_axes_with_arrow(
    fig: Any,
    ax_from: Any,
    ax_to: Any,
    *,
    start: tuple[float, float] = (0.75, 0.55),
    end: tuple[float, float] = (0.25, 0.55),
    color: str | None = None,
) -> Any:
    """Draw an arrow between axes using axes-fraction coordinates."""

    from matplotlib.patches import ConnectionPatch

    arrow = ConnectionPatch(
        xyA=end,
        coordsA=ax_to.transAxes,
        xyB=start,
        coordsB=ax_from.transAxes,
        arrowstyle="->",
        mutation_scale=14,
        linewidth=1.0,
        color=color or MIRA_COLORS["red"],
    )
    fig.add_artist(arrow)
    return arrow


def label_panel(ax: Any, label: str, *, x: float = 0.02, y: float = 0.98) -> Any:
    """Add a stable subplot label such as (a), (b), or 情形一."""

    return ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        color="#222222",
        bbox={"boxstyle": "square,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.8},
    )


def make_boundary_comparison_figure(ncols: int = 2, *, figsize: tuple[float, float] | None = None) -> tuple[Any, Any]:
    """Create a shared-layout figure for boundary-side or case comparison."""

    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, ncols, figsize=figsize or (3.6 * ncols, 3.4), squeeze=False)
    return fig, axes[0]


def apply_3d_style(ax: Any, *, xlabel: str = "", ylabel: str = "", zlabel: str = "", elev: float = 24, azim: float = -55) -> None:
    """Apply a readable 3D view for surfaces or trajectory figures."""

    ax.view_init(elev=elev, azim=azim)
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, labelpad=8)
    if zlabel:
        ax.set_zlabel(zlabel, labelpad=8)
    ax.grid(False)
