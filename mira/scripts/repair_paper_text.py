#!/usr/bin/env python3
"""Apply conservative paper-text repairs for Mira contest-final drafts.

Default behavior writes a repaired copy and leaves the original paper unchanged.
The script only performs low-risk, problem-agnostic figure-text loop repairs and
missing figure references. It never changes numeric values or source data.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Repair:
    kind: str
    detail: str


@dataclass
class FigureBlock:
    path: str
    block: str
    start: int
    end: int
    label: str
    caption: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper source, default inferred from paper/main_final.tex")
    parser.add_argument("--out", help="Output paper copy, default paper/main_final_repaired.tex")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite --paper in place")
    parser.add_argument("--write-report", default="revisions/paper_repair_report.md")
    parser.add_argument("--write-json", default="revisions/paper_repair_report.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper = resolve(root, args.paper) if args.paper else infer_paper(root)
    out = paper if args.overwrite else (resolve(root, args.out) if args.out else root / "paper" / "main_final_repaired.tex")
    text = read_text(paper)
    if not text:
        raise SystemExit(f"paper source not found or empty: {paper}")

    repaired, repairs = repair_text(text)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(repaired, encoding="utf-8")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper": rel(root, paper),
        "out": rel(root, out),
        "repairs": [asdict(item) for item in repairs],
        "metrics": {
            "repairs": len(repairs),
            "by_kind": count_by_kind(repairs),
            "changed": repaired != text,
        },
        "notes": [
            "Numeric values are not changed.",
            "This script repairs writing structure only. Rerun visual_reasoning_audit.py on the repaired copy.",
            "Review the repaired copy before replacing the original paper.",
        ],
    }
    report = resolve(root, args.write_report)
    data = resolve(root, args.write_json)
    report.parent.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(payload), encoding="utf-8")
    data.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(markdown(payload))
    print(f"INFO: wrote {rel(root, out)}")
    print(f"INFO: wrote {rel(root, report)}")
    print(f"INFO: wrote {rel(root, data)}")
    return 0


def repair_text(text: str) -> tuple[str, list[Repair]]:
    return repair_figure_text_loops(text)


def repair_figure_text_loops(text: str) -> tuple[str, list[Repair]]:
    figures = figure_blocks(text)
    if not figures:
        return text, []
    referenced = set(re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", text))
    inserts: list[tuple[int, str, Repair]] = []
    for figure in figures:
        if not figure.label:
            continue
        before = plain_window(text[max(0, figure.start - 800) : figure.start])
        after = plain_window(text[figure.end : figure.end + 900])
        has_intro = count_terms(before, ["如下图", "如图", "见图", "图示", "为刻画", "为说明", "为验证", "为比较", "为展示", "为分析", "示意", "绘制"]) > 0
        has_after = count_terms(after, ["由图", "从图", "可以看出", "可见", "表明", "说明", "验证", "因此", "据此", "进一步", "对应", "支撑", "决定"]) > 0
        purpose = purpose_from_caption(figure.caption, figure.label)
        if not has_intro:
            sentence = f"\n为{purpose}，本文绘制图~\\ref{{{figure.label}}}。\n"
            inserts.append((figure.start, sentence, Repair("figure_pre_intro", f"added pre-figure purpose for {figure.label}")))
        if not has_after or figure.label not in referenced:
            summary = caption_summary(figure.caption)
            sentence = f"\n由图~\\ref{{{figure.label}}}可见，{summary}。这说明{purpose}。\n"
            detail = "added post-figure interpretation"
            if figure.label not in referenced:
                detail += " and missing reference"
            inserts.append((figure.end, sentence, Repair("figure_post_interpretation", f"{detail} for {figure.label}")))
    if not inserts:
        return text, []
    out_parts: list[str] = []
    cursor = 0
    repairs: list[Repair] = []
    for pos, insert, repair in sorted(inserts, key=lambda item: item[0]):
        out_parts.append(text[cursor:pos])
        out_parts.append(insert)
        cursor = pos
        repairs.append(repair)
    out_parts.append(text[cursor:])
    return "".join(out_parts), repairs


def figure_blocks(text: str) -> list[FigureBlock]:
    out: list[FigureBlock] = []
    for match in re.finditer(r"\\begin\{figure\}.*?\\end\{figure\}", text, flags=re.S):
        block = match.group(0)
        path_match = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block)
        label_match = re.search(r"\\label\{([^}]+)\}", block)
        caption_match = re.search(r"\\caption\{([^}]*)\}", block, flags=re.S)
        out.append(
            FigureBlock(
                path=path_match.group(1) if path_match else "<unknown>",
                block=block,
                start=match.start(),
                end=match.end(),
                label=label_match.group(1) if label_match else "",
                caption=caption_match.group(1).strip() if caption_match else Path(path_match.group(1)).stem if path_match else "该图",
            )
        )
    return out


def purpose_from_caption(caption: str, label: str) -> str:
    text = strip_latex(caption + " " + label)
    if any(term in text for term in ["流程", "框架", "flow"]):
        return "说明各子问题之间的计算依赖和求解顺序"
    if any(term in text for term in ["几何", "参数", "构型", "相切", "圆弧"]):
        return "明确几何对象、变量关系和后续约束来源"
    if any(term in text for term in ["碰撞", "临界", "局部", "放大"]):
        return "验证临界接触位置并解释停止或边界判定"
    if any(term in text for term in ["搜索", "扫描", "候选", "螺距"]):
        return "展示参数搜索过程并支撑最终取值"
    if any(term in text for term in ["速度", "系数", "热图", "上限"]):
        return "展示速度传递规律并支撑速度上限计算"
    if any(term in text for term in ["残差", "审计", "误差"]):
        return "检验关键约束和数值精度"
    return "展示本节结论所依赖的关键形态或趋势"


def caption_summary(caption: str) -> str:
    text = strip_latex(caption)
    text = re.sub(r"\s+", " ", text).strip(" 。；;，,")
    parts = [part.strip(" ，,") for part in re.split(r"[。；;]", text) if part.strip(" ，,")]
    if len(parts) >= 2 and len(parts[0]) <= 14:
        return parts[1]
    return (parts[0] if parts else text) or "该图给出了本节关键证据"


def strip_latex(text: str) -> str:
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", text)
    text = text.replace("~", "")
    return text


def plain_window(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def count_by_kind(repairs: list[Repair]) -> dict[str, int]:
    out: dict[str, int] = {}
    for repair in repairs:
        out[repair.kind] = out.get(repair.kind, 0) + 1
    return dict(sorted(out.items()))


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Paper Repair Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Paper: `{payload['paper']}`",
        f"- Output: `{payload['out']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Repairs", "", "| Kind | Detail |", "|---|---|"])
    for item in payload["repairs"]:
        lines.append(f"| {item['kind']} | {escape(item['detail'])} |")
    lines.extend(["", "## Notes", ""])
    for note in payload["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def infer_paper(root: Path) -> Path:
    for rel_path in [
        "paper/main_final.tex",
        "paper/main.tex",
        "paper/main_final_checked.tex",
        "paper/main.typ",
        "paper/main.md",
    ]:
        candidate = root / rel_path
        if candidate.exists():
            return candidate
    return root / "paper" / "main_final.tex"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
