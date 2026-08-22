#!/usr/bin/env python3
"""Audit visual reasoning and emphasis in a Mira contest-final paper.

This gate checks paper-source structure, not the pixels themselves:
- every included figure should have caption/label/reference evidence;
- abstracts should emphasize key results;
- terminal formulas should be visually marked when they are final conclusions;
- zoom/detail, multi-case, heatmap, and 3D usage should be justified by claims.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from delivery_contract import canonical_source, collect_source_files, manifest_path, source_fingerprint


@dataclass
class Finding:
    level: str
    axis: str
    message: str


@dataclass
class FigureBlock:
    path: str
    block: str
    start: int
    end: int


@dataclass
class FigureLoopStats:
    pre_intro: int
    post_interpretation: int
    weak_examples: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper source file, default inferred from paper/main_final.tex, main.tex, main.typ, main.md")
    parser.add_argument("--figure-index", default="figures/figure_index.md")
    parser.add_argument("--diagram-index", default="diagrams/diagram_index.md")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper = resolve_path(root, args.paper) if args.paper else infer_paper(root)
    findings, metrics = audit(root, paper, resolve_path(root, args.figure_index), resolve_path(root, args.diagram_index))
    fingerprint = source_fingerprint(root, paper)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper": rel(root, paper),
        **fingerprint,
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        out = resolve_path(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve_path(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: {payload['verdict']}")
    print("metrics: " + json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    for item in findings:
        print(f"{item.level}: {item.axis}: {item.message}")
    return 1 if payload["verdict"] == "FAIL" else 0


def audit(root: Path, paper: Path, figure_index: Path, diagram_index: Path) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    sources = paper_files(root, paper)
    text = "\n".join(read_text(path) for path in sources)
    index_text = read_text(figure_index) + "\n" + read_text(diagram_index)
    if not text:
        return [Finding("FAIL", "paper", f"paper source not found or empty: {paper}")], {}

    figures = figure_blocks(text)
    included = includegraphics(text)
    labels = set(re.findall(r"\\label\{([^}]+)\}", text))
    refs = set(re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", text))
    abstract = abstract_text(text)
    abstract_body = strip_keyword_tail(abstract)
    final_formula_markers = re.findall(r"\\(?:boxed|fbox|bm|boldsymbol|mathbf)\s*\{", text)
    bold = re.findall(r"\\(?:textbf|bfseries)\b", text)
    equations = len(re.findall(r"\\begin\{equation\}|\\\[", text))
    captions = len(re.findall(r"\\caption\{", text))
    figure_labels = {label for label in labels if label.startswith("fig:")}
    referenced_figures = figure_labels & refs
    visual_text = visual_signal_text(figures, index_text)
    loop_stats = figure_loop_stats(text, figures)

    if included and captions < len(included):
        findings.append(Finding("WARN", "figure_numbering", f"{len(included)} images included but only {captions} captions found; every main-text figure should show a numbered caption"))
    for figure in figures:
        if "\\caption" not in figure.block:
            findings.append(Finding("WARN", "figure_numbering", f"{figure.path} has no caption; LaTeX cannot generate a clear 图号"))
        label_match = re.search(r"\\label\{([^}]+)\}", figure.block)
        if not label_match:
            findings.append(Finding("WARN", "figure_reference", f"{figure.path} has no label; nearby text cannot reference it as 图~\\ref{{...}}"))
        elif label_match.group(1) not in refs:
            findings.append(Finding("WARN", "figure_reference", f"{figure.path} label `{label_match.group(1)}` is not referenced in text"))

    abstract_bold = len(re.findall(r"\\(?:textbf|bfseries)\b", abstract_body))
    abstract_numbers = len(re.findall(r"\d+(?:\.\d+)?", abstract))
    if abstract_numbers >= 5 and abstract_bold < 2:
        findings.append(Finding("WARN", "abstract_emphasis", "abstract has many key numbers but few bold highlights; emphasize final answers and key result phrases"))

    if equations >= 12 and len(final_formula_markers) < 1:
        findings.append(Finding("WARN", "formula_emphasis", "many equations found but no final-answer/key-conclusion formula marker; use boxed/bold/named final-result emphasis only for terminal conclusions"))

    zoom_mentions = count_terms(text + "\n" + index_text, ["局部", "放大", "zoom", "detail"])
    heatmap_mentions = count_terms(visual_text, ["热图", "热力图", "heatmap"])
    three_d_mentions = count_terms(visual_text, ["三维图", "三维曲面", "3D", "3-D", "surface", "曲面图"])
    multi_case_mentions = count_terms(text + "\n" + index_text, ["情形", "情况", "case", "scenario", "分支", "对比", "多图"])
    scale_words = count_terms(text + "\n" + index_text, ["峰值", "临界", "阈值", "局部", "放大", "zoom", "inset", "连续搜索"])
    zoom_visuals = count_visual_items(figures, index_text, ["局部", "放大", "zoom", "detail"])
    heatmap_visuals = count_visual_items(figures, index_text, ["热图", "热力图", "heatmap"])
    three_d_visuals = count_visual_items(figures, index_text, ["三维图", "三维曲面", "3D", "3-D", "surface", "曲面图"])
    role_mentions = count_terms(index_text, ["define", "derive", "operate", "result", "validate", "zoom", "compare", "定义", "推导", "操作", "结果", "验证", "对比"])
    operation_visuals = count_visual_items(figures, index_text, ["流程", "flow", "step", "算法", "递推", "分离轴", "投影", "状态转移", "更新"])
    coarse_fine_mentions = count_terms(text + "\n" + index_text, ["粗", "大步长", "小步长", "细", "局部", "放大", "二分", "三分", "refine", "coarse", "fine"])

    if count_terms(text, ["临界", "峰值", "首次碰撞", "最大", "最小"]) >= 6 and zoom_mentions < 2:
        findings.append(Finding("WARN", "zoom_evidence", "paper has several critical/peak claims but limited zoom/detail evidence; add local magnification when full-scale plots compress the feature"))
    if heatmap_visuals and not count_terms(text + "\n" + index_text, ["colorbar", "色标", "色阶", "颜色表示", "颜色越"]):
        findings.append(Finding("WARN", "heatmap_justification", "heatmap is used but color scale meaning is not clearly described"))
    if heatmap_visuals and three_d_visuals == 0:
        findings.append(Finding("INFO", "2d_3d_choice", "heatmaps are present; consider whether a 3D surface or paired 2D/3D view would make the structure more intuitive"))
    if three_d_visuals and heatmap_visuals == 0:
        findings.append(Finding("INFO", "2d_3d_choice", "3D visual is mentioned; consider adding 2D projection/heatmap when exact values or comparisons are hard to read in 3D"))
    if multi_case_mentions < 3 and count_terms(text, ["方案", "候选", "搜索", "分支", "可行", "不可行"]) >= 8:
        findings.append(Finding("WARN", "multi_case_visuals", "many candidate/case claims appear but limited multi-case visual language; use grouped subplots or comparison tables for alternatives"))
    if len(included) >= 8 and role_mentions < max(4, len(included) // 3):
        findings.append(Finding("WARN", "visual_role_index", "many visuals are present but figure/diagram index has limited visual-role language; record roles such as define, operate, result, validate, zoom, or compare"))
    if count_terms(text, ["定理", "递推", "算法", "步骤", "STEP", "Step"]) >= 6 and operation_visuals < 1:
        findings.append(Finding("WARN", "operation_visual", "algorithm/theorem steps appear but no operation diagram or flowchart is evident"))
    if count_terms(text, ["临界", "阈值", "最小", "最大", "上限", "下限"]) >= 6 and coarse_fine_mentions < 3:
        findings.append(Finding("WARN", "coarse_to_fine_visual", "threshold or boundary claims appear but coarse-to-fine search/zoom language is weak"))
    if len(figures) >= 4:
        if loop_stats.pre_intro < max(2, len(figures) // 2):
            findings.append(
                Finding(
                    "WARN",
                    "figure_text_loop",
                    "many figures lack a nearby pre-figure purpose sentence; introduce what each figure is meant to define, compare, validate, or decide",
                )
            )
        if loop_stats.post_interpretation < max(2, len(figures) // 2):
            examples = ", ".join(loop_stats.weak_examples[:3])
            suffix = f" Examples: {examples}" if examples else ""
            findings.append(
                Finding(
                    "WARN",
                    "figure_text_loop",
                    "many figures lack nearby post-figure interpretation; close the loop from visual evidence to formula, table, or decision." + suffix,
                )
            )

    missing_index_roles = []
    if zoom_visuals == 0:
        missing_index_roles.append("zoom/detail")
    if three_d_visuals == 0:
        missing_index_roles.append("3D/surface")
    metrics = {
        "source_files": [rel(root, path) for path in sources],
        "included_images": len(included),
        "figure_blocks": len(figures),
        "captions": captions,
        "figure_labels": len(figure_labels),
        "referenced_figure_labels": len(referenced_figures),
        "abstract_numbers": abstract_numbers,
        "abstract_bold_markers": abstract_bold,
        "bold_markers_total": len(bold),
        "equation_count": equations,
        "final_formula_markers": len(final_formula_markers),
        "zoom_mentions": zoom_mentions,
        "heatmap_mentions": heatmap_mentions,
        "three_d_mentions": three_d_mentions,
        "zoom_visuals": zoom_visuals,
        "heatmap_visuals": heatmap_visuals,
        "three_d_visuals": three_d_visuals,
        "multi_case_mentions": multi_case_mentions,
        "critical_scale_terms": scale_words,
        "visual_role_mentions": role_mentions,
        "operation_visuals": operation_visuals,
        "coarse_fine_mentions": coarse_fine_mentions,
        "figure_pre_intro": loop_stats.pre_intro,
        "figure_post_interpretation": loop_stats.post_interpretation,
        "figure_loop_weak_examples": loop_stats.weak_examples[:5],
        "missing_index_roles": missing_index_roles,
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return findings, metrics


def figure_blocks(text: str) -> list[FigureBlock]:
    out: list[FigureBlock] = []
    for match in re.finditer(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", text, flags=re.S):
        block = match.group(0)
        path_match = re.search(r"\\(?:includegraphics|figinc|flowinc)(?:\[[^\]]*\])?\s*\{([^}]+)\}", block)
        out.append(
            FigureBlock(
                path=path_match.group(1) if path_match else "<unknown>",
                block=block,
                start=match.start(),
                end=match.end(),
            )
        )
    return out


def includegraphics(text: str) -> list[str]:
    return re.findall(r"\\(?:includegraphics|figinc|flowinc)(?:\[[^\]]*\])?\s*\{([^}]+)\}", text)


def abstract_text(text: str) -> str:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
    return match.group(1) if match else ""


def strip_keyword_tail(text: str) -> str:
    """Remove keyword lines so keyword bolding does not satisfy result emphasis."""

    return re.split(r"\\textbf\{?关键词|关键词", text, maxsplit=1)[0]


def visual_signal_text(figures: list[FigureBlock], index_text: str) -> str:
    """Return text that describes actual visual assets, not all paper prose."""

    parts = [index_text]
    for figure in figures:
        parts.append(figure.path)
        caption = re.search(r"\\caption\{([^}]*)\}", figure.block, flags=re.S)
        if caption:
            parts.append(caption.group(1))
    return "\n".join(parts)


def count_visual_items(figures: list[FigureBlock], index_text: str, terms: list[str]) -> int:
    """Count visual assets whose filename, caption, or index row signals a role."""

    matched: set[str] = set()
    for figure in figures:
        caption = re.search(r"\\caption\{([^}]*)\}", figure.block, flags=re.S)
        if count_terms(figure.path + "\n" + (caption.group(1) if caption else ""), terms):
            matched.add(Path(figure.path).name.lower())
    for line in index_text.splitlines():
        if re.search(r"\.(?:png|jpg|jpeg|webp|svg|pdf)\b", line, flags=re.I) and count_terms(line, terms):
            for item in re.findall(r"[\w./\\-]+\.(?:png|jpg|jpeg|webp|svg|pdf)", line, flags=re.I):
                matched.add(Path(item.replace("\\", "/")).name.lower())
    return len(matched)


def figure_loop_stats(text: str, figures: list[FigureBlock]) -> FigureLoopStats:
    pre_intro = 0
    post_interpretation = 0
    weak_examples: list[str] = []
    for figure in figures:
        before = plain_window(text[max(0, figure.start - 800) : figure.start])
        after = plain_window(text[figure.end : figure.end + 900])
        has_intro = count_terms(before, ["如下图", "如图", "见图", "图示", "为刻画", "为说明", "为验证", "为比较", "为展示", "为分析", "示意", "绘制"]) > 0
        has_after = count_terms(after, ["由图", "从图", "可以看出", "可见", "表明", "说明", "验证", "因此", "据此", "进一步", "对应", "支撑", "决定"]) > 0
        pre_intro += int(has_intro)
        post_interpretation += int(has_after)
        if not (has_intro and has_after):
            weak_examples.append(Path(figure.path).name)
    return FigureLoopStats(pre_intro, post_interpretation, weak_examples)


def plain_window(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if sum(1 for item in findings if item.level == "WARN") >= 5:
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Visual Reasoning Audit",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Paper: `{payload['paper']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    lines.append("")
    return "\n".join(lines)


def infer_paper(root: Path) -> Path:
    if manifest_path(root).is_file():
        return canonical_source(root)
    for rel_path in [
        "paper/main_final_checked.tex",
        "paper/main_final.tex",
        "paper/main.tex",
        "paper/main.typ",
        "paper/main.md",
    ]:
        candidate = root / rel_path
        if candidate.exists():
            return candidate
    return root / "paper" / "main_final.tex"


def paper_files(root: Path, paper: Path) -> list[Path]:
    if not paper.is_file():
        return []
    if paper.suffix.lower() == ".tex":
        return [path for path in collect_source_files(root, paper) if path.suffix.lower() == ".tex"]
    return [paper]


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
