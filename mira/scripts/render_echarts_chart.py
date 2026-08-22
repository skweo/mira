#!/usr/bin/env python3
"""Render local Apache ECharts figures for Mira papers.

The script writes a self-contained HTML chart from an ECharts option JSON. If
Playwright is installed, it can also export a static PNG for LaTeX/Typst/PDF
papers. Contest data stays local; gallery URLs are recorded as provenance only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
DEFAULT_ECHARTS_GL_CDN = "https://cdn.jsdelivr.net/npm/echarts-gl@2/dist/echarts-gl.min.js"


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    spec = load_spec(root, args.spec, args.demo)
    option = spec.get("option")
    if not isinstance(option, dict):
        raise SystemExit("spec must contain an object field named `option`")

    html_path = resolve_path(root, args.output_html or spec.get("output_html") or "figures/echarts_chart.html")
    png_path = resolve_path(root, args.output_png) if args.output_png else None
    html_path.parent.mkdir(parents=True, exist_ok=True)
    if png_path:
        png_path.parent.mkdir(parents=True, exist_ok=True)

    html = build_html(
        option=option,
        width=int(args.width or spec.get("width") or 1200),
        height=int(args.height or spec.get("height") or 800),
        title=str(spec.get("title") or "Mira ECharts Figure"),
        source_example=str(spec.get("source_example") or ""),
        echarts_js=str(args.echarts_js or spec.get("echarts_js") or DEFAULT_ECHARTS_CDN),
        echarts_gl_js=str(args.echarts_gl_js or spec.get("echarts_gl_js") or DEFAULT_ECHARTS_GL_CDN),
        use_gl=bool(args.use_gl or spec.get("use_gl") or needs_gl(option)),
    )
    html_path.write_text(html, encoding="utf-8")

    exported = False
    if png_path:
        exported = export_png(html_path, png_path, int(args.width or spec.get("width") or 1200), int(args.height or spec.get("height") or 800), args.timeout_ms)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "html": rel(root, html_path),
        "png": rel(root, png_path) if png_path and exported else "",
        "png_requested": bool(png_path),
        "png_exported": exported,
        "title": spec.get("title", ""),
        "source_example": spec.get("source_example", ""),
        "use_gl": bool(args.use_gl or spec.get("use_gl") or needs_gl(option)),
        "notes": [
            "Keep this HTML/JS source when ECharts drives a paper figure.",
            "For fixed PDFs, insert the PNG/PDF/SVG export or rebuild the selected view with Python.",
            "Do not treat ECharts gallery examples as evidence; they are implementation templates.",
        ],
    }
    if args.write_manifest:
        manifest_path = resolve_path(root, args.write_manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if png_path and not exported:
        print("WARN: PNG export requested but Playwright export failed or is unavailable; HTML was written.", file=sys.stderr)
    return 0


def load_spec(root: Path, spec_path: str, demo: str) -> dict[str, Any]:
    if spec_path:
        path = resolve_path(root, spec_path)
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if demo:
        return demo_spec(demo)
    raise SystemExit("provide --spec <json> or --demo <name>")


def demo_spec(name: str) -> dict[str, Any]:
    key = name.strip().lower()
    if key == "sankey":
        return {
            "title": "资源流向示例",
            "source_example": "https://echarts.apache.org/examples/zh/index.html#chart-type-sankey",
            "option": {
                "title": {"text": "资源流向示例", "left": "center"},
                "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
                "series": [
                    {
                        "type": "sankey",
                        "layout": "none",
                        "emphasis": {"focus": "adjacency"},
                        "data": [{"name": "输入"}, {"name": "模型"}, {"name": "结果"}, {"name": "验证"}],
                        "links": [
                            {"source": "输入", "target": "模型", "value": 8},
                            {"source": "模型", "target": "结果", "value": 6},
                            {"source": "结果", "target": "验证", "value": 4},
                        ],
                    }
                ],
            },
        }
    if key == "surface":
        data = [[x, y, round((x * x + y * y) / 18, 3)] for x in range(-4, 5) for y in range(-4, 5)]
        return {
            "title": "响应曲面示例",
            "source_example": "https://echarts.apache.org/examples/zh/index.html#chart-type-surface",
            "use_gl": True,
            "option": {
                "title": {"text": "响应曲面示例", "left": "center"},
                "tooltip": {},
                "visualMap": {"show": True, "dimension": 2, "min": 0, "max": 2},
                "xAxis3D": {"type": "value", "name": "参数一"},
                "yAxis3D": {"type": "value", "name": "参数二"},
                "zAxis3D": {"type": "value", "name": "目标值"},
                "grid3D": {"viewControl": {"projection": "perspective"}},
                "series": [{"type": "surface", "data": data}],
            },
        }
    if key == "graph":
        return {
            "title": "关系网络示例",
            "source_example": "https://echarts.apache.org/examples/zh/index.html#chart-type-graph",
            "option": {
                "title": {"text": "关系网络示例", "left": "center"},
                "tooltip": {},
                "series": [
                    {
                        "type": "graph",
                        "layout": "force",
                        "roam": True,
                        "label": {"show": True},
                        "data": [{"name": "状态"}, {"name": "动作"}, {"name": "转移"}, {"name": "收益"}],
                        "links": [
                            {"source": "状态", "target": "动作"},
                            {"source": "动作", "target": "转移"},
                            {"source": "转移", "target": "收益"},
                        ],
                    }
                ],
            },
        }
    raise SystemExit(f"unknown demo `{name}`; use sankey, graph, or surface")


def build_html(
    *,
    option: dict[str, Any],
    width: int,
    height: int,
    title: str,
    source_example: str,
    echarts_js: str,
    echarts_gl_js: str,
    use_gl: bool,
) -> str:
    scripts = [script_tag(echarts_js)]
    if use_gl:
        scripts.append(script_tag(echarts_gl_js))
    option_json = json.dumps(option, ensure_ascii=False, indent=2)
    source_html = f"<p>Gallery source: <a href=\"{escape_attr(source_example)}\">{escape_html(source_example)}</a></p>" if source_example else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape_html(title)}</title>
  <style>
    html, body {{ margin: 0; padding: 0; background: #ffffff; font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; }}
    #chart {{ width: {width}px; height: {height}px; background: #ffffff; }}
    .meta {{ width: {width}px; box-sizing: border-box; padding: 8px 14px; color: #555; font-size: 13px; }}
  </style>
  {"".join(scripts)}
</head>
<body>
  <div id="chart"></div>
  <div class="meta">{source_html}</div>
  <script>
    const chart = echarts.init(document.getElementById('chart'), null, {{ renderer: 'canvas' }});
    const option = {option_json};
    chart.setOption(option);
    window.__mira_chart_ready = true;
  </script>
</body>
</html>
"""


