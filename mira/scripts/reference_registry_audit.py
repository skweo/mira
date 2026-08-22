#!/usr/bin/env python3
"""Audit Mira's top-level reference registry and routing contract."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from route_references import (
    CONDITIONAL_REF_OWNER_STAGES,
    MATERIAL_REFS,
    MATERIAL_REF_OWNER_STAGES,
    MAINTENANCE_REFS,
    PUBLIC_RISK_REFS,
    PUBLIC_STAGE_REFS,
    VISUAL_LEAF_RULES,
)


REGISTRY_PATH = Path("references/reference-registry.json")
PUBLIC_STAGES = {"analysis", "modeling", "implementation", "paper"}
ALLOWED_OWNER_STAGES = PUBLIC_STAGES | {"maintenance"}
ALLOWED_CLASSIFICATIONS = {
    "stage_reference", "risk_reference", "visual_reference",
    "indirect_reference", "maintenance_record", "attribution_record",
    "cleanup_candidate",
}
ALLOWED_STATUSES = {
    "active_stage_routed", "active_risk_routed", "active_visual_leaf",
    "active_indirect", "maintenance_only", "attribution_only",
    "candidate_merge", "candidate_archive", "candidate_cleanup",
}
ALLOWED_LOAD_POLICIES = {
    "stage_base", "risk_triggered", "one_visual_leaf", "indirect_only",
    "maintenance_only", "never_runtime", "review_only",
}
ACTIVE_STATUSES = {
    "active_stage_routed", "active_risk_routed", "active_visual_leaf",
    "active_indirect", "maintenance_only",
}
CANDIDATE_STATUSES = {"candidate_merge", "candidate_archive", "candidate_cleanup"}
NON_RUNTIME_STATUSES = CANDIDATE_STATUSES | {"attribution_only"}
REQUIRED_FIELDS = {
    "path", "classification", "owner_stages", "trigger", "callers",
    "tests", "status", "load_policy", "notes",
}


@dataclass(frozen=True)
class Finding:
    level: str
    axis: str
    message: str


def audit_registry(skill_root: Path, registry_path: Path | None = None) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    path = registry_path or skill_root / REGISTRY_PATH
    path = path if path.is_absolute() else skill_root / path
    findings: list[Finding] = []
    entries: list[dict[str, Any]] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        findings.append(Finding("FAIL", "registry", f"missing registry: {rel(skill_root, path)}"))
        return build_result(skill_root, path, entries, findings)
    except json.JSONDecodeError as exc:
        findings.append(Finding("FAIL", "registry", f"invalid registry JSON: {exc}"))
        return build_result(skill_root, path, entries, findings)

    raw_entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list):
        findings.append(Finding("FAIL", "schema", "registry entries must be a list"))
        return build_result(skill_root, path, entries, findings)
    entries = [item for item in raw_entries if isinstance(item, dict)]
    if len(entries) != len(raw_entries):
        findings.append(Finding("FAIL", "schema", "every registry entry must be an object"))

    paths: list[str] = []
    for index, entry in enumerate(entries):
        item_path = str(entry.get("path") or f"entry[{index}]")
        missing = sorted(REQUIRED_FIELDS - set(entry))
        if missing:
            findings.append(Finding("FAIL", "schema", f"{item_path} is missing fields: {', '.join(missing)}"))
            continue
        paths.append(item_path)
        validate_entry(skill_root, entry, findings)

    duplicates = sorted({item for item in paths if paths.count(item) > 1})
    if duplicates:
        findings.append(Finding("FAIL", "coverage", "duplicate registry paths: " + ", ".join(duplicates)))

    actual = {
        rel(skill_root, item)
        for item in (skill_root / "references").glob("*.md")
        if item.is_file()
    }
    registered = set(paths)
    missing = sorted(actual - registered)
    stale = sorted(registered - actual)
    if missing:
        findings.append(Finding("FAIL", "coverage", "unregistered top-level references: " + ", ".join(missing)))
    if stale:
        findings.append(Finding("FAIL", "coverage", "registry paths do not exist: " + ", ".join(stale)))

    validate_route_alignment(entries, findings)
    return build_result(skill_root, path, entries, findings, actual_count=len(actual))


def validate_entry(skill_root: Path, entry: dict[str, Any], findings: list[Finding]) -> None:
    path = str(entry["path"])
    classification = entry["classification"]
    status = entry["status"]
    load_policy = entry["load_policy"]
    owner_stages = entry["owner_stages"]
    trigger = entry["trigger"]
    callers = entry["callers"]
    tests = entry["tests"]

    if not path.startswith("references/") or not path.endswith(".md"):
        findings.append(Finding("FAIL", "path", f"invalid top-level reference path: {path}"))
    if classification not in ALLOWED_CLASSIFICATIONS:
        findings.append(Finding("FAIL", "classification", f"{path} has invalid classification: {classification}"))
    if status not in ALLOWED_STATUSES:
        findings.append(Finding("FAIL", "status", f"{path} has invalid status: {status}"))
    if load_policy not in ALLOWED_LOAD_POLICIES:
        findings.append(Finding("FAIL", "load_policy", f"{path} has invalid load policy: {load_policy}"))
    if not isinstance(owner_stages, list) or not owner_stages:
        findings.append(Finding("FAIL", "owner_stage", f"{path} must name at least one owner stage"))
    elif set(owner_stages) - ALLOWED_OWNER_STAGES:
        findings.append(Finding("FAIL", "owner_stage", f"{path} has invalid owner stages: {owner_stages}"))
    if not isinstance(trigger, dict) or not str(trigger.get("kind") or "").strip() or not str(trigger.get("description") or "").strip():
        findings.append(Finding("FAIL", "trigger", f"{path} must define trigger.kind and trigger.description"))
    if not isinstance(callers, list) or not all(isinstance(item, str) for item in callers):
        findings.append(Finding("FAIL", "caller", f"{path} callers must be a string list"))
        callers = []
    if not isinstance(tests, list) or not all(isinstance(item, str) for item in tests):
        findings.append(Finding("FAIL", "test", f"{path} tests must be a string list"))
        tests = []

    if status in ACTIVE_STATUSES and not callers:
        findings.append(Finding("FAIL", "caller", f"active reference has no caller: {path}"))
    for caller in callers:
        caller_path = skill_root / caller
        if not caller_path.is_file():
            findings.append(Finding("FAIL", "caller", f"{path} names missing caller: {caller}"))
        elif status in ACTIVE_STATUSES:
            caller_text = caller_path.read_text(encoding="utf-8-sig", errors="ignore")
            if path not in caller_text and Path(path).name not in caller_text:
                findings.append(Finding("FAIL", "caller", f"{caller} does not declare its registered reference: {path}"))
    for test in tests:
        if not (skill_root / test).is_file():
            findings.append(Finding("FAIL", "test", f"{path} names missing test: {test}"))
    if status in ACTIVE_STATUSES and not tests and not str(entry.get("test_exemption") or "").strip():
        findings.append(Finding("FAIL", "test", f"active reference has no test or test exemption: {path}"))
    if status == "attribution_only" and load_policy != "never_runtime":
        findings.append(Finding("FAIL", "load_policy", f"attribution record must use never_runtime: {path}"))
    if status in CANDIDATE_STATUSES and load_policy not in {"indirect_only", "review_only"}:
        findings.append(Finding("FAIL", "load_policy", f"cleanup candidate must use indirect_only or review_only: {path}"))


def validate_route_alignment(entries: list[dict[str, Any]], findings: list[Finding]) -> None:
    by_path = {str(item.get("path")): item for item in entries}
    stage_paths = {path for paths in PUBLIC_STAGE_REFS.values() for path in paths}
    risk_paths = {item[1] for item in PUBLIC_RISK_REFS} | set(MATERIAL_REFS.values())
    maintenance_paths = set(MAINTENANCE_REFS.values())
    visual_owners = {item.path: set(item.owner_stages) for item in VISUAL_LEAF_RULES}
    stage_owners = {
        path: {stage for stage, paths in PUBLIC_STAGE_REFS.items() if path in paths}
        for path in stage_paths
    }
    risk_owners = {item[1]: set(item[3]) for item in PUBLIC_RISK_REFS}
    risk_owners.update(
        {MATERIAL_REFS[key]: set(owners) for key, owners in MATERIAL_REF_OWNER_STAGES.items()}
    )
    conditional_owners = {path: set(owners) for path, owners in CONDITIONAL_REF_OWNER_STAGES.items()}
    expected = {
        **{path: "active_stage_routed" for path in stage_paths},
        **{path: "active_risk_routed" for path in risk_paths},
        **{path: "maintenance_only" for path in maintenance_paths},
        **{path: "active_visual_leaf" for path in visual_owners},
        **{path: "active_risk_routed" for path in conditional_owners},
    }
    for path, expected_status in sorted(expected.items()):
        actual = by_path.get(path, {}).get("status")
        if actual != expected_status:
            findings.append(Finding("FAIL", "route_alignment", f"{path} status is {actual!r}, expected {expected_status!r}"))

    for path, owners in sorted(visual_owners.items()):
        entry = by_path.get(path, {})
        if set(entry.get("owner_stages") or []) != owners:
            findings.append(Finding("FAIL", "visual_alignment", f"{path} owner stages do not match its visual leaf"))
        if entry.get("load_policy") != "one_visual_leaf":
            findings.append(Finding("FAIL", "visual_alignment", f"{path} must use one_visual_leaf"))

    expected_owners = {**stage_owners, **risk_owners, **visual_owners, **conditional_owners}
    for path, owners in sorted(expected_owners.items()):
        actual = set(by_path.get(path, {}).get("owner_stages") or [])
        if actual != owners:
            findings.append(Finding("FAIL", "owner_alignment", f"{path} owner stages are {sorted(actual)}, expected {sorted(owners)}"))

    directly_routed = stage_paths | risk_paths | maintenance_paths | set(visual_owners) | set(conditional_owners)
    for path in sorted(directly_routed):
        if by_path.get(path, {}).get("status") in NON_RUNTIME_STATUSES:
            findings.append(Finding("FAIL", "route_alignment", f"non-runtime reference appears in a direct route: {path}"))


def build_result(skill_root: Path, registry_path: Path, entries: list[dict[str, Any]], findings: list[Finding], actual_count: int = 0) -> dict[str, Any]:
    candidates = sorted(str(item.get("path")) for item in entries if item.get("status") in CANDIDATE_STATUSES)
    status_counts: dict[str, int] = {}
    for item in entries:
        status = str(item.get("status") or "invalid")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skill_root": str(skill_root),
        "registry": rel(skill_root, registry_path),
        "verdict": "FAIL" if any(item.level == "FAIL" for item in findings) else "PASS",
        "metrics": {
            "actual_top_level_references": actual_count,
            "registered_references": len(entries),
            "status_counts": dict(sorted(status_counts.items())),
            "cleanup_queue_count": len(candidates),
            "cleanup_queue": candidates,
            "visual_leaf_count": sum(1 for item in entries if item.get("status") == "active_visual_leaf"),
        },
        "findings": [asdict(item) for item in findings],
    }


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--registry", help="Override the registry JSON path")
    parser.add_argument("--write-json", help="Write the audit payload as JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill_root = Path(args.skill_root).resolve()
    registry = Path(args.registry) if args.registry else None
    payload = audit_registry(skill_root, registry)
    print(f"VERDICT: {payload['verdict']}")
    for key, value in payload["metrics"].items():
        print(f"METRIC: {key}={value}")
    for item in payload["findings"]:
        print(f"{item['level']}: [{item['axis']}] {item['message']}")
    if args.write_json:
        path = Path(args.write_json)
        path = path if path.is_absolute() else skill_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote: {path}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
