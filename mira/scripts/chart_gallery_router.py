#!/usr/bin/env python3
"""Route Mira figure needs to curated chart-gallery examples.

The router is intentionally lightweight: it reads chart names and gallery URLs
from references/chart-gallery-index.md and recommends a small candidate set.
It does not scrape full gallery pages or copy example code into context.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = SKILL_ROOT / "references" / "chart-gallery-index.md"

PROJECT_CONTEXT_FILES = [
    "planning/figure_storyboard.md",
    "planning/evidence_plan.md",
    "checks/visual_opportunity_report.md",
    "results/result_report.md",
    "planning/result_ledger.md",
    "planning/modeling_plan.md",
    "paper/main.tex",
    "paper/main.md",
]

TOKEN_ALIASES = {
    "radar": ["radar", "雷达", "蛛网", "多指标", "multi-indicator"],
    "heatmap": ["heatmap", "热力", "矩阵", "grid", "correlation", "相关"],
    "surface": ["surface", "曲面", "响应面", "contour", "等值线"],
    "distribution": ["distribution", "分布", "hist", "直方", "box", "violin", "ridgeline", "monte", "残差"],
    "hexbin": ["hexbin", "joint", "联合", "散点密度", "overplot"],
    "flow": ["sankey", "flow", "流向", "资源", "转移", "source-target"],
    "network": ["graph", "network", "route", "路径", "拓扑", "node", "edge"],
    "time": ["time", "timeline", "gantt", "时间", "调度", "schedule"],
    "map": ["map", "geo", "地图", "地理", "空间分布"],
    "polar": ["polar", "angle", "方向", "角度", "周期", "circular"],
    "vector": ["vector", "quiver", "stream", "速度场", "力场", "方向场"],
    "compare": ["compare", "comparison", "对比", "方案", "基线", "ranking"],
    "validate": ["validate", "validation", "验证", "灵敏度", "稳健", "误差"],
    "echarts": ["echarts", "apache echarts", "js", "javascript", "html"],
    "custom": ["custom", "自定义", "物品", "对象", "3d model", "schematic"],
    "three_d": ["3d", "三维", "立体", "echarts gl"],
    "bar3d": ["bar3d", "voxel", "体素", "三维柱"],
    "scatter3d": ["scatter3d", "point cloud", "点云", "三维散点"],
    "globe": ["globe", "map3d", "lines3d", "地球", "三维地图", "飞线"],
}

GENERIC_CHART_NAME_TOKENS = {"apache", "echarts", "js", "javascript", "html"}

STOPWORDS = {
    "a",
    "an",
    "apache",
    "and",
    "are",
    "as",
    "by",
    "echarts",
    "for",
    "from",
    "html",
    "in",
    "into",
    "is",
    "javascript",
    "js",
    "of",
    "on",
    "or",
    "paper",
    "pdf",
    "plot",
    "show",
    "the",
    "to",
    "with",
}


@dataclass
class ChartEntry:
    chart_name: str
    library: str
    example_url: str
    data_shape: str
    paper_role: str
    best_for: str
    avoid_when: str
    static_ok: str
    notes: str


@dataclass
class Recommendation:
    score: int
    reasons: list[str]
    entry: ChartEntry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--query", default="", help="Free-text chart need")
    parser.add_argument("--data-shape", default="", help="Known data shape")
    parser.add_argument("--paper-role", default="", help="Evidence role")
    parser.add_argument("--library", default="", help="Preferred library")
    parser.add_argument("--top", type=int, default=8, help="Number of candidates")
    parser.add_argument("--from-project", action="store_true", help="Read project planning/result context")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="Chart gallery index markdown")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    index_path = Path(args.index).resolve()
    entries = load_entries(index_path)
    query_parts = [args.query, args.data_shape, args.paper_role]
    if args.from_project:
        query_parts.append(project_context(root))
    query = "\n".join(part for part in query_parts if part)
    recommendations = recommend(
        entries,
        query=query,
        data_shape=args.data_shape,
        paper_role=args.paper_role,
        library=args.library,
        top=args.top,
    )
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "index": str(index_path),
        "query": args.query,
        "data_shape": args.data_shape,
        "paper_role": args.paper_role,
        "library": args.library,
        "source_galleries": [
            "https://gallery.pyecharts.org",
            "https://matplotlib.org.cn/stable/gallery/#widgets",
            "https://seaborn.pydata.org/examples/index.html",
            "https://echarts.apache.org/examples/zh/index.html#chart-type-bar",
        ],
        "recommendations": [
            {
                "score": item.score,
                "reasons": item.reasons,
                **asdict(item.entry),
            }
            for item in recommendations
        ],
        "notes": [
            "Open gallery example pages only after selecting a small candidate set.",
            "Gallery examples provide chart grammar and code templates; they do not prove chart fit.",
            "Keep contest data local and record adapted examples in figures/figure_index.md.",
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


def load_entries(path: Path) -> list[ChartEntry]:
    text = path.read_text(encoding="utf-8-sig")
    entries: list[ChartEntry] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Chart Grammar Index"):
            in_table = True
            continue
        if in_table and stripped.startswith("## "):
            break
        if not in_table or not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0].lower() == "chart name" or len(cells) < 9:
            continue
        entries.append(
            ChartEntry(
                chart_name=cells[0],
                library=cells[1],
                example_url=cells[2],
                data_shape=cells[3],
                paper_role=cells[4],
                best_for=cells[5],
                avoid_when=cells[6],
                static_ok=cells[7],
                notes=cells[8],
            )
        )
    return entries


def recommend(
    entries: list[ChartEntry],
    query: str,
    data_shape: str,
    paper_role: str,
    library: str,
    top: int,
) -> list[Recommendation]:
    query_tokens = expand_tokens(query)
    shape_tokens = expand_tokens(data_shape)
    role_tokens = expand_tokens(paper_role)
    library_value = library.strip().lower()

    scored: list[Recommendation] = []
    for entry in entries:
        haystack = " ".join(asdict(entry).values()).lower()
        chart_haystack = entry.chart_name.lower()
        score = 0
        reasons: list[str] = []
        for token in query_tokens:
            if token and token_hit(token, haystack):
                score += 3
                if len(reasons) < 4:
                    reasons.append(f"query hit `{token}`")
            if token and token not in GENERIC_CHART_NAME_TOKENS and token_hit(token, chart_haystack):
                score += 4
                if len(reasons) < 4:
                    reasons.append(f"chart-name hit `{token}`")
        for token in shape_tokens:
            if token and token_hit(token, haystack):
                score += 5
                if len(reasons) < 4:
                    reasons.append(f"data-shape hit `{token}`")
        for token in role_tokens:
            if token and token_hit(token, haystack):
                score += 4
                if len(reasons) < 4:
                    reasons.append(f"paper-role hit `{token}`")
        if library_value and library_value in entry.library.lower():
            score += 6
            reasons.append(f"preferred library `{library}`")
        if any(word in query.lower() for word in ["论文", "paper", "pdf", "static", "静态"]) and "yes" in entry.static_ok.lower():
            score += 2
        if any(word in query.lower() for word in ["interactive", "交互", "html", "js", "javascript"]) and entry.library.lower() in {"pyecharts", "echarts js", "echarts gl"}:
            score += 3
        if any(word in query.lower() for word in ["3d", "三维", "globe", "map3d", "scatter3d", "surface", "bar3d", "物品", "建模"]) and "echarts gl" in entry.library.lower():
            score += 8
            reasons.append("meaningful 3D/ECharts GL need")
        if "echarts" in query.lower() and entry.library.lower() in {"echarts js", "echarts gl"}:
            score += 8
            reasons.append("preferred ECharts source")
        if score:
            scored.append(Recommendation(score=score, reasons=unique(reasons), entry=entry))

    if not scored:
        fallback = []
        for entry in entries:
            if entry.chart_name in {"Line plot", "Annotated heatmap", "Scatter plot", "Subplots/multi-panel"}:
                fallback.append(Recommendation(score=1, reasons=["general fallback"], entry=entry))
        scored = fallback

    scored.sort(key=lambda item: (-item.score, item.entry.library, item.entry.chart_name))
    return scored[: max(1, top)]


def expand_tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9_+.-]+|[\u4e00-\u9fff]{2,}", lowered)
    for canonical, aliases in TOKEN_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            tokens.append(canonical)
            tokens.extend(alias.lower() for alias in aliases)
    return unique([token.strip() for token in tokens if token.strip() and token.strip() not in STOPWORDS])


def token_hit(token: str, text: str) -> bool:
    if not token:
        return False
    if re.fullmatch(r"[a-z0-9_+.-]+", token):
        if token in {"3d", "bar3d", "scatter3d", "map3d", "lines3d"}:
            return token in text
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return token in text


def project_context(root: Path) -> str:
    parts: list[str] = []
    for rel_path in PROJECT_CONTEXT_FILES:
        parts.append(read_text(root / rel_path)[:12000])
    table_dir = root / "results" / "tables"
    if table_dir.exists():
        for path in sorted(table_dir.rglob("*"))[:30]:
            if path.suffix.lower() in {".csv", ".tsv", ".xlsx", ".xlsm"}:
                parts.append(path.stem)
    return "\n".join(parts)


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Chart Gallery Route",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        f"- Index: `{payload['index']}`",
        "",
        "## Priority Gallery Sources",
        "",
    ]
    for url in payload["source_galleries"]:
        lines.append(f"- {url}")
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "| Score | Chart | Library | Role | Data shape | Best for | Avoid when | Static | Example URL | Reasons |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in payload["recommendations"]:
        lines.append(
            "| {score} | {chart} | {library} | {role} | {shape} | {best} | {avoid} | {static} | {url} | {reasons} |".format(
                score=item["score"],
                chart=escape(item["chart_name"]),
                library=escape(item["library"]),
                role=escape(item["paper_role"]),
                shape=escape(item["data_shape"]),
                best=escape(item["best_for"]),
                avoid=escape(item["avoid_when"]),
                static=escape(item["static_ok"]),
                url=escape(item["example_url"]),
                reasons=escape("; ".join(item["reasons"])),
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


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
