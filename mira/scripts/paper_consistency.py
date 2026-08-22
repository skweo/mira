#!/usr/bin/env python3
"""Check final paper/report numeric consistency against Mira's result ledger."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SCAN_FILES = [
    "results/result_report.md",
    "paper/main_final.tex",
    "paper/main_final_checked.txt",
    "paper/main.tex",
]


@dataclass
class Finding:
    level: str
    axis: str
    file: str
    key: str
    message: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    ledger_path = resolve_path(root, args.ledger_json)
    if not ledger_path.exists():
        _print(f"FAIL: missing ledger: {rel(root, ledger_path)}")
        return 1
    ledger = load_json(ledger_path)
    files = scan_files(root, args.scan_file)
    findings = check_consistency(root, ledger, files, args.strict_coverage)
    payload = {
        "generated_at": now(),
        "root": str(root),
        "ledger_json": rel(root, ledger_path),
        "verdict": verdict(findings),
        "scanned_files": [rel(root, path) for path in files],
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for item in findings:
        if item.level in {"FAIL", "WARN"}:
            _print(f"{item.level}: [{item.axis}] {item.file}: {item.key}: {item.message}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def check_consistency(root: Path, ledger: dict[str, Any], files: list[Path], strict_coverage: bool) -> list[Finding]:
    findings: list[Finding] = []
    entries = [item for item in ledger.get("entries", []) if isinstance(item, dict)]
    for file_path in files:
        rel_file = rel(root, file_path)
        text = read_text(file_path)
        if not text:
            findings.append(Finding("WARN", "scan_file", rel_file, "-", "file is empty or unreadable"))
            continue
        for entry in entries:
            key = str(entry.get("key", ""))
            stale = [str(item) for item in entry.get("stale_strings", [])]
            canonical = [str(item) for item in entry.get("canonical_strings", [])]
            final_claim = entry.get("final_claim") is True
            for stale_value in stale:
                if stale_value and contains_number_string(text, stale_value):
                    if is_candidate_only_mention(text, stale_value, canonical):
                        findings.append(
                            Finding(
                                "INFO",
                                "candidate_stale_value",
                                rel_file,
                                key,
                                f"stale value `{stale_value}` appears only in a candidate/coarse-scan context with canonical refinement nearby",
                            )
                        )
                        continue
                    findings.append(
                        Finding(
                            "FAIL",
                            "stale_number",
                            rel_file,
                            key,
                            f"found stale value `{stale_value}`; canonical values include {', '.join(canonical[:4])}",
                        )
                    )
            if strict_coverage and final_claim and should_cover_file(rel_file):
                if not any(contains_number_string(text, value) for value in canonical):
                    findings.append(
                        Finding(
                            "WARN",
                            "coverage",
                            rel_file,
                            key,
                            "canonical final-claim value not found in this final paper/report file",
                        )
                    )
    if not findings:
        findings.append(Finding("INFO", "consistency", "-", "-", "no stale-number or coverage findings"))
    return findings


def scan_files(root: Path, explicit: list[str]) -> list[Path]:
    rels = explicit or DEFAULT_SCAN_FILES
    files: list[Path] = []
    seen: set[str] = set()
    for item in rels:
        path = resolve_path(root, item)
        if path.exists() and path.is_file():
            key = str(path.resolve()).lower()
            if key not in seen:
                seen.add(key)
                files.append(path)
    return files


def contains_number_string(text: str, value: str) -> bool:
    if not value:
        return False
    if re.fullmatch(r"[-+]?\d+(\.\d+)?([eE][-+]?\d+)?", value):
        return bool(re.search(rf"(?<![\d.]){re.escape(value)}(?![\d.])", text))
    return value in text


def is_candidate_only_mention(text: str, stale_value: str, canonical_values: list[str]) -> bool:
    candidate_terms = [
        "candidate",
        "coarse",
        "integer",
        "scan",
        "sampled",
        "initial",
        "refined",
        "候选",
        "粗扫",
        "整数",
        "整数秒",
        "扫描",
        "进一步",
        "连续",
        "加密",
        "定位",
    ]
    for start, end in number_occurrences(text, stale_value):
        context = text[max(0, start - 600) : min(len(text), end + 600)]
        lower = context.lower()
        has_candidate_context = any(term in lower for term in candidate_terms)
        has_canonical_nearby = any(value and value != stale_value and contains_number_string(context, value) for value in canonical_values)
        if not (has_candidate_context and has_canonical_nearby):
            return False
    return True


def number_occurrences(text: str, value: str) -> list[tuple[int, int]]:
    if re.fullmatch(r"[-+]?\d+(\.\d+)?([eE][-+]?\d+)?", value):
        pattern = re.compile(rf"(?<![\d.]){re.escape(value)}(?![\d.])")
    else:
        pattern = re.compile(re.escape(value))
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def should_cover_file(rel_file: str) -> bool:
    name = rel_file.replace("\\", "/").lower()
    return name.endswith("paper/main_final.tex") or name.endswith("paper/main_final_checked.txt") or name.endswith("results/result_report.md")


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Paper Consistency",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        f"- Ledger: `{payload['ledger_json']}`",
        "",
        "## Scanned Files",
        "",
    ]
    for file_path in payload["scanned_files"]:
        lines.append(f"- `{file_path}`")
    lines.extend(["", "## Findings", "", "| Level | Axis | File | Key | Message |", "|---|---|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | `{item['file']}` | `{item['key']}` | {escape(item['message'])} |")
    lines.append("")
    return "\n".join(lines)


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


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
    parser.add_argument("--ledger-json", default="planning/result_ledger.json", help="Result ledger JSON path")
    parser.add_argument("--scan-file", action="append", default=[], help="Specific paper/report file to scan")
    parser.add_argument("--strict-coverage", action="store_true", help="Warn when final-claim ledger values are absent")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
