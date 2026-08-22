#!/usr/bin/env python3
"""Statically preflight Python and MATLAB claim-figure source files."""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    level: str
    code: str
    message: str
    evidence: list[str]


def add(findings: list[Finding], level: str, code: str, message: str, *evidence: str) -> None:
    findings.append(Finding(level, code, message, [item for item in evidence if item]))


def evaluate_source(source: str, backend: str) -> dict[str, Any]:
    backend = backend.lower().strip()
    findings: list[Finding] = []
    if backend not in {"python", "matlab"}:
        add(findings, "FAIL", "unsupported_backend", "only Python and MATLAB plotting sources are supported")
    elif backend == "python":
        _python_checks(source, findings)
    else:
        _matlab_checks(source, findings)
    failures = sum(item.level == "FAIL" for item in findings)
    warnings = sum(item.level == "WARN" for item in findings)
    return {
        "backend": backend,
        "counts": {"FAIL": failures, "WARN": warnings},
        "findings": [asdict(item) for item in findings],
        "verdict": "FAIL" if failures else "PASS",
    }


def _python_checks(source: str, findings: list[Finding]) -> None:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        add(findings, "FAIL", "syntax", f"Python syntax error: {exc.msg}", f"line {exc.lineno}")
        return
    if re.search(r"(?:cmap\s*=\s*|set_cmap\s*\()\s*['\"]?(?:jet|rainbow|hsv)\b", source, re.I):
        add(findings, "FAIL", "unsafe_colormap", "jet/rainbow/hsv colormaps are not accepted for claim-bearing figures")
    if re.search(r"\b(?:matlab\.engine|subprocess\s*\.\s*run\s*\([^\n]*(?:matlab|octave))", source, re.I):
        add(findings, "FAIL", "mixed_backend", "a Python figure source must not silently delegate rendering to MATLAB")
    vector = re.search(r"savefig\s*\([^\n]*(?:\.pdf|\.svg)", source, re.I)
    if not vector:
        add(findings, "FAIL", "missing_vector_export", "claim figure needs PDF or SVG vector export")
    raster_calls = re.findall(r"savefig\s*\(([^\n\)]*(?:\.png|\.tif|\.tiff)[^\n\)]*)\)", source, re.I)
    if not raster_calls:
        add(findings, "FAIL", "missing_raster_export", "claim figure needs a PNG/TIFF audit export")
    elif not any(_max_number(call, r"dpi\s*=\s*(\d+)") >= 300 for call in raster_calls):
        add(findings, "FAIL", "low_raster_dpi", "raster export must declare at least 300 DPI")
    _font_checks(source, findings)
    _log_checks(source, "python", findings)
    if re.search(r"\b(?:dropna|notna|isna)\s*\(", source) and not re.search(r"(?:before|after|dropped|excluded|missing_count|len\s*\()", source, re.I):
        add(findings, "WARN", "silent_missing_exclusion", "missing-value exclusion should record before/after counts")
    if re.search(r"\b(?:np\.random|numpy\.random)\b", source) and not re.search(r"(?:seed|default_rng|simulation|monte.?carlo)", source, re.I):
        add(findings, "WARN", "untracked_random_data", "random data need a seed and an explicit simulation role")
    if re.search(r"\b(?:load_iris|make_blobs|make_classification|demo|example_data)\b", source, re.I):
        add(findings, "FAIL", "demo_data", "demonstration data must not leak into a contest claim figure")


