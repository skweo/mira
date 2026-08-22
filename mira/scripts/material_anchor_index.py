#!/usr/bin/env python3
"""Index extracted materials into page/paragraph anchors and audit source claims."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


BASES = {"quoted", "inferred", "not_explicit"}


@dataclass
class Finding:
    level: str
    code: str
    claim_id: str
    message: str
    evidence: list[str]


def index_text(source_name: str, text_path: str, text: str) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    page: int | None = None
    paragraph = 0
    heading = ""
    chunks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    for raw in chunks:
        chunk = raw.strip()
        if not chunk:
            continue
        page_match = re.fullmatch(r"#{1,6}\s*Page\s+(\d+)", chunk, flags=re.I)
        if page_match:
            page = int(page_match.group(1))
            paragraph = 0
            heading = ""
            continue
        if chunk.startswith("#"):
            heading = re.sub(r"^#{1,6}\s*", "", chunk).strip()
            continue
        paragraph += 1
        locator = f"{source_name}#"
        if page is not None:
            locator += f"page={page}&paragraph={paragraph}"
        else:
            locator += f"paragraph={paragraph}"
        blocks.append(
            {
                "locator": locator,
                "page": page,
                "paragraph": paragraph,
                "heading": heading,
                "text": chunk,
            }
        )
    return {"schema_version": 1, "source_name": source_name, "text_path": text_path, "blocks": blocks}


def validate_claim_anchors(index: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    findings: list[Finding] = []
    blocks = {str(item.get("locator") or ""): item for item in index.get("blocks", []) if isinstance(item, dict)}
    claims = contract.get("claims")
    if contract.get("schema_version") != 1:
        _add(findings, "FAIL", "schema_version", "contract", "schema_version must be 1")
    if not isinstance(claims, list):
        _add(findings, "FAIL", "claims_type", "contract", "claims must be a list")
        claims = []
    seen: set[str] = set()
    for row in claims:
        if not isinstance(row, dict):
            _add(findings, "FAIL", "claim_type", "contract", "claim anchor must be an object")
            continue
        claim_id = str(row.get("claim_id") or "")
        locator = str(row.get("locator") or "")
        basis = str(row.get("basis") or "").lower()
        excerpt = str(row.get("excerpt") or "").strip()
        reasoning = str(row.get("reasoning") or "").strip()
        if not claim_id or claim_id in seen:
            _add(findings, "FAIL", "claim_id", claim_id or "contract", "claim_id is missing or duplicated")
        seen.add(claim_id)
        if basis not in BASES:
            _add(findings, "FAIL", "basis", claim_id, "basis must be quoted, inferred, or not_explicit")
        block = blocks.get(locator)
        if block is None:
            _add(findings, "FAIL", "locator", claim_id, "locator does not resolve to an indexed block", locator)
            continue
        source_path = str(row.get("source_path") or "")
        if source_path and normalize_path(source_path) != normalize_path(str(index.get("text_path") or "")):
            _add(findings, "FAIL", "source_path", claim_id, "claim source_path does not match the indexed text", source_path)
        source_text = normalize_text(str(block.get("text") or ""))
        normalized_excerpt = normalize_text(excerpt)
        if basis == "quoted":
            if not normalized_excerpt or normalized_excerpt not in source_text:
                _add(findings, "FAIL", "quote_mismatch", claim_id, "quoted excerpt is not present at the declared locator", excerpt)
        elif basis == "inferred":
            if len(reasoning) < 20:
                _add(findings, "FAIL", "inference_reasoning", claim_id, "inferred claim needs a substantive reasoning chain")
            if not normalized_excerpt or normalized_excerpt not in source_text:
                _add(findings, "FAIL", "inference_excerpt", claim_id, "inference must quote the exact source premise separately from the inferred conclusion", excerpt)
        elif basis == "not_explicit":
            if len(reasoning) < 20:
                _add(findings, "FAIL", "not_explicit_reasoning", claim_id, "not_explicit status needs a reason and downstream handling")
            if excerpt:
                _add(findings, "WARN", "not_explicit_excerpt", claim_id, "not_explicit records should not present text as a direct quote")
    fail_count = sum(item.level == "FAIL" for item in findings)
    return {
        "schema_version": 1,
        "claims_audited": len(claims),
        "findings": [asdict(item) for item in findings],
        "verdict": "FAIL" if fail_count else "PASS",
    }


def build_index(text_dir: Path, root: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for path in sorted(text_dir.rglob("*")) if text_dir.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        source_name = _source_name(path)
        sources.append(index_text(source_name, relative(root, path), path.read_text(encoding="utf-8-sig", errors="replace")))
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "sources": sources,
        "blocks": [block for source in sources for block in source["blocks"]],
    }


def validate_project(index: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    claims = contract.get("claims") if isinstance(contract.get("claims"), list) else []
    by_path = {normalize_path(str(source.get("text_path") or "")): source for source in index.get("sources", []) if isinstance(source, dict)}
    for path, rows in _group_claims(claims).items():
        source = by_path.get(normalize_path(path))
        if source is None:
            findings.append(asdict(Finding("FAIL", "source_path", "contract", "source_path is not indexed", [path])))
            continue
        result = validate_claim_anchors(source, {"schema_version": contract.get("schema_version"), "claims": rows})
        findings.extend(result["findings"])
    if not claims:
        findings.append(asdict(Finding("FAIL", "missing_claims", "contract", "material claim anchor contract is empty", [])))
    fail_count = sum(item["level"] == "FAIL" for item in findings)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources_indexed": len(index.get("sources", [])),
        "blocks_indexed": len(index.get("blocks", [])),
        "claims_audited": len(claims),
        "findings": findings,
        "verdict": "FAIL" if fail_count else "PASS",
    }


def _group_claims(claims: list[Any]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for row in claims:
        if isinstance(row, dict):
            output.setdefault(str(row.get("source_path") or ""), []).append(row)
    return output


def _source_name(path: Path) -> str:
    first = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:4]
    for line in first:
        match = re.match(r"^#\s+(.+\.(?:pdf|docx?|pptx?|xlsx?|csv|txt|md))\s*$", line, re.I)
        if match:
            return match.group(1).strip()
    return path.stem


def _add(findings: list[Finding], level: str, code: str, claim_id: str, message: str, *evidence: str) -> None:
    findings.append(Finding(level, code, claim_id, message, [item for item in evidence if item]))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lower().strip()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Material Anchor Audit", "", f"- Verdict: **{payload['verdict']}**", f"- Sources indexed: `{payload['sources_indexed']}`", f"- Blocks indexed: `{payload['blocks_indexed']}`", f"- Claims audited: `{payload['claims_audited']}`", ""]
    for item in payload["findings"]:
        lines.append(f"- {item['level']} `{item['claim_id']}/{item['code']}`: {item['message']}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--text-dir", default="materials/extracted")
    parser.add_argument("--contract", default="planning/material_claim_anchors.json")
    parser.add_argument("--write-index", default="checks/material_anchor_index.json")
    parser.add_argument("--write-json", default="checks/material_anchor_report.json")
    parser.add_argument("--write-report", default="checks/material_anchor_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    index = build_index(resolve(root, args.text_dir), root)
    index_path = resolve(root, args.write_index)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contract_path = resolve(root, args.contract)
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        contract = {"schema_version": 0, "claims": []}
        payload = validate_project(index, contract)
        payload["findings"].insert(0, asdict(Finding("FAIL", "contract_load", "contract", str(exc), [str(contract_path)])))
        payload["verdict"] = "FAIL"
    else:
        payload = validate_project(index, contract)
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"sources_indexed: {payload['sources_indexed']}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
