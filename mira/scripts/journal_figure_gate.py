#!/usr/bin/env python3
"""Audit journal-grade figure aesthetics for Mira contest-final papers."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    level: str
    axis: str
    message: str


MULTIPANEL_TERMS = [
    "multi-panel",
    "multipanel",
    "panel",
    "composite",
    "subplot",
    "mosaic",
    "GridSpec",
    "subfigure",
    "minipage",
    "(a)",
    "(b)",
    "（a）",
    "（b）",
    "多面板",
    "组合图",
    "分图",
    "子图",
]

CALLOUT_TERMS = [
    "annotate",
    "arrow",
    "arrowprops",
    "callout",
    "axvspan",
    "axhspan",
    "shade",
    "bracket",
    "threshold",
    "inset",
    "zoom",
    "mark_inset",
    "ConnectionPatch",
    "标注",
    "箭头",
    "阴影",
    "高亮",
    "局部放大",
    "阈值",
    "临界",
]

STYLE_TERMS = [
    "visual_style",
    "apply_mira_style",
    "MIRA_PALETTE",
    "JOURNAL_PALETTE",
    "save_mira_figure",
    "dpi=300",
    "dpi = 300",
    "bbox_inches",
    "font.sans-serif",
    "label_panel",
    "create_journal_multipanel",
]

CORE_TERMS = [
    "core",
    "overview",
    "storyboard",
    "mechanism",
    "framework",
    "pipeline",
    "decision",
    "boundary",
    "robustness",
    "batch",
    "核心图",
    "总览",
    "机制",
    "框架",
    "流程",
    "决策",
    "边界",
    "稳健",
]

DEFAULT_STYLE_TERMS = [
    "plt.plot(",
    "plt.scatter(",
    "plt.bar(",
    "plt.savefig(",
    "viridis",
    "jet",
    "rainbow",
]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    metrics = collect_metrics(root, args)
    findings = review(metrics)
    payload = {
        "generated_at": now(),
        "root": str(root),
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for key, value in metrics.items():
        _print(f"METRIC: {key}={value}")
    for finding in findings:
        _print(f"{finding.level}: [{finding.axis}] {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve(root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    files = paper_files(root, args.paper)
    paper_text = "\n".join(read_text(path) for path in files)
    figure_index = read_text(root / "figures" / "figure_index.md")
    diagram_index = read_text(root / "diagrams" / "diagram_index.md")
    storyboard = read_text(root / "planning" / "figure_storyboard.md")
    paper_signal = "\n".join([paper_text, figure_index, diagram_index, storyboard])
    code_text = collect_code_text(root)
    all_signal = paper_signal + "\n" + code_text
    figures = media_files(root / "figures")
    diagrams = media_files(root / "diagrams")
    dimensions = {rel(root, path): image_size(path) for path in figures + diagrams if path.suffix.lower() in {".png", ".jpg", ".jpeg"}}
    low_res = [path for path, size in dimensions.items() if size and (size[0] < 1200 or size[1] < 800)]
    tiny = [path for path, size in dimensions.items() if size and (size[0] < 800 or size[1] < 500)]
    figure_blocks = re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", paper_text, flags=re.S)
    multipanel_blocks = [block for block in figure_blocks if len(re.findall(r"\\includegraphics", block)) >= 2 or count_terms(block, MULTIPANEL_TERMS) >= 2]
    return {
        "paper_files": [rel(root, path) for path in files],
        "included_images": len(re.findall(r"\\includegraphics", paper_text)),
        "figure_file_count": len(figures),
        "diagram_file_count": len(diagrams),
        "image_dimensions": dimensions,
        "low_resolution_images": low_res,
        "tiny_images": tiny,
        "figure_blocks": len(figure_blocks),
        "multipanel_blocks": len(multipanel_blocks),
        "multipanel_terms": count_terms(all_signal, MULTIPANEL_TERMS),
        "callout_terms": count_terms(all_signal, CALLOUT_TERMS),
        "style_terms": count_terms(all_signal, STYLE_TERMS),
        "core_figure_terms": count_terms(all_signal, CORE_TERMS),
        "default_style_terms": count_terms(code_text, DEFAULT_STYLE_TERMS),
        "uses_visual_style_module": "visual_style" in code_text or "apply_mira_style" in code_text,
        "uses_journal_helpers": "create_journal_multipanel" in code_text or "JOURNAL_PALETTE" in code_text,
        "has_figure_storyboard": bool(storyboard.strip()),
        "indexed_visual_rows": count_index_rows(figure_index) + count_index_rows(diagram_index),
        "core_named_files": [rel(root, path) for path in figures + diagrams if has_term(path.name, CORE_TERMS + MULTIPANEL_TERMS)],
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not metrics["paper_files"]:
        findings.append(Finding("FAIL", "paper_source", "no final paper source file was found"))
        return findings
    visual_count = metrics["figure_file_count"] + metrics["diagram_file_count"]
    if visual_count == 0:
        findings.append(Finding("WARN", "visual_set", "no figure or diagram files found"))
        return findings

    if visual_count >= 6 and metrics["multipanel_blocks"] == 0 and metrics["multipanel_terms"] < 4:
        findings.append(Finding("WARN", "multipanel", "figure set is large but no clear multi-panel/composite figure signal was detected"))
    if visual_count >= 6 and metrics["core_figure_terms"] < 4 and not metrics["core_named_files"]:
        findings.append(Finding("WARN", "visual_center", "no obvious core/overview/mechanism/boundary figure signal; add at least one eye-catching evidence-bearing core figure"))
    if metrics["callout_terms"] < 4 and visual_count >= 5:
        findings.append(Finding("WARN", "callouts", "few arrows, callouts, shaded windows, thresholds, or zoom markers detected; important figures may lack visual focus"))
    if not metrics["uses_visual_style_module"] and metrics["style_terms"] < 3:
        findings.append(Finding("WARN", "style_consistency", "plotting code does not visibly use Mira visual style helpers or an equivalent style system"))
    if metrics["default_style_terms"] >= 8 and metrics["style_terms"] < metrics["default_style_terms"]:
        findings.append(Finding("WARN", "default_style", "many default plotting calls detected; replace default-looking charts with styled, annotated figures"))
    if metrics["tiny_images"]:
        findings.append(Finding("WARN", "resolution", "some images are too small for journal-grade print use: " + ", ".join(metrics["tiny_images"][:5])))
    elif metrics["low_resolution_images"] and visual_count >= 6:
        findings.append(Finding("WARN", "resolution", "some images may be low resolution for A4 print: " + ", ".join(metrics["low_resolution_images"][:5])))
    if visual_count >= 6 and not metrics["has_figure_storyboard"]:
        findings.append(Finding("WARN", "storyboard", "journal-grade figure planning needs planning/figure_storyboard.md with roles and visual focus notes"))
    if visual_count >= 8 and metrics["indexed_visual_rows"] < max(4, visual_count // 2):
        findings.append(Finding("WARN", "figure_index", "figure/diagram index is thin relative to the number of visuals; record roles, source artifacts, and takeaway"))
    return findings


def collect_code_text(root: Path) -> str:
    chunks: list[str] = []
    for folder in [root / "code", root / "scripts"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            chunks.append(read_text(path))
    return "\n".join(chunks)


def media_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in suffixes)


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        if path.suffix.lower() == ".png":
            with path.open("rb") as handle:
                header = handle.read(24)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                return struct.unpack(">II", header[16:24])
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            with path.open("rb") as handle:
                data = handle.read()
            return jpeg_size(data)
    except OSError:
        return None
    return None


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(data[i + 3 : i + 5], "big")
            width = int.from_bytes(data[i + 5 : i + 7], "big")
            return width, height
        length = int.from_bytes(data[i : i + 2], "big")
        i += max(length, 2)
    return None


def paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    if paper_arg:
        path = resolve(root, paper_arg)
        return [path] if path.exists() else []
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_final.tex",
        paper_dir / "main.tex",
        paper_dir / "main.typ",
        paper_dir / "main.md",
    ]
    for path in candidates:
        if path.exists():
            files = [path]
            for pattern in ["*.tex", "*.typ", "*.md"]:
                files.extend(sorted((paper_dir / "sections").glob(pattern)) if (paper_dir / "sections").exists() else [])
            return dedupe(files)
    return []


def dedupe(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def has_term(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def count_index_rows(text: str) -> int:
    return len([line for line in text.splitlines() if "|" in line and not re.match(r"\s*\|?\s*-+\s*\|", line)])


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Journal Figure Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(value)} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    else:
        lines.append("| INFO | journal_figure | no findings |")
    lines.append("")
    return "\n".join(lines)


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


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _print(text: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(text, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper tex/typ/md path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())