def script_tag(src: str) -> str:
    path = Path(src)
    if path.exists():
        return f"<script>{path.read_text(encoding='utf-8-sig')}</script>"
    return f"<script src=\"{escape_attr(src)}\"></script>"


def export_png(html_path: Path, png_path: Path, width: int, height: int, timeout_ms: int) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height + 60}, device_scale_factor=2)
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_function("window.__mira_chart_ready === true", timeout=timeout_ms)
            page.locator("#chart").screenshot(path=str(png_path))
            browser.close()
        return True
    except Exception as exc:
        print(f"WARN: ECharts PNG export failed: {exc}", file=sys.stderr)
        return False


def needs_gl(option: dict[str, Any]) -> bool:
    text = json.dumps(option, ensure_ascii=False).lower()
    return any(term in text for term in ["3d", "globe", "surface", "bar3d", "scatter3d", "lines3d", "map3d"])


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_attr(value: str) -> str:
    return escape_html(value).replace('"', "&quot;")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--spec", default="", help="JSON spec with an `option` object")
    parser.add_argument("--demo", default="", help="Demo spec: sankey, graph, or surface")
    parser.add_argument("--output-html", help="HTML output path")
    parser.add_argument("--output-png", help="PNG output path; requires Python Playwright")
    parser.add_argument("--write-manifest", help="Write render manifest JSON")
    parser.add_argument("--width", type=int, default=1200, help="Chart width")
    parser.add_argument("--height", type=int, default=800, help="Chart height")
    parser.add_argument("--timeout-ms", type=int, default=30000, help="Playwright timeout")
    parser.add_argument("--echarts-js", default="", help="Local echarts.min.js or URL")
    parser.add_argument("--echarts-gl-js", default="", help="Local echarts-gl.min.js or URL")
    parser.add_argument("--use-gl", action="store_true", help="Load echarts-gl")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
