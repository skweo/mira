#!/usr/bin/env python3
"""Build a provenance-preserving Mira blind-comparison package from existing artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EVIDENCE_CLASSES = {
    "internal": {"fresh_double_run", "migration_audit"},
    "external": {"external_calibration"},
}


class PackageError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise PackageError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def source_file(source_root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PackageError(f"{label} requires a source path")
    path = (source_root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if not inside(source_root, path):
        raise PackageError(f"{label} escapes source root: {path}")
    if not path.is_file():
        raise PackageError(f"{label} is missing: {path}")
    return path


def verify_declared_hash(path: Path, record: dict[str, Any], label: str) -> str:
    actual = sha256(path)
    expected = str(record.get("sha256") or "").strip().upper()
    if expected and expected != actual:
        raise PackageError(f"{label} SHA256 mismatch: expected {expected}, got {actual}")
    return actual


def floor_status(report: dict[str, Any]) -> tuple[str, str]:
    for key in ("technical_readiness", "verdict", "overall_verdict"):
        value = str(report.get(key) or "").upper()
        if value in {"PASS", "FAIL", "UNVERIFIED"}:
            return value, f"{key}={value}"
    status = str(report.get("status") or "").upper()
    if status == "READY":
        return "PASS", "delivery status=READY"
    if status == "AUDIT_FAILED":
        return "FAIL", "delivery status=AUDIT_FAILED"
    return "UNVERIFIED", f"no recognized technical verdict (status={status or 'missing'})"


def prepare_floor(
    source_root: Path,
    candidate_root: Path,
    candidate: dict[str, Any],
    sources: dict[str, Any],
) -> None:
    source_value = candidate.get("technical_floor_source")
    if source_value:
        report_path = source_file(source_root, source_value, "technical_floor_source")
        report = load_json(report_path)
        status, derivation = floor_status(report)
        report_hash = sha256(report_path)
        source_locator = relative(source_root, report_path)
    else:
        status, derivation = "UNVERIFIED", "no source technical report supplied"
        report_hash = ""
        source_locator = ""
    payload = {
        "schema_version": 1,
        "technical_readiness": status,
        "derivation": derivation,
        "source_report": source_locator,
        "source_report_sha256": report_hash,
    }
    write_json(candidate_root / "checks" / "technical_floor.json", payload)
    sources["technical_floor"] = payload


def prepare_candidate(
    source_root: Path,
    package_root: Path,
    candidate: dict[str, Any],
    evidence_class: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    role = str(candidate.get("role") or "").strip()
    generator_id = str(candidate.get("generator_id") or "").strip()
    if not SAFE_ID.fullmatch(candidate_id):
        raise PackageError(f"unsafe candidate_id: {candidate_id or '<missing>'}")
    if not role or not generator_id:
        raise PackageError(f"candidate {candidate_id} requires role and generator_id")

    candidate_root = package_root / "candidates" / candidate_id
    paper_record = candidate.get("paper")
    if not isinstance(paper_record, dict):
        raise PackageError(f"candidate {candidate_id} requires a paper object")
    paper_source = source_file(source_root, paper_record.get("path"), f"{candidate_id} paper")
    if paper_source.suffix.lower() != ".pdf":
        raise PackageError(f"candidate {candidate_id} paper must be a PDF")
    paper_hash = verify_declared_hash(paper_source, paper_record, f"{candidate_id} paper")
    paper_target = candidate_root / "output" / "paper.pdf"
    paper_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paper_source, paper_target)

    input_rows = candidate.get("input_files")
    if not isinstance(input_rows, list) or not input_rows:
        raise PackageError(f"candidate {candidate_id} requires nonempty input_files")
    run_inputs: list[dict[str, Any]] = []
    source_inputs: list[dict[str, Any]] = []
    logical_names: set[str] = set()
    for index, record in enumerate(input_rows, start=1):
        if not isinstance(record, dict):
            raise PackageError(f"candidate {candidate_id} has a non-object input record")
        logical_name = str(record.get("logical_name") or "").strip()
        if not logical_name or logical_name in logical_names:
            raise PackageError(f"candidate {candidate_id} has an invalid or duplicate logical input name")
        source = source_file(source_root, record.get("path"), f"{candidate_id} input {logical_name}")
        actual_hash = verify_declared_hash(source, record, f"{candidate_id} input {logical_name}")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", logical_name).strip("._") or f"input_{index}"
        target = candidate_root / "materials" / f"{index:02d}_{safe_name}{source.suffix.lower()}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target_rel = relative(candidate_root, target)
        run_inputs.append({"logical_name": logical_name, "path": target_rel, "sha256": actual_hash})
        source_inputs.append(
            {
                "logical_name": logical_name,
                "source_path": relative(source_root, source),
                "copied_path": target_rel,
                "sha256": actual_hash,
                "size_bytes": source.stat().st_size,
            }
        )
        logical_names.add(logical_name)

    sources: dict[str, Any] = {
        "candidate_id": candidate_id,
        "historical_source": candidate.get("historical_source", {}),
        "paper": {
            "source_path": relative(source_root, paper_source),
            "copied_path": relative(candidate_root, paper_target),
            "sha256": paper_hash,
            "size_bytes": paper_source.stat().st_size,
        },
        "input_files": source_inputs,
    }
    prepare_floor(source_root, candidate_root, candidate, sources)

    clean_claim_allowed = evidence_class == "fresh_double_run"
    run_manifest = {
        "version": 1,
        "evidence_class": evidence_class,
        "clean_root_verified": bool(candidate.get("clean_root_verified")) if clean_claim_allowed else False,
        "started_empty": bool(candidate.get("started_empty")) if clean_claim_allowed else False,
        "paper_pdf": "output/paper.pdf",
        "paper_sha256": paper_hash,
        "technical_floor_report": "checks/technical_floor.json",
        "input_files": run_inputs,
        "resource_budget": candidate.get("resource_budget") or {"status": "unknown"},
        "historical_source": candidate.get("historical_source", {}),
    }
    write_json(candidate_root / "planning" / "run_manifest.json", run_manifest)
    comparison_candidate = {
        "candidate_id": candidate_id,
        "role": role,
        "root": f"candidates/{candidate_id}",
        "run_manifest": "planning/run_manifest.json",
        "generator_id": generator_id,
    }
    return comparison_candidate, sources


def prepare(config_path: Path, source_root: Path, output_root: Path) -> dict[str, Any]:
    config = load_json(config_path)
    if config.get("version") != 1:
        raise PackageError("comparison package config version must be 1")
    kind = str(config.get("comparison_kind") or "").strip()
    evidence_class = str(config.get("evidence_class") or "").strip()
    if evidence_class not in EVIDENCE_CLASSES.get(kind, set()):
        raise PackageError(f"comparison_kind={kind or '<missing>'} does not allow evidence_class={evidence_class or '<missing>'}")
    candidates = config.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise PackageError("exactly two candidates are required")
    for key in ("comparison_id", "case_id", "problem_family"):
        if not str(config.get(key) or "").strip():
            raise PackageError(f"{key} is required")
    if output_root.exists():
        raise PackageError(f"output root already exists: {output_root}")

    staging = output_root.with_name(f".{output_root.name}.staging-{uuid.uuid4().hex[:8]}")
    try:
        staging.mkdir(parents=True)
        prepared_candidates: list[dict[str, Any]] = []
        source_records: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise PackageError("candidate record must be an object")
            prepared, sources = prepare_candidate(source_root, staging, candidate, evidence_class)
            prepared_candidates.append(prepared)
            source_records.append(sources)
        comparison_manifest = {
            "version": 1,
            "comparison_id": config["comparison_id"],
            "case_id": config["case_id"],
            "comparison_kind": kind,
            "evidence_class": evidence_class,
            "problem_family": config["problem_family"],
            "assignment_seed": config.get("assignment_seed", "frozen"),
            "blind_output_dir": f"checks/blind/{config['comparison_id']}",
            "review_file": "planning/blind_reviews.json",
            "identity_terms": config.get("identity_terms", []),
            "candidates": prepared_candidates,
        }
        if kind == "external":
            comparison_manifest["external_provenance"] = config.get("external_provenance", {})
        write_json(staging / "planning" / "blind_comparison.json", comparison_manifest)
        sources_payload = {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "config": relative(source_root, config_path),
            "config_sha256": sha256(config_path),
            "comparison_id": config["comparison_id"],
            "evidence_class": evidence_class,
            "candidates": source_records,
            "review_status": "NOT_PROVIDED",
        }
        write_json(staging / "planning" / "comparison_sources.json", sources_payload)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(output_root)
        return sources_payload
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--output-root", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root).resolve()
    config_path = (source_root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config).resolve()
    output_root = Path(args.output_root).resolve()
    if not inside(source_root, config_path):
        print("ERROR: config must stay inside source root", file=sys.stderr)
        return 2
    try:
        payload = prepare(config_path, source_root, output_root)
    except PackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"PREPARED: {output_root}")
    print(f"comparison_id: {payload['comparison_id']}")
    print("review_status: NOT_PROVIDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
