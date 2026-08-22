#!/usr/bin/env python3
"""Route Mira figure needs to semantic color palettes.

The router follows Seaborn's color principles: use hue for categories,
luminance for numeric values, and diverging palettes around a meaningful
midpoint. It writes a small planning artifact; plotting scripts should still
record the final palette in the figure index or manifest.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SOURCE_URL = "https://seaborn.pydata.org/tutorial/color_palettes.html#general-principles-for-using-color-in-plots"

PROJECT_CONTEXT_FILES = [
    "planning/figure_storyboard.md",
    "planning/chart_gallery_route.md",
    "checks/visual_opportunity_report.md",
    "results/result_report.md",
    "planning/result_ledger.md",
    "paper/main.tex",
    "paper/main.md",
]


@dataclass
class PaletteRoute:
    route_id: str
    palette_class: str
    recommended: str
    use_when: str
    avoid_when: str
    evidence_role: str
    color_meaning: str
    implementation_hint: str
    score: int


ROUTES = [
    PaletteRoute(
        "categorical-colorblind",
        "qualitative",
        "colorblind",
        "unordered categories, methods, scenarios, clusters, teams, routes",
        "numeric magnitude, ordered intensity, more than about 10 unaggregated categories",
        "compare/result",
        "color identifies a category; pair with marker/line style when needed",
        "visual_style.mira_palette('categorical', n)",
        0,
    ),
    PaletteRoute(
        "categorical-muted",
        "qualitative",
        "deep or muted",
        "polished small category sets in paper body",
        "accessibility-critical or crowded legends",
        "compare/result",
        "hue identifies a category",
        "visual_style.mira_palette('muted', n)",
        0,
    ),
    PaletteRoute(
        "ordered-sequential",
        "ordered",
        "crest or flare",
        "ordered categories, ranks, levels, stages",
        "pure nominal categories",
        "compare/result",
        "color order follows category order",
        "visual_style.mira_palette('ordered', n)",
        0,
    ),
    PaletteRoute(
        "numeric-heatmap",
        "sequential",
        "mako, rocket, viridis",
        "heatmap, hexbin, density, count, nonnegative surface value",
        "line/point marks on white background when extreme colors approach white",
        "validate/result",
        "luminance represents numeric magnitude",
        "visual_style.mira_cmap('sequential', name='mako')",
        0,
    ),
    PaletteRoute(
        "numeric-line-point",
        "sequential",
        "flare or crest",
        "numeric color on points, lines, trajectories, or small marks",
        "filled heatmaps needing a very wide luminance range",
        "validate/result",
        "luminance and mild hue variation represent numeric magnitude",
        "visual_style.mira_cmap('sequential_points', name='flare')",
        0,
    ),
    PaletteRoute(
        "midpoint-diverging",
        "diverging",
        "vlag, icefire, or coolwarm",
        "residuals, signed errors, deviations from baseline, correlation around 0",
        "strictly nonnegative values or nominal categories",
        "validate/compare",
        "two hue ramps show values below/above a meaningful midpoint",
        "visual_style.mira_cmap('diverging', name='vlag'); record midpoint",
        0,
    ),
    PaletteRoute(
        "neutral-highlight",
        "highlight",
        "gray base plus red/orange/blue accent",
        "one threshold, winner, failure, selected policy, or local risk must stand out",
        "many equally important categories",
        "zoom/result",
        "neutral marks give context; accent marks the key claim",
        "plot base in gray and highlight with MIRA_COLORS['red'] or ['orange']",
        0,
    ),
]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    query = "\n".join(
        part
        for part in [
            args.query,
            args.data_role,
            args.visual_role,
            project_context(root) if args.from_project else "",
        ]
        if part
    )
    routes = recommend(query, args.top)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "source": SOURCE_URL,
        "query": args.query,
        "recommendations": [asdict(item) for item in routes],
        "notes": [
            "Use hue for categories, luminance for numeric magnitude, and diverging palettes around a meaningful midpoint.",
            "Avoid rainbow and red-green scales for final contest-paper figures.",
            "Record the final color meaning in figure_index.md or the plotting manifest.",
        ],
    }
    if args.write_report:
        out = resolve_path(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve_path(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(markdown(payload))
    return 0


def recommend(query: str, top: int) -> list[PaletteRoute]:
    lower = query.lower()
    out: list[PaletteRoute] = []
    for route in ROUTES:
        score = 0
        haystack = " ".join(
            [
                route.route_id,
                route.palette_class,
                route.recommended,
                route.use_when,
                route.evidence_role,
                route.color_meaning,
            ]
        ).lower()
        for token in tokens(lower):
            if token in haystack:
                score += 3
        if route.palette_class == "qualitative" and re.search(r"categor|category|class|cluster|scenario|method|scheme|类别|分类|聚类|方案|方法|情景|路线", lower):
            score += 12
        if route.palette_class == "sequential" and re.search(r"numeric|value|density|heatmap|hexbin|count|surface|magnitude|数值|密度|热力|计数|强度|大小|曲面", lower):
            score += 12
        if route.route_id == "numeric-line-point" and re.search(r"point|line|scatter|trajectory|mark|点|线|散点|轨迹", lower):
            score += 7
        if route.palette_class == "diverging" and re.search(r"residual|error|signed|deviation|baseline|zero|midpoint|correlation|残差|误差|正负|偏差|基线|零|中点|相关", lower):
            score += 14
        if route.palette_class == "ordered" and re.search(r"rank|ordered|stage|level|等级|排序|阶段|层级|顺序", lower):
            score += 10
        if route.palette_class == "highlight" and re.search(r"highlight|threshold|winner|selected|risk|failure|critical|强调|阈值|获胜|选中|风险|失败|临界", lower):
            score += 12
        if score:
            out.append(PaletteRoute(**{**asdict(route), "score": score}))
    if not out:
        out = [PaletteRoute(**{**asdict(ROUTES[0]), "score": 1}), PaletteRoute(**{**asdict(ROUTES[3]), "score": 1})]
    out.sort(key=lambda item: (-item.score, item.palette_class, item.route_id))
    return out[: max(1, top)]


def tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9_+.-]+|[\u4e00-\u9fff]{2,}", text)
    stop = {"and", "or", "the", "for", "with", "plot", "figure", "paper", "chart"}
    return [item for item in raw if item not in stop]


def project_context(root: Path) -> str:
    return "\n".join(read_text(root / rel_path)[:12000] for rel_path in PROJECT_CONTEXT_FILES)


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Color Palette Route",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        f"- Source: {payload['source']}",
        "",
        "## Recommendations",
        "",
        "| Score | Class | Recommended | Use when | Avoid when | Color meaning | Implementation |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload["recommendations"]:
        lines.append(
            "| {score} | `{cls}` | {rec} | {use} | {avoid} | {meaning} | `{hint}` |".format(
                score=item["score"],
                cls=escape(item["palette_class"]),
                rec=escape(item["recommended"]),
                use=escape(item["use_when"]),
                avoid=escape(item["avoid_when"]),
                meaning=escape(item["color_meaning"]),
                hint=escape(item["implementation_hint"]),
            )
        )
    lines.extend(["", "## Notes", ""])
    for note in payload["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--query", default="", help="Free-text palette need")
    parser.add_argument("--data-role", default="", help="categorical, numeric, residual, ordered, highlight")
    parser.add_argument("--visual-role", default="", help="result, validate, compare, zoom, etc.")
    parser.add_argument("--from-project", action="store_true", help="Read planning and result context")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
