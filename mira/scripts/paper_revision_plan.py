#!/usr/bin/env python3
"""Create a paper-revision plan from Mira audit outputs.

The plan is intentionally conservative: it lists auto-repairable paper-writing
issues separately from issues that require new figures, results, or modeling
work. It does not edit paper files.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RevisionItem:
    item_id: str
    source: str
    level: str
    axis: str
    owner_phase: str
    auto_repairable: bool
    action: str
    evidence: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--audit-json", default="checks/visual_reasoning_audit_report.json")
    parser.add_argument("--storyboard-json", default="planning/figure_storyboard.json")
    parser.add_argument("--write-report", default="revisions/paper_revision_plan.md")
    parser.add_argument("--write-json", default="revisions/paper_revision_plan.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    items = build_plan(root, resolve(root, args.audit_json), resolve(root, args.storyboard_json))
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "items": [asdict(item) for item in items],
        "metrics": metrics(items),
        "notes": [
            "Auto-repairable means a writing-only patch is plausible. It does not mean the repair should overwrite the original paper without review.",
            "Items owned by implementation require figure, diagram, table, or result artifacts before paper prose can close them.",
            "Run repair scripts on a copy first, then rerun the source audits.",
        ],
    }

    report = resolve(root, args.write_report)
    data = resolve(root, args.write_json)
    report.parent.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(payload), encoding="utf-8")
    data.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(markdown(payload))
    print(f"INFO: wrote {rel(root, report)}")
    print(f"INFO: wrote {rel(root, data)}")
    return 0


def build_plan(root: Path, audit_json: Path, storyboard_json: Path) -> list[RevisionItem]:
    items: list[RevisionItem] = []
    audit = read_json(audit_json)
    for idx, finding in enumerate(audit.get("findings", []), start=1):
        level = str(finding.get("level", "WARN"))
        axis = str(finding.get("axis", "audit"))
        message = str(finding.get("message", ""))
        owner, auto, action = classify_finding(axis, message)
        items.append(
            RevisionItem(
                item_id=f"vr-{idx:03d}",
                source=rel(root, audit_json),
                level=level,
                axis=axis,
                owner_phase=owner,
                auto_repairable=auto,
                action=action,
                evidence=message,
            )
        )

    storyboard = read_json(storyboard_json)
    gap_id = 1
    for item in storyboard.get("items", []):
        if item.get("status") != "planned_gap":
            continue
        role = str(item.get("role", ""))
        question = str(item.get("question", ""))
        visual = str(item.get("proposed_visual", ""))
        if role in {"derive", "result", "zoom", "compare", "validate"}:
            action = f"{question}: create or justify missing `{role}` visual before final prose claims rely on it."
            owner = "implementation"
            auto = False
        else:
            action = f"{question}: review planned visual gap `{role}`."
            owner = "implementation"
            auto = False
        items.append(
            RevisionItem(
                item_id=f"sb-{gap_id:03d}",
                source=rel(root, storyboard_json),
                level="INFO",
                axis=f"storyboard_{role}",
                owner_phase=owner,
                auto_repairable=auto,
                action=action,
                evidence=visual,
            )
        )
        gap_id += 1
    return items


def classify_finding(axis: str, message: str) -> tuple[str, bool, str]:
    axis_l = axis.lower()
    message_l = message.lower()
    if axis_l == "figure_reference":
        return (
            "paper",
            True,
            "Add nearby prose that references the figure label and states what the figure proves.",
        )
    if axis_l == "abstract_emphasis":
        return (
            "paper",
            True,
            "Bold the main answer phrases and key final numbers in the abstract result ledger.",
        )
    if axis_l == "formula_emphasis":
        return (
            "paper",
            True,
            "Selectively highlight terminal/final-result formulas; keep auxiliary derivations unboxed and unnumbered unless referenced.",
        )
    if axis_l == "figure_text_loop":
        return (
            "paper",
            True,
            "Add pre-figure purpose sentences and post-figure interpretation so each important visual closes a reasoning loop.",
        )
    if axis_l in {"zoom_evidence", "multi_case_visuals", "heatmap_justification"}:
        return (
            "implementation",
            "justification" in message_l,
            "Repair the visual evidence or add nearby justification; do not solve by decorative prose.",
        )
    if axis_l == "2d_3d_choice":
        return (
            "implementation",
            False,
            "Review whether a 3D or paired 2D/3D view adds information; no automatic edit is required.",
        )
    return ("paper", False, "Review the finding and return to the owning stage.")


def metrics(items: list[RevisionItem]) -> dict[str, Any]:
    return {
        "items": len(items),
        "auto_repairable": sum(1 for item in items if item.auto_repairable),
        "manual": sum(1 for item in items if not item.auto_repairable),
        "by_phase": count_by(items, "owner_phase"),
        "by_axis": count_by(items, "axis"),
    }


def count_by(items: list[RevisionItem], attr: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        key = str(getattr(item, attr))
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Paper Revision Plan",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(
        [
            "",
            "## Revision Items",
            "",
            "| ID | Level | Axis | Owner | Auto | Action | Evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in payload["items"]:
        lines.append(
            "| {item_id} | {level} | {axis} | {owner} | {auto} | {action} | {evidence} |".format(
                item_id=item["item_id"],
                level=item["level"],
                axis=item["axis"],
                owner=item["owner_phase"],
                auto="yes" if item["auto_repairable"] else "no",
                action=escape(item["action"]),
                evidence=escape(item["evidence"]),
            )
        )
    lines.extend(["", "## Notes", ""])
    for note in payload["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