def _matlab_checks(source: str, findings: list[Finding]) -> None:
    if _unbalanced(source, "(", ")") or _unbalanced(source, "[", "]") or _unbalanced(source, "{", "}"):
        add(findings, "FAIL", "syntax", "MATLAB source contains unbalanced delimiters")
    if re.search(r"\bcolormap\s*\(\s*(?:jet|rainbow|hsv)\b", source, re.I):
        add(findings, "FAIL", "unsafe_colormap", "jet/rainbow/hsv colormaps are not accepted for claim-bearing figures")
    if re.search(r"\bpy\.[A-Za-z_]", source) or re.search(r"\bsystem\s*\([^\n]*(?:python|py )", source, re.I):
        add(findings, "FAIL", "mixed_backend", "a MATLAB figure source must not silently delegate rendering to Python")
    vector_calls = re.findall(r"exportgraphics\s*\(([^;]+)\)", source, re.I)
    has_vector = any(re.search(r"\.(?:pdf|svg)['\"]", call, re.I) for call in vector_calls)
    if not has_vector:
        add(findings, "FAIL", "missing_vector_export", "MATLAB claim figure needs PDF or SVG vector export")
    elif not any(re.search(r"ContentType['\"]?\s*,\s*['\"]vector['\"]", call, re.I) for call in vector_calls if re.search(r"\.pdf['\"]", call, re.I)):
        add(findings, "WARN", "vector_content_type", "PDF export should declare ContentType='vector'")
    raster_calls = [call for call in vector_calls if re.search(r"\.(?:png|tif|tiff)['\"]", call, re.I)]
    if not raster_calls:
        add(findings, "FAIL", "missing_raster_export", "MATLAB claim figure needs a PNG/TIFF audit export")
    elif not any(_max_number(call, r"Resolution['\"]?\s*,\s*(\d+)") >= 300 for call in raster_calls):
        add(findings, "FAIL", "low_raster_dpi", "MATLAB raster export must declare Resolution >= 300")
    _font_checks(source, findings)
    _log_checks(source, "matlab", findings)
    if re.search(r"\b(?:rmmissing|fillmissing)\s*\(", source, re.I) and not re.search(r"(?:before|after|dropped|excluded|missing_count|nnz\s*\(\s*ismissing)", source, re.I):
        add(findings, "WARN", "silent_missing_exclusion", "missing-value handling should record before/after counts")
    if re.search(r"\b(?:peaks|membrane|flow|load\s+handel)\b", source, re.I):
        add(findings, "FAIL", "demo_data", "MATLAB demonstration data must not leak into a contest claim figure")
    if re.search(r"\b(?:rand|randn|randi|randperm)\s*\(", source, re.I) and not re.search(r"\brng\s*\(", source, re.I):
        add(findings, "WARN", "untracked_random_data", "random data need rng(seed) and an explicit simulation role")


def _font_checks(source: str, findings: list[Finding]) -> None:
    sizes = [float(value) for value in re.findall(r"(?:font\.size|FontSize|fontsize)['\"]?\s*(?::|=|,)\s*([0-9.]+)", source, re.I)]
    if sizes and min(sizes) < 7:
        add(findings, "FAIL", "small_font", "declared figure text is smaller than 7 pt", str(min(sizes)))
    if not sizes:
        add(findings, "WARN", "font_size_undeclared", "figure source should declare a stable font size")


def _log_checks(source: str, backend: str, findings: list[Finding]) -> None:
    if backend == "python":
        uses_log = bool(re.search(r"(?:set_[xy]scale\s*\(\s*['\"]log|\b(?:np\.)?log(?:10|2)?\s*\()", source, re.I))
        guarded = bool(re.search(r"(?:>\s*0|clip\s*\([^\n]*(?:1e-|eps)|maximum\s*\([^\n]*(?:1e-|eps)|assert[^\n]*>\s*0)", source, re.I))
    else:
        uses_log = bool(re.search(r"\b(?:semilog[xy]|loglog|log10?|set\s*\([^\n]*[XY]Scale['\"]?\s*,\s*['\"]log)\b", source, re.I))
        guarded = bool(re.search(r"(?:>\s*0|max\s*\([^\n]*eps|assert\s*\([^\n]*>\s*0|realmin)", source, re.I))
    if uses_log and not guarded:
        add(findings, "FAIL", "unguarded_log_domain", "logarithmic plotting or transformation needs an explicit positive-domain guard")


def _max_number(text: str, pattern: str) -> int:
    values = [int(value) for value in re.findall(pattern, text, flags=re.I)]
    return max(values, default=0)


