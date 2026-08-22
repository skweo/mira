#!/usr/bin/env python3
"""Turn Mira paper-quality review findings into an actionable repair plan.

This is the 0.4.7 bridge between review and repair. It does not edit the paper.
It reads the paper-quality review output, orders the repairs, and emits a
practical plan with figure redesign briefs, prose rewrite targets, and polish
targets so the next revision round can work from a concrete queue.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RepairItem:
    item_id: str
    source: str
    level: str
    axis: str
    owner_phase: str
    auto_repairable: bool
    priority: int
    target_artifact: str
    action: str
    evidence: str
    next_check: str


@dataclass
class FigureBrief:
    figure: str
    qid: str
    role: str
    current_decision: str
    current_score: int
    redesign_brief: str
    why: str
    next_check: str


@dataclass
class ProseTarget:
    line: int
    figure_hint: str
    rewrite_goal: str
    pattern: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--quality-json", default="checks/paper_quality_review_report.json")
    parser.add_argument("--write-report", default="revisions/paper_quality_repair_plan.md")
    parser.add_argument("--write-json", default="revisions/paper_quality_repair_plan.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    quality_path = resolve(root, args.quality_json)
    quality = read_json(quality_path)
    payload = build_plan(root, quality_path, quality)

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


def build_plan(root: Path, quality_path: Path, quality: dict[str, Any]) -> dict[str, Any]:
    findings = list(quality.get("findings", []))
    figure_reviews = list(quality.get("figure_reviews", []))
    mechanical = list(quality.get("mechanical_sentences", []))
    scorecard = dict(quality.get("scorecard", {}))
    pdf_metrics = dict(quality.get("pdf_metrics", quality.get("metrics", {}).get("pdf", {})))

    repair_items: list[RepairItem] = []
    figure_briefs: list[FigureBrief] = []
    prose_targets: list[ProseTarget] = []

    for idx, finding in enumerate(sorted(findings, key=finding_sort_key), start=1):
        item = classify_finding(idx, quality_path, finding, quality)
        if item is not None:
            repair_items.append(item)

    for sentence in mechanical:
        prose_targets.append(classify_prose_target(sentence))

    for figure in sorted(figure_reviews, key=figure_sort_key):
        brief = classify_figure_brief(figure, quality)
        if brief is not None:
            figure_briefs.append(brief)

    focus_axis = lowest_score_axis(scorecard)
    repair_order = [item.item_id for item in sorted(repair_items, key=repair_item_sort_key)]

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "quality_review": rel(root, quality_path),
        "review_paper": quality.get("paper", ""),
        "review_verdict": quality.get("verdict", "UNKNOWN"),
        "review_scorecard": scorecard,
        "review_pdf": pdf_metrics,
        "repair_items": [asdict(item) for item in sorted(repair_items, key=repair_item_sort_key)],
        "figure_briefs": [asdict(item) for item in figure_briefs],
        "prose_targets": [asdict(item) for item in prose_targets],
        "metrics": {
            "repair_items": len(repair_items),
            "figure_briefs": len(figure_briefs),
            "prose_targets": len(prose_targets),
            "auto_repairable": sum(1 for item in repair_items if item.auto_repairable),
            "manual": sum(1 for item in repair_items if not item.auto_repairable),
            "lowest_score_axis": focus_axis,
            "lowest_score_value": scorecard.get(focus_axis, None),
            "review_score": scorecard.get("contest_final_score", quality.get("metrics", {}).get("contest_final_score")),
        },
        "repair_order": repair_order,
        "notes": [
            "This plan does not modify the paper. It orders the next repair round from the quality review output.",
            "Start with the numbered repair queue, then use the figure briefs and prose targets as local sub-tasks.",
            "Re-run paper_quality_review.py after each real repair round.",
        ],
    }
    return payload


def classify_finding(idx: int, quality_path: Path, finding: dict[str, Any], quality: dict[str, Any]) -> RepairItem | None:
    axis = str(finding.get("axis", "audit"))
    level = str(finding.get("level", "WARN"))
    evidence = str(finding.get("evidence", finding.get("finding", "")))
    review_paper = str(quality.get("paper", "paper/main.tex"))
    scorecard = dict(quality.get("scorecard", {}))

    if axis == "mechanical_prose":
        lines = [str(item.get("line", "")) for item in quality.get("mechanical_sentences", [])]
        return RepairItem(
            item_id=f"rq-{idx:03d}",
            source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
            level=level,
            axis=axis,
            owner_phase="paper",
            auto_repairable=True,
            priority=10,
            target_artifact=review_paper or "paper/main_final_repaired.tex",
            action="Rewrite the template-like visual-loop sentences so each figure intro/exit names the exact object, variable, value, or decision the figure supports.",
            evidence="lines " + ", ".join(lines[:8]) if lines else evidence,
            next_check="Run paper_quality_review.py again on the repaired copy.",
        )
    if axis == "figure_effectiveness":
        weak = [item for item in quality.get("figure_reviews", []) if item.get("recommendation") != "KEEP"]
        return RepairItem(
            item_id=f"rq-{idx:03d}",
            source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
            level=level,
            axis=axis,
            owner_phase="implementation",
            auto_repairable=False,
            priority=20,
            target_artifact="figures/ + diagrams/",
            action=f"Redraw or simplify the {len(weak)} weak visuals so each one earns main-text space; prioritize the weakest scan, then the weak operation/geometry figures.",
            evidence=evidence,
            next_check="Re-run visual_reasoning_audit.py and paper_quality_review.py after the new visuals exist.",
        )
    if axis == "figure_value":
        return RepairItem(
            item_id=f"rq-{idx:03d}",
            source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
            level=level,
            axis=axis,
            owner_phase="implementation",
            auto_repairable=False,
            priority=15,
            target_artifact="weak comparison visual identified by the quality review",
            action="Replace a low-information candidate scan with an annotated comparison table or branch diagram; otherwise keep it as a separate result file or drop it.",
            evidence=evidence,
            next_check="Re-run visual_reasoning_audit.py and paper_quality_review.py after the replacement.",
        )
    if axis == "pdf_polish":
        return RepairItem(
            item_id=f"rq-{idx:03d}",
            source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
            level=level,
            axis=axis,
            owner_phase="paper",
            auto_repairable=True,
            priority=30,
            target_artifact=review_paper or "paper/main_final_repaired.tex",
            action="Tighten long tables and captions, then inspect the compiled PDF pages for overflow or cropping risk.",
            evidence=evidence,
            next_check="Recompile the paper and rerun the PDF/presentation checks.",
        )
    if axis == "contest_final_feel":
        lowest = lowest_score_axis(scorecard)
        return RepairItem(
            item_id=f"rq-{idx:03d}",
            source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
            level=level,
            axis=axis,
            owner_phase="implementation",
            auto_repairable=False,
            priority=40,
            target_artifact=review_paper or "paper/main_final_repaired.tex",
            action=f"Raise the lowest scorecard axis first: {lowest} ({scorecard.get(lowest, 'n/a')}/100).",
            evidence=evidence,
            next_check="Re-run paper_quality_review.py and compare the scorecard again.",
        )
    return RepairItem(
        item_id=f"rq-{idx:03d}",
        source=rel(quality_path.parent.parent if quality_path.parent.name == "checks" else quality_path.parent, quality_path),
        level=level,
        axis=axis,
        owner_phase=str(finding.get("return_phase", "paper")),
        auto_repairable=False,
        priority=50,
        target_artifact=review_paper or "paper/main_final_repaired.tex",
        action=str(finding.get("recommendation", "Review and repair the owning artifact.")),
        evidence=evidence,
        next_check="Re-run the owning audit after the repair.",
    )


def classify_figure_brief(figure: dict[str, Any], quality: dict[str, Any]) -> FigureBrief | None:
    decision = str(figure.get("recommendation", "KEEP"))
    if decision == "KEEP":
        return None
    path = str(figure.get("figure", ""))
    qid = str(figure.get("qid", ""))
    role = str(figure.get("role", ""))
    score = int(figure.get("score", 0) or 0)
    reasons = [str(item) for item in figure.get("reasons", [])]
    redesign = figure_redesign_brief(path, qid, role, decision, reasons, quality)
    return FigureBrief(
        figure=path,
        qid=qid or "-",
        role=role or "result",
        current_decision=decision,
        current_score=score,
        redesign_brief=redesign,
        why="; ".join(reasons[:4]) if reasons else "weak visual decision",
        next_check="Re-run visual_reasoning_audit.py and paper_quality_review.py after replacing this asset.",
    )


def classify_prose_target(sentence: dict[str, Any]) -> ProseTarget:
    line = int(sentence.get("line", 0) or 0)
    text = str(sentence.get("text", ""))
    hint = figure_hint(text)
    goal = prose_rewrite_goal(hint, text)
    pattern = prose_rewrite_pattern(hint)
    return ProseTarget(
        line=line,
        figure_hint=hint or "-",
        rewrite_goal=goal,
        pattern=pattern,
    )


def figure_redesign_brief(path: str, qid: str, role: str, decision: str, reasons: list[str], quality: dict[str, Any]) -> str:
    stem = Path(path.replace("\\", "/")).name.lower()
    tokens = set(re.split(r"[^a-z0-9]+", stem))
    if "candidate" in tokens and tokens & {"scan", "comparison", "compare"}:
        return "Replace the flat candidate scan with an annotated branch-comparison table or tree; show the best feasible candidate, the rejected near-misses, and the reason the final choice wins."
    if "model" in tokens and tokens & {"flow", "flowchart"}:
        return "Turn the workflow into a denser flowchart with explicit inputs, outputs, and decision points; if it adds no new logic beyond prose, keep it outside the paper or drop it."
    if "chain" in tokens and tokens & {"sample", "samples", "snapshot", "snapshots"}:
        return "Add sample-time labels and a clear ordering legend so the chain plot proves the invariant instead of just showing repeated snapshots."
    if "collision" in tokens and tokens & {"scan", "sweep", "search"}:
        return "Pair the coarse sweep with a zoomed collision window and annotate the first-feasible/first-collision boundary that drives the stop time."
    if "geometry" in tokens and tokens & {"schematic", "construction", "diagram"}:
        return "Label the tangency points, radii, and direction arrows so the geometry sketch explains the turn construction rather than restating it."
    if "path" in tokens and "chain" in tokens:
        return "If kept, split the path chain into a global passability view and a local turn-space inset so the figure shows what the path proves."
    if "speed" in tokens and "heatmap" in tokens:
        return "Keep only if the color field exposes a time-by-handle pattern that the table cannot; otherwise keep it as a separate support figure or drop it."
    return f"Redesign the {role} figure so the reviewer can see why {decision.lower()} is justified, not just that the asset exists."


def figure_hint(text: str) -> str:
    match = re.search(r"fig:([A-Za-z0-9_-]+)", text)
    if match:
        return f"fig:{match.group(1)}"
    match = re.search(r"(q[1-5][A-Za-z0-9_-]*)", text, flags=re.I)
    if match:
        return match.group(1)
    return ""


def prose_rewrite_goal(hint: str, text: str) -> str:
    hint_l = hint.lower()
    tokens = set(re.split(r"[^a-z0-9]+", hint_l))
    if "geometry" in tokens:
        return "Replace the generic geometry lead-in with a sentence naming the exact parameters and the downstream constraint they determine."
    if "model" in tokens and tokens & {"flow", "flowchart"}:
        return "Say what the flowchart makes clearer: the data handoff, solver order, or validation checkpoint that the next formula depends on."
    if "chain" in tokens and tokens & {"sample", "samples", "snapshot", "snapshots"}:
        return "State exactly what the chain samples prove about ordering, continuity, or layer transitions."
    if tokens & {"scan", "sweep", "search"}:
        return "State the coarse interval and the boundary that the scan brackets before the final value is fixed."
    if tokens & {"feasible", "feasibility", "threshold", "boundary"}:
        return "State the feasibility threshold and the interval-side decision that the zoom resolves."
    if "path" in tokens and "chain" in tokens:
        return "State what the path chain proves about passability through the turn space."
    if tokens & {"candidate", "candidates", "comparison", "compare"}:
        return "State the decision value, not just the absence of improvement, and tie it to the comparison artifact."
    return "Rewrite the sentence so it names the specific figure, the key variables or values, and the exact decision it supports."


def prose_rewrite_pattern(hint: str) -> str:
    hint_l = hint.lower()
    tokens = set(re.split(r"[^a-z0-9]+", hint_l))
    if tokens & {"candidate", "candidates", "comparison", "compare"}:
        return "Example shape: '图 X 表明 ...，因此 ... 被选为最终方案。'"
    if tokens & {"scan", "sweep", "search", "feasible", "feasibility", "threshold", "boundary"}:
        return "Example shape: '图 X 将粗扫区间收窄到 ...，因此最终值固定为 ...。'"
    return "Example shape: '图 X 显示 {specific feature}; 因而下一步公式/判断/选择成立。'"


def lowest_score_axis(scorecard: dict[str, Any]) -> str:
    axes = ["reasoning_chain", "visual_value", "abstract_result_ledger", "formula_emphasis", "polish"]
    best = None
    for axis in axes:
        value = scorecard.get(axis)
        if not isinstance(value, (int, float)):
            continue
        if best is None or value < best[1]:
            best = (axis, float(value))
    return best[0] if best else "polish"


def finding_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    axis = str(item.get("axis", ""))
    order = {
        "mechanical_prose": 0,
        "figure_value": 1,
        "figure_effectiveness": 2,
        "pdf_polish": 3,
        "contest_final_feel": 4,
    }.get(axis, 5)
    level = 0 if str(item.get("level", "")).upper() == "FAIL" else 1
    return (order, level, axis)


def repair_item_sort_key(item: RepairItem) -> tuple[int, int, int, str]:
    level = 0 if item.level.upper() == "FAIL" else 1
    return (item.priority, level, 0 if item.auto_repairable else 1, item.axis)


def figure_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    score = int(item.get("score", 0) or 0)
    decision = str(item.get("recommendation", "KEEP"))
    order = 0 if decision != "KEEP" else 1
    return (order, score, str(item.get("figure", "")))


def build_metric_rows(payload: dict[str, Any]) -> list[tuple[str, Any]]:
    metrics = payload["metrics"]
    rows = [(key, metrics[key]) for key in ["repair_items", "figure_briefs", "prose_targets", "auto_repairable", "manual", "lowest_score_axis", "lowest_score_value", "review_score"]]
    return rows


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Paper Quality Repair Plan",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        f"- Quality review: `{payload['quality_review']}`",
        f"- Review verdict: **{payload['review_verdict']}**",
        f"- Review paper: `{payload['review_paper']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in build_metric_rows(payload):
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")

    lines.extend(
        [
            "",
            "## Repair Queue",
            "",
            "| Rank | Level | Axis | Owner | Auto | Target | Action | Evidence | Next check |",
            "|---:|---|---|---|---|---|---|---|---|",
        ]
    )
    for idx, item in enumerate(payload["repair_items"], start=1):
        lines.append(
            "| {rank} | {level} | {axis} | {owner} | {auto} | `{target}` | {action} | {evidence} | {next_check} |".format(
                rank=idx,
                level=item["level"],
                axis=item["axis"],
                owner=item["owner_phase"],
                auto="yes" if item["auto_repairable"] else "no",
                target=escape(item["target_artifact"]),
                action=escape(item["action"]),
                evidence=escape(item["evidence"]),
                next_check=escape(item["next_check"]),
            )
        )

    lines.extend(
        [
            "",
            "## Figure Redesign Briefs",
            "",
            "| Figure | Q | Role | Score | Current decision | Redesign brief | Why |",
            "|---|---|---|---:|---|---|---|",
        ]
    )
    for item in payload["figure_briefs"]:
        lines.append(
            "| `{figure}` | {qid} | `{role}` | {score} | {decision} | {brief} | {why} |".format(
                figure=escape(item["figure"]),
                qid=item["qid"],
                role=item["role"],
                score=item["current_score"],
                decision=item["current_decision"],
                brief=escape(item["redesign_brief"]),
                why=escape(item["why"]),
            )
        )

    lines.extend(
        [
            "",
            "## Prose Rewrite Targets",
            "",
            "| Line | Figure hint | Rewrite goal | Pattern |",
            "|---:|---|---|---|",
        ]
    )
    for item in payload["prose_targets"]:
        lines.append(
            "| {line} | {hint} | {goal} | {pattern} |".format(
                line=item["line"],
                hint=escape(item["figure_hint"]),
                goal=escape(item["rewrite_goal"]),
                pattern=escape(item["pattern"]),
            )
        )

    lines.extend(
        [
            "",
            "## Repair Order",
            "",
            "1. Clear the mechanical repair prose first, because it is the cheapest paper win and it makes later reading cleaner.",
            "2. Redesign the Q4 candidate-length scan next, because it is the lowest-value figure and has the strongest replacement case.",
            "3. Redraw the weak operation and geometry figures so each one proves a concrete decision or local feature.",
            "4. Fix PDF polish and long-table overflow after the content changes settle.",
            "5. Re-run `paper_quality_review.py` and then `visual_reasoning_audit.py` on the repaired copy.",
            "",
            "## Notes",
            "",
        ]
    )
    for note in payload["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
