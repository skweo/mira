#!/usr/bin/env python3
"""Audit abstract-page and front-matter layout for Mira contest-final papers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from delivery_contract import collect_source_files, manifest_path, source_fingerprint


PROBLEM_TOKEN = r"问题\s*(?:[一二三四五六七八九十]+|[1-9][0-9]*)"
PAGEBREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak)\b")
MAIN_START_RE = re.compile(r"\\(?:section|chapter)\*?\{([^}]*)\}|\\tableofcontents\b", re.S)
HEADING_RE = re.compile(r"\\(?:section|subsection|subsubsection|chapter)\*?\{([^}]*)\}", re.S)


@dataclass
class Finding:
    level: str
    axis: str
    message: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paper_paths = paper_files(root, args.paper)
    metrics, findings = audit(root, paper_paths)
    entry = paper_entry(root, args.paper)
    fingerprint = source_fingerprint(root, entry) if entry else {
        "canonical_source": "",
        "source_files": [],
        "source_sha256": "",
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        **fingerprint,
        "paper_files": [rel(root, path) for path in paper_paths],
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
        _print(f"METRIC: {key}={value}")
    for item in findings:
        _print(f"{item.level}: [{item.axis}] {item.message}")
    return 1 if payload["verdict"] == "FAIL" else 0


def audit(root: Path, paper_paths: list[Path]) -> tuple[dict[str, Any], list[Finding]]:
    findings: list[Finding] = []
    if not paper_paths:
        return {}, [Finding("FAIL", "paper", "no paper source found")]

    text = "\n".join(read_text(path) for path in paper_paths)
    clean = strip_latex_comments(text)
    abstract, abstract_start, abstract_end = extract_abstract(clean)
    first_main_match = next(MAIN_START_RE.finditer(clean), None)
    first_after_abstract = first_main_after(clean, abstract_end)
    keyword_match = keyword_position(clean, abstract_start, first_after_abstract.start() if first_after_abstract else len(clean))
    after_abstract = clean[abstract_end : first_after_abstract.start() if first_after_abstract else len(clean)]
    body_text = clean[first_after_abstract.start() :] if first_after_abstract else ""
    headings = [normalize_space(match.group(1)) for match in HEADING_RE.finditer(clean)]
    body_problem_labels = unique_problem_labels(" ".join(headings))
    abstract_problem_labels = unique_problem_labels(abstract)
    abstract_bold_problem_labels = bold_problem_label_count(abstract)
    abstract_paragraphs = paragraph_count(abstract)
    abstract_numbers = len(re.findall(r"\d+(?:\.\d+)?", abstract))
    abstract_bold_markers = len(re.findall(r"\\(?:textbf|bfseries|bm|mathbf)\b", abstract))
    pagebreak_after_abstract = bool(PAGEBREAK_RE.search(after_abstract))
    title_evidence = has_title_evidence(clean, abstract_start)
    first_main_title = first_main_title_from_match(first_after_abstract)

    metrics: dict[str, Any] = {
        "paper_files": [rel(root, path) for path in paper_paths],
        "has_abstract_environment": bool(abstract),
        "has_title_evidence_before_abstract": title_evidence,
        "has_keywords_before_main_body": bool(keyword_match),
        "has_pagebreak_after_abstract_keywords": pagebreak_after_abstract,
        "first_main_block": first_main_title,
        "top_level_heading_count": len([h for h in headings if h]),
        "body_problem_label_count": len(body_problem_labels),
        "abstract_problem_label_count": len(abstract_problem_labels),
        "abstract_bold_problem_label_count": abstract_bold_problem_labels,
        "abstract_paragraph_count": abstract_paragraphs,
        "abstract_number_count": abstract_numbers,
        "abstract_bold_marker_count": abstract_bold_markers,
        "uses_tableofcontents": "\\tableofcontents" in clean,
    }

    if not abstract:
        findings.append(Finding("FAIL", "abstract", "missing LaTeX abstract environment"))
        return metrics, findings

    if not title_evidence:
        findings.append(Finding("WARN", "front_matter", "no clear title evidence before abstract; contest-final papers need a formal title/front matter"))

    if not keyword_match:
        findings.append(Finding("FAIL", "keywords", "keywords must appear with the abstract before the main body starts"))

    if not pagebreak_after_abstract:
        findings.append(Finding("FAIL", "abstract_page", "abstract and keywords must end with \\newpage or \\clearpage before contents/problem sections"))

    if max(len(body_problem_labels), len(abstract_problem_labels)) >= 2:
        required = min(max(len(body_problem_labels), len(abstract_problem_labels)), 4)
        if len(abstract_problem_labels) < required:
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_question_coverage",
                    f"body appears to have {len(body_problem_labels)} problem labels, but abstract exposes only {len(abstract_problem_labels)}",
                )
            )
        if abstract_bold_problem_labels < len(abstract_problem_labels):
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_problem_label_bold",
                    "each abstract problem label such as 问题一/问题二 should be bolded with \\textbf{...}",
                )
            )
        if len(abstract_problem_labels) >= 2 and abstract_paragraphs < len(abstract_problem_labels):
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_question_paragraphs",
                    "abstract problem summaries are not clearly separated into one paragraph per subquestion",
                )
            )

    if abstract_numbers >= 5 and abstract_bold_markers < max(2, abstract_bold_problem_labels):
        findings.append(Finding("FAIL", "abstract_emphasis", "abstract has many numeric results but too little bold emphasis for scan-critical answers"))

    if first_main_title and not re.search(r"问题\s*(重述|背景|提出|分析)|问题重述|问题分析", first_main_title):
        if not ("tableofcontents" in first_main_title.lower() or "目录" in first_main_title):
            findings.append(
                Finding(
                    "WARN",
                    "main_body_opening",
                    f"first main block is `{first_main_title}`; start the body with 问题重述/问题分析 or an official-template equivalent",
                )
            )

    if body_text and re.search(r"\\section\*?\{\s*摘要\s*\}", body_text):
        findings.append(Finding("WARN", "abstract_environment", "摘要 appears as a body section; use the front-matter abstract environment instead"))

    return metrics, findings


def extract_abstract(text: str) -> tuple[str, int, int]:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
    if match:
        return match.group(1), match.start(), match.end()
    return "", -1, 0


def keyword_position(text: str, start: int, end: int) -> re.Match[str] | None:
    if start < 0:
        start = 0
    return re.search(r"关键词|关键字|Keywords|Key\s*words", text[start:end], flags=re.I)


def first_main_after(text: str, index: int) -> re.Match[str] | None:
    for match in MAIN_START_RE.finditer(text, max(0, index)):
        return match
    return None


def first_main_title_from_match(match: re.Match[str] | None) -> str:
    if not match:
        return ""
    if match.group(0).startswith("\\tableofcontents"):
        return "目录"
    return normalize_space(match.group(1) or "")


def unique_problem_labels(text: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in re.findall(PROBLEM_TOKEN, text):
        normalized = re.sub(r"\s+", "", item)
        if normalized not in seen:
            seen.add(normalized)
            labels.append(normalized)
    return labels


def bold_problem_label_count(text: str) -> int:
    count = 0
    for match in re.finditer(r"\\textbf\s*\{([^{}]*(?:" + PROBLEM_TOKEN + r")[^{}]*)\}", text):
        count += len(unique_problem_labels(match.group(1)))
    for match in re.finditer(r"\{\\bfseries\s+([^{}]*(?:" + PROBLEM_TOKEN + r")[^{}]*)\}", text):
        count += len(unique_problem_labels(match.group(1)))
    return count


def paragraph_count(text: str) -> int:
    without_keywords = re.split(r"关键词|关键字|Keywords|Key\s*words", text, maxsplit=1, flags=re.I)[0]
    pieces = re.split(r"(?:\n\s*\n|\\par\b)", without_keywords)
    return len([piece for piece in pieces if normalize_space(piece)])


def has_title_evidence(text: str, abstract_start: int) -> bool:
    before = text[: max(0, abstract_start)]
    return bool(
        re.search(r"\\title\s*\{|\\maketitle|\\begin\{center\}|\\zihao\{[^}]+\}|\\heiti", before)
        or len([line for line in before.splitlines() if normalize_space(line)]) >= 2
    )


def strip_latex_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    entry = paper_entry(root, paper_arg)
    if not entry:
        return []
    if entry.suffix.lower() == ".tex":
        return [path for path in collect_source_files(root, entry) if path.suffix.lower() == ".tex"]
    if paper_arg:
        return [entry]
    paper_dir = root / "paper"
    files = [entry]
    sections = paper_dir / "sections"
    if sections.exists():
        files.extend(sorted(sections.glob("*.tex")))
        files.extend(sorted(sections.glob("*.typ")))
        files.extend(sorted(sections.glob("*.md")))
    return dedupe(files)


def paper_entry(root: Path, paper_arg: str | None) -> Path | None:
    if paper_arg:
        path = resolve(root, paper_arg)
        return path if path.is_file() else None
    if manifest_path(root).is_file():
        path = root / "paper" / "main.tex"
        return path if path.is_file() else None
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_final.tex",
        paper_dir / "main.tex",
        paper_dir / "main.typ",
        paper_dir / "main.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


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
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Abstract Layout Audit",
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
        lines.append("| INFO | abstract_layout | no findings |")
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