def _unbalanced(source: str, opening: str, closing: str) -> bool:
    stripped = re.sub(r"%[^\n]*|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "", source)
    return stripped.count(opening) != stripped.count(closing)


def discover_sources(root: Path) -> tuple[list[tuple[str, Path, str]], list[Finding]]:
    records: list[tuple[str, Path, str]] = []
    findings: list[Finding] = []
    directory = root / "results" / "figures_data"
    for record_path in directory.glob("*_provenance.json") if directory.is_dir() else []:
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            add(findings, "FAIL", "provenance_parse", "figure provenance cannot be parsed", relative(root, record_path), str(exc))
            continue
        if not isinstance(payload, dict):
            add(findings, "FAIL", "provenance_type", "figure provenance must be a JSON object", relative(root, record_path))
            continue
        source_record = payload.get("source")
        source_code = source_record.get("source_code") if isinstance(source_record, dict) else None
        raw = source_code.get("path") if isinstance(source_code, dict) else None
        route = payload.get("route")
        actual = route.get("actual") if isinstance(route, dict) else None
        backend = str(actual.get("backend") if isinstance(actual, dict) else "").lower().strip()
        if not raw:
            add(
                findings,
                "FAIL",
                "provenance_source_path",
                "figure provenance must name source.source_code.path",
                relative(root, record_path),
            )
            continue
        path = resolve(root, str(raw))
        if not within(root, path):
            add(findings, "FAIL", "source_outside_root", "figure source must remain inside the project root", str(path))
            continue
        if backend not in {"python", "matlab"}:
            backend = "python" if path.suffix.lower() == ".py" else "matlab" if path.suffix.lower() == ".m" else backend
        if backend not in {"python", "matlab"}:
            add(
                findings,
                "FAIL",
                "provenance_backend",
                "figure provenance needs a Python or MATLAB backend, or an inferable .py/.m source suffix",
                relative(root, record_path),
            )
            continue
        records.append((str(payload.get("figure_id") or record_path.stem), path, backend))
    return records, findings


def audit_project(
    root: Path,
    sources: list[tuple[str, Path, str]],
    discovery_findings: list[Finding] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    project_findings = list(discovery_findings or [])
    for figure_id, path, backend in sources:
        if not path.is_file():
            result = {"backend": backend, "counts": {"FAIL": 1, "WARN": 0}, "findings": [asdict(Finding("FAIL", "missing_source", "figure source is missing", [relative(root, path)]))], "verdict": "FAIL"}
        else:
            result = evaluate_source(path.read_text(encoding="utf-8-sig", errors="replace"), backend)
        rows.append({"figure_id": figure_id, "source": relative(root, path), **result})
    if not rows:
        add(project_findings, "FAIL", "no_sources_audited", "no Python or MATLAB claim-figure source was audited")
    failures = sum(item.level == "FAIL" for item in project_findings) + sum(
        row["counts"]["FAIL"] for row in rows
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "sources_audited": len(rows),
        "note": "Static source preflight does not prove data truth, statistical validity, or rendered aesthetics.",
        "findings": [asdict(item) for item in project_findings],
        "sources": rows,
        "verdict": "FAIL" if failures else "PASS",
    }


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def within(root: Path, path: Path) -> bool:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Figure Source Preflight", "", f"- Verdict: **{payload['verdict']}**", f"- Sources audited: `{payload['sources_audited']}`", f"- Scope: {payload['note']}", ""]
    for item in payload["findings"]:
        lines.append(f"- {item['level']} `{item['code']}`: {item['message']}")
    if payload["findings"]:
        lines.append("")
    for row in payload["sources"]:
        lines.extend([f"## {row['figure_id']}", "", f"- Source: `{row['source']}`", f"- Backend: `{row['backend']}`", f"- Verdict: `{row['verdict']}`", ""])
        for item in row["findings"]:
            lines.append(f"- {item['level']} `{item['code']}`: {item['message']}")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--source")
    parser.add_argument("--backend", choices=("auto", "python", "matlab"), default="auto")
    parser.add_argument("--write-json", default="checks/figure_source_preflight.json")
    parser.add_argument("--write-report", default="checks/figure_source_preflight.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if args.source:
        path = resolve(root, args.source)
        backend = args.backend
        if backend == "auto":
            backend = "python" if path.suffix.lower() == ".py" else "matlab" if path.suffix.lower() == ".m" else ""
        sources = [(path.stem, path, backend)]
        discovery_findings: list[Finding] = []
    else:
        sources, discovery_findings = discover_sources(root)
    payload = audit_project(root, sources, discovery_findings)
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"sources_audited: {payload['sources_audited']}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
