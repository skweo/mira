#!/usr/bin/env python3
"""Audit central-claim coverage across proof, table, figure, diagram, or waiver."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from matlab_execution_record import validate_execution_record


EVIDENCE_FORMS = {"proof", "table", "figure", "diagram", "no_visual_waiver", "unresolved"}
VISUAL_FORMS = {"figure", "diagram"}
PLACEHOLDERS = {"", "tbd", "todo", "pending", "unresolved", "not_selected"}


@dataclass
class Finding:
    level: str
    axis: str
    claim_id: str
    item_id: str
    message: str


@dataclass
class ClaimCoverage:
    claim_id: str
    key: str
    question: str
    evidence_forms: list[str]
    item_ids: list[str]
    artifacts: list[str]
    status: str
    recommendation: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    ledger_path = resolve_path(root, args.ledger_json)
    storyboard_path = resolve_path(root, args.storyboard_json)
    if not ledger_path.exists():
        _print(f"FAIL: missing ledger: {rel(root, ledger_path)}")
        return 1
    ledger = load_json(ledger_path)
    storyboard = load_json(storyboard_path) if storyboard_path.exists() else {}
    coverage, findings = audit_coverage(root, ledger, storyboard)
    payload = {
        "schema_version": 2,
        "authority": "non_authoritative_coverage_report",
        "generated_at": now(),
        "root": str(root),
        "ledger_json": rel(root, ledger_path),
        "storyboard_json": rel(root, storyboard_path),
        "verdict": verdict(findings),
        "items": [asdict(item) for item in coverage],
        "findings": [asdict(item) for item in findings],
        "metrics": metrics(coverage, findings),
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
    _print("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
    for finding in findings:
        if finding.level in {"FAIL", "WARN"}:
            _print(f"{finding.level}: [{finding.axis}] {finding.claim_id or '-'}: {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    strict_check = args.check and args.output_level == "contest_final"
    return 1 if strict_check and payload["verdict"] == "FAIL" else 0


def audit_coverage(
    root: Path,
    ledger: dict[str, Any],
    storyboard: dict[str, Any],
) -> tuple[list[ClaimCoverage], list[Finding]]:
    ledger_entries = [item for item in ledger.get("entries", []) if isinstance(item, dict)]
    central = [item for item in ledger_entries if is_central(item)]
    central_by_id = {clean(item.get("claim_id")): item for item in central if clean(item.get("claim_id"))}
    ledger_by_id = {clean(item.get("claim_id")): item for item in ledger_entries if clean(item.get("claim_id"))}
    storyboard_items = [item for item in storyboard.get("items", []) if isinstance(item, dict)]
    findings: list[Finding] = []
    valid_item_ids: set[str] = set()

    if not central:
        findings.append(Finding("FAIL", "central_claims", "-", "-", "ledger has no central claims to cover"))

    grouped: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in central_by_id}
    for index, item in enumerate(storyboard_items, start=1):
        item_id = clean(item.get("item_id")) or f"item-{index}"
        claim_id = clean(item.get("claim_id"))
        if not claim_id:
            findings.append(Finding("FAIL", "misbound", "-", item_id, "storyboard item has no claim_id"))
            continue
        if claim_id not in ledger_by_id:
            findings.append(Finding("FAIL", "misbound", claim_id, item_id, "claim_id is absent from the result ledger"))
            continue
        if claim_id not in central_by_id:
            findings.append(Finding("FAIL", "misbound", claim_id, item_id, "storyboard item is bound to a non-central claim"))
            continue
        normalized_item = dict(item)
        normalized_item["_resolved_item_id"] = item_id
        grouped[claim_id].append(normalized_item)
        item_findings = validate_item(root, central_by_id[claim_id], normalized_item, item_id)
        findings.extend(item_findings)
        if not any(finding.level == "FAIL" for finding in item_findings):
            valid_item_ids.add(item_id)

    detect_redundancy(grouped, findings)

    coverage: list[ClaimCoverage] = []
    for claim_id, claim in central_by_id.items():
        bound = grouped.get(claim_id, [])
        valid = [item for item in bound if clean(item.get("_resolved_item_id")) in valid_item_ids]
        if not bound:
            findings.append(Finding("FAIL", "missing", claim_id, "-", "central claim has no storyboard evidence decision"))
        elif not valid:
            findings.append(Finding("FAIL", "missing", claim_id, "-", "central claim has no complete evidence item"))
        status = "covered" if valid else "missing"
        coverage.append(
            ClaimCoverage(
                claim_id=claim_id,
                key=clean(claim.get("key")),
                question=clean(claim.get("question")),
                evidence_forms=unique([clean(item.get("chosen_evidence_form")) for item in bound]),
                item_ids=unique([clean(item.get("_resolved_item_id")) for item in bound]),
                artifacts=unique([artifact_for(item) for item in bound]),
                status=status,
                recommendation=(
                    "retain the evidence item and its distinct inference role"
                    if status == "covered"
                    else recommendation_for(claim)
                ),
            )
        )
    coverage.sort(key=lambda item: natural_key(item.key))
    return coverage, findings


def validate_item(root: Path, claim: dict[str, Any], item: dict[str, Any], item_id: str) -> list[Finding]:
    claim_id = clean(claim.get("claim_id"))
    findings: list[Finding] = []
    question = clean(item.get("question"))
    if question and question != clean(claim.get("question")):
        findings.append(Finding("FAIL", "misbound", claim_id, item_id, "storyboard question does not match the ledger claim"))
    require_text(findings, item, "reader_question", claim_id, item_id)
    require_text(findings, item, "intended_inference", claim_id, item_id)
    require_text(findings, item, "backend_rationale", claim_id, item_id)
    require_text(findings, item, "paper_location", claim_id, item_id)
    alternatives = item.get("alternatives_considered")
    if not isinstance(alternatives, list) or not alternatives:
        findings.append(Finding("FAIL", "alternatives", claim_id, item_id, "alternatives_considered must record at least one rejected form"))

    form = clean(item.get("chosen_evidence_form"))
    if form not in EVIDENCE_FORMS or form == "unresolved":
        findings.append(Finding("FAIL", "evidence_form", claim_id, item_id, "chosen evidence form is unresolved or unsupported"))
        return findings
    if form in {"table", "figure", "diagram"}:
        require_text(findings, item, "caption", claim_id, item_id)
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        findings.append(Finding("FAIL", "provenance", claim_id, item_id, "provenance must be an object"))
        return findings

    if form == "no_visual_waiver":
        findings.extend(validate_waiver(root, claim_id, item_id, item.get("waiver")))
        return findings

    artifact = artifact_for(item)
    source_data = clean(provenance.get("source_data"))
    script = clean(provenance.get("script"))
    backend = clean(item.get("backend")).lower()
    if is_placeholder(artifact):
        findings.append(Finding("FAIL", "artifact", claim_id, item_id, "evidence output is missing"))
    elif not project_file_exists(root, artifact):
        findings.append(Finding("FAIL", "artifact", claim_id, item_id, f"evidence output does not exist: {artifact}"))
    if is_placeholder(source_data):
        findings.append(Finding("FAIL", "provenance", claim_id, item_id, "source_data is missing"))
    elif not project_file_exists(root, source_data):
        findings.append(Finding("FAIL", "provenance", claim_id, item_id, f"source_data does not exist: {source_data}"))

    if form in VISUAL_FORMS:
        allowed = {"python", "matlab"} | ({"mermaid"} if form == "diagram" else set())
        if backend not in allowed:
            findings.append(Finding("FAIL", "backend", claim_id, item_id, f"{form} backend must be one of {sorted(allowed)}"))
        if "drawio" in backend or "draw.io" in backend:
            findings.append(Finding("FAIL", "backend", claim_id, item_id, "draw.io is retired for new Mira evidence"))
        if is_placeholder(script):
            findings.append(Finding("FAIL", "provenance", claim_id, item_id, "visual generation script is missing"))
        elif not project_file_exists(root, script):
            findings.append(Finding("FAIL", "provenance", claim_id, item_id, f"generation script does not exist: {script}"))
        if not is_placeholder(artifact) and project_file_exists(root, artifact):
            findings.extend(validate_visual_artifact(root, claim_id, item_id, artifact, backend, form))
    elif form == "table":
        if backend not in {"none", "python", "matlab"}:
            findings.append(Finding("FAIL", "backend", claim_id, item_id, "table backend must be none, python, or matlab"))
        if script not in {"", "not_applicable"} and not project_file_exists(root, script):
            findings.append(Finding("FAIL", "provenance", claim_id, item_id, f"table script does not exist: {script}"))
    elif form == "proof":
        if backend != "none":
            findings.append(Finding("FAIL", "backend", claim_id, item_id, "proof backend must be none"))
    return findings


def validate_visual_artifact(
    root: Path,
    claim_id: str,
    item_id: str,
    artifact: str,
    backend: str,
    form: str,
) -> list[Finding]:
    findings: list[Finding] = []
    artifact_path = project_path(root, artifact)
    if form == "figure":
        png = artifact_path.with_suffix(".png")
        pdf = artifact_path.with_suffix(".pdf")
        if not png.is_file() or not pdf.is_file():
            findings.append(Finding("FAIL", "render", claim_id, item_id, "figure requires PNG and vector PDF companions"))
        summary_path = root / "results" / "figures_data" / f"{artifact_path.stem}_summary.json"
        summary = load_json(summary_path) if summary_path.exists() else {}
        if not summary:
            findings.append(Finding("FAIL", "provenance", claim_id, item_id, "claim-oriented figure summary is missing or invalid"))
        else:
            if clean(summary.get("claim_id")) != claim_id:
                findings.append(Finding("FAIL", "misbound", claim_id, item_id, "figure summary claim_id does not match the storyboard"))
            summary_backend = clean(summary.get("backend")).lower()
            if backend == "python" and "python" not in summary_backend:
                findings.append(Finding("FAIL", "backend", claim_id, item_id, "figure summary does not prove Python execution"))
            if backend == "matlab" and not summary_backend.startswith("matlab"):
                findings.append(Finding("FAIL", "backend", claim_id, item_id, "figure summary does not prove MATLAB execution"))
    if backend == "matlab":
        capability = load_json(root / "results" / "logs" / "matlab_visual_capability.json")
        execution_errors = validate_execution_record(root, capability, require_success=True)
        if execution_errors:
            findings.append(Finding(
                "FAIL",
                "backend",
                claim_id,
                item_id,
                "a valid successful MATLAB MCP or batch execution record is required: "
                + "; ".join(execution_errors),
            ))
        elif claim_id not in matlab_capability_claim_ids(capability):
            findings.append(Finding("FAIL", "misbound", claim_id, item_id, "MATLAB execution record claim_id does not match the storyboard"))
    return findings


def matlab_capability_claim_ids(capability: dict[str, Any]) -> set[str]:
    """Return claim bindings from the canonical request and compatibility fields."""
    bindings = [capability]
    request = capability.get("request")
    if isinstance(request, dict):
        bindings.append(request)
    claim_ids: set[str] = set()
    for binding in bindings:
        claim_ids.add(clean(binding.get("claim_id")))
        raw_claim_ids = binding.get("claim_ids")
        if isinstance(raw_claim_ids, list):
            claim_ids.update(clean(item) for item in raw_claim_ids)
    return {item for item in claim_ids if item}


def validate_waiver(root: Path, claim_id: str, item_id: str, waiver: Any) -> list[Finding]:
    if not isinstance(waiver, dict) or waiver.get("applies") is not True:
        return [Finding("FAIL", "waiver", claim_id, item_id, "no-visual decision requires an active waiver")]
    findings: list[Finding] = []
    for field in ("reason", "scope"):
        if is_placeholder(clean(waiver.get(field))):
            findings.append(Finding("FAIL", "waiver", claim_id, item_id, f"waiver {field} is missing"))
    evidence = waiver.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        findings.append(Finding("FAIL", "waiver", claim_id, item_id, "waiver evidence is missing"))
    else:
        for path in evidence:
            if not project_file_exists(root, clean(path)):
                findings.append(Finding("FAIL", "waiver", claim_id, item_id, f"waiver evidence does not exist: {path}"))
    return findings


def detect_redundancy(grouped: dict[str, list[dict[str, Any]]], findings: list[Finding]) -> None:
    for claim_id, items in grouped.items():
        seen: dict[tuple[str, str, str], str] = {}
        for index, item in enumerate(items, start=1):
            item_id = clean(item.get("_resolved_item_id")) or clean(item.get("item_id")) or f"item-{index}"
            signature = (
                clean(item.get("chosen_evidence_form")),
                artifact_for(item).lower(),
                clean(item.get("intended_inference")).lower(),
            )
            if signature in seen:
                findings.append(
                    Finding(
                        "FAIL",
                        "redundant",
                        claim_id,
                        item_id,
                        f"duplicates the evidence form, artifact, and inference of {seen[signature]}",
                    )
                )
            else:
                seen[signature] = item_id


def require_text(
    findings: list[Finding],
    item: dict[str, Any],
    field: str,
    claim_id: str,
    item_id: str,
) -> None:
    if is_placeholder(clean(item.get(field))):
        findings.append(Finding("FAIL", field, claim_id, item_id, f"{field} is missing or placeholder"))


def artifact_for(item: dict[str, Any]) -> str:
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    return clean(item.get("artifact") or provenance.get("output") or item.get("source_artifact"))


def is_central(entry: dict[str, Any]) -> bool:
    return entry.get("centrality") == "central" or entry.get("final_claim") is True


def recommendation_for(claim: dict[str, Any]) -> str:
    claim_type = clean(claim.get("claim_type"))
    if claim_type in {"bound", "threshold", "regime", "uncertainty", "comparison"}:
        return "bind a rendered comparison/threshold figure or record why a proof/table is clearer"
    if claim_type == "mechanism":
        return "bind a mechanism proof or reproducible structural diagram"
    return "bind the clearest proof, table, figure, diagram, or scoped no-visual waiver"


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def metrics(coverage: list[ClaimCoverage], findings: list[Finding]) -> dict[str, int]:
    return {
        "final_claims": len(coverage),
        "central_claims": len(coverage),
        "covered": sum(item.status == "covered" for item in coverage),
        "missing": sum(item.status == "missing" for item in coverage),
        "misbound": sum(item.axis == "misbound" and item.level == "FAIL" for item in findings),
        "redundant": sum(item.axis == "redundant" and item.level == "FAIL" for item in findings),
        "failures": sum(item.level == "FAIL" for item in findings),
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Central-Claim Evidence Coverage",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        "- Authority: non-authoritative coverage report; edit the result ledger or storyboard, not this file.",
        "",
        "## Coverage Matrix",
        "",
        "| Status | Claim | Key | Form | Artifact | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            f"| {item['status']} | `{item['claim_id']}` | `{item['key']}` | "
            f"{escape(', '.join(item['evidence_forms']) or '-')} | "
            f"{escape(', '.join(item['artifacts']) or '-')} | {escape(item['recommendation'])} |"
        )
    lines.extend(["", "## Findings", "", "| Level | Axis | Claim | Item | Message |", "|---|---|---|---|---|"])
    for item in payload["findings"]:
        lines.append(
            f"| {item['level']} | `{item['axis']}` | `{item['claim_id']}` | "
            f"`{item['item_id']}` | {escape(item['message'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def project_path(root: Path, value: str) -> Path:
    raw = value.split("#", 1)[0]
    path = Path(raw)
    return path if path.is_absolute() else root / path


def project_file_exists(root: Path, value: str) -> bool:
    return bool(value) and project_path(root, value).is_file()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def clean(value: Any) -> str:
    return str(value or "").strip()


def is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDERS


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _print(value: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(value, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--ledger-json", default="planning/result_ledger.json", help="Result ledger JSON path")
    parser.add_argument("--storyboard-json", default="planning/figure_storyboard.json", help="Claim-evidence storyboard JSON path")
    parser.add_argument("--check", action="store_true", help="Fail contest_final when central-claim coverage is incomplete")
    parser.add_argument("--output-level", default="reproducible_draft")
    parser.add_argument("--write-report", help="Write markdown coverage report")
    parser.add_argument("--write-json", help="Write JSON coverage report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
