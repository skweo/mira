#!/usr/bin/env python3
"""Review Mira final-paper quality beyond mechanical audit pass/fail gates.

This script is deliberately heuristic. It does not prove a paper is award-level;
it catches signs that a paper has passed structural checks while still reading
like a mechanically repaired report: low-value figures, generic figure prose,
weak final-formula/result emphasis, and poor contest-final polish.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".svg"}
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
WEAK_FILENAME_TERMS = {
    "audit_summary",
    "candidate",
    "factor",
    "heatmap",
    "margin",
    "scan",
}
MECHANICAL_PHRASES = [
    "为展示本节结论所依赖的关键形态或趋势",
    "这说明展示本节结论所依赖的关键形态或趋势",
    "为验证临界接触位置并解释停止或边界判定",
    "这说明明确几何对象、变量关系和后续约束来源",
    "本文绘制图",
]
GENERIC_VISUAL_TERMS = [
    "关键形态",
    "关键趋势",
    "支撑",
    "验证",
    "解释",
    "展示",
    "说明",
    "本节结论",
    "后续约束来源",
]
SPECIFIC_TERMS = [
    "临界",
    "峰值",
    "最小",
    "最大",
    "首次",
    "局部",
    "放大",
    "边界",
    "可行",
    "不可行",
    "碰撞",
    "速度",
    "螺距",
    "半径",
    "时间",
    "误差",
    "残差",
    "阈值",
    "上限",
    "下限",
]


@dataclass
class Finding:
    level: str
    axis: str
    return_phase: str
    finding: str
    recommendation: str
    evidence: str = ""


@dataclass
class MechanicalSentence:
    line: int
    text: str
    reason: str


@dataclass
class FigureUse:
    path: str
    label: str
    caption: str
    start_line: int
    end_line: int
    before: str
    after: str


@dataclass
class FigureReview:
    figure: str
    label: str
    caption: str
    qid: str
    role: str
    score: int
    recommendation: str
    reasons: list[str]
    asset_bytes: int | None
    width: int | None
    height: int | None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument(
        "--paper",
        help="Paper source file. Defaults to the strongest known final-paper candidate.",
    )
    parser.add_argument("--figure-index", default="figures/figure_index.md")
    parser.add_argument("--diagram-index", default="diagrams/diagram_index.md")
    parser.add_argument("--visual-audit-json", help="Optional visual_reasoning_audit JSON")
    parser.add_argument("--asset-audit-json", help="Optional visual_asset_audit JSON")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper = resolve_path(root, args.paper) if args.paper else infer_paper(root)
    payload = review(
        root=root,
        paper=paper,
        figure_index=resolve_path(root, args.figure_index),
        diagram_index=resolve_path(root, args.diagram_index),
        visual_audit=load_json(resolve_path(root, args.visual_audit_json)) if args.visual_audit_json else {},
        asset_audit=load_json(resolve_path(root, args.asset_audit_json)) if args.asset_audit_json else {},
    )

    if args.write_report:
        out = resolve_path(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve_path(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"VERDICT: {payload['verdict']}")
    print("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
    for item in payload["findings"]:
        print(f"{item['level']}: {item['axis']}: {item['finding']}")
    return 1 if payload["verdict"] == "FAIL" else 0


def review(
    root: Path,
    paper: Path,
    figure_index: Path,
    diagram_index: Path,
    visual_audit: dict[str, Any],
    asset_audit: dict[str, Any],
) -> dict[str, Any]:
    text = read_text(paper)
    index_text = read_text(figure_index) + "\n" + read_text(diagram_index)
    findings: list[Finding] = []

    if not text:
        findings.append(
            Finding(
                level="FAIL",
                axis="paper_quality",
                return_phase="paper",
                finding=f"paper source not found or empty: {paper}",
                recommendation="return to paper and generate the final paper source before quality review.",
            )
        )
        return payload(root, paper, findings, [], [], {}, {}, {}, visual_audit, asset_audit)

    figures = figure_uses(text)
    mechanical = mechanical_sentences(text)
    figure_reviews = review_figures(root, figures, index_text)
    pdf_metrics, pdf_findings = review_pdf_polish(root, paper)
    findings.extend(pdf_findings)

    if mechanical:
        sample = "; ".join(f"L{item.line}: {compact(item.text, 42)}" for item in mechanical[:4])
        level = "FAIL" if len(mechanical) >= 12 else "WARN"
        findings.append(
            Finding(
                level=level,
                axis="mechanical_prose",
                return_phase="paper",
                finding=f"detected {len(mechanical)} mechanical or template-like figure/prose sentences. {sample}",
                recommendation=(
                    "rewrite these sentences with figure-specific variables, exact values, local features, and the decision each visual supports; "
                    "remove generic repair phrases left by paper_revision_loop.py."
                ),
                evidence=sample,
            )
        )

    weak_reviews = [item for item in figure_reviews if item.score < 58 or item.recommendation in {"REDRAW", "KEEP_AS_SUPPORT", "DROP"}]
    low_value = [item for item in figure_reviews if any("low-value" in reason for reason in item.reasons)]
    if weak_reviews:
        examples = "; ".join(f"{Path(item.figure).name}={item.score}/{item.recommendation}" for item in weak_reviews[:5])
        level = "FAIL" if len(weak_reviews) >= max(5, len(figure_reviews) // 2 + 1) else "WARN"
        findings.append(
            Finding(
                level=level,
                axis="figure_effectiveness",
                return_phase="implementation",
                finding=f"{len(weak_reviews)} figures look weak, low-information, or poorly connected to a claim. {examples}",
                recommendation=(
                    "for each weak figure, either redraw with an annotated local feature, replace with a compact comparison table/branch diagram, "
                    "keep supporting-only visuals as separate result files, or drop decorative duplicates."
                ),
                evidence=examples,
            )
        )
    if low_value:
        examples = "; ".join(Path(item.figure).name for item in low_value[:5])
        findings.append(
            Finding(
                level="WARN",
                axis="figure_value",
                return_phase="implementation",
                finding=f"{len(low_value)} figures may add little beyond the nearby table/prose. {examples}",
                recommendation="keep only if the visual reveals a pattern that the table cannot; otherwise keep it as a separate result file, replace it, or drop it.",
                evidence=examples,
            )
        )

    scorecard = score_paper(text, figures, figure_reviews, mechanical, pdf_metrics, visual_audit, asset_audit)
    if scorecard["contest_final_score"] < 60:
        findings.append(
            Finding(
                level="FAIL",
                axis="contest_final_feel",
                return_phase="implementation",
                finding=f"contest-final feel score is {scorecard['contest_final_score']}/100, below delivery threshold.",
                recommendation="return to visual evidence planning and paper writing; improve reasoning continuity, figure value, abstract ledger, formula emphasis, and PDF polish.",
            )
        )
    elif scorecard["contest_final_score"] < 78:
        findings.append(
            Finding(
                level="WARN",
                axis="contest_final_feel",
                return_phase="implementation",
                finding=f"contest-final feel score is {scorecard['contest_final_score']}/100; adequate but not yet strong-award stable.",
                recommendation="prioritize the lowest subscore before final comparison with excellent papers.",
            )
        )

    metrics = {
        "figures_reviewed": len(figure_reviews),
        "mechanical_sentence_count": len(mechanical),
        "weak_visual_candidates": len(weak_reviews),
        "low_information_figure_count": len(low_value),
        "contest_final_score": scorecard["contest_final_score"],
        "scorecard": scorecard,
        "pdf": pdf_metrics,
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return payload(root, paper, findings, figure_reviews, mechanical, scorecard, metrics, pdf_metrics, visual_audit, asset_audit)


def payload(
    root: Path,
    paper: Path,
    findings: list[Finding],
    figure_reviews: list[FigureReview],
    mechanical: list[MechanicalSentence],
    scorecard: dict[str, Any],
    metrics: dict[str, Any],
    pdf_metrics: dict[str, Any],
    visual_audit: dict[str, Any],
    asset_audit: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper": rel(root, paper),
        "verdict": verdict(findings),
        "metrics": metrics,
        "scorecard": scorecard,
        "pdf_metrics": pdf_metrics,
        "findings": [asdict(item) for item in findings],
        "figure_reviews": [asdict(item) for item in figure_reviews],
        "mechanical_sentences": [asdict(item) for item in mechanical],
        "upstream_audits": {
            "visual_reasoning_verdict": visual_audit.get("verdict"),
            "asset_verdict": asset_audit.get("verdict"),
        },
    }


def figure_uses(text: str) -> list[FigureUse]:
    out: list[FigureUse] = []
    for match in re.finditer(r"\\begin\{figure\}.*?\\end\{figure\}", text, flags=re.S):
        block = match.group(0)
        graphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block)
        caption = latex_command_arg(block, "caption")
        label = latex_command_arg(block, "label")
        before = clean_latex(text[max(0, match.start() - 950) : match.start()])
        after = clean_latex(text[match.end() : match.end() + 1050])
        start_line = text.count("\n", 0, match.start()) + 1
        end_line = text.count("\n", 0, match.end()) + 1
        for path in graphics or ["<unknown>"]:
            out.append(
                FigureUse(
                    path=path,
                    label=label,
                    caption=clean_latex(caption),
                    start_line=start_line,
                    end_line=end_line,
                    before=before,
                    after=after,
                )
            )
    return out


def review_figures(root: Path, figures: list[FigureUse], index_text: str) -> list[FigureReview]:
    byte_values: list[int] = []
    raw_assets: dict[str, tuple[int | None, int | None, int | None]] = {}
    for figure in figures:
        asset = resolve_asset(root, figure.path)
        size = asset.stat().st_size if asset.exists() and asset.is_file() else None
        width, height = image_size(asset) if asset.exists() and asset.suffix.lower() in RASTER_SUFFIXES else (None, None)
        raw_assets[figure.path] = (size, width, height)
        if size:
            byte_values.append(size)
    median_bytes = median(byte_values)

    reviews: list[FigureReview] = []
    for figure in figures:
        asset_bytes, width, height = raw_assets.get(figure.path, (None, None, None))
        context = "\n".join([figure.path, figure.caption, figure.before, figure.after, index_rows_for(index_text, figure.path)])
        score = 70
        reasons: list[str] = []
        role = infer_role(context)

        if not asset_bytes:
            score -= 35
            reasons.append("asset missing or unreadable")
        elif median_bytes and asset_bytes < median_bytes * 0.45:
            score -= 7
            reasons.append("small file compared with other visuals; verify it is not visually sparse")
        if width and height:
            if width < 900 or height < 600:
                score -= 8
                reasons.append(f"small raster dimensions {width}x{height}")
            aspect = width / max(height, 1)
            if aspect > 2.8 or aspect < 0.45:
                score -= 6
                reasons.append(f"unusual aspect ratio {aspect:.2f}")

        if not figure.caption:
            score -= 20
            reasons.append("missing caption")
        elif caption_specificity(figure.caption) < 2:
            score -= 12
            reasons.append("caption lacks specific value, variable, or conclusion")
        if not figure.label:
            score -= 10
            reasons.append("missing label")
        if not has_specific_interpretation(figure.after):
            score -= 12
            reasons.append("nearby post-figure interpretation is weak or generic")
        if generic_visual_prose(figure.before) or generic_visual_prose(figure.after):
            score -= 8
            reasons.append("nearby prose contains mechanical visual-loop wording")

        lower = context.lower()
        path_lower = Path(figure.path).stem.lower()
        weak_name = any(term in path_lower for term in WEAK_FILENAME_TERMS)
        flat_or_no_gain = has_any(context, ["未发现", "相同", "缩短量为 0", "缩短量为0", "无变化", "均为0", "水平", "几乎不变"])
        table_nearby = has_any(context, ["表", "table", "结果见", "清单"])
        if weak_name and flat_or_no_gain and table_nearby:
            score -= 20
            reasons.append("low-value comparison: visual appears to repeat a no-improvement table/prose conclusion")
        elif weak_name and flat_or_no_gain:
            score -= 14
            reasons.append("low-value scan: the visual supports a negative/no-change conclusion")
        if "q4_candidate_length_scan" in path_lower:
            score -= 16
            reasons.append("low-value Q4 candidate scan; replace by an annotated branch comparison or keep it outside the paper as a support file")
        if "heatmap" in lower and not has_any(context, ["colorbar", "颜色", "色标", "峰值", "集中", "分布"]):
            score -= 8
            reasons.append("heatmap needs explicit color-scale interpretation")
        if role == "search" and not has_any(context, ["局部", "放大", "二分", "细化", "阈值", "临界"]):
            score -= 7
            reasons.append("search visual lacks coarse-to-fine or local-threshold explanation")

        score = max(0, min(100, score))
        recommendation = recommend_figure(score, reasons, figure.path)
        reviews.append(
            FigureReview(
                figure=figure.path,
                label=figure.label,
                caption=figure.caption,
                qid=qid(context),
                role=role,
                score=score,
                recommendation=recommendation,
                reasons=reasons or ["claim-bearing visual with adequate caption and nearby interpretation"],
                asset_bytes=asset_bytes,
                width=width,
                height=height,
            )
        )
    return reviews


def score_paper(
    text: str,
    figures: list[FigureUse],
    figure_reviews: list[FigureReview],
    mechanical: list[MechanicalSentence],
    pdf_metrics: dict[str, Any],
    visual_audit: dict[str, Any],
    asset_audit: dict[str, Any],
) -> dict[str, Any]:
    abstract = abstract_text(text)
    equations = len(re.findall(r"\\begin\{equation\}|\\\[|\\begin\{align", text))
    final_formula_markers = len(re.findall(r"\\(?:boxed|fbox|bm|boldsymbol|mathbf)\s*\{", text))
    abstract_numbers = len(re.findall(r"\d+(?:\.\d+)?", abstract))
    abstract_bold = len(re.findall(r"\\(?:textbf|bfseries)\b", abstract))
    sections = len(re.findall(r"\\section\{", text))
    subsections = len(re.findall(r"\\subsection\{", text))
    table_count = len(re.findall(r"\\caption\{", text)) - len(figures)
    avg_figure_score = round(sum(item.score for item in figure_reviews) / max(len(figure_reviews), 1), 1)
    weak_count = sum(1 for item in figure_reviews if item.score < 58 or item.recommendation in {"REDRAW", "KEEP_AS_SUPPORT", "DROP"})

    reasoning = 72
    reasoning += min(10, sections * 2)
    reasoning += min(8, subsections)
    reasoning += min(8, equations // 3)
    reasoning -= min(12, max(0, mechanical_sentences_in_reasoning(mechanical) - 3) * 2)
    reasoning = clamp(reasoning)

    visual = avg_figure_score
    visual += min(8, len(figure_reviews) // 2)
    visual -= min(18, weak_count * 4)
    visual = clamp(visual)

    abstract_score = 62
    abstract_score += min(18, abstract_numbers * 2)
    abstract_score += min(12, abstract_bold * 4)
    if abstract_numbers >= 5 and abstract_bold < 2:
        abstract_score -= 14
    abstract_score = clamp(abstract_score)

    formula_score = 68
    if equations >= 4:
        formula_score += 8
    if equations >= 8:
        formula_score += 4
    formula_score += min(12, final_formula_markers * 6)
    if equations >= 12 and final_formula_markers == 0:
        formula_score -= 15
    if final_formula_markers > max(3, equations // 4):
        formula_score -= min(10, (final_formula_markers - max(3, equations // 4)) * 2)
    formula_score = clamp(formula_score)

    polish = 84
    polish -= min(24, len(mechanical) * 3)
    polish -= min(16, weak_count * 3)
    polish -= min(10, int(pdf_metrics.get("overfull_hbox", 0)) // 2)
    polish = clamp(polish)

    if visual_audit.get("verdict") == "FAIL":
        visual -= 8
        polish -= 4
    if asset_audit.get("verdict") == "FAIL":
        visual -= 8
        polish -= 4

    contest_final = round(
        0.27 * reasoning
        + 0.25 * visual
        + 0.16 * abstract_score
        + 0.14 * formula_score
        + 0.18 * polish
    )
    return {
        "contest_final_score": int(clamp(contest_final)),
        "reasoning_chain": int(clamp(reasoning)),
        "visual_value": int(clamp(visual)),
        "abstract_result_ledger": int(clamp(abstract_score)),
        "formula_emphasis": int(clamp(formula_score)),
        "polish": int(clamp(polish)),
        "avg_figure_score": avg_figure_score,
        "equation_count": equations,
        "final_formula_markers": final_formula_markers,
        "abstract_numbers": abstract_numbers,
        "abstract_bold_markers": abstract_bold,
        "table_count_estimate": max(0, table_count),
    }


def review_pdf_polish(root: Path, paper: Path) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    pdf = paper.with_suffix(".pdf")
    if not pdf.exists():
        fallback = paper.parent / "main_final.pdf"
        if fallback.exists():
            pdf = fallback
    log = paper.with_suffix(".log")
    metrics: dict[str, Any] = {
        "pdf": rel(root, pdf) if pdf.exists() else "",
        "pdf_exists": pdf.exists(),
        "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0,
        "page_count": pdf_page_count(pdf) if pdf.exists() else 0,
        "log": rel(root, log) if log.exists() else "",
        "overfull_hbox": 0,
        "underfull_hbox": 0,
    }
    if log.exists():
        log_text = read_text(log)
        metrics["overfull_hbox"] = len(re.findall(r"Overfull \\hbox", log_text))
        metrics["underfull_hbox"] = len(re.findall(r"Underfull \\hbox", log_text))
        if metrics["overfull_hbox"] >= 8:
            findings.append(
                Finding(
                    level="WARN",
                    axis="pdf_polish",
                    return_phase="paper",
                    finding=f"LaTeX log has {metrics['overfull_hbox']} overfull hbox warnings; tables, captions, or long file names may overflow.",
                    recommendation="inspect the compiled PDF pages with long tables/captions and shorten columns or use smaller tabular layout.",
                )
            )
    if not pdf.exists():
        findings.append(
            Finding(
                level="WARN",
                axis="pdf_polish",
                return_phase="paper",
                finding="compiled PDF was not found next to the reviewed paper source.",
                recommendation="compile the reviewed paper copy and run a visual PDF check before delivery.",
            )
        )
    return metrics, findings


def mechanical_sentences(text: str) -> list[MechanicalSentence]:
    out: list[MechanicalSentence] = []
    buffer = ""
    start_line = 1
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = clean_latex(raw_line)
        if not line:
            continue
        if not buffer:
            start_line = line_no
        buffer = (buffer + " " + line).strip()
        sentences = re.split(r"(?<=[。！？；;])\s*", buffer)
        complete = sentences[:-1]
        buffer = sentences[-1] if sentences else ""
        for sentence in complete:
            sentence = sentence.strip()
            if not sentence:
                continue
            reason = mechanical_reason(sentence)
            if reason:
                out.append(MechanicalSentence(line=start_line, text=sentence, reason=reason))
            start_line = line_no
    if buffer.strip():
        reason = mechanical_reason(buffer.strip())
        if reason:
            out.append(MechanicalSentence(line=start_line, text=buffer.strip(), reason=reason))
    return dedupe_mechanical(out)


def mechanical_reason(sentence: str) -> str:
    for phrase in MECHANICAL_PHRASES:
        if phrase in sentence:
            if phrase == "本文绘制图" and caption_specificity(sentence) >= 2 and not generic_visual_prose(sentence):
                continue
            return f"contains template phrase `{phrase}`"
    if generic_visual_prose(sentence):
        return "generic visual-loop sentence without enough figure-specific interpretation"
    return ""


def generic_visual_prose(text: str) -> bool:
    compact_text = re.sub(r"\s+", "", text)
    if not compact_text:
        return False
    if "由图" in compact_text and "可见" in compact_text and "这说明" in compact_text:
        return caption_specificity(compact_text) < 3 or count_terms(compact_text, GENERIC_VISUAL_TERMS) >= 3
    if "为展示本节结论" in compact_text or "关键形态或趋势" in compact_text:
        return True
    if "为验证临界接触位置并解释停止或边界判定" in compact_text:
        return True
    return False


def has_specific_interpretation(text: str) -> bool:
    if not text:
        return False
    return (
        count_terms(text, ["由图", "从图", "可见", "表明", "说明", "验证", "因此", "对应", "支撑"]) >= 2
        and caption_specificity(text) >= 2
    )


def caption_specificity(text: str) -> int:
    score = 0
    score += min(2, len(re.findall(r"\d+(?:\.\d+)?", text)))
    score += min(2, count_terms(text, SPECIFIC_TERMS))
    score += 1 if re.search(r"[A-Za-z_]\w*|\\[a-zA-Z]+|[α-ωΑ-Ω]", text) else 0
    score += 1 if has_any(text, ["取", "得到", "决定", "未发现", "发生", "集中", "误差", "残差"]) else 0
    return score


def infer_role(context: str) -> str:
    lower = context.lower()
    if has_any(lower, ["flow", "流程", "算法", "步骤", "递推"]):
        return "operation"
    if has_any(lower, ["geometry", "schematic", "几何", "构型", "示意"]):
        return "define"
    if has_any(lower, ["zoom", "局部", "放大"]):
        return "zoom"
    if has_any(lower, ["candidate", "compare", "对比", "候选", "扫描", "scan", "search", "搜索"]):
        return "search"
    if has_any(lower, ["audit", "validate", "validation", "残差", "验证", "审计"]):
        return "validate"
    if has_any(lower, ["heatmap", "热图", "热力"]):
        return "distribution"
    return "result"


def recommend_figure(score: int, reasons: list[str], path: str) -> str:
    text = " ".join(reasons).lower()
    if "asset missing" in text or "missing caption" in text:
        return "REDRAW"
    if "q4 candidate" in text:
        return "REDRAW"
    if "low-value" in text and score < 55:
        return "KEEP_AS_SUPPORT"
    if score < 45:
        return "REDRAW"
    if score < 62:
        return "REDRAW"
    return "KEEP"


def abstract_text(text: str) -> str:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
    return match.group(1) if match else ""


def latex_command_arg(text: str, command: str) -> str:
    marker = "\\" + command
    start = text.find(marker)
    if start < 0:
        return ""
    brace = text.find("{", start + len(marker))
    if brace < 0:
        return ""
    depth = 0
    for idx in range(brace, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : idx]
    return ""


def clean_latex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", text)
    text = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", r" \1 ", text)
    text = re.sub(r"\\(?:ref|eqref|label|cite|caption|textbf|emph|boxed|mathbf|boldsymbol|bm)\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    text = text.replace("~", "")
    return re.sub(r"\s+", " ", text).strip()


def qid(text: str) -> str:
    match = re.search(r"\bq([1-9])\b|问题([一二三四五六七八九])", text, flags=re.I)
    if not match:
        return ""
    if match.group(1):
        return f"Q{match.group(1)}"
    mapping = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
    return f"Q{mapping.get(match.group(2), '')}"


def index_rows_for(index_text: str, figure_path: str) -> str:
    name = Path(figure_path.replace("\\", "/")).name.lower()
    rows = [line for line in index_text.splitlines() if name and name in line.lower()]
    return "\n".join(rows)


def resolve_asset(root: Path, figure_path: str) -> Path:
    path = Path(figure_path)
    if path.is_absolute():
        return path
    candidate = (root / "paper" / path).resolve()
    if candidate.exists():
        return candidate
    candidate = (root / path).resolve()
    if candidate.exists():
        return candidate
    return (root / "paper" / path).resolve()


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        data = path.read_bytes()
    except OSError:
        return None, None
    suffix = path.suffix.lower()
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_size(data)
    if suffix == ".webp" and len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
    return None, None


def jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    idx = 2
    while idx + 9 < len(data):
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1]
        idx += 2
        if marker in {0xD8, 0xD9}:
            continue
        if idx + 2 > len(data):
            break
        length = int.from_bytes(data[idx : idx + 2], "big")
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            if idx + 7 <= len(data):
                height = int.from_bytes(data[idx + 3 : idx + 5], "big")
                width = int.from_bytes(data[idx + 5 : idx + 7], "big")
                return width, height
        idx += max(length, 2)
    return None, None


def pdf_page_count(pdf: Path) -> int:
    try:
        import pypdf  # type: ignore

        return len(pypdf.PdfReader(str(pdf)).pages)
    except Exception:
        try:
            data = pdf.read_bytes()
        except OSError:
            return 0
        return len(re.findall(rb"/Type\s*/Page\b", data))


def infer_paper(root: Path) -> Path:
    candidates = [
        "paper/main_final_v045_rewrite.tex",
        "paper/main_final_repaired.tex",
        "paper/main_final.tex",
        "paper/main.tex",
        "paper/main.typ",
        "paper/main.md",
    ]
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    paper_dir = root / "paper"
    for suffix in ["*.tex", "*.typ", "*.md"]:
        matches = sorted(paper_dir.glob(suffix)) if paper_dir.exists() else []
        if matches:
            return matches[0]
    return root / candidates[0]


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    scorecard = payload.get("scorecard") or payload.get("metrics", {}).get("scorecard", {})
    lines = [
        "# Mira Paper Quality Review",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Paper: `{payload['paper']}`",
        f"- Contest-final score: **{payload.get('metrics', {}).get('contest_final_score', scorecard.get('contest_final_score', 'n/a'))}/100**",
        "",
        "## Scorecard",
        "",
        "| Axis | Score | Meaning |",
        "|---|---:|---|",
    ]
    labels = {
        "reasoning_chain": "推理链条是否连续、细节是否展开",
        "visual_value": "图表是否真正承载结论而非装饰",
        "abstract_result_ledger": "摘要是否像结果账本并突出关键结果",
        "formula_emphasis": "结论公式是否被选择性清晰标出",
        "polish": "终稿观感、机械痕迹和 PDF 排版风险",
    }
    for key, label in labels.items():
        lines.append(f"| {key} | {scorecard.get(key, '')} | {label} |")
    lines.extend(["", "## Metrics", "", "| Metric | Value |", "|---|---:|"])
    for key, value in payload["metrics"].items():
        if isinstance(value, dict):
            continue
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")

    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Level | Axis | Return to | Finding | Recommendation | Evidence |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in payload["findings"]:
        lines.append(
            "| {level} | {axis} | {phase} | {finding} | {rec} | {evidence} |".format(
                level=item["level"],
                axis=item["axis"],
                phase=item["return_phase"],
                finding=escape(item["finding"]),
                rec=escape(item["recommendation"]),
                evidence=escape(item.get("evidence", "")),
            )
        )
    if not payload["findings"]:
        lines.append("| INFO | paper_quality | - | no blocking or warning findings | keep current final-review chain | |")

    lines.extend(
        [
            "",
            "## Figure Decisions",
            "",
            "| Figure | Q | Role | Score | Decision | Main reasons |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for item in payload["figure_reviews"]:
        lines.append(
            "| `{figure}` | {qid} | {role} | {score} | {decision} | {reasons} |".format(
                figure=item["figure"],
                qid=item.get("qid") or "-",
                role=item["role"],
                score=item["score"],
                decision=item["recommendation"],
                reasons=escape("; ".join(item["reasons"][:4])),
            )
        )

    lines.extend(
        [
            "",
            "## Mechanical Prose Candidates",
            "",
            "| Line | Reason | Sentence |",
            "|---:|---|---|",
        ]
    )
    for item in payload["mechanical_sentences"]:
        lines.append(f"| {item['line']} | {escape(item['reason'])} | {escape(compact(item['text'], 120))} |")
    if not payload["mechanical_sentences"]:
        lines.append("| - | - | no obvious mechanical repair prose detected |")

    lines.extend(
        [
            "",
            "## Next Upgrade Focus",
            "",
            "- If `mechanical_prose` appears: upgrade paper polishing so automatic repair sentences must be figure-specific, not template-like.",
            "- If `figure_effectiveness` appears: return to implementation storyboard and redraw weak visuals before adding more prose.",
            "- If `figure_value` appears: decide whether the figure earns main-text space; otherwise keep it as a separate result file, replace it, or drop it.",
            "- If `pdf_polish` appears: inspect the compiled PDF pages, not only the LaTeX source.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve_path(root: Path, value: str | Path | None) -> Path:
    if value is None:
        return root
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def clamp(value: float, lower: int = 0, upper: int = 100) -> float:
    return max(lower, min(upper, value))


def mechanical_sentences_in_reasoning(mechanical: list[MechanicalSentence]) -> int:
    return sum(1 for item in mechanical if "图" in item.text or "说明" in item.text or "展示" in item.text)


def dedupe_mechanical(items: list[MechanicalSentence]) -> list[MechanicalSentence]:
    seen: set[str] = set()
    out: list[MechanicalSentence] = []
    for item in items:
        key = re.sub(r"\s+", "", item.text)[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
