#!/usr/bin/env python3
"""Audit end-to-end evidence chains for central contest-paper claims."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_STAGES = (
    "problem_interpretation",
    "model_derivation",
    "result_evidence",
    "validation",
    "paper_conclusion",
)


@dataclass
class Finding:
    level: str
    code: str
    claim_id: str
    stage: str
    message: str
    evidence: list[str]


def evaluate_contract(root: Path, contract: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    findings: list[Finding] = []
    chains = contract.get("chains")
    entries = ledger.get("entries")
    if contract.get("schema_version") != 1:
        add(findings, "FAIL", "schema_version", "contract", "contract", "schema_version must be 1")
    if not isinstance(chains, list):
        add(findings, "FAIL", "chains_type", "contract", "contract", "chains must be a list")
        chains = []
    if not isinstance(entries, list):
        add(findings, "FAIL", "ledger_entries", "ledger", "ledger", "result ledger entries must be a list")
        entries = []

    central_claims = central_claim_ids(entries)
    seen_chain_ids: set[str] = set()
    seen_claim_ids: set[str] = set()
    complete_claim_ids: set[str] = set()

    for raw in chains:
        if not isinstance(raw, dict):
            add(findings, "FAIL", "chain_type", "contract", "contract", "each evidence chain must be an object")
            continue
        chain_id = str(raw.get("chain_id") or "").strip()
        claim_id = str(raw.get("claim_id") or "").strip()
        before = failure_count(findings)
        if not chain_id or chain_id in seen_chain_ids:
            add(findings, "FAIL", "chain_id", claim_id or "contract", "contract", "chain_id is missing or duplicated", chain_id)
        seen_chain_ids.add(chain_id)
        if not claim_id or claim_id in seen_claim_ids:
            add(findings, "FAIL", "claim_id", claim_id or "contract", "contract", "claim_id is missing or duplicated", claim_id)
        seen_claim_ids.add(claim_id)
        if claim_id and claim_id not in central_claims:
            add(
                findings,
                "FAIL",
                "noncentral_claim_chain",
                claim_id,
                "contract",
                "evidence-chain records are reserved for central result-ledger claims",
            )

        require_text(findings, raw, "decision_value", claim_id, "contract", 12)
        require_text(findings, raw, "scope", claim_id, "contract", 12)
        require_text(findings, raw, "evidence_gap", claim_id, "contract", 4)
        stages = raw.get("stages")
        if not isinstance(stages, dict):
            add(findings, "FAIL", "stages_type", claim_id, "contract", "stages must be an object")
            stages = {}
        for stage_name in REQUIRED_STAGES:
            validate_stage(root, findings, claim_id, stage_name, stages.get(stage_name))
        if claim_id and failure_count(findings) == before:
            complete_claim_ids.add(claim_id)

    for claim_id in sorted(central_claims - seen_claim_ids):
        add(
            findings,
            "FAIL",
            "missing_central_claim_chain",
            claim_id,
            "contract",
            "central result-ledger claim has no complete contest evidence chain",
        )
    if not central_claims:
        add(findings, "FAIL", "missing_central_claims", "ledger", "ledger", "result ledger contains no central claims")

    fail_total = failure_count(findings)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "required_stages": list(REQUIRED_STAGES),
        "metrics": {
            "central_claims": len(central_claims),
            "chains": len(chains),
            "central_claims_covered": len(complete_claim_ids & central_claims),
            "failures": fail_total,
        },
        "findings": [asdict(item) for item in findings],
        "verdict": "FAIL" if fail_total else "PASS",
    }


def central_claim_ids(entries: list[Any]) -> set[str]:
    output: set[str] = set()
    for row in entries:
        if not isinstance(row, dict):
            continue
        centrality = str(row.get("centrality") or "").lower()
        is_central = centrality == "central" or (not centrality and row.get("final_claim") is True)
        claim_id = str(row.get("claim_id") or "").strip()
        if is_central and claim_id:
            output.add(claim_id)
    return output


def validate_stage(
    root: Path,
    findings: list[Finding],
    claim_id: str,
    stage_name: str,
    stage: Any,
) -> None:
    if not isinstance(stage, dict):
        add(findings, "FAIL", "missing_chain_stage", claim_id, stage_name, f"missing required stage: {stage_name}")
        return
    require_text(findings, stage, "statement", claim_id, stage_name, 12)
    artifact = str(stage.get("artifact") or "").strip()
    locator = str(stage.get("locator") or "").strip()
    artifact_path: Path | None = None
    if not artifact:
        add(findings, "FAIL", "missing_stage_artifact", claim_id, stage_name, "stage artifact is required")
    else:
        artifact_path = resolve(root, artifact)
        if not within(root, artifact_path) or not artifact_path.is_file():
            add(
                findings,
                "FAIL",
                "missing_stage_artifact",
                claim_id,
                stage_name,
                "stage artifact does not resolve to a project file",
                artifact,
            )
    if not locator or not locator_resolves_to_artifact(locator, artifact, artifact_path):
        add(
            findings,
            "FAIL",
            "unresolved_stage_locator",
            claim_id,
            stage_name,
            "stage locator must anchor a page, paragraph, line, row, cell, or named section in its artifact",
            locator,
        )


def locator_resolves_to_artifact(locator: str, artifact: str, artifact_path: Path | None = None) -> bool:
    if not locator or not artifact:
        return False
    normalized_locator = normalize_path(locator)
    normalized_artifact = normalize_path(artifact)
    if not normalized_locator.startswith(normalized_artifact):
        return False
    suffix = normalized_locator[len(normalized_artifact) :]
    if not re.match(
        r"^(?::\d+(?::\d+)?|#(?:page|paragraph|section|row|cell|figure|table)=|\?(?:page|sheet|cell|row)=)",
        suffix,
    ):
        return False
    if artifact_path is None or not artifact_path.is_file():
        return artifact_path is None

    line_match = re.fullmatch(r":(\d+)(?::(\d+))?", suffix)
    if line_match:
        lines = read_text_lines(artifact_path)
        line_number = int(line_match.group(1))
        if lines is None or line_number < 1 or line_number > len(lines):
            return False
        column = int(line_match.group(2)) if line_match.group(2) else None
        return column is None or 1 <= column <= len(lines[line_number - 1]) + 1

    paragraph_match = re.match(r"^#paragraph=(\d+)(?:&|$)", suffix)
    if paragraph_match and artifact_path.suffix.lower() in {".md", ".txt", ".tex"}:
        lines = read_text_lines(artifact_path)
        if lines is None:
            return False
        paragraphs = [item for item in re.split(r"\n\s*\n", "\n".join(lines)) if item.strip()]
        number = int(paragraph_match.group(1))
        return 1 <= number <= len(paragraphs)

    row_match = re.match(r"^#row=(\d+)(?:&|$)", suffix)
    if row_match and artifact_path.suffix.lower() in {".csv", ".tsv", ".txt", ".md"}:
        lines = read_text_lines(artifact_path)
        number = int(row_match.group(1))
        return lines is not None and 1 <= number <= len(lines)
    return True


def read_text_lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return None


def require_text(
    findings: list[Finding],
    row: dict[str, Any],
    field: str,
    claim_id: str,
    stage: str,
    minimum: int,
) -> None:
    value = str(row.get(field) or "").strip()
    if len(value) < minimum:
        add(findings, "FAIL", f"missing_{field}", claim_id, stage, f"{field} requires at least {minimum} characters")


def add(
    findings: list[Finding],
    level: str,
    code: str,
    claim_id: str,
    stage: str,
    message: str,
    *evidence: str,
) -> None:
    findings.append(Finding(level, code, claim_id, stage, message, [item for item in evidence if item]))


def failure_count(findings: list[Finding]) -> int:
    return sum(item.level == "FAIL" for item in findings)


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lower().strip()


def within(root: Path, path: Path) -> bool:
    return path == root or root in path.parents


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def failure_payload(root: Path, code: str, message: str, evidence: str) -> dict[str, Any]:
    finding = Finding("FAIL", code, "contract", "contract", message, [evidence])
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "required_stages": list(REQUIRED_STAGES),
        "metrics": {"central_claims": 0, "chains": 0, "central_claims_covered": 0, "failures": 1},
        "findings": [asdict(finding)],
        "verdict": "FAIL",
    }


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metrics = payload["metrics"]
    lines = [
        "# Contest Evidence Chain Audit",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Central claims covered: `{metrics['central_claims_covered']}/{metrics['central_claims']}`",
        "- Required chain: problem interpretation -> model/derivation -> result evidence -> validation -> paper conclusion.",
        "",
        "| Level | Claim | Stage | Code | Message |",
        "|---|---|---|---|---|",
    ]
    for item in payload["findings"]:
        message = str(item["message"]).replace("|", "/")
        lines.append(f"| {item['level']} | {item['claim_id']} | {item['stage']} | {item['code']} | {message} |")
    if not payload["findings"]:
        lines.append("| INFO | - | - | complete | all central claims have complete evidence chains |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="planning/contest_evidence_chains.json")
    parser.add_argument("--ledger", default="planning/result_ledger.json")
    parser.add_argument("--write-json", default="checks/contest_evidence_chain_report.json")
    parser.add_argument("--write-report", default="checks/contest_evidence_chain_report.md")
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
        payload = failure_payload(root, "input_load", str(exc), f"{contract_path}; {ledger_path}")
    else:
        payload = evaluate_contract(root, contract, ledger)
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(
        f"central_claims_covered: {payload['metrics']['central_claims_covered']}"
        f"/{payload['metrics']['central_claims']}"
    )
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
