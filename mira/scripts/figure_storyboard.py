#!/usr/bin/env python3
"""Create or refresh Mira's claim-to-evidence storyboard."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from visual_opportunity_audit import build_three_d_candidates, collect_table_profiles


EVIDENCE_FORMS = ["proof", "table", "figure", "diagram", "no_visual_waiver"]
ROLE_ORDER = ["define", "derive", "operate", "result", "validate", "zoom", "compare"]
PLACEHOLDERS = {"", "tbd", "todo", "pending", "unresolved", "not_selected"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--ledger-json", default="planning/result_ledger.json")
    parser.add_argument("--evidence-json", default="planning/figure_evidence.json")
    parser.add_argument("--write-report", default="planning/figure_storyboard.md")
    parser.add_argument("--write-json", default="planning/figure_storyboard.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    ledger = load_json(resolve_path(root, args.ledger_json))
    figure_evidence = load_json(resolve_path(root, args.evidence_json))
    json_path = resolve_path(root, args.write_json)
    existing = load_json(json_path)
    items, mode = build_storyboard(root, ledger, existing, figure_evidence)
    three_d_candidates = sync_three_d_candidates(root, existing.get("three_d_candidates", []))
    payload = {
        "schema_version": 3,
        "authority": "canonical_claim_evidence_plan",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "mode": mode,
        "items": items,
        "three_d_candidates": three_d_candidates,
        "metrics": metrics(items, three_d_candidates),
        "notes": [
            "Central claims use stable claim_id bindings; supporting claims do not enter this plan.",
            "Choose proof, table, figure, diagram, or no_visual_waiver from evidence shape, not from a quota.",
            "Python is the default visual backend; MATLAB needs a material engineering reason and a successful batch record.",
            "Generated TBD fields are decisions to complete, not evidence that a claim is covered.",
            "Every detected 3D candidate must be generated with a companion view or waived with a specific evidence-backed reason.",
        ],
    }
    report_path = resolve_path(root, args.write_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(markdown(payload))
    print(f"INFO: wrote {rel(root, report_path)}")
    print(f"INFO: wrote {rel(root, json_path)}")
    return 0


def build_storyboard(
    root: Path,
    ledger: dict[str, Any],
    existing: dict[str, Any],
    figure_evidence: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    entries = [item for item in ledger.get("entries", []) if isinstance(item, dict)]
    central = [item for item in entries if is_central(item) and clean(item.get("claim_id"))]
    existing_items = [item for item in existing.get("items", []) if isinstance(item, dict)]
    evidence_items = [
        item
        for item in (figure_evidence or {}).get("figures", [])
        if isinstance(item, dict) and clean(item.get("claim_id"))
    ]
    if not central:
        return build_legacy_storyboard(root, existing_items), "legacy_question_role"

    central_ids = {clean(item.get("claim_id")) for item in central}
    used: set[int] = set()
    output: list[dict[str, Any]] = []
    for claim in sorted(central, key=lambda item: natural_key(clean(item.get("key")))):
        claim_id = clean(claim.get("claim_id"))
        matches = [
            (index, item)
            for index, item in enumerate(existing_items)
            if clean(item.get("claim_id")) == claim_id
            or (not clean(item.get("claim_id")) and clean(item.get("claim_key")) == clean(claim.get("key")))
        ]
        claim_evidence = sorted(
            [item for item in evidence_items if clean(item.get("claim_id")) == claim_id],
            key=lambda item: natural_key(clean(item.get("figure_id")) or clean(item.get("vector_file"))),
        )
        if claim_evidence:
            claimed_existing: set[int] = set()
            for sequence, evidence in enumerate(claim_evidence, start=1):
                match = match_existing_evidence(matches, claimed_existing, evidence)
                if match is None:
                    existing_index, existing_item = -1, {}
                else:
                    existing_index, existing_item = match
                    used.add(existing_index)
                    claimed_existing.add(existing_index)
                fallback_id = clean(evidence.get("figure_id")) or f"EVD-{slug(claim_id)}-{sequence:02d}"
                output.append(normalize_claim_item(existing_item, claim, fallback_id, evidence))
            for index, item in matches:
                if index in claimed_existing:
                    continue
                used.add(index)
                fallback_id = f"EVD-{slug(claim_id)}-{len(output) + 1:02d}"
                output.append(normalize_claim_item(item, claim, fallback_id))
            continue
        if not matches:
            output.append(normalize_claim_item({}, claim, f"EVD-{slug(claim_id)}-01"))
            continue
        for sequence, (index, item) in enumerate(matches, start=1):
            used.add(index)
            fallback_id = f"EVD-{slug(claim_id)}-{sequence:02d}"
            output.append(normalize_claim_item(item, claim, fallback_id))

    for index, item in enumerate(existing_items):
        if index in used:
            continue
        preserved = normalize_orphan(item, index + 1)
        if clean(preserved.get("claim_id")) not in central_ids:
            output.append(preserved)
    return output, "central_claim"


def sync_three_d_candidates(root: Path, existing: Any) -> list[dict[str, Any]]:
    detected = build_three_d_candidates(root, collect_table_profiles(root))
    prior = {
        clean(item.get("candidate_id")): item
        for item in existing if isinstance(item, dict) and clean(item.get("candidate_id"))
    } if isinstance(existing, list) else {}
    output: list[dict[str, Any]] = []
    for candidate in detected:
        record = prior.get(candidate.candidate_id, {})
        output.append(
            {
                "candidate_id": candidate.candidate_id,
                "source": candidate.source,
                "question": candidate.question,
                "kind": candidate.kind,
                "priority": candidate.priority,
                "reason": candidate.reason,
                "data_columns": candidate.data_columns,
                "required_companion": candidate.required_companion,
                "status": clean(record.get("status")).lower() or "unresolved",
                "artifact": meaningful(record.get("artifact")),
                "waiver_reason": meaningful(record.get("waiver_reason")),
                "waiver_evidence": list_value(record.get("waiver_evidence")),
            }
        )
    return output


def normalize_claim_item(
    existing: dict[str, Any],
    claim: dict[str, Any],
    fallback_id: str,
    evidence_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_record = evidence_record or {}
    claim_id = clean(claim.get("claim_id"))
    key = clean(claim.get("key"))
    question = clean(claim.get("question")) or question_from_key(key)
    role = meaningful(existing.get("role")) or role_from_evidence(evidence_record) or role_for_claim(claim)
    provenance = existing.get("provenance") if isinstance(existing.get("provenance"), dict) else {}
    evidence = [clean(value) for value in claim.get("evidence", []) if clean(value)]
    legacy_artifact = clean(existing.get("artifact") or existing.get("source_artifact"))
    evidence_artifact = clean(evidence_record.get("vector_file") or evidence_record.get("png_file"))
    artifact = meaningful(existing.get("artifact")) or meaningful(provenance.get("output")) or meaningful(legacy_artifact) or evidence_artifact or "TBD"
    source_data = meaningful(provenance.get("source_data")) or meaningful(evidence_record.get("data_source")) or (evidence[0] if evidence else "TBD")
    script = meaningful(provenance.get("script")) or meaningful(evidence_record.get("source_file")) or "TBD"
    chosen_form = meaningful(existing.get("chosen_evidence_form")) or ("figure" if evidence_record else "unresolved")
    intended = meaningful(existing.get("intended_inference")) or meaningful(evidence_record.get("expected_inference")) or "TBD"
    nearby = clean(existing.get("nearby_claim")) or claim_text(claim)
    proposed = clean(existing.get("proposed_visual"))
    if not proposed:
        proposed = evidence_description(chosen_form)
    waiver = existing.get("waiver") if isinstance(existing.get("waiver"), dict) else {}
    status = meaningful(existing.get("status"))
    if evidence_record and (not status or status == "planned_gap"):
        status = "evidence_ready"
    return {
        "item_id": clean(existing.get("item_id")) or fallback_id,
        "evidence_id": clean(evidence_record.get("figure_id")) or clean(existing.get("evidence_id")),
        "claim_id": claim_id,
        "claim_key": key,
        "question": clean(existing.get("question")) or question,
        "role": role,
        "reader_question": meaningful(existing.get("reader_question")) or meaningful(evidence_record.get("reader_question")) or reader_question(claim),
        "chosen_evidence_form": chosen_form,
        "alternatives_considered": list_value(existing.get("alternatives_considered")),
        "intended_inference": intended,
        "backend": meaningful(existing.get("backend")) or meaningful(evidence_record.get("backend")) or "unresolved",
        "backend_rationale": meaningful(existing.get("backend_rationale")) or meaningful(evidence_record.get("backend_reason")) or "TBD",
        "provenance": {
            "source_data": source_data,
            "script": script,
            "output": artifact,
            "png": clean(evidence_record.get("png_file")) or clean(provenance.get("png")),
            "log": clean(evidence_record.get("log_file")) or clean(provenance.get("log")),
            **{key: value for key, value in provenance.items() if key not in {"source_data", "script", "output"}},
        },
        "artifact": artifact,
        "caption": meaningful(existing.get("caption")) or meaningful(evidence_record.get("caption")) or intended,
        "paper_location": meaningful(existing.get("paper_location")) or meaningful(evidence_record.get("paper_section")) or "TBD",
        "prelude": meaningful(existing.get("prelude")) or meaningful(evidence_record.get("prelude")) or "TBD",
        "conclusion": meaningful(existing.get("conclusion")) or meaningful(evidence_record.get("conclusion")) or intended,
        "layout": meaningful(existing.get("layout")) or meaningful(evidence_record.get("layout")) or "single",
        "legend_strategy": meaningful(existing.get("legend_strategy")) or meaningful(evidence_record.get("legend_strategy")) or "TBD",
        "waiver": {
            "applies": bool(waiver.get("applies", False)),
            "reason": clean(waiver.get("reason")),
            "scope": clean(waiver.get("scope")),
            "evidence": list_value(waiver.get("evidence")),
        },
        # Compatibility fields consumed by older visual portfolio and revision gates.
        "proposed_visual": proposed,
        "nearby_claim": nearby,
        "callout": meaningful(existing.get("callout")) or meaningful(evidence_record.get("conclusion")) or intended,
        "source_artifact": artifact,
        "status": status or "planned_gap",
    }


def match_existing_evidence(
    matches: list[tuple[int, dict[str, Any]]],
    claimed: set[int],
    evidence: dict[str, Any],
) -> tuple[int, dict[str, Any]] | None:
    evidence_id = clean(evidence.get("figure_id"))
    artifacts = {
        clean(evidence.get("vector_file")),
        clean(evidence.get("png_file")),
    } - {""}
    for index, item in matches:
        if index in claimed:
            continue
        provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
        item_artifacts = {
            clean(item.get("artifact")),
            clean(item.get("source_artifact")),
            clean(provenance.get("output")),
            clean(provenance.get("png")),
        } - {""}
        if (evidence_id and clean(item.get("evidence_id")) == evidence_id) or artifacts.intersection(item_artifacts):
            return index, item
    for index, item in matches:
        if index in claimed:
            continue
        if not meaningful(item.get("artifact")) and not meaningful(item.get("chosen_evidence_form")):
            return index, item
    return None


def role_from_evidence(evidence: dict[str, Any]) -> str:
    role = clean(evidence.get("evidence_role")).lower()
    mapping = {
        "structure": "define",
        "definition": "define",
        "mechanism": "derive",
        "operation": "operate",
        "process": "operate",
        "result": "result",
        "validation": "validate",
        "residual": "validate",
        "zoom": "zoom",
        "comparison": "compare",
    }
    return mapping.get(role, role if role in ROLE_ORDER else "")


def normalize_orphan(item: dict[str, Any], index: int) -> dict[str, Any]:
    preserved = dict(item)
    preserved["item_id"] = clean(item.get("item_id")) or f"STALE-{index:03d}"
    preserved["claim_id"] = clean(item.get("claim_id"))
    preserved["status"] = "stale_binding" if preserved["claim_id"] else "stale_unbound"
    return preserved


def build_legacy_storyboard(root: Path, existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if existing:
        return existing
    context = collect_context(root)
    questions = detect_questions(context) or ["Q1"]
    rows = read_visual_index(root)
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        artifact = row["artifact"]
        items.append(
            legacy_item(
                item_id=f"LEGACY-{index:03d}",
                question=detect_question(" ".join(row.values()), questions),
                role=infer_role(" ".join(row.values())),
                artifact=artifact,
                claim=row.get("claim", ""),
                status="existing_index",
            )
        )
    if not items:
        for index, question in enumerate(questions, start=1):
            items.append(legacy_item(f"LEGACY-{index:03d}", question, "result", "TBD", "", "planned_gap"))
    return items


def legacy_item(item_id: str, question: str, role: str, artifact: str, claim: str, status: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "claim_id": "",
        "claim_key": "",
        "question": question,
        "role": role,
        "reader_question": "TBD",
        "chosen_evidence_form": "unresolved",
        "alternatives_considered": [],
        "intended_inference": "TBD",
        "backend": "unresolved",
        "backend_rationale": "TBD",
        "provenance": {"source_data": "TBD", "script": "TBD", "output": artifact},
        "artifact": artifact,
        "caption": "TBD",
        "paper_location": "TBD",
        "waiver": {"applies": False, "reason": "", "scope": "", "evidence": []},
        "proposed_visual": "existing visual" if artifact != "TBD" else "claim-bearing result evidence",
        "nearby_claim": claim or f"{question}: support the principal result",
        "callout": "TBD",
        "source_artifact": artifact,
        "status": status,
    }


def collect_context(root: Path) -> str:
    paths = [
        "planning/problem_analysis.md",
        "planning/modeling_plan.md",
        "results/result_report.md",
        "planning/result_ledger.md",
    ]
    return "\n".join(read_text(root / value)[:20000] for value in paths)


def read_visual_index(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in (root / "figures" / "figure_index.md", root / "diagrams" / "diagram_index.md"):
        for line in read_text(path).splitlines():
            if not line.startswith("|") or "---" in line:
                continue
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            if not cells or cells[0].lower() in {"figure", "diagram"}:
                continue
            while len(cells) < 5:
                cells.append("")
            rows.append({"artifact": cells[0], "source": cells[1], "script": cells[2], "claim": cells[3], "location": cells[4]})
    return rows


def detect_questions(text: str) -> list[str]:
    values = {f"Q{int(value)}" for value in re.findall(r"\bQ([1-9])\b", text, flags=re.I)}
    values.update(f"Q{int(value)}" for value in re.findall(r"问题\s*([1-9])", text))
    return sorted(values, key=lambda value: int(value[1:]))


def detect_question(text: str, questions: list[str]) -> str:
    match = re.search(r"\bQ([1-9])\b", text, flags=re.I)
    if match:
        return "Q" + match.group(1)
    return questions[0] if len(questions) == 1 else "ALL"


def role_for_claim(claim: dict[str, Any]) -> str:
    claim_type = clean(claim.get("claim_type")).lower()
    mapping = {
        "mechanism": "derive",
        "bound": "zoom",
        "threshold": "compare",
        "regime": "compare",
        "comparison": "compare",
        "uncertainty": "validate",
        "feasibility": "validate",
    }
    return mapping.get(claim_type, "result")


def infer_role(text: str) -> str:
    lower = text.lower()
    terms = {
        "validate": ["residual", "audit", "sensitivity", "robust", "残差", "灵敏度", "验证"],
        "compare": ["compare", "baseline", "scenario", "对比", "情景"],
        "operate": ["algorithm", "flow", "solver", "算法", "流程"],
        "define": ["geometry", "structure", "state", "几何", "结构", "状态"],
        "zoom": ["zoom", "critical", "boundary", "局部", "边界"],
        "derive": ["constraint", "formula", "relation", "约束", "公式"],
    }
    for role, needles in terms.items():
        if any(needle in lower for needle in needles):
            return role
    return "result"


def evidence_description(form: str) -> str:
    if form in EVIDENCE_FORMS:
        return f"{form} selected for this claim"
    return "select proof, table, figure, diagram, or no-visual waiver"


def reader_question(claim: dict[str, Any]) -> str:
    implication = clean(claim.get("decision_implication"))
    key = clean(claim.get("key"))
    return f"What evidence lets the reader accept {implication or key}?"


def claim_text(claim: dict[str, Any]) -> str:
    return clean(claim.get("decision_implication")) or clean(claim.get("mechanism")) or clean(claim.get("key"))


def question_from_key(key: str) -> str:
    match = re.match(r"q([1-9])(?:\.|$)", key, flags=re.I)
    return "Q" + match.group(1) if match else "ALL"


def is_central(entry: dict[str, Any]) -> bool:
    return entry.get("centrality") == "central" or entry.get("final_claim") is True


def metrics(items: list[dict[str, Any]], three_d_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": len(items),
        "central_claims": len({clean(item.get("claim_id")) for item in items if clean(item.get("claim_id"))}),
        "unresolved": sum(clean(item.get("chosen_evidence_form")).lower() not in EVIDENCE_FORMS for item in items),
        "stale_bindings": sum(clean(item.get("status")).startswith("stale_") for item in items),
        "forms": {form: sum(clean(item.get("chosen_evidence_form")) == form for item in items) for form in EVIDENCE_FORMS},
        "three_d_candidates": len(three_d_candidates),
        "unresolved_three_d_candidates": sum(
            clean(item.get("status")).lower() not in {"generated", "waived"}
            for item in three_d_candidates
        ),
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Claim-Evidence Storyboard",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Mode: `{payload['mode']}`",
        "- Authority: canonical claim-evidence plan; edit this plan or its JSON, not the derived evidence report.",
        "",
        "## Coverage Decisions",
        "",
        "| Item | Claim | Question | Role | Form | Backend | Artifact | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            f"| `{escape(item.get('item_id'))}` | `{escape(item.get('claim_id'))}` | "
            f"{escape(item.get('question'))} | `{escape(item.get('role'))}` | "
            f"`{escape(item.get('chosen_evidence_form'))}` | `{escape(item.get('backend'))}` | "
            f"`{escape(item.get('artifact'))}` | {escape(item.get('status'))} |"
        )
    lines.extend(["", "## Decision Detail", ""])
    for item in payload["items"]:
        lines.extend(
            [
                f"### {escape(item.get('item_id'))}",
                "",
                f"- Reader question: {escape(item.get('reader_question'))}",
                f"- Intended inference: {escape(item.get('intended_inference'))}",
                f"- Alternatives considered: {escape(', '.join(list_value(item.get('alternatives_considered'))) or 'TBD')}",
                f"- Backend rationale: {escape(item.get('backend_rationale'))}",
                f"- Caption: {escape(item.get('caption'))}",
                f"- Paper location: {escape(item.get('paper_location'))}",
                "",
            ]
        )
    lines.extend(
        [
            "## Three-Dimensional Opportunity Decisions",
            "",
            "| Candidate | Question | Kind | Source | Status | Artifact | Waiver reason | Waiver evidence |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    if payload["three_d_candidates"]:
        for item in payload["three_d_candidates"]:
            lines.append(
                f"| `{escape(item.get('candidate_id'))}` | {escape(item.get('question'))} | "
                f"`{escape(item.get('kind'))}` | `{escape(item.get('source'))}` | "
                f"`{escape(item.get('status'))}` | `{escape(item.get('artifact'))}` | "
                f"{escape(item.get('waiver_reason'))} | "
                f"{escape(', '.join(list_value(item.get('waiver_evidence'))))} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | no data-driven 3D opportunity detected | - |")
    lines.append("")
    lines.extend(["## Notes", ""])
    lines.extend(f"- {note}" for note in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ""


def list_value(value: Any) -> list[str]:
    return [clean(item) for item in value] if isinstance(value, list) else []


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper() or "CLAIM"


def clean(value: Any) -> str:
    return str(value or "").strip()


def meaningful(value: Any) -> str:
    cleaned = clean(value)
    return "" if cleaned.lower() in PLACEHOLDERS else cleaned


def escape(value: Any) -> str:
    return clean(value).replace("|", "\\|").replace("\n", " ")


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
