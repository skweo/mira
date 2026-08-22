#!/usr/bin/env python3
"""Block final-paper polish regressions in Chinese Mira contest papers.

This gate catches defects that are visually obvious to reviewers but easy for
generic structural audits to miss:
- unsegmented multi-question abstracts;
- missing or weak keyword lines;
- missing selective emphasis on final-answer/key-conclusion formulas or answer numbers;
- English figure/table captions or matplotlib labels in Chinese papers.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROBLEM_TOKEN = r"(?:问题\s*[一二三四五六七八九十]+|问题\s*[1-9][0-9]*|Q[1-9][0-9]*)"
DISPLAY_EQUATION_RE = re.compile(
    r"\\begin\{(?:equation|align|aligned|gather|multline)\}|\\\[",
    flags=re.I,
)
FINAL_FORMULA_RE = re.compile(
    r"\\(?:boxed|fbox|colorbox|keyformula|importantformula|finalformula)\b|\\tag\{[^}]*?(?:结论|结果|最终|答案)[^}]*\}",
    flags=re.I,
)
CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}", re.S)
PLOT_FUNCTIONS = {
    "set_title",
    "set_xlabel",
    "set_ylabel",
    "set_zlabel",
    "suptitle",
    "title",
    "xlabel",
    "ylabel",
    "zlabel",
    "legend",
    "text",
    "annotate",
    "figtext",
}
PLOT_KEYWORDS = {"label", "title", "xlabel", "ylabel", "zlabel"}
ENGLISH_WHITELIST = {
    "AHP",
    "ARIMA",
    "BP",
    "CNN",
    "CUMCM",
    "DP",
    "GA",
    "GPT",
    "HTTP",
    "ICM",
    "LSTM",
    "MAE",
    "MAPE",
    "MCM",
    "MILP",
    "MSE",
    "OpenAI",
    "PCA",
    "PDF",
    "PSO",
    "QUBO",
    "RMSE",
    "SA",
    "SVM",
    "TOPSIS",
    "TSP",
    "VRP",
    "VRPTW",
    "AI",
    "API",
    "CSV",
    "JSON",
    "LaTeX",
    "Typst",
    "Q",
    "N",
    "kg",
    "m",
    "s",
    "ms",
    "min",
    "max",
    "rad",
    "deg",
    "x",
    "y",
    "z",
}


@dataclass
class Finding:
    level: str
    axis: str
    message: str
    location: str = ""


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paper_files = collect_paper_files(root, args.paper)
    findings, metrics = audit(root, paper_files, args.language)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper_files": [rel(root, path) for path in paper_files],
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
    print(f"VERDICT: {payload['verdict']}")
    print("metrics: " + json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    for item in findings:
        where = f" ({item.location})" if item.location else ""
        print(f"{item.level}: {item.axis}: {item.message}{where}")
    return 1 if payload["verdict"] == "FAIL" else 0


def audit(root: Path, paper_files: list[Path], language: str) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    text = "\n".join(read_text(path) for path in paper_files)
    clean = strip_comments(text)
    abstract, keyword_text = extract_abstract_and_keywords(clean)
    abstract_body = strip_keyword_tail(abstract)
    body_problem_labels = unique_problem_labels(" ".join(section_titles(clean)))
    abstract_problem_labels = unique_problem_labels(abstract_body)
    bold_problem_labels = bold_problem_label_count(abstract_body)
    abstract_paragraphs = paragraph_count(abstract_body)
    keyword_terms = split_keywords(keyword_text)
    abstract_numbers = len(re.findall(r"\d+(?:\.\d+)?", abstract_body))
    abstract_result_bold = bold_result_marker_count(strip_problem_bold(strip_keyword_tail(abstract)))
    display_equations = len(DISPLAY_EQUATION_RE.findall(clean))
    final_formula_markers = len(FINAL_FORMULA_RE.findall(clean))
    captions = caption_texts(clean)
    english_caption_findings = english_text_findings(captions, "paper_caption")
    plot_findings = plot_source_language_findings(root) if language.lower().startswith(("zh", "chinese", "cn")) else []

    if not abstract:
        findings.append(Finding("FAIL", "abstract", "missing abstract block or abstract macro"))
    if not keyword_text:
        findings.append(Finding("FAIL", "keywords", "missing keyword line inside the abstract/front-matter area"))
    elif not re.search(r"\\textbf\s*\{\s*关键[词字]\s*[:：]?\s*\}|\\bfseries\s*关键[词字]|关键[词字]\s*[:：]", abstract):
        findings.append(Finding("FAIL", "keywords", "keyword label must be visibly marked as `关键词：` or `关键字：`"))
    if keyword_text and len(keyword_terms) < 3:
        findings.append(Finding("FAIL", "keywords", f"keyword line has only {len(keyword_terms)} terms; use 3-6 precise Chinese terms"))
    if len(keyword_terms) > 6:
        findings.append(Finding("WARN", "keywords", f"keyword line has {len(keyword_terms)} terms; prefer 3-6 terms"))

    if max(len(body_problem_labels), len(abstract_problem_labels)) >= 2:
        required = min(max(len(body_problem_labels), len(abstract_problem_labels)), 4)
        if len(abstract_problem_labels) < required:
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_question_coverage",
                    f"abstract exposes {len(abstract_problem_labels)} problem labels, expected at least {required}",
                )
            )
        if bold_problem_labels < len(abstract_problem_labels):
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_problem_labels",
                    "each problem summary in the abstract must begin with a bold label such as `\\textbf{针对问题一：}`",
                )
            )
        if len(abstract_problem_labels) >= 2 and abstract_paragraphs < len(abstract_problem_labels):
            findings.append(
                Finding(
                    "FAIL",
                    "abstract_paragraphs",
                    "multi-question abstracts must use one separated paragraph per official subquestion",
                )
            )

    if abstract_numbers >= 5 and abstract_result_bold < 2:
        findings.append(
            Finding(
                "FAIL",
                "abstract_result_emphasis",
                "abstract contains many numeric results but does not bold enough scan-critical answer numbers or strategy phrases",
            )
        )

    if display_equations >= 8 and final_formula_markers < 1:
        findings.append(
            Finding(
                "FAIL",
                "formula_emphasis",
                "paper has many display equations but no visible final-answer/key-conclusion formula marker; mark only the terminal result formula, not auxiliary derivations",
            )
        )

    findings.extend(english_caption_findings)
    findings.extend(plot_findings)

    metrics = {
        "abstract_problem_labels": len(abstract_problem_labels),
        "abstract_bold_problem_labels": bold_problem_labels,
        "abstract_paragraphs": abstract_paragraphs,
        "keyword_terms": len(keyword_terms),
        "abstract_numbers": abstract_numbers,
        "abstract_result_bold_markers": abstract_result_bold,
        "display_equations": display_equations,
        "final_formula_markers": final_formula_markers,
        "captions_scanned": len(captions),
        "plot_source_language_findings": len(plot_findings),
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return findings, metrics


def extract_abstract_and_keywords(text: str) -> tuple[str, str]:
    env = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
    if env:
        abstract = env.group(1)
        return abstract, keyword_from_text(abstract)
    args = latex_command_args(text, "abstractcn", 2)
    if args:
        abstract = args[0]
        keywords = args[1] if len(args) > 1 else keyword_from_text(abstract)
        return abstract + "\n关键词：" + keywords, keywords
    sec = re.search(r"\\section\*?\{\s*摘要\s*\}(.*?)(?:\\(?:newpage|clearpage|tableofcontents|section)\b)", text, flags=re.S)
    if sec:
        abstract = sec.group(1)
        return abstract, keyword_from_text(abstract)
    return "", ""


def keyword_from_text(text: str) -> str:
    match = re.search(r"(?:\\textbf\s*\{\s*)?关键[词字]\s*[:：]?\s*(?:\})?\s*([^\n\r]+)", text)
    return clean_inline(match.group(1)) if match else ""


def strip_keyword_tail(text: str) -> str:
    return re.split(r"(?:\\textbf\s*\{\s*)?关键[词字]\s*[:：]?", text, maxsplit=1)[0]


def split_keywords(text: str) -> list[str]:
    text = clean_inline(text)
    parts = re.split(r"(?:；|;|、|，|,|\\quad|\s{2,})", text)
    return [part.strip(" ：:;；,，") for part in parts if part.strip(" ：:;；,，")]


def latex_command_args(text: str, command: str, max_args: int) -> list[str]:
    marker = "\\" + command
    pos = text.find(marker)
    if pos < 0:
        return []
    args: list[str] = []
    idx = pos + len(marker)
    while len(args) < max_args:
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text) or text[idx] != "{":
            break
        arg, idx = balanced_brace_arg(text, idx)
        args.append(arg)
    return args


def balanced_brace_arg(text: str, start: int) -> tuple[str, int]:
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{" and (idx == 0 or text[idx - 1] != "\\"):
            depth += 1
        elif char == "}" and (idx == 0 or text[idx - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start + 1 : idx], idx + 1
    return text[start + 1 :], len(text)


def unique_problem_labels(text: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in re.findall(PROBLEM_TOKEN, text, flags=re.I):
        normalized = re.sub(r"\s+", "", item).upper()
        if normalized not in seen:
            seen.add(normalized)
            labels.append(normalized)
    return labels


def bold_problem_label_count(text: str) -> int:
    count = 0
    for match in re.finditer(r"\\textbf\s*\{([^{}]*(?:" + PROBLEM_TOKEN + r")[^{}]*)\}", text, flags=re.I):
        count += len(unique_problem_labels(match.group(1)))
    for match in re.finditer(r"\{\\bfseries\s+([^{}]*(?:" + PROBLEM_TOKEN + r")[^{}]*)\}", text, flags=re.I):
        count += len(unique_problem_labels(match.group(1)))
    return count


def strip_problem_bold(text: str) -> str:
    return re.sub(r"\\textbf\s*\{[^{}]*(?:" + PROBLEM_TOKEN + r")[^{}]*\}", " ", text, flags=re.I)


def bold_result_marker_count(text: str) -> int:
    chunks = re.findall(r"\\textbf\s*\{([^{}]+)\}|\{\\bfseries\s+([^{}]+)\}", text)
    count = 0
    for a, b in chunks:
        chunk = a or b
        if re.search(r"\d+(?:\.\d+)?|最[优大小]|最大|最小|最终|策略|结论|方向|概率|速度|目标", chunk):
            count += 1
    return count


def paragraph_count(text: str) -> int:
    pieces = re.split(r"(?:\n\s*\n|\\par\b)", text)
    return len([piece for piece in pieces if clean_inline(piece)])


def section_titles(text: str) -> list[str]:
    return [clean_inline(match.group(1)) for match in re.finditer(r"\\(?:section|subsection|subsubsection|chapter)\*?\{([^}]*)\}", text)]


def caption_texts(text: str) -> list[tuple[str, str]]:
    captions: list[tuple[str, str]] = []
    for idx, match in enumerate(CAPTION_RE.finditer(text), start=1):
        captions.append((f"caption#{idx}", clean_inline(match.group(1))))
    return captions


def english_text_findings(items: list[tuple[str, str]], axis: str) -> list[Finding]:
    findings: list[Finding] = []
    for location, text in items:
        terms = suspicious_english_terms(text)
        if terms:
            findings.append(
                Finding(
                    "FAIL",
                    axis,
                    "Chinese final paper visual/table descriptions must not contain English prose words: " + ", ".join(terms[:8]),
                    location,
                )
            )
    return findings


def plot_source_language_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    code_dir = root / "code"
    if not code_dir.exists():
        return findings
    for path in sorted(code_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node.func)
            if name in PLOT_FUNCTIONS:
                for value in positional_strings(node):
                    terms = suspicious_english_terms(value)
                    if terms:
                        findings.append(Finding("FAIL", "figure_language", f"plot text should be Chinese, found English words: {', '.join(terms[:8])}", f"{rel(root, path)}:{node.lineno}"))
            for keyword in node.keywords:
                if keyword.arg in PLOT_KEYWORDS:
                    value = literal_or_fstring(keyword.value)
                    if value:
                        terms = suspicious_english_terms(value)
                        if terms:
                            findings.append(Finding("FAIL", "figure_language", f"plot keyword `{keyword.arg}` should be Chinese, found English words: {', '.join(terms[:8])}", f"{rel(root, path)}:{node.lineno}"))
    return findings


def call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def positional_strings(node: ast.Call) -> list[str]:
    values: list[str] = []
    for arg in node.args:
        value = literal_or_fstring(arg)
        if value:
            values.append(value)
    return values


def literal_or_fstring(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        return "".join(parts)
    return ""


def suspicious_english_terms(text: str) -> list[str]:
    cleaned = clean_inline(text)
    terms: list[str] = []
    for term in re.findall(r"[A-Za-z][A-Za-z-]{1,}", cleaned):
        raw = term.strip("-")
        if not raw:
            continue
        if raw in ENGLISH_WHITELIST or raw.upper() in ENGLISH_WHITELIST:
            continue
        if re.fullmatch(r"[Qq]\d+", raw):
            continue
        if len(raw) <= 2:
            continue
        if raw.lower() in {"sin", "cos", "tan", "log", "exp", "arg", "min", "max"}:
            continue
        if raw not in terms:
            terms.append(raw)
    return terms


def clean_inline(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:textbf|emph|mathbf|bm|boldsymbol)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    text = text.replace("~", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def collect_paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    if paper_arg:
        path = resolve(root, paper_arg)
        return [path] if path.exists() else []
    paper_dir = root / "paper"
    candidates = [
        paper_dir / "main_final_checked.tex",
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


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira 0.8 Final Polish Language Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(value)} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Location | Message |", "|---|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | `{escape(item.get('location', ''))}` | {escape(item['message'])} |")
    else:
        lines.append("| INFO | final_polish_language | - | no findings |")
    lines.append("")
    return "\n".join(lines)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper tex/typ/md path")
    parser.add_argument("--language", default="zh", help="Paper language, default zh")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
