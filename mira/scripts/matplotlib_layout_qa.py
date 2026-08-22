#!/usr/bin/env python3
"""Inspect a live Matplotlib figure for high-signal layout collisions.

The design is informed by Mathodology's ``figqa.py`` at tag ``v0.8.0``
(commit ``8b57eb0f5e00db6e7b53310729e5d02e71cfc7e1``, MIT).  This native Mira
implementation broadens text discovery to titles, labels, ticks, figure text,
tables, colorbar axes, and multiple subplots while keeping the public API
small and importable.

This module works on a live ``Figure`` because a saved PNG no longer carries
the artist relationships needed to identify which line, point, patch, or text
caused a collision.  Raster and final-PDF inspection remain separate checks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable


DEFAULT_MIN_OVERLAP_PX2 = 4.0
DEFAULT_EDGE_TOLERANCE_PX = 1.0
DEFAULT_TEXT_INSET_PX = 0.75


@dataclass(frozen=True)
class LayoutFinding:
    """One deterministic layout finding in display-pixel coordinates."""

    code: str
    axes: int | str
    primary: str
    secondary: str
    message: str
    overlap_px2: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FigureLayoutError(AssertionError):
    """Raised when strict layout QA finds one or more collisions."""


@dataclass(frozen=True)
class _TextBox:
    artist: Any
    bbox: Any
    role: str
    label: str
    axes: int | str


@dataclass(frozen=True)
class _LegendBox:
    artist: Any
    bbox: Any
    label: str
    axes: int | str


def inspect_figure(
    fig: Any,
    *,
    min_overlap_px2: float = DEFAULT_MIN_OVERLAP_PX2,
    edge_tolerance_px: float = DEFAULT_EDGE_TOLERANCE_PX,
    text_inset_px: float = DEFAULT_TEXT_INSET_PX,
) -> list[LayoutFinding]:
    """Return layout findings for a live Matplotlib ``Figure``.

    The check covers text-to-text overlap, free text crossing data patches,
    lines or scatter centers hidden by free text/legends, legends covering data,
    and text extending beyond the current canvas.  Findings are diagnostics;
    callers choose whether to warn or fail.
    """

    renderer = _renderer(fig)
    axes_index = {id(ax): index for index, ax in enumerate(fig.axes)}
    text_boxes, legend_boxes = _collect_text_and_legends(fig, renderer, axes_index)
    findings: list[LayoutFinding] = []

    findings.extend(_text_overlap_findings(text_boxes, min_overlap_px2))
    findings.extend(
        _canvas_findings(
            text_boxes,
            fig.bbox,
            min_overlap_px2=min_overlap_px2,
            edge_tolerance_px=edge_tolerance_px,
        )
    )

    for index, ax in enumerate(fig.axes):
        if not ax.get_visible():
            continue
        free_text = [item for item in text_boxes if item.axes == index and item.role == "free"]
        legends = [item for item in legend_boxes if item.axes == index]
        protected = [(item.label, item.bbox) for item in free_text]
        protected.extend((item.label, item.bbox) for item in legends)

        patches = _visible_data_patches(ax)
        lines = [line for line in ax.lines if line.get_visible()]
        scatters = _visible_scatter_collections(ax)

        findings.extend(
            _free_text_patch_findings(
                index,
                free_text,
                patches,
                renderer,
                min_overlap_px2=min_overlap_px2,
                edge_tolerance_px=edge_tolerance_px,
            )
        )
        findings.extend(
            _legend_data_findings(
                index,
                legends,
                patches,
                lines,
                scatters,
                renderer,
                min_overlap_px2=min_overlap_px2,
                text_inset_px=text_inset_px,
            )
        )
        findings.extend(
            _line_text_findings(index, lines, protected, text_inset_px=text_inset_px)
        )
        findings.extend(
            _scatter_text_findings(index, scatters, protected, text_inset_px=text_inset_px)
        )

    return _deduplicate(findings)


def assert_layout_clean(fig: Any, **kwargs: Any) -> None:
    """Raise ``FigureLayoutError`` when ``inspect_figure`` returns findings."""

    findings = inspect_figure(fig, **kwargs)
    if findings:
        raise FigureLayoutError(format_findings(findings))


def format_findings(findings: Iterable[LayoutFinding], *, limit: int = 20) -> str:
    """Format findings as a concise actionable diagnostic."""

    items = list(findings)
    lines = [f"Mira figure layout QA found {len(items)} issue(s):"]
    for finding in items[: max(limit, 0)]:
        area = f", {finding.overlap_px2:.1f}px^2" if finding.overlap_px2 is not None else ""
        lines.append(
            f"  - [{finding.code}] axes#{finding.axes}: "
            f"{finding.primary} x {finding.secondary}{area}"
        )
    if len(items) > limit:
        lines.append(f"  - ... {len(items) - limit} more finding(s)")
    return "\n".join(lines)


def _renderer(fig: Any) -> Any:
    fig.canvas.draw()
    getter = getattr(fig.canvas, "get_renderer", None)
    if getter is not None:
        try:
            return getter()
        except Exception:
            pass
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    return canvas.get_renderer()


def _collect_text_and_legends(
    fig: Any,
    renderer: Any,
    axes_index: dict[int, int],
) -> tuple[list[_TextBox], list[_LegendBox]]:
    from matplotlib.legend import Legend
    from matplotlib.text import Text

    legends = [artist for artist in fig.findobj(match=Legend) if artist.get_visible()]
    legend_boxes: list[_LegendBox] = []
    for legend_index, legend in enumerate(legends):
        bbox = _extent(legend, renderer)
        if not _usable(bbox):
            continue
        scope = _axes_scope(getattr(legend, "axes", None), axes_index)
        legend_boxes.append(
            _LegendBox(
                artist=legend,
                bbox=bbox,
                label=f"legend#{legend_index}",
                axes=scope,
            )
        )

    role_by_id: dict[int, str] = {}
    scope_by_id: dict[int, int | str] = {}
    texts_by_id: dict[int, Any] = {}

    def register(text: Any | None, role: str, scope: int | str) -> None:
        if text is None:
            return
        text_id = id(text)
        role_by_id[text_id] = role
        scope_by_id[text_id] = scope
        texts_by_id.setdefault(text_id, text)

    for text in fig.texts:
        register(text, "figure-text", "figure")

    for ax_index, ax in enumerate(fig.axes):
        for text in ax.texts:
            register(text, "free", ax_index)
        for text in (ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)):
            register(text, "title", ax_index)
        if ax.axison:
            for axis_name in ("xaxis", "yaxis", "zaxis"):
                axis = getattr(ax, axis_name, None)
                if axis is None or not axis.get_visible():
                    continue
                register(getattr(axis, "label", None), "axis-label", ax_index)
                for text in axis.get_ticklabels():
                    register(text, "tick", ax_index)
                get_offset_text = getattr(axis, "get_offset_text", None)
                if get_offset_text is not None:
                    register(get_offset_text(), "tick-offset", ax_index)
        for table in ax.tables:
            for cell in table.get_celld().values():
                register(cell.get_text(), "table", ax_index)

    text_boxes: list[_TextBox] = []
    for text_id, text in texts_by_id.items():
        if not text.get_visible():
            continue
        value = " ".join((text.get_text() or "").split())
        if not value:
            continue
        bbox = _extent(text, renderer)
        if not _usable(bbox):
            continue
        role = role_by_id[text_id]
        scope = scope_by_id.get(
            text_id,
            _axes_scope(getattr(text, "axes", None), axes_index),
        )
        text_boxes.append(
            _TextBox(
                artist=text,
                bbox=bbox,
                role=role,
                label=f"{role} {_short_text(value)}",
                axes=scope,
            )
        )
    return text_boxes, legend_boxes


def _text_overlap_findings(
    text_boxes: list[_TextBox],
    min_overlap_px2: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    active: list[_TextBox] = []
    for current in sorted(text_boxes, key=lambda item: item.bbox.x0):
        active = [other for other in active if other.bbox.x1 > current.bbox.x0]
        for other in active:
            area = _intersection_area(current.bbox, other.bbox)
            if area <= min_overlap_px2:
                continue
            scope = current.axes if current.axes == other.axes else "figure"
            findings.append(
                LayoutFinding(
                    code="text-over-text",
                    axes=scope,
                    primary=current.label,
                    secondary=other.label,
                    overlap_px2=round(area, 1),
                    message="Move, shorten, rotate, or reduce one of the overlapping labels.",
                )
            )
        active.append(current)
    return findings


def _canvas_findings(
    text_boxes: list[_TextBox],
    figure_bbox: Any,
    *,
    min_overlap_px2: float,
    edge_tolerance_px: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    for item in text_boxes:
        # Tick and axis-label extents commonly cross the pre-tight-layout canvas
        # and are intentionally recovered by Mira's bbox_inches="tight" export.
        # Free annotations and titles crossing the canvas are much more likely
        # to indicate an accidental placement or an unexpectedly large output.
        if item.role not in {"free", "title", "figure-text"}:
            continue
        if _inside(item.bbox, figure_bbox, edge_tolerance_px):
            continue
        intersection = _intersection_area(item.bbox, figure_bbox)
        if intersection <= min_overlap_px2:
            continue
        findings.append(
            LayoutFinding(
                code="text-outside-canvas",
                axes=item.axes,
                primary=item.label,
                secondary="figure canvas",
                overlap_px2=None,
                message=(
                    "Text crosses the current canvas boundary; confirm tight-bbox export or adjust margins."
                ),
            )
        )
    return findings


def _free_text_patch_findings(
    axes: int,
    text_boxes: list[_TextBox],
    patches: list[Any],
    renderer: Any,
    *,
    min_overlap_px2: float,
    edge_tolerance_px: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    for text in text_boxes:
        for patch_index, patch in enumerate(patches):
            patch_bbox = _extent(patch, renderer)
            if not _usable(patch_bbox):
                continue
            area = _intersection_area(text.bbox, patch_bbox)
            if area <= min_overlap_px2 or not _patch_intersects_bbox(patch, text.bbox):
                continue
            if _inside(text.bbox, patch_bbox, edge_tolerance_px):
                continue
            findings.append(
                LayoutFinding(
                    code="text-over-patch",
                    axes=axes,
                    primary=text.label,
                    secondary=f"{type(patch).__name__}#{patch_index}",
                    overlap_px2=round(area, 1),
                    message="Move the annotation away from the filled data region.",
                )
            )
    return findings


def _legend_data_findings(
    axes: int,
    legends: list[_LegendBox],
    patches: list[Any],
    lines: list[Any],
    scatters: list[Any],
    renderer: Any,
    *,
    min_overlap_px2: float,
    text_inset_px: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    for legend in legends:
        for patch_index, patch in enumerate(patches):
            patch_bbox = _extent(patch, renderer)
            if not _usable(patch_bbox):
                continue
            area = _intersection_area(legend.bbox, patch_bbox)
            if area <= min_overlap_px2 or not _patch_intersects_bbox(patch, legend.bbox):
                continue
            findings.append(
                LayoutFinding(
                    code="legend-over-data",
                    axes=axes,
                    primary=legend.label,
                    secondary=f"{type(patch).__name__}#{patch_index}",
                    overlap_px2=round(area, 1),
                    message="Move the legend to reserved whitespace or outside the axes.",
                )
            )
        for line_index, line in enumerate(lines):
            if _segments_hit_bbox(_line_segments(line), legend.bbox, text_inset_px):
                findings.append(
                    LayoutFinding(
                        code="legend-over-data",
                        axes=axes,
                        primary=legend.label,
                        secondary=f"Line2D#{line_index}",
                        message="Move the legend away from plotted lines.",
                    )
                )
        for scatter_index, collection in enumerate(scatters):
            if _points_hit_bbox(_collection_points(collection), legend.bbox, text_inset_px):
                findings.append(
                    LayoutFinding(
                        code="legend-over-data",
                        axes=axes,
                        primary=legend.label,
                        secondary=f"PathCollection#{scatter_index}",
                        message="Move the legend away from plotted points.",
                    )
                )
    return findings


def _line_text_findings(
    axes: int,
    lines: list[Any],
    protected: list[tuple[str, Any]],
    *,
    text_inset_px: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    for line_index, line in enumerate(lines):
        segments = _line_segments(line)
        for label, bbox in protected:
            if not _segments_hit_bbox(segments, bbox, text_inset_px):
                continue
            findings.append(
                LayoutFinding(
                    code="line-through-text",
                    axes=axes,
                    primary=label,
                    secondary=f"Line2D#{line_index}",
                    message="Offset the label or reserve whitespace around it.",
                )
            )
    return findings


def _scatter_text_findings(
    axes: int,
    scatters: list[Any],
    protected: list[tuple[str, Any]],
    *,
    text_inset_px: float,
) -> list[LayoutFinding]:
    findings: list[LayoutFinding] = []
    for scatter_index, collection in enumerate(scatters):
        points = _collection_points(collection)
        for label, bbox in protected:
            if not _points_hit_bbox(points, bbox, text_inset_px):
                continue
            findings.append(
                LayoutFinding(
                    code="point-under-text",
                    axes=axes,
                    primary=label,
                    secondary=f"PathCollection#{scatter_index}",
                    message="Offset the label or move the legend away from the marker.",
                )
            )
    return findings


def _visible_data_patches(ax: Any) -> list[Any]:
    from matplotlib.patches import FancyArrowPatch

    return [
        patch
        for patch in ax.patches
        if patch.get_visible() and not isinstance(patch, FancyArrowPatch)
    ]


def _visible_scatter_collections(ax: Any) -> list[Any]:
    from matplotlib.collections import PathCollection

    return [
        collection
        for collection in ax.collections
        if collection.get_visible() and isinstance(collection, PathCollection)
    ]


def _line_segments(line: Any) -> list[tuple[Any, Any]]:
    try:
        points = line.get_transform().transform(line.get_xydata())
    except Exception:
        return []
    segments: list[tuple[Any, Any]] = []
    for start, end in zip(points, points[1:]):
        if _finite_point(start) and _finite_point(end):
            segments.append((start, end))
    return segments


def _collection_points(collection: Any) -> list[Any]:
    try:
        offsets = collection.get_offsets()
        transform = collection.get_offset_transform()
        points = transform.transform(offsets)
    except Exception:
        return []
    return [point for point in points if _finite_point(point)]


def _segments_hit_bbox(segments: list[tuple[Any, Any]], bbox: Any, inset: float) -> bool:
    xmin, ymin = bbox.x0 + inset, bbox.y0 + inset
    xmax, ymax = bbox.x1 - inset, bbox.y1 - inset
    return any(_segment_intersects_box(start, end, xmin, ymin, xmax, ymax) for start, end in segments)


def _points_hit_bbox(points: list[Any], bbox: Any, inset: float) -> bool:
    xmin, ymin = bbox.x0 + inset, bbox.y0 + inset
    xmax, ymax = bbox.x1 - inset, bbox.y1 - inset
    if xmax <= xmin or ymax <= ymin:
        return False
    return any(xmin <= float(point[0]) <= xmax and ymin <= float(point[1]) <= ymax for point in points)


def _segment_intersects_box(
    start: Any,
    end: Any,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> bool:
    """Liang-Barsky segment/axis-aligned-box intersection."""

    if xmax <= xmin or ymax <= ymin:
        return False
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    dx, dy = x1 - x0, y1 - y0
    lower, upper = 0.0, 1.0
    for direction, distance in (
        (-dx, x0 - xmin),
        (dx, xmax - x0),
        (-dy, y0 - ymin),
        (dy, ymax - y0),
    ):
        if direction == 0.0:
            if distance < 0.0:
                return False
            continue
        ratio = distance / direction
        if direction < 0.0:
            if ratio > upper:
                return False
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return False
            upper = min(upper, ratio)
    return lower <= upper


def _patch_intersects_bbox(patch: Any, bbox: Any) -> bool:
    try:
        path = patch.get_path().transformed(patch.get_transform())
        return bool(path.intersects_bbox(bbox, filled=True))
    except Exception:
        return True


def _extent(artist: Any, renderer: Any) -> Any | None:
    try:
        return artist.get_window_extent(renderer)
    except TypeError:
        try:
            return artist.get_window_extent(renderer=renderer)
        except Exception:
            return None
    except Exception:
        return None


def _usable(bbox: Any | None) -> bool:
    return bbox is not None and bbox.width > 0 and bbox.height > 0


def _intersection_area(left: Any, right: Any) -> float:
    from matplotlib.transforms import Bbox

    intersection = Bbox.intersection(left, right)
    if intersection is None or intersection.width <= 0 or intersection.height <= 0:
        return 0.0
    return float(intersection.width * intersection.height)


def _inside(inner: Any, outer: Any, tolerance: float) -> bool:
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.y0 >= outer.y0 - tolerance
        and inner.y1 <= outer.y1 + tolerance
    )


def _finite_point(point: Any) -> bool:
    try:
        return math.isfinite(float(point[0])) and math.isfinite(float(point[1]))
    except (TypeError, ValueError, IndexError):
        return False


def _axes_scope(ax: Any | None, axes_index: dict[int, int]) -> int | str:
    return axes_index.get(id(ax), "figure") if ax is not None else "figure"


def _short_text(value: str, limit: int = 42) -> str:
    shortened = value if len(value) <= limit else value[: limit - 3] + "..."
    return f'"{shortened}"'


def _deduplicate(findings: list[LayoutFinding]) -> list[LayoutFinding]:
    unique: list[LayoutFinding] = []
    seen: set[tuple[Any, ...]] = set()
    for finding in findings:
        key = (finding.code, finding.axes, finding.primary, finding.secondary)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


__all__ = [
    "FigureLayoutError",
    "LayoutFinding",
    "assert_layout_clean",
    "format_findings",
    "inspect_figure",
]
