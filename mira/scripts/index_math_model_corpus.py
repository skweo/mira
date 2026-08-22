#!/usr/bin/env python3
"""Create a lightweight index for a large math-modeling corpus."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


CATEGORIES: dict[str, list[str]] = {
    "official_rubrics": ["评阅", "评卷", "官方答案", "答案提示", "评分"],
    "writing_experience": ["经验", "心得", "写好", "论文格式", "格式规范", "新手", "入门", "总结"],
    "templates": ["模板", "LaTeX", "latex", "Word模板", "论文格式"],
    "mathorcup": ["mathorcup", "Mathor", "数学应用挑战赛"],
    "optimization": ["线性规划", "整数规划", "非线性规划", "模拟退火", "遗传算法", "粒子群", "目标规划", "TSP", "VRP", "VRPTW", "优化", "规划"],
    "evaluation": ["AHP", "Topsis", "TOPSIS", "层次分析", "熵权", "评价", "主成分", "PCA", "灰色关联", "模糊综合"],
    "forecasting": ["ARIMA", "ARMA", "时间序列", "灰色预测", "GM", "预测", "回归"],
    "graph_network": ["Dijkstra", "Floyd", "图论", "网络流", "最短路径", "路径"],
    "matlab_code": [".m"],
    "excel_data": [".xls", ".xlsx", ".csv"],
}


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def matches(path_text: str, terms: list[str], suffix: str) -> bool:
    lower = path_text.lower()
    for term in terms:
        if term.startswith("."):
            if suffix.lower() == term.lower():
                return True
        elif term.lower() in lower:
            return True
    return False


def build_index(root: Path, limit: int) -> str:
    files = [p for p in root.rglob("*") if p.is_file()]
    ext_counts = Counter((p.suffix.lower() or "[no extension]") for p in files)
    top_level_counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    for path in files:
        relative = path.relative_to(root)
        first = relative.parts[0] if relative.parts else "."
        top_level_counts[first] += 1
        path_text = rel(path, root)
        for category, terms in CATEGORIES.items():
            if matches(path_text, terms, path.suffix):
                if len(examples[category]) < limit:
                    examples[category].append(path_text)

    lines: list[str] = []
    lines.append("# Math_Model Corpus Index")
    lines.append("")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Indexed at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Total files: {len(files)}")
    lines.append("")
    lines.append("## Top-Level Folders")
    lines.append("")
    lines.append("| Folder | Files |")
    lines.append("|---|---:|")
    for name, count in top_level_counts.most_common():
        lines.append(f"| `{name}` | {count} |")
    lines.append("")
    lines.append("## Extension Counts")
    lines.append("")
    lines.append("| Extension | Files |")
    lines.append("|---|---:|")
    for ext, count in ext_counts.most_common(30):
        lines.append(f"| `{ext}` | {count} |")
    lines.append("")
    lines.append("## Category Examples")
    lines.append("")
    for category in CATEGORIES:
        lines.append(f"### {category}")
        lines.append("")
        found = examples.get(category, [])
        if not found:
            lines.append("- No filename matches found.")
        else:
            for item in found:
                lines.append(f"- `{item}`")
        lines.append("")
    lines.append("## Usage Notes")
    lines.append("")
    lines.append("- Use this index to choose a narrow search path before opening large PDFs, Word files, or code folders.")
    lines.append("- Treat all examples as raw material; extract rules into `materials/extracted/` before promoting them.")
    lines.append("- Do not execute binaries from the corpus.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Path to Math_Model corpus")
    parser.add_argument("--output", required=True, help="Markdown output path")
    parser.add_argument("--limit", type=int, default=25, help="Examples per category")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Corpus root does not exist: {root}")

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_index(root, args.limit), encoding="utf-8")
    print(f"wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
