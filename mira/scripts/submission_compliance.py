#!/usr/bin/env python3
"""Check actual final-submission violations without blocking on optional configuration."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from project_paths import ProjectPathError, project_relative, resolve_project_path


DEFAULT_REQUIREMENTS = "planning/submission_requirements.json"
DEFAULT_JSON = "checks/submission_compliance_report.json"
DEFAULT_REPORT = "checks/submission_compliance_report.md"
DEFAULT_DOCUMENT_PLACEHOLDERS = ("TODO", "TBC", "XXXX", "MATHMODEL_")
TEXT_SUFFIXES = {".tex", ".typ", ".md", ".txt", ".json", ".csv"}
GENERIC_REQUIREMENTS: dict[str, Any] = {
    "schema_version": 1,
    "paper": {"source": "paper/main.tex", "pdf": "output/contest_final/paper.pdf"},
    "required_files": ["output/contest_final/paper.pdf"],
    "forbidden_placeholders": list(DEFAULT_DOCUMENT_PLACEHOLDERS),
    "anonymity": {"required": False, "identity_tokens": []},
    "ai_disclosure": {"required": False, "artifact": ""},
}


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    evidence: str = ""


def add(findings: list[Finding], level: str, code: str, message: str, evidence: str = "") -> None:
    findings.append(Finding(level, code, message, evidence))


def nonempty(value: Any) -> bool:
    return bool(str(value or "").strip())


def normalized_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", value.lower())


def visible_source(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if path.suffix.lower() == ".tex":
        return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())
    return text


def pdf_content(path: Path) -> tuple[int | None, str, str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        metadata = " ".join(f"{key}={value}" for key, value in (reader.metadata or {}).items())
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return len(reader.pages), f"{metadata}\n{text}", ""
    except Exception as exc:  # parser failures vary by PDF producer
        return None, "", str(exc)


def safe_path(root: Path, value: Any, findings: list[Finding], code: str) -> Path | None:
    try:
        return resolve_project_path(root, value)
    except ProjectPathError as exc:
        add(findings, "FAIL", code, str(exc), str(value or ""))
        return None


def evaluate_submission(
    root: Path,
    requirements: dict[str, Any],
    requirements_path: str = DEFAULT_REQUIREMENTS,
    config_warning: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    findings: list[Finding] = []
    metrics: dict[str, Any] = {"page_count": None, "page_limit": None, "required_files": 0}

    if config_warning:
        add(findings, "WARN", "requirements_fallback", "using generic final checks", config_warning)
    if requirements.get("schema_version") != 1:
        add(findings, "WARN", "schema_version", "unknown requirements schema; optional fields may be skipped", requirements_path)

    paper = requirements.get("paper")
    if not isinstance(paper, dict):
        paper = GENERIC_REQUIREMENTS["paper"]
        add(findings, "WARN", "paper_requirements", "paper settings are invalid; using generic paths")
    source_value = paper.get("source") or GENERIC_REQUIREMENTS["paper"]["source"]
    pdf_value = paper.get("pdf") or GENERIC_REQUIREMENTS["paper"]["pdf"]
    source_path = safe_path(root, source_value, findings, "paper_source_path")
    pdf_path = safe_path(root, pdf_value, findings, "paper_pdf_path")
    source_text = ""
    if source_path is None or not source_path.is_file():
        add(findings, "FAIL", "paper_source", "configured paper source is missing", str(source_value))
    else:
        source_text = visible_source(source_path)

    expected_title = str(paper.get("expected_title") or "").strip()
    if expected_title and normalized_text(expected_title) not in normalized_text(source_text):
        add(findings, "FAIL", "title_missing", "configured title was not found in the paper source", expected_title)

    keywords = paper.get("keywords", [])
    if isinstance(keywords, list):
        source_normalized = normalized_text(source_text)
        missing_keywords = [str(item) for item in keywords if nonempty(item) and normalized_text(str(item)) not in source_normalized]
        if missing_keywords:
            add(findings, "FAIL", "keywords_missing", "required keywords were not found in the paper source", ", ".join(missing_keywords))
    elif keywords is not None:
        add(findings, "WARN", "keywords_requirements", "paper.keywords is not a list; check skipped")

    sections = paper.get("required_sections", [])
    if isinstance(sections, list):
        source_normalized = normalized_text(source_text)
        missing_sections = [str(item) for item in sections if nonempty(item) and normalized_text(str(item)) not in source_normalized]
        if missing_sections:
            add(findings, "FAIL", "sections_missing", "required sections were not found in the paper source", ", ".join(missing_sections))
    elif sections is not None:
        add(findings, "WARN", "sections_requirements", "paper.required_sections is not a list; check skipped")

    page_limit = paper.get("page_limit")
    if isinstance(page_limit, int) and not isinstance(page_limit, bool) and page_limit > 0:
        normalized_limit = page_limit
    else:
        normalized_limit = None
        if page_limit not in (None, "", "unlimited"):
            add(findings, "WARN", "page_limit_requirements", "invalid page limit; check skipped", str(page_limit))
    metrics["page_limit"] = normalized_limit

    pdf_text = ""
    if pdf_path is None or not pdf_path.is_file():
        add(findings, "FAIL", "paper_pdf", "configured submission PDF is missing", str(pdf_value))
    else:
        page_count, pdf_text, error = pdf_content(pdf_path)
        if error:
            add(findings, "FAIL", "pdf_read", "submission PDF could not be inspected", error)
        else:
            metrics["page_count"] = page_count
            if isinstance(normalized_limit, int) and page_count is not None and page_count > normalized_limit:
                add(findings, "FAIL", "page_limit", f"submission PDF has {page_count} pages, exceeding the limit of {normalized_limit}", project_relative(root, pdf_path))

    required_files = requirements.get("required_files", GENERIC_REQUIREMENTS["required_files"])
    if not isinstance(required_files, list):
        add(findings, "WARN", "required_files_requirements", "required_files is not a list; using generic PDF requirement")
        required_files = GENERIC_REQUIREMENTS["required_files"]
    metrics["required_files"] = len(required_files)
    inspected_text = [source_text, pdf_text]
    for value in required_files:
        path = safe_path(root, value, findings, "required_file_path")
        if path is None:
            continue
        if not path.is_file() or path.stat().st_size == 0:
            add(findings, "FAIL", "required_file_missing", "required submission file is missing or empty", str(value))
        elif path.suffix.lower() in TEXT_SUFFIXES and path != source_path:
            inspected_text.append(visible_source(path))

    forbidden = requirements.get("forbidden_placeholders", DEFAULT_DOCUMENT_PLACEHOLDERS)
    if not isinstance(forbidden, list) or not all(nonempty(item) for item in forbidden):
        add(findings, "WARN", "placeholder_requirements", "invalid placeholder list; using generic markers")
        forbidden = list(DEFAULT_DOCUMENT_PLACEHOLDERS)
    scan_text = "\n".join(inspected_text)
    markers = list(dict.fromkeys([*DEFAULT_DOCUMENT_PLACEHOLDERS, *(str(item) for item in forbidden)]))
    found_markers = [marker for marker in markers if marker.lower() in scan_text.lower()]
    if found_markers:
        add(findings, "FAIL", "document_placeholder", "submission artifacts contain forbidden placeholders", ", ".join(found_markers))

    anonymity = requirements.get("anonymity", {})
    if isinstance(anonymity, dict) and anonymity.get("required") is True:
        tokens = anonymity.get("identity_tokens")
        if not isinstance(tokens, list) or not tokens or not all(nonempty(item) for item in tokens):
            add(findings, "WARN", "identity_tokens", "anonymity is enabled but no identity tokens were configured")
        else:
            leaked = [str(token) for token in tokens if str(token).lower() in scan_text.lower()]
            if leaked:
                add(findings, "FAIL", "identity_leak", "anonymous submission contains configured identity tokens", ", ".join(leaked))

    ai = requirements.get("ai_disclosure", {})
    if isinstance(ai, dict) and ai.get("required") is True:
        artifact = ai.get("artifact")
        path = safe_path(root, artifact, findings, "ai_artifact_path")
        if path is None or not path.is_file() or path.stat().st_size == 0:
            add(findings, "FAIL", "ai_artifact", "the official rules require a non-empty AI disclosure artifact", str(artifact or ""))

    fail_count = sum(item.level == "FAIL" for item in findings)
    warn_count = sum(item.level == "WARN" for item in findings)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "contract": requirements_path,
        "verdict": "FAIL" if fail_count else ("PASS_WITH_WARNINGS" if warn_count else "PASS"),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Submission Compliance",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Requirements: `{payload['contract']}`",
        f"- PDF pages: **{payload['metrics'].get('page_count')}**",
        f"- Page limit: **{payload['metrics'].get('page_limit')}**",
        "",
        "| Level | Check | Evidence | Message |",
        "|---|---|---|---|",
    ]
    if payload["findings"]:
        for item in payload["findings"]:
            evidence = str(item.get("evidence") or "-").replace("|", "/")
            message = str(item.get("message") or "").replace("|", "/")
            lines.append(f"| {item['level']} | {item['code']} | `{evidence}` | {message} |")
    else:
        lines.append("| PASS | all | `-` | All configured submission requirements passed. |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--requirements", "--contract", dest="requirements", default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--write-json", default=DEFAULT_JSON)
    parser.add_argument("--write-report", default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        requirements_path = resolve_project_path(root, args.requirements)
        json_path = resolve_project_path(root, args.write_json)
        report_path = resolve_project_path(root, args.write_report)
    except ProjectPathError as exc:
        print(f"FAIL: {exc}")
        return 1
    try:
        requirements = json.loads(requirements_path.read_text(encoding="utf-8-sig"))
        if not isinstance(requirements, dict):
            raise ValueError("submission requirements must be a JSON object")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = evaluate_submission(
            root,
            GENERIC_REQUIREMENTS,
            project_relative(root, requirements_path),
            config_warning=str(exc),
        )
    else:
        payload = evaluate_submission(root, requirements, project_relative(root, requirements_path))
    write_reports(payload, json_path, report_path)
    print(f"VERDICT: {payload['verdict']}")
    print(f"findings: {len(payload['findings'])}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
