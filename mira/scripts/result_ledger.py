#!/usr/bin/env python3
"""Build Mira's canonical result ledger from frozen result artifacts."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


QUESTION_RE = re.compile(r"(?:^|\.)(q\d+)(?=[._]|$)", re.I)
CLAIM_ID_RE = re.compile(r"^CLM-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
CENTRALITIES = {"central", "supporting", "context"}
CLAIM_TYPES = {
    "numeric_result",
    "comparison",
    "mechanism",
    "threshold",
    "bound",
    "regime",
    "counterexample",
    "decision",
    "uncertainty",
    "feasibility",
    "unclassified",
}
INSIGHT_FORMS = {
    "mechanism",
    "threshold",
    "bound",
    "regime",
    "counterexample",
    "value_of_information",
    "none",
}
SURPRISE_STATUSES = {"expected", "surprising", "mixed", "not_assessed"}
WAIVABLE_FIELDS = {"insight_form", "mechanism", "decision_implication", "surprise_status"}


@dataclass
class LedgerEntry:
    key: str
    question: str
    label: str
    value: Any
    value_type: str
    canonical_strings: list[str]
    stale_strings: list[str]
    source_path: str
    evidence: list[str]
    confidence: str
    final_claim: bool
    claim_id: str
    centrality: str
    claim_type: str
    insight_form: str
    mechanism: str
    scope: str
    assumptions: list[str]
    uncertainty: dict[str, str]
    decision_implication: str
    surprise_status: str
    waiver: dict[str, Any] | None


@dataclass
class Finding:
    level: str
    claim_id: str
    key: str
    field: str
    message: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    frozen_path = resolve_path(root, args.frozen)
    confidence_path = resolve_path(root, args.confidence_json) if args.confidence_json else root / "checks" / "result_confidence_report.json"
    stale_map = load_stale_map(resolve_path(root, args.stale_map)) if args.stale_map else {}
    if not frozen_path.exists():
        _print(f"FAIL: missing frozen numbers: {rel(root, frozen_path)}")
        return 1
    frozen = load_json(frozen_path)
    confidence = load_json(confidence_path) if confidence_path.exists() else {}
    existing_path = resolve_path(root, args.write_json) if args.write_json else root / "planning" / "result_ledger.json"
    existing = load_json(existing_path) if existing_path.exists() else {}
    entries = build_entries(root, frozen_path, frozen, confidence, stale_map, existing)
    findings = validate_entries(entries)
    payload = {
        "schema_version": 2,
        "generated_at": now(),
        "root": str(root),
        "frozen_numbers": rel(root, frozen_path),
        "confidence_json": rel(root, confidence_path) if confidence_path.exists() else "",
        "entry_count": len(entries),
        "entries": [asdict(item) for item in entries],
        "migration": migration_summary(existing, entries),
        "insight_validation": {
            "verdict": validation_verdict(findings),
            "metrics": validation_metrics(entries, findings),
            "findings": [asdict(item) for item in findings],
        },
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"ledger_entries: {len(entries)}")
    _print(f"insight_validation: {payload['insight_validation']['verdict']}")
    for finding in findings:
        if finding.level in {"FAIL", "WARN"}:
            _print(f"{finding.level}: [{finding.field}] {finding.claim_id or finding.key}: {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    strict_check = args.check and args.output_level == "contest_final"
    return 1 if strict_check and payload["insight_validation"]["verdict"] == "FAIL" else 0


def build_entries(
    root: Path,
    frozen_path: Path,
    frozen: dict[str, Any],
    confidence: dict[str, Any],
    stale_map: dict[str, list[str]],
    existing: dict[str, Any] | None = None,
) -> list[LedgerEntry]:
    confidence_by_path = {
        str(item.get("path")): item
        for item in confidence.get("grades", [])
        if isinstance(item, dict) and item.get("path")
    }
    existing_by_key = {
        str(item.get("key")): item
        for item in (existing or {}).get("entries", [])
        if isinstance(item, dict) and item.get("key")
    }
    entries: list[LedgerEntry] = []
    for key, value in flatten_values(frozen):
        question = question_for(key)
        if not question:
            continue
        if not is_public_result_key(key, value):
            continue
        grade = confidence_by_path.get(key, {})
        old = existing_by_key.get(key, {})
        confidence_class = str(grade.get("confidence") or infer_confidence(key, value))
        grade_evidence = [str(item) for item in grade.get("evidence", [])] if isinstance(grade.get("evidence"), list) else []
        old_evidence = string_list(old.get("evidence"))
        evidence = unique(grade_evidence + old_evidence + [rel(root, frozen_path)])
        if str(old.get("centrality")) in CENTRALITIES:
            centrality = str(old["centrality"])
        elif old.get("final_claim") is True:
            centrality = "central"
        else:
            centrality = "supporting"
        final_claim = centrality == "central"
        uncertainty = normalize_uncertainty(old.get("uncertainty"))
        waiver = normalize_waiver(old.get("waiver"))
        entries.append(
            LedgerEntry(
                key=key,
                question=question,
                label=str(old.get("label") or label_for(key)),
                value=value,
                value_type=value_type(value),
                canonical_strings=canonical_strings(value),
                stale_strings=stale_map.get(key, string_list(old.get("stale_strings"))),
                source_path=rel(root, frozen_path),
                evidence=evidence,
                confidence=confidence_class,
                final_claim=final_claim,
                claim_id=str(old.get("claim_id") or claim_id_for(key)),
                centrality=centrality,
                claim_type=str(old.get("claim_type") or "unclassified"),
                insight_form=str(old.get("insight_form") or "none"),
                mechanism=str(old.get("mechanism") or "").strip(),
                scope=str(old.get("scope") or "").strip(),
                assumptions=string_list(old.get("assumptions")),
                uncertainty=uncertainty,
                decision_implication=str(old.get("decision_implication") or "").strip(),
                surprise_status=str(old.get("surprise_status") or "not_assessed"),
                waiver=waiver,
            )
        )
    entries.sort(key=lambda item: natural_key(item.key))
    return entries


def validate_entries(entries: list[LedgerEntry]) -> list[Finding]:
    findings: list[Finding] = []
    if not entries:
        return [Finding("FAIL", "-", "-", "ledger_coverage", "no question-scoped result entries were discovered")]
    for question in sorted({entry.question for entry in entries}, key=natural_key):
        if not any(entry.question == question and entry.centrality == "central" for entry in entries):
            findings.append(
                Finding(
                    "FAIL",
                    "-",
                    question,
                    "centrality",
                    f"{question} requires at least one explicitly selected central claim",
                )
            )
    seen_claim_ids: set[str] = set()
    for entry in entries:
        claim_id = entry.claim_id
        if not CLAIM_ID_RE.fullmatch(claim_id):
            findings.append(Finding("FAIL", claim_id, entry.key, "claim_id", "claim_id must use stable CLM-... syntax"))
        elif claim_id in seen_claim_ids:
            findings.append(Finding("FAIL", claim_id, entry.key, "claim_id", "claim_id is duplicated"))
        seen_claim_ids.add(claim_id)
        if entry.centrality not in CENTRALITIES:
            findings.append(Finding("FAIL", claim_id, entry.key, "centrality", f"unsupported centrality: {entry.centrality}"))
        if entry.claim_type not in CLAIM_TYPES:
            findings.append(Finding("FAIL", claim_id, entry.key, "claim_type", f"unsupported claim_type: {entry.claim_type}"))
        if entry.insight_form not in INSIGHT_FORMS:
            findings.append(Finding("FAIL", claim_id, entry.key, "insight_form", f"unsupported insight_form: {entry.insight_form}"))
        if entry.surprise_status not in SURPRISE_STATUSES:
            findings.append(Finding("FAIL", claim_id, entry.key, "surprise_status", f"unsupported surprise_status: {entry.surprise_status}"))
        if not isinstance(entry.assumptions, list):
            findings.append(Finding("FAIL", claim_id, entry.key, "assumptions", "assumptions must be a list"))
        if entry.waiver and not valid_waiver(entry.waiver):
            findings.append(Finding("FAIL", claim_id, entry.key, "waiver", "waiver requires allowed fields, reason, scope, and evidence"))
        if entry.centrality != "central":
            continue
        required_text = {
            "mechanism": entry.mechanism,
            "decision_implication": entry.decision_implication,
        }
        if entry.claim_type == "unclassified":
            findings.append(Finding("FAIL", claim_id, entry.key, "claim_type", "central claim must be classified"))
        if not entry.scope:
            findings.append(Finding("FAIL", claim_id, entry.key, "scope", "central claim requires a validity scope"))
        if not entry.evidence:
            findings.append(Finding("FAIL", claim_id, entry.key, "evidence", "central claim requires evidence paths"))
        if not entry.uncertainty.get("characterization", "").strip():
            findings.append(Finding("FAIL", claim_id, entry.key, "uncertainty", "central claim requires uncertainty characterization"))
        if not entry.uncertainty.get("decision_switch_risk", "").strip():
            findings.append(Finding("FAIL", claim_id, entry.key, "uncertainty", "central claim requires decision-switch risk"))
        if entry.insight_form == "none" and not field_waived(entry, "insight_form"):
            findings.append(Finding("FAIL", claim_id, entry.key, "insight_form", "central claim needs an insight form or scoped waiver"))
        for field, value in required_text.items():
            if not value and not field_waived(entry, field):
                findings.append(Finding("FAIL", claim_id, entry.key, field, f"central claim requires {field} or scoped waiver"))
        if entry.surprise_status == "not_assessed" and not field_waived(entry, "surprise_status"):
            findings.append(Finding("FAIL", claim_id, entry.key, "surprise_status", "central claim must record expected/surprising status or waiver"))
    if not findings:
        findings.append(Finding("INFO", "-", "-", "schema", "all result-ledger v2 entries satisfy the insight contract"))
    return findings


def field_waived(entry: LedgerEntry, field: str) -> bool:
    waiver = entry.waiver
    return bool(valid_waiver(waiver) and field in waiver.get("waived_fields", []))


def valid_waiver(waiver: dict[str, Any] | None) -> bool:
    if not isinstance(waiver, dict) or waiver.get("applies") is not True:
        return False
    fields = waiver.get("waived_fields")
    if not isinstance(fields, list) or not fields or any(str(item) not in WAIVABLE_FIELDS for item in fields):
        return False
    return bool(str(waiver.get("reason") or "").strip() and str(waiver.get("scope") or "").strip() and string_list(waiver.get("evidence")))


def normalize_uncertainty(value: Any) -> dict[str, str]:
    data = value if isinstance(value, dict) else {}
    return {
        "characterization": str(data.get("characterization") or "").strip(),
        "decision_switch_risk": str(data.get("decision_switch_risk") or "").strip(),
    }


def normalize_waiver(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("applies") is not True:
        return None
    return {
        "applies": True,
        "waived_fields": unique(string_list(value.get("waived_fields"))),
        "reason": str(value.get("reason") or "").strip(),
        "scope": str(value.get("scope") or "").strip(),
        "evidence": unique(string_list(value.get("evidence"))),
    }


def claim_id_for(key: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", key.upper()).strip("-")
    return f"CLM-{slug}"


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def migration_summary(existing: dict[str, Any], entries: list[LedgerEntry]) -> dict[str, Any]:
    if not existing:
        return {"source_schema_version": None, "migrated": False, "matched_entries": 0}
    source_version = existing.get("schema_version", 1)
    old_keys = {str(item.get("key")) for item in existing.get("entries", []) if isinstance(item, dict) and item.get("key")}
    matched = sum(1 for entry in entries if entry.key in old_keys)
    return {
        "source_schema_version": source_version,
        "migrated": source_version != 2,
        "matched_entries": matched,
    }


def validation_verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def validation_metrics(entries: list[LedgerEntry], findings: list[Finding]) -> dict[str, int]:
    central = [entry for entry in entries if entry.centrality == "central"]
    failed_ids = {item.claim_id for item in findings if item.level == "FAIL"}
    return {
        "entries": len(entries),
        "central_claims": len(central),
        "complete_central_claims": sum(1 for entry in central if entry.claim_id not in failed_ids),
        "waived_central_claims": sum(1 for entry in central if entry.waiver is not None),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }


def flatten_values(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.extend(flatten_values(value, next_prefix))
    elif isinstance(data, list):
        if all(is_scalar(item) for item in data):
            out.append((prefix, data))
        else:
            for index, value in enumerate(data):
                out.extend(flatten_values(value, f"{prefix}.{index}"))
    elif is_scalar(data):
        out.append((prefix, data))
    return out


def is_public_result_key(key: str, value: Any) -> bool:
    lower = key.lower()
    excluded_suffixes = (".status", ".search_records", ".source", ".source_path", ".file", ".path", ".log", ".stage")
    if lower.endswith(excluded_suffixes):
        return False
    if "result_files" in lower:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, list):
        return True
    public_string_terms = ("strategy", "policy", "action", "route", "scenario", "phase", "mode")
    return isinstance(value, str) and any(term in lower for term in public_string_terms)


def question_for(key: str) -> str:
    match = QUESTION_RE.search(key)
    return match.group(1).upper() if match else ""


def is_final_claim(key: str, confidence: str) -> bool:
    lower = key.lower()
    if "integer_second" in lower or "candidate" in lower or "baseline_" in lower or "best_" in lower:
        return False
    if confidence == "single_run_or_sampled":
        return False
    return True


def canonical_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, float):
        out.extend(
            [
                f"{value:.12g}",
                f"{value:.10g}",
                f"{value:.8g}",
                f"{value:.6f}".rstrip("0").rstrip("."),
            ]
        )
        if abs(value) >= 1e-4:
            out.append(f"{value:.5f}".rstrip("0").rstrip("."))
        if abs(value) >= 1e-3:
            out.append(f"{value:.4f}".rstrip("0").rstrip("."))
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, list):
        out.append(json.dumps(value, ensure_ascii=False))
        if all(isinstance(item, int) for item in value):
            out.append(", ".join(str(item) for item in value))
            out.append("-".join(str(item) for item in value))
            out.append(" and ".join(str(item) for item in value))
    elif isinstance(value, str):
        out.append(value)
    return unique([item for item in out if item not in {"", "-0", "-0.0"}])


def label_for(key: str) -> str:
    tail = key.split(".")[-1]
    return tail.replace("_", " ")


def value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    return "string"


def infer_confidence(key: str, value: Any) -> str:
    lower = key.lower()
    if "integer_second" in lower:
        return "single_run_or_sampled"
    if any(term in lower for term in ["max", "min", "peak", "stop_time", "pitch", "factor"]):
        return "refined_continuous"
    if any(term in lower for term in ["error", "gap", "margin", "collision"]):
        return "audited_simulation"
    return "audited_simulation"


def load_stale_map(path: Path) -> dict[str, list[str]]:
    data = load_json(path)
    if isinstance(data, dict):
        return {
            str(key): [str(item) for item in value]
            for key, value in data.items()
            if isinstance(value, list)
        }
    return {}


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Result Ledger",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        f"- Frozen numbers: `{payload['frozen_numbers']}`",
        f"- Schema version: {payload['schema_version']}",
        f"- Entries: {payload['entry_count']}",
        f"- Insight validation: **{payload['insight_validation']['verdict']}**",
        "",
        "## Canonical Results",
        "",
        "| Claim | Key | Centrality | Type | Insight | Value | Confidence | Scope | Decision implication |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]
    for item in payload["entries"]:
        lines.append(
            "| {claim_id} | {key} | {centrality} | {claim_type} | {insight_form} | {value} | {confidence} | {scope} | {decision} |".format(
                claim_id=f"`{item['claim_id']}`",
                key=f"`{item['key']}`",
                centrality=item["centrality"],
                claim_type=item["claim_type"],
                insight_form=item["insight_form"],
                value=escape(format_value(item["value"])),
                confidence=item["confidence"],
                scope=escape(item["scope"] or "-"),
                decision=escape(item["decision_implication"] or "-"),
            )
        )
    lines.extend(["", "## Insight Validation", "", "| Level | Claim | Field | Message |", "|---|---|---|---|"])
    for item in payload["insight_validation"]["findings"]:
        lines.append(f"| {item['level']} | `{item['claim_id']}` | `{item['field']}` | {escape(item['message'])} |")
    lines.append("")
    return "\n".join(lines)


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, bool) and (not isinstance(value, float) or math.isfinite(value))


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    return json.dumps(value, ensure_ascii=False)


def natural_key(text: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


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
    parser.add_argument("--frozen", default="results/frozen_numbers.json", help="Frozen numbers JSON path")
    parser.add_argument("--confidence-json", help="Result confidence JSON path")
    parser.add_argument("--stale-map", help="Optional JSON mapping result key to forbidden stale strings")
    parser.add_argument("--check", action="store_true", help="Fail when central result-ledger v2 claims are incomplete")
    parser.add_argument("--output-level", default="reproducible_draft", help="Reserved for command-profile compatibility")
    parser.add_argument("--write-report", help="Write markdown ledger")
    parser.add_argument("--write-json", help="Write JSON ledger")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
