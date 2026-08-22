#!/usr/bin/env python3
"""Batch-learn lightweight patterns from a math-modeling PDF corpus.

This script extracts metadata and short structural signals only. It does not
copy full paper text into the knowledge base.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


MODEL_KEYWORDS: dict[str, list[str]] = {
    "forecasting": ["ARMA", "ARIMA", "ARCH", "GARCH", "时间序列", "灰色预测", "GM", "预测", "回归"],
    "evaluation": ["TOPSIS", "Topsis", "熵权", "层次分析", "AHP", "主成分", "PCA", "评价", "灰色关联", "模糊综合"],
    "optimization": ["线性规划", "整数规划", "非线性规划", "目标规划", "动态规划", "优化", "最优化", "规划"],
    "heuristic": ["模拟退火", "遗传算法", "粒子群", "蚁群", "禁忌搜索", "启发式", "annealing", "genetic algorithm"],
    "network_routing": ["Dijkstra", "Floyd", "网络流", "最短路径", "路径", "VRP", "VRPTW", "TSP", "邮路", "调度"],
    "queueing": ["排队", "排队论", "服务率", "到达率", "等待时间", "空驶率", "queue"],
    "differential_equation": ["微分方程", "差分方程", "动力学", "Runge", "龙格库塔", "Lotka", "Volterra"],
    "parameter_estimation": ["参数估计", "参数辨识", "最小二乘", "Kalman", "卡尔曼", "滤波", "协方差"],
    "simulation": ["仿真", "模拟", "Monte Carlo", "蒙特卡罗", "元胞自动机", "cellular automata"],
    "statistics": ["假设检验", "相关系数", "聚类", "方差", "回归分析", "统计"],
}

QUALITY_KEYWORDS: dict[str, list[str]] = {
    "abstract": ["摘要", "Summary", "Abstract"],
    "toc": ["目录", "Contents", "Content"],
    "assumptions": ["假设", "Assumption", "假定"],
    "symbols": ["符号", "变量", "Definitions", "Notation"],
    "validation": ["验证", "检验", "误差", "灵敏度", "Sensitivity", "robust", "simulation"],
    "appendix": ["附录", "Appendix"],
    "references": ["参考文献", "References"],
    "figures": ["图 ", "Figure", "Fig."],
    "tables": ["表 ", "Table"],
}

SOURCE_PATTERNS: list[tuple[str, str]] = [
    ("official_rubric", "评阅|评卷|官方答案|答案提示|评分"),
    ("excellent_chinese_paper", "优秀论文|获奖论文|一等奖|特等奖"),
    ("mcm_outstanding", r"\\bO\\b|O奖|Outstanding|Summary Sheet|MCM|ICM"),
    ("writing_note", "经验|心得|写好|论文格式|格式规范"),
    ("method_sorted_paper", "按模型整理"),
    ("unknown_pdf", ""),
]


@dataclass(frozen=True)
class Candidate:
    path: Path
    source_type: str
    score: int


def run_text_command(command: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return completed.returncode, completed.stdout, completed.stderr


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def classify_source(path: Path) -> str:
    text = str(path)
    for source_type, pattern in SOURCE_PATTERNS:
        if not pattern or re.search(pattern, text, re.IGNORECASE):
            return source_type
    return "unknown_pdf"


def candidate_score(path: Path, source_type: str) -> int:
    text = str(path).lower()
    score = 0
    weights = {
        "excellent_chinese_paper": 80,
        "mcm_outstanding": 70,
        "official_rubric": 60,
        "method_sorted_paper": 40,
        "writing_note": 25,
        "unknown_pdf": 0,
    }
    score += weights.get(source_type, 0)
    for keyword in ["优秀", "获奖", "o奖", "outstanding", "o ", "评阅", "评卷"]:
        if keyword in text:
            score += 15
    for keyword in ["美赛", "研赛", "国赛", "mcm", "icm"]:
        if keyword in text:
            score += 8
    if any(part in text for part in ["2-0", "2-1", "1-1", "5-1"]):
        score += 5
    return score


def select_candidates(root: Path, limit: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in root.rglob("*.pdf"):
        source_type = classify_source(path)
        score = candidate_score(path, source_type)
        candidates.append(Candidate(path=path, source_type=source_type, score=score))
    candidates.sort(key=lambda item: (-item.score, str(item.path)))

    selected: list[Candidate] = []
    seen_names: set[str] = set()
    per_type: Counter[str] = Counter()
    for candidate in candidates:
        name_key = candidate.path.name.lower()
        # Keep near-duplicates from taking over the batch.
        if name_key in seen_names and per_type[candidate.source_type] >= 5:
            continue
        if per_type[candidate.source_type] >= max(10, limit // 2):
            continue
        selected.append(candidate)
        seen_names.add(name_key)
        per_type[candidate.source_type] += 1
        if len(selected) >= limit:
            break
    return selected


def get_pdf_pages(path: Path) -> int | None:
    code, stdout, _ = run_text_command(["pdfinfo", str(path)], timeout=10)
    if code != 0:
        return None
    for line in stdout.splitlines():
        if line.startswith("Pages:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def extract_text(path: Path, max_chars: int) -> tuple[str, str | None]:
    code, stdout, stderr = run_text_command(["pdftotext", "-layout", "-f", "1", "-l", "8", str(path), "-"], timeout=25)
    text = stdout[:max_chars]
    if code != 0 and not text.strip():
        return "", stderr.strip() or f"pdftotext exit {code}"
    if len(text.strip()) < 500:
        return text, "low_text_extraction"
    return text, None


def find_title(path: Path, text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:40]:
        clean = normalize_space(line)
        if len(clean) < 4:
            continue
        if clean in {"目录", "Contents", "Content"}:
            continue
        if "更多数学建模资料" in clean or "weidian" in clean or "copyright" in clean.lower():
            continue
        if re.search(r"^\d+$", clean):
            continue
        return clean[:120]
    return path.stem[:120]


def extract_headings(text: str, limit: int = 14) -> list[str]:
    headings: list[str] = []
    for raw in text.splitlines():
        line = normalize_space(raw)
        if not line or len(line) > 120:
            continue
        if "----" in line or "...." in line:
            cleaned = re.sub(r"[-.]{3,}.*$", "", line).strip()
            if cleaned:
                line = cleaned
        is_heading = bool(
            re.match(r"^(\d+(\.\d+){0,3}|[一二三四五六七八九十]+[、.])\s*[\u4e00-\u9fffA-Za-z]", line)
            or re.match(r"^(Abstract|Summary|Introduction|Assumptions|Model|Results|Conclusion|References|Appendix)\b", line, re.I)
            or line in {"摘要", "关键词", "目录", "参考文献", "附录"}
        )
        if is_heading and line not in headings:
            headings.append(line)
            if len(headings) >= limit:
                break
    return headings


def keyword_hits(text: str, keywords: dict[str, list[str]]) -> dict[str, int]:
    hits: dict[str, int] = {}
    lower = text.lower()
    for category, terms in keywords.items():
        count = 0
        for term in terms:
            if re.search(re.escape(term.lower()), lower):
                count += len(re.findall(re.escape(term.lower()), lower))
        if count:
            hits[category] = count
    return hits


def extract_short_passage(text: str, markers: list[str], max_chars: int = 360) -> str:
    for marker in markers:
        index = text.find(marker)
        if index >= 0:
            passage = normalize_space(text[index : index + max_chars])
            return passage[:max_chars]
    return ""


def analyze_candidate(candidate: Candidate, root: Path, max_chars: int) -> dict[str, object]:
    pages = get_pdf_pages(candidate.path)
    text, failure = extract_text(candidate.path, max_chars=max_chars)
    rel_path = str(candidate.path.relative_to(root)).replace("\\", "/")
    model_hits = keyword_hits(text + " " + rel_path, MODEL_KEYWORDS)
    quality_hits = keyword_hits(text, QUALITY_KEYWORDS)
    abstract_hint = extract_short_passage(text, ["摘要", "Summary", "Abstract"], max_chars=320)
    result_hint = extract_short_passage(text, ["结果", "Results", "Conclusion", "结论"], max_chars=320)
    headings = extract_headings(text)
    word_count_est = len(re.findall(r"[\w\u4e00-\u9fff]+", text))
    return {
        "path": str(candidate.path),
        "relative_path": rel_path,
        "source_type": candidate.source_type,
        "selection_score": candidate.score,
        "pages": pages,
        "text_chars": len(text),
        "word_count_est": word_count_est,
        "title": find_title(candidate.path, text),
        "headings": headings,
        "model_tags": sorted(model_hits, key=model_hits.get, reverse=True),
        "model_hits": model_hits,
        "quality_tags": sorted(quality_hits, key=quality_hits.get, reverse=True),
        "quality_hits": quality_hits,
        "abstract_hint": abstract_hint,
        "result_hint": result_hint,
        "extraction_failure": failure,
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return lines


def build_topic_map(rows: list[dict[str, object]]) -> str:
    by_tag: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        for tag in row.get("model_tags", []):
            by_tag[str(tag)].append(row)
    lines = ["# Batch Topic Map", "", "This map is generated from lightweight PDF extraction. Use it to choose deep-reading targets; do not treat it as verified model knowledge.", ""]
    for tag, tagged_rows in sorted(by_tag.items(), key=lambda item: (-len(item[1]), item[0])):
        lines.append(f"## {tag} ({len(tagged_rows)})")
        lines.append("")
        for row in tagged_rows[:12]:
            title = str(row.get("title", ""))
            rel_path = str(row.get("relative_path", ""))
            quality = ", ".join(row.get("quality_tags", [])[:4])
            lines.append(f"- `{rel_path}` - {title} ({quality})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_model_coverage(rows: list[dict[str, object]]) -> str:
    tag_counts = Counter()
    source_counts = Counter()
    quality_counts = Counter()
    for row in rows:
        source_counts[str(row.get("source_type", "unknown"))] += 1
        for tag in row.get("model_tags", []):
            tag_counts[str(tag)] += 1
        for tag in row.get("quality_tags", []):
            quality_counts[str(tag)] += 1
    lines = ["# Batch Model Coverage", ""]
    lines.extend(markdown_table(["Model tag", "Sources"], [[tag, str(count)] for tag, count in tag_counts.most_common()]))
    lines.append("")
    lines.extend(markdown_table(["Source type", "Count"], [[tag, str(count)] for tag, count in source_counts.most_common()]))
    lines.append("")
    lines.extend(markdown_table(["Quality signal", "Count"], [[tag, str(count)] for tag, count in quality_counts.most_common()]))
    lines.append("")
    lines.append("## Gaps To Fill")
    lines.append("")
    for tag in MODEL_KEYWORDS:
        if tag_counts[tag] == 0:
            lines.append(f"- `{tag}` has no matched source in this batch.")
    if all(tag_counts[tag] > 0 for tag in MODEL_KEYWORDS):
        lines.append("- No zero-coverage model tag in this batch.")
    return "\n".join(lines).rstrip() + "\n"


def build_candidates_report(rows: list[dict[str, object]], deep_limit: int) -> str:
    def candidate_value(row: dict[str, object]) -> int:
        value = int(row.get("selection_score", 0))
        quality_tags = set(row.get("quality_tags", []))
        model_tags = set(row.get("model_tags", []))
        value += 8 * len(quality_tags & {"abstract", "toc", "validation", "references"})
        value += 5 * len(model_tags)
        if row.get("extraction_failure"):
            value -= 30
        pages = row.get("pages")
        if isinstance(pages, int):
            if 8 <= pages <= 35:
                value += 8
            elif pages > 60:
                value -= 8
        return value

    ranked = sorted(rows, key=lambda row: (-candidate_value(row), str(row.get("relative_path", ""))))
    lines = ["# Excellent Paper Candidates", "", f"Top {deep_limit} candidates for later per-paper deep learning.", ""]
    table_rows: list[list[str]] = []
    for row in ranked[:deep_limit]:
        table_rows.append([
            str(candidate_value(row)),
            str(row.get("source_type", "")),
            str(row.get("pages", "")),
            ", ".join(row.get("model_tags", [])[:4]),
            ", ".join(row.get("quality_tags", [])[:5]),
            f"`{row.get('relative_path', '')}`",
        ])
    lines.extend(markdown_table(["Value", "Type", "Pages", "Model tags", "Quality tags", "Path"], table_rows))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Select from this report for `materials/extracted/paper-learning/` deep notes.")
    lines.append("- Prefer sources with validation, result evidence, and traceable references over title-only matches.")
    return "\n".join(lines).rstrip() + "\n"


def build_failures_report(rows: list[dict[str, object]]) -> str:
    failed = [row for row in rows if row.get("extraction_failure")]
    lines = ["# Batch Extraction Failures", ""]
    if not failed:
        lines.append("- No extraction failures in this batch.")
        return "\n".join(lines) + "\n"
    table_rows = []
    for row in failed:
        table_rows.append([
            str(row.get("extraction_failure")),
            str(row.get("pages", "")),
            str(row.get("text_chars", "")),
            f"`{row.get('relative_path', '')}`",
        ])
    lines.extend(markdown_table(["Failure", "Pages", "Text chars", "Path"], table_rows))
    lines.append("")
    lines.append("## Handling")
    lines.append("")
    lines.append("- Use visual inspection or OCR only for high-value sources.")
    lines.append("- Do not promote rules from low-text sources without manual review.")
    return "\n".join(lines).rstrip() + "\n"


def build_batch_patterns(rows: list[dict[str, object]]) -> str:
    tag_counts = Counter()
    for row in rows:
        for tag in row.get("model_tags", []):
            tag_counts[str(tag)] += 1
    lines = ["# Batch Paper Patterns", "", "Generated from corpus-scale lightweight extraction. Treat these as triage patterns until confirmed by deep reading.", ""]
    lines.append("## Stable Triage Rules")
    lines.append("")
    lines.append("- Prefer deep-reading papers with at least three quality signals among abstract/summary, contents, validation, result evidence, and references.")
    lines.append("- For scanned or low-text PDFs, require visual review before extracting rules.")
    lines.append("- Use model tags to route future contest problems to candidate examples before opening large PDFs.")
    lines.append("- Do not promote a method rule unless at least one candidate includes validation or result evidence.")
    lines.append("")
    lines.append("## Model Routing Signals")
    lines.append("")
    for tag, count in tag_counts.most_common():
        lines.append(f"- `{tag}` appeared in {count} batch sources; use candidates in `excellent_paper_candidates.md` for deep reading.")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Path to Math_Model corpus")
    parser.add_argument("--output-dir", required=True, help="Output directory under materials/extracted/batch-learning")
    parser.add_argument("--limit", type=int, default=100, help="Number of PDFs to analyze")
    parser.add_argument("--deep-limit", type=int, default=30, help="Number of deep-reading candidates to report")
    parser.add_argument("--max-chars", type=int, default=45000, help="Maximum extracted chars per PDF")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = select_candidates(root, args.limit)
    rows = [analyze_candidate(candidate, root, args.max_chars) for candidate in candidates]

    write_jsonl(output_dir / "corpus_scan.jsonl", rows)
    (output_dir / "topic_map.md").write_text(build_topic_map(rows), encoding="utf-8")
    (output_dir / "model_coverage.md").write_text(build_model_coverage(rows), encoding="utf-8")
    (output_dir / "excellent_paper_candidates.md").write_text(build_candidates_report(rows, args.deep_limit), encoding="utf-8")
    (output_dir / "extraction_failures.md").write_text(build_failures_report(rows), encoding="utf-8")
    (output_dir / "paper-patterns-batch.md").write_text(build_batch_patterns(rows), encoding="utf-8")

    print(f"analyzed: {len(rows)} PDFs")
    print(f"wrote: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
