#!/usr/bin/env python3
"""Audit table style for Mira contest-final papers."""

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


@dataclass
class Finding:
    level: str
    axis: str
    message: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    metrics = collect_metrics(root, args)
    findings = review(metrics)
    entry = paper_entry(root, args.paper)
    fingerprint = source_fingerprint(root, entry) if entry else {
        "canonical_source": "",
        "source_files": [],
        "source_sha256": "",
    }
    payload = {
        "generated_at": now(),
        "root": str(root),
        **fingerprint,
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
    text = "\n".join(read_text(path) for path in files)
    latex_blocks = latex_table_blocks(text)
    markdown_rows = len(re.findall(r"(?m)^\s*\|.+\|\s*$", text))
    typst_tables = len(re.findall(r"#table\s*\(", text))
    three_line_blocks = [block for block in latex_blocks if has_booktabs_triplet(block)]
    vertical_rule_blocks = [block for block in latex_blocks if has_vertical_tabular_rules(block)]
    hline_count = len(re.findall(r"\\hline\b", text))
    booktabs_rule_count = len(re.findall(r"\\(?:toprule|midrule|bottomrule)\b", text))
    return {
        "paper_files": [rel(root, path) for path in files],
        "latex_table_blocks": len(latex_blocks),
        "latex_three_line_blocks": len(three_line_blocks),
        "latex_vertical_rule_blocks": len(vertical_rule_blocks),
        "latex_hline_count": hline_count,
        "booktabs_rule_count": booktabs_rule_count,
        "uses_booktabs_package": bool(re.search(r"\\usepackage(?:\[[^\]]*\])?\{booktabs\}", text)),
        "markdown_table_rows": markdown_rows,
        "typst_table_count": typst_tables,
        "caption_count": len(re.findall(r"\\caption\s*(?:\[[^\]]*\])?\{", text)),
        "raw_header_terms": len(raw_header_hits(latex_blocks, text)),
        "raw_header_hits": raw_header_hits(latex_blocks, text),
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    table_count = metrics["latex_table_blocks"] + metrics["typst_table_count"] + max(0, metrics["markdown_table_rows"] // 2)
    if table_count == 0:
        findings.append(Finding("INFO", "table_style", "no tables detected"))
        return findings

    if metrics["latex_table_blocks"]:
        if metrics["latex_three_line_blocks"] == 0:
            findings.append(Finding("WARN", "three_line_table", "LaTeX tables are present but no complete booktabs three-line table was detected"))
        elif metrics["latex_three_line_blocks"] < metrics["latex_table_blocks"]:
            findings.append(Finding("WARN", "three_line_table", "some LaTeX tables do not use top/mid/bottom booktabs rules"))
        if metrics["booktabs_rule_count"] > 0 and not metrics["uses_booktabs_package"]:
            findings.append(Finding("WARN", "booktabs_package", "booktabs rules are used but \\usepackage{booktabs} was not detected in paper sources"))
        if metrics["latex_hline_count"] > max(2, metrics["booktabs_rule_count"]):
            findings.append(Finding("WARN", "hline_grid", "many \\hline rules detected; prefer booktabs three-line tables for final paper tables"))
        if metrics["latex_vertical_rule_blocks"]:
            findings.append(Finding("WARN", "vertical_rules", "vertical column rules were detected in LaTeX tabular specs; prefer no vertical rules for three-line tables"))

    if metrics["markdown_table_rows"] >= 6 and metrics["latex_table_blocks"] == 0 and metrics["typst_table_count"] == 0:
        findings.append(Finding("WARN", "markdown_tables", "Markdown tables detected; contest-final PDF should render them as three-line-equivalent tables or be converted to LaTeX/Typst tables"))

    if metrics["raw_header_terms"]:
        findings.append(Finding("WARN", "raw_table_headers", "raw engineering/CSV-style headers appear in table text; translate or explain them in final-paper tables"))

    return findings


def latex_table_blocks(text: str) -> list[str]:
    blocks = re.findall(r"\\begin\{table\}.*?\\end\{table\}", text, flags=re.S)
    if blocks:
        return blocks
    return re.findall(r"\\begin\{tabular\}.*?\\end\{tabular\}", text, flags=re.S)


def has_booktabs_triplet(block: str) -> bool:
    return all(rule in block for rule in [r"\toprule", r"\midrule", r"\bottomrule"])


def has_vertical_tabular_rules(block: str) -> bool:
    return bool(re.search(r"\\begin\{tabular\}\s*\{[^}]*\|[^}]*\}", block))


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
    files.extend(sorted((paper_dir / "sections").glob("*.tex")) if (paper_dir / "sections").exists() else [])
    files.extend(sorted((paper_dir / "sections").glob("*.typ")) if (paper_dir / "sections").exists() else [])
    files.extend(sorted((paper_dir / "sections").glob("*.md")) if (paper_dir / "sections").exists() else [])
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


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Table Style Audit",
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
        lines.append("| INFO | table_style | no findings |")
    lines.append("")
    return "\n".join(lines)


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms)


def raw_header_hits(latex_blocks: list[str], text: str) -> list[str]:
    regions: list[str] = []
    for block in latex_blocks:
        match = re.search(r"\\toprule(.*?)\\midrule", block, flags=re.S)
        if match:
            regions.append(match.group(1))
    if not regions:
        markdown_rows = re.findall(r"(?m)^\s*\|.+\|\s*$", text)
        if markdown_rows:
            regions.append(markdown_rows[0])
    patterns = {
        "veh": r"(?<![A-Za-z0-9])veh(?![A-Za-z0-9])",
        "ord": r"(?<![A-Za-z0-9])ord(?![A-Za-z0-9])",
        "node": r"(?<![A-Za-z0-9])node(?![A-Za-z0-9])",
        "idx": r"(?<![A-Za-z0-9])idx(?![A-Za-z0-9])",
        "Unnamed:": r"Unnamed\s*:",
        "REPRODUCIBLE RESULT TABLES": r"REPRODUCIBLE\s+RESULT\s+TABLES",
    }
    hits: list[str] = []
    for region in regions:
        for label, pattern in patterns.items():
            hits.extend(label for _ in re.finditer(pattern, region, flags=re.I))
    return hits


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
