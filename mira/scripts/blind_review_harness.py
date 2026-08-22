#!/usr/bin/env python3
"""Prepare and validate anonymized, order-reversed Mira blind comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SUBJECTIVE_OWNERS = {"blind_reviewer", "mixed_review"}
PREFERENCES = {"A", "B", "TIE"}
CONFIDENCE = {"low", "medium", "high"}
DEFAULT_IDENTITY_TERMS = ["mira", "grok", "gpt-5", "fable", "claude"]
EVIDENCE_CLASSES_BY_KIND = {
    "internal": {"fresh_double_run", "migration_audit"},
    "external": {"external_calibration"},
}


@dataclass
class Finding:
    level: str
    code: str
    message: str
    locator: str = ""


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def comparison(root: Path, manifest_path: Path, rubric_path: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    try:
        manifest = load_json(manifest_path)
        rubric = load_json(rubric_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return failure(root, manifest_path, "manifest", str(exc))

    if manifest.get("version") != 1:
        findings.append(Finding("FAIL", "manifest_version", "comparison manifest version must be 1"))
    comparison_id = str(manifest.get("comparison_id") or "").strip()
    case_id = str(manifest.get("case_id") or "").strip()
    kind = str(manifest.get("comparison_kind") or "").strip()
    evidence_class = str(manifest.get("evidence_class") or "").strip()
    family = str(manifest.get("problem_family") or "").strip()
    if not comparison_id or not case_id or kind not in {"internal", "external"} or not family:
        findings.append(Finding("FAIL", "comparison_identity", "comparison_id, case_id, problem_family, and valid comparison_kind are required"))
    allowed_evidence_classes = EVIDENCE_CLASSES_BY_KIND.get(kind, set())
    if evidence_class not in allowed_evidence_classes:
        findings.append(
            Finding(
                "FAIL",
                "evidence_class",
                f"comparison_kind={kind or '<missing>'} requires evidence_class in {sorted(allowed_evidence_classes)}",
            )
        )

    candidate_rows = manifest.get("candidates")
    if not isinstance(candidate_rows, list) or len(candidate_rows) != 2:
        findings.append(Finding("FAIL", "candidate_count", "exactly two candidates are required"))
        candidate_rows = []

    candidates: dict[str, dict[str, Any]] = {}
    roots: list[Path] = []
    for item in candidate_rows:
        prepared = prepare_candidate(root, item, findings)
        candidate_id = prepared.get("candidate_id")
        if candidate_id:
            if candidate_id in candidates:
                findings.append(Finding("FAIL", "duplicate_candidate", f"duplicate candidate_id: {candidate_id}"))
            candidates[candidate_id] = prepared
            roots.append(prepared["root_path"])

    if len(roots) == 2 and (roots[0] == roots[1] or inside(roots[0], roots[1]) or inside(roots[1], roots[0])):
        findings.append(Finding("FAIL", "clean_root_separation", "candidate roots must be distinct and non-nested"))

    validate_roles(kind, candidates, findings)
    equivalence = validate_equivalence(candidates, findings)
    label_map = assign_labels(comparison_id, str(manifest.get("assignment_seed") or "frozen"), candidates)

    blind_dir = resolve(root, str(manifest.get("blind_output_dir") or f"checks/blind/{comparison_id or 'comparison'}"))
    blind_dir.mkdir(parents=True, exist_ok=True)
    identity_terms = identity_terms_for(manifest, candidates)
    anonymized: dict[str, dict[str, Any]] = {}
    if len(label_map) == 2:
        for label, candidate_id in label_map.items():
            source = candidates[candidate_id].get("paper_path")
            target = blind_dir / f"{label}.pdf"
            if isinstance(source, Path) and source.is_file():
                try:
                    anonymize_pdf(source, target)
                    leaks = scan_pdf(target, identity_terms)
                    if leaks:
                        for leak in leaks:
                            findings.append(Finding("FAIL", "identity_leak", leak, relative(root, target)))
                    anonymized[label] = {
                        "path": relative(root, target),
                        "sha256": sha256(target),
                        "identity_leaks": leaks,
                    }
                except Exception as exc:  # PDF engines expose several parser-specific errors.
                    findings.append(Finding("FAIL", "anonymization", str(exc), relative(root, source)))

    floor = technical_floor(candidates, findings)
    provenance = validate_external_provenance(kind, manifest.get("external_provenance"), findings)
    reviews_path = resolve(root, str(manifest.get("review_file") or "planning/blind_reviews.json"))
    reviews = validate_reviews(reviews_path, rubric, candidates, label_map, findings)

    blockers = {item.code for item in findings if item.level == "FAIL"}
    integrity_blockers = {
        "manifest_version",
        "comparison_identity",
        "evidence_class",
        "candidate_count",
        "duplicate_candidate",
        "candidate_manifest",
        "clean_root_claim",
        "clean_root_separation",
        "path_escape",
        "missing_file",
        "role_contract",
        "input_mismatch",
        "budget_mismatch",
        "anonymization",
        "identity_leak",
        "floor_missing",
        "l1_regression",
        "external_provenance",
        "review_file",
        "reviewer_count",
        "reviewer_authorization",
        "reviewer_independence",
        "self_review",
        "review_round",
        "order_reversal",
        "axis_coverage",
        "axis_score",
        "axis_preference",
        "axis_evidence",
        "axis_rationale",
        "axis_confidence",
        "low_confidence_decisive",
    }
    protocol_complete = not (blockers & integrity_blockers)
    group_preferences = reviews.get("group_preferences", {}) if protocol_complete else {}
    candidate_group_preferences = semantic_group_preferences(group_preferences, label_map, candidates) if protocol_complete else {}
    case_preference = aggregate_case_preference(group_preferences, label_map, candidates) if protocol_complete else "UNVERIFIED"

    result = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "manifest": relative(root, manifest_path),
        "comparison_id": comparison_id,
        "case_id": case_id,
        "comparison_kind": kind,
        "evidence_class": evidence_class,
        "promotion_eligible": protocol_complete and evidence_class == "fresh_double_run",
        "problem_family": family,
        "protocol_complete": protocol_complete,
        "equivalent_inputs": equivalence["inputs"],
        "equivalent_resource_budget": equivalence["budget"],
        "technical_floor": floor,
        "external_provenance": provenance,
        "anonymized_outputs": anonymized,
        "private_label_map": label_map,
        "review_summary": reviews,
        "group_preferences": group_preferences,
        "candidate_group_preferences": candidate_group_preferences,
        "candidate_case_preference": case_preference,
        "internal_improvement": "UNVERIFIED",
        "external_competitiveness": "UNVERIFIED",
        "award_probability": "NOT_ESTIMATED",
        "findings": [asdict(item) for item in findings],
        "verdict": "PASS" if protocol_complete else "FAIL",
    }
    return result


def prepare_candidate(root: Path, item: Any, findings: list[Finding]) -> dict[str, Any]:
    if not isinstance(item, dict):
        findings.append(Finding("FAIL", "candidate_manifest", "candidate record must be an object"))
        return {}
    candidate_id = str(item.get("candidate_id") or "").strip()
    role = str(item.get("role") or "").strip()
    generator_id = str(item.get("generator_id") or "").strip()
    candidate_root = resolve(root, str(item.get("root") or ""))
    run_manifest_path = resolve(candidate_root, str(item.get("run_manifest") or "planning/run_manifest.json"))
    output: dict[str, Any] = {
        "candidate_id": candidate_id,
        "role": role,
        "generator_id": generator_id,
        "root_path": candidate_root,
        "run_manifest_path": run_manifest_path,
    }
    if not candidate_id or not role or not generator_id:
        findings.append(Finding("FAIL", "candidate_manifest", "candidate_id, role, and generator_id are required"))
    if not candidate_root.is_dir() or not inside(candidate_root, run_manifest_path) or not run_manifest_path.is_file():
        findings.append(Finding("FAIL", "candidate_manifest", "candidate root or confined run manifest is missing", str(run_manifest_path)))
        return output
    try:
        run_manifest = load_json(run_manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(Finding("FAIL", "candidate_manifest", str(exc), str(run_manifest_path)))
        return output
    output["run_manifest"] = run_manifest
    if run_manifest.get("version") != 1:
        findings.append(Finding("FAIL", "candidate_manifest", "run manifest version must be 1", str(run_manifest_path)))
    if run_manifest.get("clean_root_verified") is not True or run_manifest.get("started_empty") is not True:
        findings.append(Finding("FAIL", "clean_root_claim", "run must record clean_root_verified and started_empty", str(run_manifest_path)))

    paper_path = resolve(candidate_root, str(run_manifest.get("paper_pdf") or ""))
    floor_path = resolve(candidate_root, str(run_manifest.get("technical_floor_report") or ""))
    for path, code in ((paper_path, "paper PDF"), (floor_path, "technical floor report")):
        if not inside(candidate_root, path):
            findings.append(Finding("FAIL", "path_escape", f"{code} must stay inside candidate root", str(path)))
        elif not path.is_file():
            findings.append(Finding("FAIL", "missing_file", f"{code} is missing", str(path)))
    output["paper_path"] = paper_path
    output["floor_path"] = floor_path
    output["resource_budget"] = run_manifest.get("resource_budget")

    input_hashes: dict[str, str] = {}
    input_files = run_manifest.get("input_files")
    if not isinstance(input_files, list) or not input_files:
        findings.append(Finding("FAIL", "input_mismatch", "run manifest needs nonempty input_files", str(run_manifest_path)))
    else:
        for record in input_files:
            if not isinstance(record, dict):
                findings.append(Finding("FAIL", "input_mismatch", "input record must be an object", str(run_manifest_path)))
                continue
            name = str(record.get("logical_name") or "").strip()
            path = resolve(candidate_root, str(record.get("path") or ""))
            if not name or name in input_hashes or not inside(candidate_root, path) or not path.is_file():
                findings.append(Finding("FAIL", "input_mismatch", f"invalid input record: {name or '<missing>'}", str(path)))
                continue
            input_hashes[name] = sha256(path)
    output["input_hashes"] = input_hashes
    return output


def validate_roles(kind: str, candidates: dict[str, dict[str, Any]], findings: list[Finding]) -> None:
    roles = {item.get("role") for item in candidates.values()}
    expected = {"baseline", "candidate"} if kind == "internal" else {"external_comparator", "candidate"}
    if roles != expected:
        findings.append(Finding("FAIL", "role_contract", f"{kind or 'unknown'} comparison requires roles {sorted(expected)}"))


def validate_equivalence(candidates: dict[str, dict[str, Any]], findings: list[Finding]) -> dict[str, bool]:
    if len(candidates) != 2:
        return {"inputs": False, "budget": False}
    rows = list(candidates.values())
    same_inputs = bool(rows[0].get("input_hashes")) and rows[0].get("input_hashes") == rows[1].get("input_hashes")
    budgets = [row.get("resource_budget") for row in rows]
    same_budget = all(resource_budget_is_known(value) for value in budgets) and budgets[0] == budgets[1]
    if not same_inputs:
        findings.append(Finding("FAIL", "input_mismatch", "candidate input logical names and SHA256 values must match"))
    if not same_budget:
        findings.append(Finding("FAIL", "budget_mismatch", "candidate resource budgets must be known and match exactly"))
    return {"inputs": same_inputs, "budget": same_budget}


def resource_budget_is_known(value: Any) -> bool:
    """Unknown placeholders are evidence gaps, even when both candidates use the same placeholder."""
    unknown = {"", "unknown", "unverified", "unspecified", "not_recorded", "not recorded", "n/a", "na", "pending"}
    if not isinstance(value, dict) or not value:
        return False
    for item in value.values():
        if item is None:
            return False
        if isinstance(item, str) and item.strip().lower() in unknown:
            return False
        if isinstance(item, dict) and not resource_budget_is_known(item):
            return False
        if isinstance(item, list) and any(
            nested is None or (isinstance(nested, str) and nested.strip().lower() in unknown)
            for nested in item
        ):
            return False
    return True


def assign_labels(comparison_id: str, seed: str, candidates: dict[str, dict[str, Any]]) -> dict[str, str]:
    ids = sorted(candidates)
    if len(ids) != 2:
        return {}
    swap = hashlib.sha256(f"{comparison_id}\0{seed}".encode("utf-8")).digest()[0] % 2 == 1
    ordered = list(reversed(ids)) if swap else ids
    return {"A": ordered[0], "B": ordered[1]}


def identity_terms_for(manifest: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> list[str]:
    supplied = manifest.get("identity_terms")
    terms = list(DEFAULT_IDENTITY_TERMS)
    if isinstance(supplied, list):
        terms.extend(str(item) for item in supplied)
    terms.extend(str(item.get("generator_id") or "") for item in candidates.values())
    return sorted({term.strip().lower() for term in terms if len(term.strip()) >= 3})


def anonymize_pdf(source: Path, target: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter(clone_from=reader)
    writer.metadata = None
    writer.xmp_metadata = None
    writer.add_metadata(
        {
            "/Title": "Anonymous contest paper",
            "/Author": "",
            "/Subject": "Blind review copy",
            "/Creator": "Blind review harness",
            "/Producer": "Blind review harness",
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        writer.write(handle)


def scan_pdf(path: Path, terms: list[str]) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    metadata = " ".join(f"{key}={value}" for key, value in (reader.metadata or {}).items())
    text_parts = [metadata]
    for page in reader.pages:
        try:
            text_parts.append(page.extract_text() or "")
        except Exception:
            text_parts.append("")
    text = "\n".join(text_parts).lower()
    leaks = []
    for term in terms:
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.IGNORECASE):
            leaks.append(f"identity term remains in PDF: {term}")
    return leaks


def technical_floor(candidates: dict[str, dict[str, Any]], findings: list[Finding]) -> dict[str, Any]:
    statuses: dict[str, str] = {}
    roles: dict[str, str] = {}
    for candidate_id, item in candidates.items():
        path = item.get("floor_path")
        status = "UNVERIFIED"
        if isinstance(path, Path) and path.is_file():
            try:
                report = load_json(path)
                status = str(report.get("technical_readiness") or report.get("verdict") or "UNVERIFIED").upper()
            except (OSError, ValueError, json.JSONDecodeError):
                status = "UNVERIFIED"
        if status not in {"PASS", "FAIL", "UNVERIFIED"}:
            status = "UNVERIFIED"
        statuses[candidate_id] = status
        roles[str(item.get("role"))] = status
        if status != "PASS":
            findings.append(Finding("FAIL", "floor_missing", f"{candidate_id} technical floor is {status}"))
    regression = roles.get("baseline") == "PASS" and roles.get("candidate") != "PASS"
    if regression:
        findings.append(Finding("FAIL", "l1_regression", "candidate regresses from a passing baseline technical floor"))
    return {"statuses": statuses, "l1_regression": regression}


def validate_external_provenance(kind: str, value: Any, findings: list[Finding]) -> dict[str, Any]:
    if kind != "external":
        return {"required": False, "status": "NOT_APPLICABLE"}
    required = {"source_type", "source_locator", "license_or_permission", "use_boundary", "integrity_status"}
    if not isinstance(value, dict) or any(not str(value.get(key) or "").strip() for key in required):
        findings.append(Finding("FAIL", "external_provenance", "external comparison requires complete provenance and use-boundary fields"))
        return {"required": True, "status": "UNVERIFIED"}
    if str(value.get("integrity_status")).upper() not in {"VERIFIED", "SOURCE_LIMITED"}:
        findings.append(Finding("FAIL", "external_provenance", "external comparator integrity_status must be VERIFIED or SOURCE_LIMITED"))
        return {"required": True, "status": "UNVERIFIED"}
    return {"required": True, "status": "PASS", "record": value}


def validate_reviews(
    path: Path,
    rubric: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    label_map: dict[str, str],
    findings: list[Finding],
) -> dict[str, Any]:
    try:
        payload = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(Finding("FAIL", "review_file", str(exc), str(path)))
        return {"status": "UNVERIFIED", "reviewers": [], "axis_disagreements": [], "group_preferences": {}}
    reviewers_value = payload.get("reviewers")
    rounds_value = payload.get("rounds")
    if not isinstance(reviewers_value, list) or not isinstance(rounds_value, list):
        findings.append(Finding("FAIL", "review_file", "reviewers and rounds must be lists", str(path)))
        return {"status": "UNVERIFIED", "reviewers": [], "axis_disagreements": [], "group_preferences": {}}

    reviewers: dict[str, dict[str, Any]] = {}
    generator_ids = {str(item.get("generator_id") or "").lower() for item in candidates.values()}
    for record in reviewers_value:
        reviewer_id = str(record.get("reviewer_id") or "").strip() if isinstance(record, dict) else ""
        if not reviewer_id or reviewer_id in reviewers:
            findings.append(Finding("FAIL", "reviewer_count", "reviewer IDs must be present and unique"))
            continue
        reviewers[reviewer_id] = record
        if record.get("authorized") is not True:
            findings.append(Finding("FAIL", "reviewer_authorization", f"{reviewer_id} is not authorized"))
        if record.get("independent") is not True:
            findings.append(Finding("FAIL", "reviewer_independence", f"{reviewer_id} is not recorded as independent"))
        reviewer_model = str(record.get("reviewer_model_id") or reviewer_id).lower()
        if reviewer_model in generator_ids:
            findings.append(Finding("FAIL", "self_review", f"{reviewer_id} matches a candidate generator"))
    if len(reviewers) < 2:
        findings.append(Finding("FAIL", "reviewer_count", "at least two authorized reviewers are required"))

    axes = {
        str(axis["id"]): axis
        for axis in rubric.get("weighted_axes", [])
        if str(axis.get("review_owner")) in SUBJECTIVE_OWNERS
    }
    valid_rounds: list[dict[str, Any]] = []
    seen_reviewers: set[str] = set()
    for round_record in rounds_value:
        if not isinstance(round_record, dict):
            findings.append(Finding("FAIL", "review_round", "review round must be an object"))
            continue
        reviewer_id = str(round_record.get("reviewer_id") or "")
        if reviewer_id not in reviewers or reviewer_id in seen_reviewers:
            findings.append(Finding("FAIL", "review_round", f"invalid or duplicate reviewer round: {reviewer_id}"))
            continue
        seen_reviewers.add(reviewer_id)
        order = round_record.get("display_order")
        if order not in (["A", "B"], ["B", "A"]):
            findings.append(Finding("FAIL", "review_round", f"invalid display_order for {reviewer_id}"))
        axis_records = round_record.get("axis_reviews")
        rows = {}
        if isinstance(axis_records, list):
            for row in axis_records:
                axis_id = str(row.get("axis_id") or "") if isinstance(row, dict) else ""
                if axis_id in rows:
                    findings.append(Finding("FAIL", "axis_coverage", f"duplicate axis {axis_id} for {reviewer_id}"))
                elif axis_id:
                    rows[axis_id] = row
        if set(rows) != set(axes):
            findings.append(Finding("FAIL", "axis_coverage", f"{reviewer_id} must review every subjective rubric axis"))
        clean_rows: dict[str, dict[str, Any]] = {}
        for axis_id, axis in axes.items():
            row = rows.get(axis_id)
            if row is None:
                continue
            if validate_axis_pair(reviewer_id, axis, row, findings):
                clean_rows[axis_id] = row
        valid_rounds.append({"reviewer_id": reviewer_id, "display_order": order, "axis_reviews": clean_rows})

    orders = {tuple(item.get("display_order") or []) for item in valid_rounds}
    if {("A", "B"), ("B", "A")} - orders:
        findings.append(Finding("FAIL", "order_reversal", "review rounds must cover both A/B and B/A display orders"))
    if set(reviewers) - seen_reviewers:
        findings.append(Finding("FAIL", "reviewer_count", "every reviewer must submit exactly one round"))

    axis_disagreements = disagreement_rows(valid_rounds, axes)
    group_preferences = group_outcomes(valid_rounds, axes)
    return {
        "status": "COMPLETE" if len(valid_rounds) >= 2 and not ({("A", "B"), ("B", "A")} - orders) else "UNVERIFIED",
        "reviewers": sorted(reviewers),
        "round_orders": [item.get("display_order") for item in valid_rounds],
        "axis_disagreements": axis_disagreements,
        "group_preferences": group_preferences,
        "blind_labels": sorted(label_map),
    }


def validate_axis_pair(reviewer_id: str, axis: dict[str, Any], row: dict[str, Any], findings: list[Finding]) -> bool:
    axis_id = str(axis["id"])
    score_a = row.get("score_A")
    score_b = row.get("score_B")
    valid = True
    for label, score in (("A", score_a), ("B", score_b)):
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 4:
            findings.append(Finding("FAIL", "axis_score", f"{reviewer_id}/{axis_id} score_{label} must be integer 0-4"))
            valid = False
        elif not str(axis.get("anchors", {}).get(str(score)) or ""):
            findings.append(Finding("FAIL", "axis_score", f"rubric lacks anchor {score} for {axis_id}"))
            valid = False
    preference = str(row.get("preference") or "").upper()
    expected = "A" if valid and score_a > score_b else ("B" if valid and score_b > score_a else "TIE")
    if preference not in PREFERENCES or preference != expected:
        findings.append(Finding("FAIL", "axis_preference", f"{reviewer_id}/{axis_id} preference must match the scores"))
        valid = False
    evidence = row.get("evidence_locators")
    if not isinstance(evidence, dict) or any(not isinstance(evidence.get(label), list) or not evidence.get(label) for label in ("A", "B")):
        findings.append(Finding("FAIL", "axis_evidence", f"{reviewer_id}/{axis_id} needs evidence for A and B"))
        valid = False
    if len(str(row.get("rationale") or "")) < 20:
        findings.append(Finding("FAIL", "axis_rationale", f"{reviewer_id}/{axis_id} needs a substantive rationale"))
        valid = False
    confidence = str(row.get("confidence") or "").lower()
    if confidence not in CONFIDENCE:
        findings.append(Finding("FAIL", "axis_confidence", f"{reviewer_id}/{axis_id} confidence is invalid"))
        valid = False
    elif confidence == "low" and expected != "TIE":
        findings.append(Finding("FAIL", "low_confidence_decisive", f"{reviewer_id}/{axis_id} has a low-confidence decisive score"))
        valid = False
    return valid


def disagreement_rows(rounds: list[dict[str, Any]], axes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for axis_id in axes:
        preferences = [item["axis_reviews"][axis_id]["preference"] for item in rounds if axis_id in item["axis_reviews"]]
        if len(set(preferences)) > 1:
            output.append({"axis_id": axis_id, "preferences": preferences, "status": "PRESERVED"})
    return output


def group_outcomes(rounds: list[dict[str, Any]], axes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    groups = sorted({str(axis.get("group")) for axis in axes.values()})
    output: dict[str, Any] = {}
    for group in groups:
        group_axes = [axis_id for axis_id, axis in axes.items() if axis.get("group") == group]
        reviewer_preferences = []
        for round_record in rounds:
            if any(axis_id not in round_record["axis_reviews"] for axis_id in group_axes):
                continue
            score_a = sum(round_record["axis_reviews"][axis_id]["score_A"] for axis_id in group_axes)
            score_b = sum(round_record["axis_reviews"][axis_id]["score_B"] for axis_id in group_axes)
            preference = "A" if score_a > score_b else ("B" if score_b > score_a else "TIE")
            reviewer_preferences.append({"reviewer_id": round_record["reviewer_id"], "preference": preference, "score_A": score_a, "score_B": score_b})
        preferences = {item["preference"] for item in reviewer_preferences}
        if len(reviewer_preferences) < 2:
            aggregate = "UNVERIFIED"
        elif len(preferences) > 1:
            aggregate = "MIXED"
        else:
            aggregate = next(iter(preferences))
        output[group] = {"blind_preference": aggregate, "reviewer_preferences": reviewer_preferences}
    return output


def aggregate_case_preference(
    groups: dict[str, Any], label_map: dict[str, str], candidates: dict[str, dict[str, Any]]
) -> str:
    candidate_id = next((key for key, value in candidates.items() if value.get("role") == "candidate"), "")
    candidate_label = next((label for label, key in label_map.items() if key == candidate_id), "")
    values = [str(record.get("blind_preference") or "UNVERIFIED") for record in groups.values()]
    if not values or "UNVERIFIED" in values:
        return "UNVERIFIED"
    if "MIXED" in values:
        return "MIXED"
    if all(value == "TIE" for value in values):
        return "TIE"
    non_ties = [value for value in values if value != "TIE"]
    if non_ties and all(value == candidate_label for value in non_ties):
        return "PREFERRED" if len(non_ties) == len(values) else "MIXED"
    other_label = "B" if candidate_label == "A" else "A"
    if non_ties and all(value == other_label for value in non_ties):
        return "NOT_PREFERRED" if len(non_ties) == len(values) else "MIXED"
    return "MIXED"


def semantic_group_preferences(
    groups: dict[str, Any], label_map: dict[str, str], candidates: dict[str, dict[str, Any]]
) -> dict[str, str]:
    candidate_id = next((key for key, value in candidates.items() if value.get("role") == "candidate"), "")
    candidate_label = next((label for label, key in label_map.items() if key == candidate_id), "")
    other_label = "B" if candidate_label == "A" else "A"
    output: dict[str, str] = {}
    for group, record in groups.items():
        preference = str(record.get("blind_preference") or "UNVERIFIED")
        if preference == candidate_label:
            output[group] = "PREFERRED"
        elif preference == other_label:
            output[group] = "NOT_PREFERRED"
        elif preference in {"TIE", "MIXED", "UNVERIFIED"}:
            output[group] = preference
        else:
            output[group] = "UNVERIFIED"
    return output


def failure(root: Path, manifest_path: Path, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "manifest": relative(root, manifest_path),
        "evidence_class": "",
        "promotion_eligible": False,
        "protocol_complete": False,
        "candidate_case_preference": "UNVERIFIED",
        "internal_improvement": "UNVERIFIED",
        "external_competitiveness": "UNVERIFIED",
        "award_probability": "NOT_ESTIMATED",
        "findings": [asdict(Finding("FAIL", code, message))],
        "verdict": "FAIL",
    }


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Blind Comparison Report",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Protocol complete: `{payload.get('protocol_complete')}`",
        f"- Evidence class: `{payload.get('evidence_class', 'UNVERIFIED')}`",
        f"- Promotion eligible: `{payload.get('promotion_eligible', False)}`",
        f"- Case preference: `{payload.get('candidate_case_preference')}`",
        "- Award probability: `NOT_ESTIMATED`",
        "",
        "| Level | Code | Locator | Message |",
        "|---|---|---|---|",
    ]
    for item in payload.get("findings", []):
        clean = lambda value: str(value).replace("|", "/").replace("\n", " ")
        lines.append(f"| {clean(item['level'])} | {clean(item['code'])} | {clean(item.get('locator', ''))} | {clean(item['message'])} |")
    if not payload.get("findings"):
        lines.append("| INFO | complete | - | no protocol findings |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="planning/blind_comparison.json")
    parser.add_argument("--rubric", default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "award-readiness-rubric.json"))
    parser.add_argument("--write-json", default="checks/blind_comparison_report.json")
    parser.add_argument("--write-report", default="checks/blind_comparison_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = comparison(root, resolve(root, args.manifest), resolve(root, args.rubric))
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"candidate_case_preference: {payload.get('candidate_case_preference', 'UNVERIFIED')}")
    print("award_probability: NOT_ESTIMATED")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
