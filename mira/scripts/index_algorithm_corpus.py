#!/usr/bin/env python3
"""Index local algorithm folders for Mira learning.

This script does not execute any external code. It scans filenames and small
text/code snippets to classify algorithm materials for later deep reading.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


TEXT_SUFFIXES = {".m", ".txt", ".md", ".html", ".py", ".c", ".cpp"}
DOC_SUFFIXES = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".caj", ".chm"}
BINARY_OR_ARCHIVE = {".exe", ".bat", ".rar", ".7z", ".zip", ".lnk", ".db", ".mat", ".fig", ".mdl"}

TOPIC_PATTERNS = {
    "linear_integer_programming": [
        "linearprogramming",
        "integerprogramming",
        "线性规划",
        "整数规划",
        "linprog",
        "intlinprog",
        "pulp",
    ],
    "nonlinear_programming": ["nonlinear", "非线性规划", "fmincon", "fminunc"],
    "goal_programming": ["goalprogramming", "目标规划"],
    "graph_network": ["graphtheory", "图论", "dijkstra", "floyd", "最短路", "网络"],
    "simulated_annealing": ["simulated", "annealing", "模拟退火", "monituihuo"],
    "genetic_algorithm": ["遗传算法", "genetic", "ga", "mutation", "crossover"],
    "particle_swarm": ["粒子群", "pso", "swarm", "initswarm"],
    "monte_carlo": ["蒙特卡洛", "monte", "random", "rand"],
    "markov_chain": ["马尔科夫", "markov"],
    "cellular_automata": ["cellular", "automata", "元胞"],
    "grey_system": ["greysystem", "灰色", "gm"],
    "time_series": ["timeseries", "时间序列", "arima"],
    "regression": ["regression", "回归", "least", "polyfit"],
    "multivariate_analysis": ["multivariate", "多元分析", "pca", "cluster", "聚类"],
    "interpolation": ["interpolation", "插值", "interp"],
    "fuzzy_model": ["fuzzy", "模糊"],
    "ahp_evaluation": ["ahp", "层次分析"],
    "neural_network": ["neural", "神经网络", "bp", "rbf", "lvq", "hopfield"],
    "wavelet": ["小波", "wavelet", "morlet"],
    "simulation": ["仿真", "simulation", "simulink"],
}


def norm(text: str) -> str:
    return text.lower().replace("\\", "/")


def classify(path: Path) -> list[str]:
    text = norm(str(path))
    topics = []
    for topic, patterns in TOPIC_PATTERNS.items():
        if any(norm(pattern) in text for pattern in patterns):
            topics.append(topic)
    return topics or ["uncategorized"]


def read_snippet(path: Path, max_chars: int = 3000) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def score_file(path: Path, topics: list[str], snippet: str) -> int:
    suffix = path.suffix.lower()
    score = 0
    if suffix == ".m":
        score += 8
    elif suffix in {".pdf", ".doc", ".ppt", ".txt", ".md"}:
        score += 5
    elif suffix in {".html", ".py", ".cpp", ".c"}:
        score += 3
    score += 3 * len([topic for topic in topics if topic != "uncategorized"])

    snippet_lower = norm(snippet)
    useful_terms = [
        "function",
        "for ",
        "while ",
        "rand",
        "fitness",
        "objective",
        "distance",
        "plot",
        "linprog",
        "fmincon",
        "crossover",
        "mutation",
        "目标",
        "约束",
        "适应度",
        "迭代",
        "误差",
    ]
    score += sum(1 for term in useful_terms if term in snippet_lower)
    if suffix in BINARY_OR_ARCHIVE:
        score -= 20
    return score


def rel(path: Path, roots: list[Path]) -> str:
    resolved = path.resolve()
    for root in roots:
        try:
            return str(resolved.relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            continue
    return str(path)


def scan_roots(roots: list[Path]) -> dict[str, object]:
    files = []
    suffix_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    top_by_topic: dict[str, list[dict[str, object]]] = defaultdict(list)
    risk_files = []

    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            suffix = path.suffix.lower()
            topics = classify(path)
            snippet = read_snippet(path)
            score = score_file(path, topics, snippet)
            item = {
                "path": str(path),
                "relative_path": rel(path, roots),
                "root": str(root),
                "suffix": suffix,
                "size": path.stat().st_size,
                "topics": topics,
                "score": score,
                "snippet_terms": extract_terms(snippet),
            }
            files.append(item)
            suffix_counts[suffix or "(none)"] += 1
            for topic in topics:
                topic_counts[topic] += 1
                top_by_topic[topic].append(item)
            if suffix in BINARY_OR_ARCHIVE:
                risk_files.append(item)

    for topic, items in top_by_topic.items():
        items.sort(key=lambda item: (-int(item["score"]), str(item["relative_path"])))
        top_by_topic[topic] = items[:20]

    files.sort(key=lambda item: (-int(item["score"]), str(item["relative_path"])))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(root) for root in roots],
        "file_count": len(files),
        "suffix_counts": dict(suffix_counts.most_common()),
        "topic_counts": dict(topic_counts.most_common()),
        "top_candidates": files[:120],
        "top_by_topic": dict(top_by_topic),
        "risk_files": sorted(risk_files, key=lambda item: str(item["relative_path"]))[:200],
    }


def extract_terms(snippet: str) -> list[str]:
    if not snippet:
        return []
    terms = []
    for term in [
        "function",
        "linprog",
        "intlinprog",
        "fmincon",
        "rand",
        "fitness",
        "crossover",
        "mutation",
        "plot",
        "目标",
        "约束",
        "适应度",
        "迭代",
        "误差",
    ]:
        if re.search(re.escape(term), snippet, re.I):
            terms.append(term)
    return terms


def write_outputs(index: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "algorithm_corpus_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "algorithm_corpus_index.md").write_text(
        render_markdown(index),
        encoding="utf-8",
    )


def render_markdown(index: dict[str, object]) -> str:
    lines = [
        "# Algorithm Corpus Index",
        "",
        f"- Generated: `{index['generated_at']}`",
        f"- File count: {index['file_count']}",
        "",
        "## Roots",
        "",
    ]
    for root in index["roots"]:  # type: ignore[index]
        lines.append(f"- `{root}`")

    lines.extend(["", "## File Types", ""])
    lines.append("| Suffix | Count |")
    lines.append("|---|---:|")
    for suffix, count in list(index["suffix_counts"].items())[:30]:  # type: ignore[index]
        lines.append(f"| `{suffix}` | {count} |")

    lines.extend(["", "## Topic Coverage", ""])
    lines.append("| Topic | Count |")
    lines.append("|---|---:|")
    for topic, count in index["topic_counts"].items():  # type: ignore[index]
        lines.append(f"| `{topic}` | {count} |")

    lines.extend(["", "## Top Candidates", ""])
    lines.append("| Score | Topics | File |")
    lines.append("|---:|---|---|")
    for item in index["top_candidates"][:60]:  # type: ignore[index]
        lines.append(
            f"| {item['score']} | {', '.join(item['topics'])} | `{item['relative_path']}` |"
        )

    lines.extend(["", "## Topic Candidates", ""])
    for topic, items in index["top_by_topic"].items():  # type: ignore[index]
        lines.extend([f"### {topic}", "", "| Score | File |", "|---:|---|"])
        for item in items[:10]:
            lines.append(f"| {item['score']} | `{item['relative_path']}` |")
        lines.append("")

    lines.extend(["", "## Do Not Execute Directly", ""])
    lines.append("| Suffix | File |")
    lines.append("|---|---|")
    for item in index["risk_files"][:80]:  # type: ignore[index]
        lines.append(f"| `{item['suffix']}` | `{item['relative_path']}` |")

    lines.extend(
        [
            "",
            "## Learning Use",
            "",
            "- Treat this as a routing index, not verified model knowledge.",
            "- Prefer `.m`, `.txt`, `.pdf`, and `.ppt` sources for deep reading.",
            "- Never execute `.exe`, `.bat`, archives, shortcuts, or unknown binaries.",
            "- Promote only operational rules: applicability, variables, objective, constraints, solver route, validation, and paper evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True, help="Algorithm corpus root")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(item).resolve() for item in args.root]
    missing = [str(root) for root in roots if not root.exists()]
    if missing:
        raise SystemExit(f"missing roots: {missing}")
    write_outputs(scan_roots(roots), Path(args.output_dir))
    print(f"wrote {Path(args.output_dir) / 'algorithm_corpus_index.md'}")
    print(f"wrote {Path(args.output_dir) / 'algorithm_corpus_index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
