#!/usr/bin/env python3
"""Verify reference metadata with explicit offline and local-only states."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


FINAL_STATUSES = {"VERIFIED", "LOCAL_ONLY", "UNVERIFIABLE", "CONFLICT"}
LOCAL_TYPES = {"book", "standard", "thesis", "manual", "dataset", "official_document"}


@dataclass
class Finding:
    level: str
    code: str
    reference_id: str
    message: str
    evidence: list[str]


def add(findings: list[Finding], level: str, code: str, reference_id: str, message: str, *evidence: str) -> None:
    findings.append(Finding(level, code, reference_id or "contract", message, [item for item in evidence if item]))


def evaluate_references(
    root: Path,
    contract: dict[str, Any],
    ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    findings: list[Finding] = []
    references = contract.get("references")
    ledger_entries = ledger.get("entries") if isinstance(ledger, dict) else None
    if contract.get("schema_version") != 1:
        add(findings, "FAIL", "schema_version", "contract", "schema_version must be 1")
    if not isinstance(references, list):
        add(findings, "FAIL", "references_type", "contract", "references must be a list")
        references = []
    if not references:
        add(findings, "FAIL", "missing_references", "contract", "reference authenticity contract is empty")
    if not isinstance(ledger_entries, list):
        add(findings, "FAIL", "ledger_entries", "contract", "result ledger entries must be available for claim binding")
        ledger_entries = []
    ledger_claim_ids = {
        str(item.get("claim_id") or "").strip()
        for item in ledger_entries
        if isinstance(item, dict) and str(item.get("claim_id") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for row in references:
        if not isinstance(row, dict):
            add(findings, "FAIL", "reference_type", "contract", "reference record must be an object")
            continue
        reference_id = str(row.get("reference_id") or "")
        citation_key = str(row.get("citation_key") or "")
        if not reference_id or reference_id in seen_ids:
            add(findings, "FAIL", "reference_id", reference_id or "contract", "reference_id is missing or duplicated")
        if not citation_key or citation_key in seen_keys:
            add(findings, "FAIL", "citation_key", reference_id, "citation_key is missing or duplicated")
        seen_ids.add(reference_id)
        seen_keys.add(citation_key)
        metadata = row.get("cited_metadata")
        if not isinstance(metadata, dict) or not _core_metadata_present(metadata):
            add(findings, "FAIL", "cited_metadata", reference_id, "authors, title, and year are required")
            metadata = metadata if isinstance(metadata, dict) else {}
        in_text_locations = row.get("in_text_locations")
        if not _nonempty_list(in_text_locations):
            add(findings, "FAIL", "in_text_binding", reference_id, "reference needs at least one in-text location")
        else:
            for location in in_text_locations:
                if not in_text_location_resolves(root, str(location)):
                    add(
                        findings,
                        "FAIL",
                        "in_text_location",
                        reference_id,
                        "in-text location must resolve to an existing line in a project file",
                        str(location),
                    )
        supported_claim_ids = row.get("supported_claim_ids")
        if not _nonempty_list(supported_claim_ids):
            add(findings, "FAIL", "claim_binding", reference_id, "reference needs at least one supported claim_id")
        else:
            for claim_id in supported_claim_ids:
                normalized_claim = str(claim_id).strip()
                if normalized_claim not in ledger_claim_ids:
                    add(
                        findings,
                        "FAIL",
                        "unknown_supported_claim",
                        reference_id,
                        "supported claim_id does not exist in the result ledger",
                        normalized_claim,
                    )
        status, issues, evidence = _classify(root, row, metadata)
        level = "FAIL" if status in {"CONFLICT", "UNVERIFIABLE"} else "INFO"
        if status in {"CONFLICT", "UNVERIFIABLE"}:
            add(findings, level, status.lower(), reference_id, "; ".join(issues) or status, *evidence)
        rows.append(
            {
                "reference_id": reference_id,
                "citation_key": citation_key,
                "reference_type": str(row.get("reference_type") or "unknown"),
                "status": status,
                "issues": issues,
                "evidence": evidence,
                "fallback_route": fallback_route(row, status),
            }
        )
    fail_count = sum(item.level == "FAIL" for item in findings)
    counts = {status: sum(item["status"] == status for item in rows) for status in FINAL_STATUSES}
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "counts": counts,
        "references": rows,
        "findings": [asdict(item) for item in findings],
        "verdict": "FAIL" if fail_count else "PASS",
    }


def _classify(root: Path, row: dict[str, Any], cited: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    sources = row.get("verification_sources")
    if not isinstance(sources, list):
        sources = []
    conflicts: list[str] = []
    insufficient: list[str] = []
    evidence: list[str] = []
    authoritative_matches = 0
    local_matches = 0
    attempted = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        state = str(source.get("status") or "").lower()
        locator = str(source.get("locator") or "")
        if locator:
            evidence.append(locator)
        if state in {"offline", "not_found", "error", "unavailable"}:
            attempted += 1
            continue
        candidate = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        if state == "matched":
            attempted += 1
            if not locator:
                insufficient.append("matched verification source has no authoritative locator")
                continue
            if not _core_metadata_present(candidate):
                insufficient.append("matched verification source lacks authors, title, or year metadata")
                continue
            authoritative_matches += 1
            conflicts.extend(_metadata_conflicts(cited, candidate))
        elif state == "local":
            attempted += 1
            local_path = resolve(root, locator.split("#", 1)[0]) if locator else None
            local_issues: list[str] = []
            if local_path is None or not within(root, local_path) or not local_path.is_file():
                local_issues.append("local verification locator is missing or outside the project")
            if not local_locator_is_anchored(locator):
                local_issues.append("local verification locator needs a page, section, or paragraph anchor")
            if len(str(source.get("authority") or "").strip()) < 4:
                local_issues.append("local verification source needs an issuing authority or official catalog")
            if len(str(source.get("passage") or "").strip()) < 8:
                local_issues.append("local verification source needs the cited passage")
            if not _core_metadata_present(candidate):
                local_issues.append("local verification source lacks authors, title, or year metadata")
            if local_issues:
                insufficient.extend(local_issues)
            else:
                local_matches += 1
                conflicts.extend(_metadata_conflicts(cited, candidate, local=True))
    if conflicts:
        return "CONFLICT", sorted(set(conflicts)), evidence
    if authoritative_matches:
        return "VERIFIED", [], evidence
    reference_type = str(row.get("reference_type") or "").lower()
    if local_matches and reference_type in LOCAL_TYPES:
        return "LOCAL_ONLY", ["verified from a traceable local authoritative copy"], evidence
    if insufficient:
        reason = "; ".join(sorted(set(insufficient)))
    else:
        reason = "all configured verification sources were offline or returned no match" if attempted else "no verification source was recorded"
    return "UNVERIFIABLE", [reason], evidence


def _metadata_conflicts(cited: dict[str, Any], candidate: dict[str, Any], local: bool = False) -> list[str]:
    conflicts: list[str] = []
    cited_doi, candidate_doi = normalize_doi(cited.get("doi")), normalize_doi(candidate.get("doi"))
    if cited_doi and candidate_doi and cited_doi != candidate_doi:
        conflicts.append(f"DOI conflict: {cited_doi} != {candidate_doi}")
    cited_title, candidate_title = normalize_text(cited.get("title")), normalize_text(candidate.get("title"))
    if cited_title and candidate_title and SequenceMatcher(None, cited_title, candidate_title).ratio() < (0.72 if local else 0.62):
        conflicts.append("title conflict")
    cited_year, candidate_year = str(cited.get("year") or ""), str(candidate.get("year") or "")
    if cited_year and candidate_year and cited_year != candidate_year:
        conflicts.append(f"year conflict: {cited_year} != {candidate_year}")
    cited_author = first_author(cited.get("authors"))
    candidate_author = first_author(candidate.get("authors"))
    if cited_author and candidate_author and not _author_compatible(cited_author, candidate_author):
        conflicts.append("first-author conflict")
    cited_pages, candidate_pages = normalize_pages(cited.get("pages")), normalize_pages(candidate.get("pages"))
    if cited_pages and candidate_pages and cited_pages != candidate_pages:
        conflicts.append(f"page conflict: {cited_pages} != {candidate_pages}")
    return conflicts


def fallback_route(row: dict[str, Any], status: str) -> list[str]:
    if status in {"VERIFIED", "LOCAL_ONLY"}:
        return []
    metadata = row.get("cited_metadata") if isinstance(row.get("cited_metadata"), dict) else {}
    reference_type = str(row.get("reference_type") or "").lower()
    route: list[str] = []
    if normalize_doi(metadata.get("doi")):
        route.append("Crossref DOI lookup")
    route.append("exact title + first-author search")
    if reference_type in LOCAL_TYPES:
        route.append("official catalog, standard registry, thesis repository, or local authoritative copy")
    else:
        route.append("publisher page or discipline index")
    route.append("manual field-by-field review; never convert an unavailable lookup into PASS")
    return route


def query_crossref(doi: str, timeout: float = 10.0) -> dict[str, Any]:
    normalized = normalize_doi(doi)
    if not normalized:
        return {"source": "crossref", "status": "not_found", "locator": "", "metadata": {}}
    url = "https://api.crossref.org/works/" + urllib.parse.quote(normalized, safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "Mira-reference-audit/0.11"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            message = json.loads(response.read().decode("utf-8"))["message"]
    except (OSError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError):
        return {"source": "crossref", "status": "offline", "locator": url, "metadata": {}}
    issued = message.get("issued", {}).get("date-parts", [[None]])
    return {
        "source": "crossref",
        "status": "matched",
        "locator": f"https://doi.org/{normalized}",
        "metadata": {
            "authors": [" ".join(part for part in (item.get("family"), item.get("given")) if part) for item in message.get("author", [])],
            "title": (message.get("title") or [""])[0],
            "year": issued[0][0] if issued and issued[0] else None,
            "journal": (message.get("container-title") or [""])[0],
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "pages": message.get("page"),
            "doi": message.get("DOI"),
        },
    }


def _core_metadata_present(metadata: dict[str, Any]) -> bool:
    return _nonempty_list(metadata.get("authors")) and bool(str(metadata.get("title") or "").strip()) and bool(metadata.get("year"))


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def in_text_location_resolves(root: Path, locator: str) -> bool:
    match = re.fullmatch(r"(.+):(\d+)(?::(\d+))?", locator.strip())
    if not match:
        return False
    path = resolve(root, match.group(1))
    if not within(root, path) or not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return False
    line_number = int(match.group(2))
    if line_number < 1 or line_number > len(lines):
        return False
    if match.group(3):
        column = int(match.group(3))
        return 1 <= column <= len(lines[line_number - 1]) + 1
    return True


def local_locator_is_anchored(locator: str) -> bool:
    return bool(re.search(r"#(?:page|section|paragraph)=[^&#]+", locator, flags=re.I))


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text).rstrip(" .")


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", str(value or "").lower())


def normalize_pages(value: Any) -> str:
    return re.sub(r"[^0-9a-z]+", "-", str(value or "").lower()).strip("-")


def first_author(value: Any) -> str:
    if isinstance(value, list) and value:
        return normalize_text(value[0])
    return ""


def _author_compatible(left: str, right: str) -> bool:
    return left in right or right in left or SequenceMatcher(None, left, right).ratio() >= 0.55


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def within(root: Path, path: Path) -> bool:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("reference contract must be a JSON object")
    return payload


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Reference Authenticity Audit", "", f"- Verdict: **{payload['verdict']}**", "- Offline or unavailable lookup never counts as verification.", "", "| Reference | Status | Issues |", "|---|---|---|"]
    for row in payload["references"]:
        lines.append(f"| {row['citation_key']} | {row['status']} | {'; '.join(row['issues']).replace('|', '/')} |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="planning/reference_authenticity.json")
    parser.add_argument("--ledger", default="planning/result_ledger.json")
    parser.add_argument("--write-json", default="checks/reference_authenticity_report.json")
    parser.add_argument("--write-report", default="checks/reference_authenticity_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    contract_path = resolve(root, args.contract)
    ledger_path = resolve(root, args.ledger)
    try:
        contract = load_json(contract_path)
        ledger = load_json(ledger_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        contract = {"schema_version": 0, "references": []}
        payload = evaluate_references(root, contract, {})
        add_row = asdict(Finding("FAIL", "contract_load", "contract", str(exc), [str(contract_path)]))
        payload["findings"].insert(0, add_row)
        payload["verdict"] = "FAIL"
    else:
        payload = evaluate_references(root, contract, ledger)
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(" ".join(f"{key}={value}" for key, value in payload["counts"].items()))
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
