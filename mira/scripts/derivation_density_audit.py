#!/usr/bin/env python3
"""Audit derivation density and math continuity in Mira contest-final papers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"\\section\*?\{([^}]*)\}", re.S)
DISPLAY_MATH_RE = re.compile(
    r"\\\[(.*?)\\\]|\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|split|cases|array)\}(.*?)\\end\{\2\}",
    re.S,
)
MATH_MARKER_RE = re.compile(
    r"\\\(|\\\[|\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|split|cases|array)\}|(?<!\\)\$(?!\$)"
)
TABLE_RE = re.compile(r"\\begin\{(?:table|tabular|longtable|tabularx)\}", re.I)
FIGURE_RE = re.compile(r"\\begin\{figure\}|\\includegraphics", re.I)
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cite|citep|citet)\{", re.I)
ALGO_RE = re.compile(r"\\begin\{(?:algorithm|algorithmic|lstlisting|verbatim)\}", re.I)

EXEMPT_TITLE_RE = re.compile(r"参考文献|附录|结论|可复现|文件清单|模型评价")
EVIDENCE_TITLE_RE = re.compile(
    r"问题|模型|求解|结果|灵敏度|稳健|鲁棒|误差|检验|验证|可信|证据|算法|效率|复杂度|假设|放宽|创新|贡献|工程|落地|执行|讨论|复核"
)
FORMULA_EXPECT_TITLE_RE = re.compile(
    r"问题|模型|求解|灵敏度|稳健|鲁棒|可信|证据|算法|效率|复杂度|假设|放宽|创新|贡献|工程|落地|执行|讨论|复核"
)


@dataclass
class Finding:
    level: str
    axis: str
    message: str


@dataclass
class SectionMetric:
    index: int
    title: str
    zh_chars: int
    paragraphs: int
    math_markers: int
    display_math: int
    tables: int
    figures: int
    refs: int
    algorithms: int
    evidence_density: float
    pure_prose_runs: int


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    files = paper_files(root, args.paper)
    metrics, findings = audit(root, files)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper_files": [rel(root, path) for path in files],
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        out = resolve(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for key, value in metrics.items():
        if key != "sections":
            _print(f"METRIC: {key}={value}")
    for item in findings:
        _print(f"{item.level}: [{item.axis}] {item.message}")
    return 1 if payload["verdict"] == "FAIL" else 0


def audit(root: Path, files: list[Path]) -> tuple[dict[str, Any], list[Finding]]:
    if not files:
        return {}, [Finding("FAIL", "paper", "no paper source found")]

    text = "\n".join(read_text(path) for path in files)
    clean = strip_comments(text)
    sections = section_metrics(clean)
    findings: list[Finding] = []

    if not sections:
        return {"section_count": 0}, [Finding("FAIL", "structure", "no top-level sections detected")]

    main_sections = [s for s in sections if not EXEMPT_TITLE_RE.search(s.title)]
    tail_start = max(0, int(len(main_sections) * 0.62))
    tail_sections = main_sections[tail_start:]
    tail_zh = sum(s.zh_chars for s in tail_sections)
    tail_display = sum(s.display_math for s in tail_sections)
    tail_math = sum(s.math_markers for s in tail_sections)
    tail_evidence = sum(s.math_markers + 2 * s.display_math + 2 * s.tables + 2 * s.figures + s.refs for s in tail_sections)
    tail_density = tail_evidence * 1000 / tail_zh if tail_zh else 0.0
    total_zh = sum(s.zh_chars for s in main_sections)
    total_display = sum(s.display_math for s in main_sections)
    total_math = sum(s.math_markers for s in main_sections)

    weak_sections: list[SectionMetric] = []
    prose_sections: list[SectionMetric] = []
    for section in main_sections:
        if section.zh_chars < 700:
            continue
        if EXEMPT_TITLE_RE.search(section.title):
            continue
        needs_anchor = bool(EVIDENCE_TITLE_RE.search(section.title))
        needs_formula = bool(FORMULA_EXPECT_TITLE_RE.search(section.title))
        has_anchor = section.display_math + section.tables + section.figures + section.algorithms > 0
        if needs_formula and section.zh_chars >= 1000 and section.display_math == 0:
            findings.append(
                Finding(
                    "WARN",
                    "display_derivation_anchor",
                    f"section {section.index} `{section.title}` is long ({section.zh_chars} Chinese chars) but has no display equation or derivation block",
                )
            )
        if needs_anchor and not has_anchor and section.evidence_density < 12:
            weak_sections.append(section)
        if section.zh_chars >= 1200 and section.pure_prose_runs >= 4 and section.display_math == 0:
            prose_sections.append(section)

    if tail_zh >= 5000 and tail_display == 0:
        findings.append(
            Finding(
                "FAIL",
                "tail_derivation_collapse",
                f"tail sections contain {tail_zh} Chinese chars but no display equations; formulas and derivations are front-loaded",
            )
        )
    elif tail_zh >= 2500 and tail_display == 0 and tail_density < 22:
        findings.append(
            Finding(
                "FAIL",
                "tail_derivation_collapse",
                f"tail sections contain {tail_zh} Chinese chars but no display equations and low evidence density ({tail_density:.1f}/1000 chars)",
            )
        )
    elif tail_zh >= 2500 and tail_density < 18:
        findings.append(
            Finding(
                "WARN",
                "tail_derivation_weak",
                f"tail sections are prose-heavy: {tail_zh} Chinese chars, {tail_display} display equations, evidence density {tail_density:.1f}/1000 chars",
            )
        )

    for section in weak_sections[:6]:
        findings.append(
            Finding(
                "WARN",
                "section_anchor",
                f"section {section.index} `{section.title}` is long ({section.zh_chars} Chinese chars) but has no display equation/table/figure/algorithm anchor",
            )
        )

    for section in prose_sections[:6]:
        findings.append(
            Finding(
                "WARN",
                "pure_prose_run",
                f"section {section.index} `{section.title}` has {section.pure_prose_runs} long prose paragraphs without math/table/figure/reference anchors",
            )
        )

    problem_sections = [s for s in main_sections if re.search(r"问题\s*[一二三四五六七八九十0-9]", s.title)]
    weak_problem_sections = [
        s
        for s in problem_sections
        if s.zh_chars >= 450 and s.math_markers < 6 and s.display_math + s.tables + s.figures == 0
    ]
    for section in weak_problem_sections[:4]:
        findings.append(
            Finding(
                "WARN",
                "problem_section_math",
                f"problem section `{section.title}` has limited mathematical anchors; specialize the shared model or add objective/constraint/result evidence",
            )
        )

    metrics: dict[str, Any] = {
        "section_count": len(sections),
        "main_section_count": len(main_sections),
        "total_zh_chars": total_zh,
        "total_math_markers": total_math,
        "total_display_math": total_display,
        "tail_section_titles": [s.title for s in tail_sections],
        "tail_zh_chars": tail_zh,
        "tail_math_markers": tail_math,
        "tail_display_math": tail_display,
        "tail_evidence_density_per_1000zh": round(tail_density, 2),
        "weak_anchor_sections": [s.title for s in weak_sections],
        "pure_prose_sections": [s.title for s in prose_sections],
        "sections": [asdict(s) for s in sections],
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return metrics, findings


def section_metrics(text: str) -> list[SectionMetric]:
    matches = list(SECTION_RE.finditer(text))
    out: list[SectionMetric] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        title = normalize(match.group(1))
        zh_chars = len(re.findall(r"[\u4e00-\u9fff]", block))
        paragraphs = len([p for p in re.split(r"\n\s*\n", block) if normalize(p)])
        math_markers = len(MATH_MARKER_RE.findall(block))
        display_math = len(DISPLAY_MATH_RE.findall(block))
        tables = len(TABLE_RE.findall(block))
        figures = len(FIGURE_RE.findall(block))
        refs = len(REF_RE.findall(block))
        algorithms = len(ALGO_RE.findall(block))
        evidence_count = math_markers + 2 * display_math + 2 * tables + 2 * figures + refs + algorithms
        density = evidence_count * 1000 / zh_chars if zh_chars else 0.0
        out.append(
            SectionMetric(
                index=i + 1,
                title=title,
                zh_chars=zh_chars,
                paragraphs=paragraphs,
                math_markers=math_markers,
                display_math=display_math,
                tables=tables,
                figures=figures,
                refs=refs,
                algorithms=algorithms,
                evidence_density=round(density, 2),
                pure_prose_runs=pure_prose_run_count(block),
            )
        )
    return out


def pure_prose_run_count(block: str) -> int:
    max_run = 0
    run = 0
    for para in re.split(r"\n\s*\n", block):
        if len(re.findall(r"[\u4e00-\u9fff]", para)) < 120:
            continue
        has_anchor = bool(MATH_MARKER_RE.search(para) or TABLE_RE.search(para) or FIGURE_RE.search(para) or REF_RE.search(para))
        if has_anchor:
            run = 0
        else:
            run += 1
            max_run = max(max_run, run)
    return max_run


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    if paper_arg:
        path = resolve(root, paper_arg)
        return [path] if path.exists() else []
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_contest.tex",
        paper_dir / "main_final.tex",
        paper_dir / "main.tex",
        paper_dir / "main.typ",
        paper_dir / "main.md",
    ]
    for path in candidates:
        if path.exists():
            files = [path]
            sections = paper_dir / "sections"
            if sections.exists():
                files.extend(sorted(sections.glob("*.tex")))
                files.extend(sorted(sections.glob("*.typ")))
                files.extend(sorted(sections.glob("*.md")))
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


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Derivation Density Audit",
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
        if key == "sections":
            continue
        lines.append(f"| {key} | {escape(value)} |")
    lines.extend(
        [
            "",
            "## Section Metrics",
            "",
            "| # | Section | Chinese chars | Math | Display | Tables | Figures | Evidence/1000 zh | Pure prose run |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in payload["metrics"].get("sections", []):
        lines.append(
            "| {index} | {title} | {zh_chars} | {math_markers} | {display_math} | {tables} | {figures} | {evidence_density} | {pure_prose_runs} |".format(
                **{k: escape(v) for k, v in item.items()}
            )
        )
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    else:
        lines.append("| INFO | derivation_density | no findings |")
    lines.append("")
    return "\n".join(lines)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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
