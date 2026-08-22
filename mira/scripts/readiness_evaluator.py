#!/usr/bin/env python3
"""Evaluate Mira readiness with anchored, reviewer-owned rubric records."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    level: str
    code: str
    axis_id: str
    message: str


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def evaluator(root: Path, rubric_path: Path, review_path: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    try:
        rubric = load_json(rubric_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return failure(root, review_path, "rubric", str(exc))
    try:
        review = load_json(review_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return failure(root, review_path, "review", str(exc))

    if review.get("version") != 1:
        findings.append(Finding("FAIL", "review_version", "profile", "review version must be 1"))

    floor_rows = unique_records(review.get("technical_floor"), "axis_id", findings, "technical_floor")
    floor_statuses: list[str] = []
    floor_output: list[dict[str, Any]] = []
    for axis in rubric.get("hard_floor", {}).get("axes", []):
        axis_id = str(axis.get("id") or "")
        record = floor_rows.get(axis_id)
        if record is None:
            status = "UNVERIFIED"
            findings.append(Finding("UNVERIFIED", "missing_floor", axis_id, "technical floor record is missing"))
        else:
            status = str(record.get("status") or "UNVERIFIED").upper()
            if status not in {"PASS", "FAIL", "UNVERIFIED"}:
                findings.append(Finding("FAIL", "invalid_floor_status", axis_id, f"invalid status: {status}"))
                status = "UNVERIFIED"
            if status in {"PASS", "FAIL"} and not record.get("evidence_locators"):
                findings.append(Finding("FAIL", "missing_floor_evidence", axis_id, "PASS/FAIL floor status needs evidence locators"))
                status = "UNVERIFIED"
        floor_statuses.append(status)
        floor_output.append({"axis_id": axis_id, "status": status})

    technical = "FAIL" if "FAIL" in floor_statuses else ("UNVERIFIED" if "UNVERIFIED" in floor_statuses else "PASS")
    gate_reports = optional_technical_gate_reports(root, findings)
    if any(item["status"] == "FAIL" for item in gate_reports):
        technical = "FAIL"
    review_rows = unique_records(review.get("weighted_reviews"), "axis_id", findings, "weighted_reviews")
    scored_axes: list[dict[str, Any]] = []
    missing_axes: list[str] = []
    invalid_axes: set[str] = set()
    total = 0.0
    for axis in rubric.get("weighted_axes", []):
        axis_id = str(axis.get("id") or "")
        record = review_rows.get(axis_id)
        if record is None:
            missing_axes.append(axis_id)
            findings.append(Finding("UNVERIFIED", "missing_subjective_review", axis_id, "anchored axis review is missing"))
            continue
        valid, level = validate_axis_review(axis, record, findings)
        if not valid or level is None:
            invalid_axes.add(axis_id)
            continue
        points = round(float(axis["weight"]) * level / 4.0, 2)
        total += points
        scored_axes.append(
            {
                "axis_id": axis_id,
                "group": axis["group"],
                "level": level,
                "weight": axis["weight"],
                "points": points,
                "reviewer_id": record.get("reviewer_id"),
                "reviewer_role": record.get("reviewer_role"),
                "confidence": record.get("confidence"),
                "evidence_locators": record.get("evidence_locators", []),
                "rationale": record.get("rationale", ""),
            }
        )

    all_axes = len(rubric.get("weighted_axes", []))
    complete = technical == "PASS" and len(scored_axes) == all_axes and not invalid_axes and not missing_axes
    profile = "COMPLETE" if complete else ("UNVERIFIED" if missing_axes else "INCOMPLETE")
    group_points: dict[str, float] = {}
    for item in scored_axes:
        group_points[item["group"]] = round(group_points.get(item["group"], 0.0) + item["points"], 2)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "review": relative(root, review_path),
        "rubric": str(rubric_path),
        "technical_readiness": technical,
        "competitive_profile": profile,
        "weighted_score": round(total, 2) if complete else None,
        "partial_score": round(total, 2),
        "group_points": group_points,
        "internal_improvement": "UNVERIFIED",
        "external_competitiveness": "UNVERIFIED",
        "award_probability": "NOT_ESTIMATED",
        "technical_floor": floor_output,
        "technical_gate_reports": gate_reports,
        "scored_axes": scored_axes,
        "missing_axes": missing_axes,
        "findings": [asdict(item) for item in findings],
        "verdict": "PASS" if complete else "FAIL",
    }


def optional_technical_gate_reports(root: Path, findings: list[Finding]) -> list[dict[str, str]]:
    """Consume new technical reports when present without invalidating legacy reviews."""
    reports = (("contest_evidence_chain", root / "checks" / "contest_evidence_chain_report.json"),)
    output: list[dict[str, str]] = []
    for code, path in reports:
        if not path.is_file():
            continue
        try:
            payload = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            status = "FAIL"
            message = f"technical gate report cannot be read: {exc}"
        else:
            verdict = str(payload.get("verdict") or "").upper()
            status = "PASS" if verdict == "PASS" else "FAIL"
            message = (
                "contest evidence chain gate passed"
                if status == "PASS"
                else f"contest evidence chain gate is {verdict or 'UNVERIFIED'}"
            )
        output.append({"code": code, "status": status, "report": relative(root, path)})
        if status == "FAIL":
            findings.append(Finding("FAIL", code, "technical_floor", message))
    return output


def unique_records(value: Any, key: str, findings: list[Finding], code: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        findings.append(Finding("FAIL", code, "profile", f"{code} must be a list"))
        return {}
    output: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            findings.append(Finding("FAIL", code, "profile", f"{code} record must be an object"))
            continue
        identity = str(item.get(key) or "")
        if not identity:
            findings.append(Finding("FAIL", code, "profile", f"{code} record lacks {key}"))
        elif identity in output:
            findings.append(Finding("FAIL", "duplicate_axis", identity, "duplicate review record"))
        else:
            output[identity] = item
    return output


def validate_axis_review(axis: dict[str, Any], record: dict[str, Any], findings: list[Finding]) -> tuple[bool, int | None]:
    axis_id = str(axis["id"])
    level = record.get("level")
    if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
        findings.append(Finding("FAIL", "invalid_level", axis_id, "level must be an integer from 0 to 4"))
        return False, None
    role = str(record.get("reviewer_role") or "")
    owner = str(axis.get("review_owner") or "")
    allowed = {
        "blind_reviewer": {"blind_reviewer"},
        "mixed_review": {"blind_reviewer", "mixed_reviewer"},
        "deterministic_gate": {"deterministic_gate"},
    }.get(owner, set())
    valid = True
    if role not in allowed:
        findings.append(Finding("FAIL", "unauthorized_role", axis_id, f"{role or 'missing role'} cannot score owner={owner}"))
        valid = False
    if role != "deterministic_gate" and record.get("authorized") is not True:
        findings.append(Finding("FAIL", "reviewer_authorization", axis_id, "human/mixed reviewer must be explicitly authorized"))
        valid = False
    if not str(record.get("reviewer_id") or "").strip():
        findings.append(Finding("FAIL", "reviewer_identity", axis_id, "reviewer_id is required"))
        valid = False
    confidence = str(record.get("confidence") or "").lower()
    if confidence not in {"low", "medium", "high"}:
        findings.append(Finding("FAIL", "confidence", axis_id, "confidence must be low, medium, or high"))
        valid = False
    if not isinstance(record.get("evidence_locators"), list) or not record.get("evidence_locators"):
        findings.append(Finding("FAIL", "evidence", axis_id, "axis score requires specific evidence locators"))
        valid = False
    if len(str(record.get("rationale") or "")) < 20:
        findings.append(Finding("FAIL", "rationale", axis_id, "axis score requires a substantive reviewer rationale"))
        valid = False
    anchor = str(axis.get("anchors", {}).get(str(level)) or "")
    if not anchor:
        findings.append(Finding("FAIL", "anchor", axis_id, "rubric anchor is missing for selected level"))
        valid = False
    return valid, level


def failure(root: Path, review_path: Path, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "review": relative(root, review_path),
        "technical_readiness": "UNVERIFIED",
        "competitive_profile": "UNVERIFIED",
        "weighted_score": None,
        "partial_score": 0.0,
        "internal_improvement": "UNVERIFIED",
        "external_competitiveness": "UNVERIFIED",
        "award_probability": "NOT_ESTIMATED",
        "findings": [asdict(Finding("FAIL", code, "profile", message))],
        "verdict": "FAIL",
    }


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Anchored Readiness Evaluation",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Technical readiness: `{payload['technical_readiness']}`",
        f"- Competitive profile: `{payload['competitive_profile']}`",
        f"- Weighted score: `{payload['weighted_score']}`",
        "- Award probability: `NOT_ESTIMATED`",
        "",
        "| Level | Axis | Code | Message |",
        "|---|---|---|---|",
    ]
    for item in payload.get("findings", []):
        lines.append(f"| {item['level']} | {item['axis_id']} | {item['code']} | {str(item['message']).replace('|', '/')} |")
    if not payload.get("findings"):
        lines.append("| INFO | - | complete | no findings |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--review", default="planning/readiness_review.json")
    parser.add_argument("--rubric", default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "award-readiness-rubric.json"))
    parser.add_argument("--write-json", default="checks/readiness_evaluation.json")
    parser.add_argument("--write-report", default="checks/readiness_evaluation.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = evaluator(root, resolve(root, args.rubric), resolve(root, args.review))
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"technical_readiness: {payload['technical_readiness']}")
    print(f"competitive_profile: {payload['competitive_profile']}")
    print("award_probability: NOT_ESTIMATED")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
