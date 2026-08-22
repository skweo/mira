#!/usr/bin/env python3
"""Build and enforce Mira's revision iteration queue.

The loop turns audit findings into explicit return-to-stage tasks. A Mira run
is not iterative unless these tasks are created, repaired, and rechecked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from delivery_contract import source_report_status
from workflow_stages import STAGES, normalize_stage_path


REPORTS = [
    "planning/mira_state.md",
    "checks/data_quality_report.md",
    "checks/poc_decision_report.md",
    "checks/result_quality_report.md",
    "checks/knowledge_application_report.md",
    "checks/model_solver_consistency_report.md",
    "checks/result_confidence_report.md",
    "checks/paper_consistency_report.md",
    "planning/evidence_plan.md",
    "checks/solver_efficiency_report.md",
    "checks/semantic_audit_report.md",
    "checks/quality_balance_report.md",
    "checks/presentation_strength_report.md",
    "checks/abstract_layout_report.md",
    "checks/final_polish_language_report.md",
    "checks/modeling_route_report.md",
    "checks/reasoning_core_report.md",
    "checks/paper_strategy_report.md",
    "checks/derivation_density_report.md",
    "checks/derivation_logic_report.md",
    "checks/prose_density_report.md",
    "checks/table_style_report.md",
    "checks/visual_asset_audit_report.md",
    "checks/visual_opportunity_report.md",
    "checks/visual_reasoning_audit_report.md",
    "checks/figure_portfolio_report.md",
    "checks/figure_claim_ownership_report.md",
    "checks/diagram_tool_route_report.md",
    "checks/flowchart_diagram_report.md",
    "checks/journal_figure_report.md",
    "checks/showcase_presentation_report.md",
    "checks/award_review_report.md",
    "checks/paper_quality_review_report.md",
    "revisions/paper_quality_repair_plan.md",
    "revisions/paper_revision_loop_report.md",
    "checks/compliance_report.md",
]
SOURCE_BOUND_REPORTS = {
    "checks/abstract_layout_report.md": "checks/abstract_layout_report.json",
    "checks/table_style_report.md": "checks/table_style_report.json",
    "checks/visual_reasoning_audit_report.md": "checks/visual_reasoning_audit_report.json",
    "checks/flowchart_diagram_report.md": "checks/flowchart_diagram_report.json",
    "checks/award_review_report.md": "checks/award_review_report.json",
}

OPEN_STATUSES = {"open", "in_progress", "returned"}
CLOSED_STATUSES = {"resolved", "waived"}
VALID_STATUSES = OPEN_STATUSES | CLOSED_STATUSES


@dataclass
class IterationItem:
    item_id: str
    source_report: str
    level: str
    axis: str
    return_phase: str
    finding: str
    recommended_action: str
    status: str
    evidence: list[str]
    created_at: str
    updated_at: str


@dataclass
class RootCause:
    cluster_id: str
    theme: str
    scope: str
    level: str
    status: str
    return_phase: str
    item_ids: list[str]
    source_reports: list[str]
    summary: str
    recommended_action: str


class IterationLoop:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.queue_path = self.root / "revisions" / "iteration_queue.json"
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "revisions" / "iteration_report.md"
        self.queue = self._load_queue()
        self.items: list[IterationItem] = []
        self.findings: list[str] = []
        self.stale_reports: set[str] = set()

    def run(self) -> int:
        if self.args.mark:
            self._mark_item()
        else:
            self._sync_from_reports()
        if self.args.prune_resolved:
            self._prune_resolved()
        self._refresh_root_causes()
        self._save_queue()
        self._write_report()
        self._emit()
        return 1 if self._blocking_items() else 0

    def _sync_from_reports(self) -> None:
        existing = {item["item_id"]: item for item in self.queue.get("items", []) if isinstance(item, dict)}
        existing_by_key = {
            _finding_key(item.get("source_report", ""), item.get("level", ""), item.get("axis", ""), item.get("finding", "")): item
            for item in self.queue.get("items", [])
            if isinstance(item, dict)
        }
        parsed = self._parse_reports()
        parsed_keys = {_finding_key(item.source_report, item.level, item.axis, item.finding) for item in parsed}
        matched_existing_ids: set[str] = set()
        now = _now()
        out: list[dict[str, Any]] = []

        for item in parsed:
            item_key = _finding_key(item.source_report, item.level, item.axis, item.finding)
            old = existing.get(item.item_id) or existing_by_key.get(item_key)
            if old:
                matched_existing_ids.add(str(old.get("item_id", "")))
                status = old.get("status", "open")
                if status not in VALID_STATUSES:
                    status = "open"
                item.status = status
                item.evidence = _as_list(old.get("evidence"))
                item.created_at = old.get("created_at") or item.created_at
                item.updated_at = now
            out.append(asdict(item))

        for old_id, old in existing.items():
            old_key = _finding_key(old.get("source_report", ""), old.get("level", ""), old.get("axis", ""), old.get("finding", ""))
            if old_id not in matched_existing_ids and old_key not in parsed_keys:
                if old.get("source_report") in self.stale_reports:
                    old["updated_at"] = now
                    note = "source report is stale; retain finding until the gate is rerun against current paper sources"
                    if note not in old.setdefault("evidence", []):
                        old["evidence"].append(note)
                    out.append(old)
                    continue
                status = old.get("status", "open")
                old["status"] = "resolved" if status in OPEN_STATUSES else status
                old["updated_at"] = now
                old.setdefault("evidence", []).append("source finding no longer appears in audit reports")
                out.append(old)

        out.sort(key=lambda item: (_severity_rank(item.get("level", "")), _phase_rank(item.get("return_phase", "")), item.get("item_id", "")))
        self.queue = {"version": 2, "updated_at": now, "items": out}
        self.items = [IterationItem(**item) for item in out]

    def _mark_item(self) -> None:
        status = self.args.status
        if status not in VALID_STATUSES:
            raise SystemExit(f"invalid status: {status}")
        now = _now()
        changed = False
        for item in self.queue.get("items", []):
            if item.get("item_id") == self.args.mark:
                item["status"] = status
                item["updated_at"] = now
                if self.args.evidence:
                    item.setdefault("evidence", []).append(self.args.evidence)
                changed = True
                break
        if not changed:
            raise SystemExit(f"item not found: {self.args.mark}")
        self.queue["updated_at"] = now
        self.items = [IterationItem(**item) for item in self.queue.get("items", [])]

    def _parse_reports(self) -> list[IterationItem]:
        items: list[IterationItem] = []
        for rel in REPORTS:
            path = self.root / rel
            if not path.exists():
                continue
            source = rel.replace("\\", "/")
            source_json = SOURCE_BOUND_REPORTS.get(source)
            if source_json:
                status = source_report_status(self.root, self.root / source_json)
                if status != "CURRENT":
                    self.stale_reports.add(source)
                    items.append(
                        self._make_item(
                            source,
                            "WARN",
                            "control_state",
                            "paper",
                            f"{source} is {status.lower()} for the current paper sources and was not consumed; rerun its source gate",
                        )
                    )
                    continue
            text = _read(path)
            if "paper_quality_repair_plan.md" in rel:
                items.extend(self._parse_paper_quality_repair_plan(rel, text))
                continue
            if "paper_revision_loop_report.md" in rel:
                items.extend(self._parse_paper_revision_loop(rel, text))
                continue
            items.extend(self._parse_markdown_table(rel, text))
            items.extend(self._parse_compliance_tables(rel, text))
        return _dedupe(items)

    def _parse_paper_quality_repair_plan(self, rel: str, text: str) -> list[IterationItem]:
        items: list[IterationItem] = []
        in_queue = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                in_queue = stripped.lower() == "## repair queue"
                continue
            if not in_queue or not stripped.startswith("|"):
                continue
            cols = [col.strip() for col in stripped.strip("|").split("|")]
            if len(cols) < 9 or _is_table_rule(cols) or cols[0].lower() == "rank":
                continue
            level = cols[1].upper()
            axis = cols[2]
            owner_phase = cols[3]
            target = cols[5]
            action = cols[6]
            evidence = cols[7]
            next_check = cols[8]
            finding = f"{action} [target={target}; evidence={evidence}; next={next_check}]"
            item = self._make_item(rel.replace("\\", "/"), level, axis, owner_phase, finding)
            item.recommended_action = action
            item.evidence = [evidence] if evidence else []
            if axis == "figure_value" and "q4_candidate_length_scan" in finding:
                item.return_phase = "implementation"
            items.append(item)
        return items

    def _parse_paper_revision_loop(self, rel: str, text: str) -> list[IterationItem]:
        verdict_match = re.search(r"^- Verdict:\s*\*\*([^*]+)\*\*", text, flags=re.M)
        if not verdict_match:
            return []
        verdict = verdict_match.group(1).strip().upper()
        if verdict in {"PASS", "IMPROVED"}:
            return []
        repaired_match = re.search(r"^- Repaired paper:\s*`([^`]+)`", text, flags=re.M)
        repaired = repaired_match.group(1).strip() if repaired_match else "paper/main_final_repaired.tex"
        if verdict == "FAIL":
            level = "FAIL"
            finding = f"paper revision loop failed; inspect commands and repaired copy `{repaired}` before delivery"
        else:
            level = "WARN"
            finding = f"paper revision loop verdict is {verdict}; review repaired copy `{repaired}` and rerun visual reasoning audit"
        return [self._make_item(rel.replace("\\", "/"), level, "paper_revision_loop", "paper", finding)]

    def _parse_markdown_table(self, rel: str, text: str) -> list[IterationItem]:
        items: list[IterationItem] = []
        source = rel.replace("\\", "/")
        header: dict[str, int] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                if stripped.startswith("#"):
                    header = {}
                continue
            cols = [col.strip() for col in stripped.strip("|").split("|")]
            if not cols or _is_table_rule(cols):
                continue
            normalized = [re.sub(r"[^a-z0-9]+", "_", col.strip("` ").lower()).strip("_") for col in cols]
            if normalized[0] == "level":
                header = {name: index for index, name in enumerate(normalized) if name}
                continue
            if cols[0] in {"---", "Metric", "Gate"}:
                continue
            level = cols[0].upper()
            if level not in {"FAIL", "WARN"}:
                continue
            if header and "level" in header:
                axis_index = next((header[name] for name in ("axis", "type", "gate", "category") if name in header), None)
                phase_index = next((header[name] for name in ("return_to", "return_phase", "owner_phase") if name in header), None)
                finding_index = next((header[name] for name in ("finding", "message", "issue") if name in header), None)
                if finding_index is not None and finding_index < len(cols):
                    axis = cols[axis_index] if axis_index is not None and axis_index < len(cols) else _axis_from_source(source)
                    finding = cols[finding_index]
                    return_phase = cols[phase_index] if phase_index is not None and phase_index < len(cols) else _stage_from_text(finding)
                    items.append(self._make_item(source, level, axis, return_phase, finding))
                    continue
            if "poc_decision_report.md" in source and len(cols) >= 6:
                axis = "poc_decision"
                return_phase = cols[1]
                finding = f"{cols[2]} {cols[3]}: {cols[4]}"
            elif "mira_state.md" in source and len(cols) >= 5:
                if _looks_like_stage(cols[1]):
                    axis = "shared_state"
                    return_phase = cols[1]
                    finding = f"{cols[4]} ({cols[2]} -> {cols[3]})"
                elif _looks_like_stage(cols[2]):
                    axis = cols[1]
                    return_phase = cols[2]
                    finding = f"{cols[4]} ({cols[3]})"
                else:
                    axis = "shared_state"
                    return_phase = _stage_from_text(stripped)
                    finding = stripped
            elif len(cols) >= 4:
                axis = cols[1]
                return_phase = cols[2]
                finding = cols[3]
            elif len(cols) >= 3:
                axis = cols[1] or _axis_from_source(source)
                finding = cols[2]
                return_phase = _stage_from_text(f"{source} {axis} {finding}")
            else:
                axis = _axis_from_source(source)
                return_phase = _stage_from_text(stripped)
                finding = stripped
            items.append(self._make_item(source, level, axis, return_phase, finding))
        return items

    def _parse_compliance_tables(self, rel: str, text: str) -> list[IterationItem]:
        if "compliance_report.md" not in rel:
            return []
        items: list[IterationItem] = []
        current = ""
        for line in text.splitlines():
            heading = re.match(r"^##\s+(.+)", line.strip())
            if heading:
                current = heading.group(1).strip()
                continue
            stripped = line.strip()
            if not stripped.startswith("|") or "---" in stripped or "Problem" in stripped or "Issue" in stripped:
                continue
            cols = [col.strip() for col in stripped.strip("|").split("|")]
            if len(cols) < 3 or _is_table_rule(cols):
                continue
            if current.lower().startswith("blocking"):
                level = "FAIL"
            elif current.lower().startswith("major"):
                level = "WARN"
            else:
                continue
            finding = " | ".join(col for col in cols if col)
            items.append(self._make_item(rel, level, "compliance", _stage_from_text(finding), finding))
        return items

    def _make_item(self, source: str, level: str, axis: str, return_phase: str, finding: str) -> IterationItem:
        clean_stage = _stage_from_text(return_phase) or _stage_from_text(finding) or "paper"
        item_id = _item_id(source, level, axis, clean_stage, finding)
        return IterationItem(
            item_id=item_id,
            source_report=source,
            level=level,
            axis=axis or _axis_from_source(source),
            return_phase=clean_stage,
            finding=finding,
            recommended_action=_recommend(clean_stage, axis, finding),
            status="open",
            evidence=[],
            created_at=_now(),
            updated_at=_now(),
        )

    def _blocking_items(self) -> list[IterationItem]:
        return [
            item
            for item in self.items
            if item.status in OPEN_STATUSES and item.level == "FAIL"
        ]

    def _prune_resolved(self) -> None:
        items = [item for item in self.queue.get("items", []) if isinstance(item, dict) and item.get("status") not in CLOSED_STATUSES]
        self.queue["items"] = items
        self.queue["updated_at"] = _now()
        self.items = [IterationItem(**item) for item in items]

    def _refresh_root_causes(self) -> None:
        clusters = _cluster_items(self.items)
        self.queue["version"] = max(int(self.queue.get("version", 1)), 2)
        self.queue["root_causes"] = [asdict(cluster) for cluster in clusters]
        self.root_causes = clusters

    def _save_queue(self) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_path.write_text(json.dumps(self.queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(self._markdown(), encoding="utf-8")

    def _markdown(self) -> str:
        blocking = self._blocking_items()
        open_items = [item for item in self.items if item.status in OPEN_STATUSES]
        root_causes = getattr(self, "root_causes", _cluster_items(self.items))
        open_root_causes = [cluster for cluster in root_causes if cluster.status in OPEN_STATUSES]
        verdict = "FAIL" if blocking else ("PASS_WITH_WARNINGS" if open_items else "PASS")
        lines = [
            "# Mira Iteration Report",
            "",
            f"- Generated: {_now()}",
            f"- Verdict: **{verdict}**",
            f"- Queue: `{self._rel(self.queue_path)}`",
            f"- Open items: {len(open_items)}",
            f"- Blocking items: {len(blocking)}",
            f"- Open root causes: {len(open_root_causes)}",
            "",
            "## Root Cause Groups",
            "",
            "| Cluster | Level | Status | Return to | Sources | Items | Summary | Recommended action |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for cluster in root_causes:
            lines.append(
                "| {id} | {level} | {status} | {phase} | {sources} | {items} | {summary} | {action} |".format(
                    id=cluster.cluster_id,
                    level=cluster.level,
                    status=cluster.status,
                    phase=cluster.return_phase,
                    sources=_escape_table(", ".join(cluster.source_reports)),
                    items=", ".join(cluster.item_ids),
                    summary=_escape_table(cluster.summary),
                    action=_escape_table(cluster.recommended_action),
                )
            )
        lines.extend(
            [
                "",
                "## Iteration Queue",
                "",
                "| ID | Level | Status | Return to | Source | Finding | Recommended action |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for item in self.items:
            lines.append(
                "| {id} | {level} | {status} | {phase} | {source} | {finding} | {action} |".format(
                    id=item.item_id,
                    level=item.level,
                    status=item.status,
                    phase=item.return_phase,
                    source=item.source_report,
                    finding=_escape_table(item.finding),
                    action=_escape_table(item.recommended_action),
                )
            )
        lines.extend(
            [
                "",
                "## Loop Rule",
                "",
                "- Open FAIL items block final delivery.",
                "- Open WARN items remain visible as nonblocking diagnostics and produce `PASS_WITH_WARNINGS`.",
                "- `--allow-warnings` remains accepted for command compatibility but no longer changes blocking behavior.",
                "- Do not mark an item `resolved` until the owning stage artifact is changed and the source audit no longer reports the finding.",
                "- Use `waived` only when the limitation is intentionally accepted and stated in the paper/compliance report.",
                "- Repair work should start from the root-cause table; the flat item table remains source evidence and close-check history.",
                "",
            ]
        )
        return "\n".join(lines)

    def _emit(self) -> None:
        blocking = self._blocking_items()
        for item in self.items:
            if item.status in OPEN_STATUSES:
                _print(f"{item.level}: [{item.item_id}] {item.return_phase}: {item.finding}")
        verdict = "FAIL" if blocking else ("PASS_WITH_WARNINGS" if any(item.status in OPEN_STATUSES for item in self.items) else "PASS")
        _print(f"VERDICT: {verdict}")
        _print(f"INFO: wrote {self._rel(self.queue_path)}")
        _print(f"INFO: wrote {self._rel(self.report_path)}")

    def _load_queue(self) -> dict[str, Any]:
        if not self.queue_path.exists():
            return {"version": 1, "updated_at": _now(), "items": []}
        try:
            return json.loads(_read(self.queue_path))
        except json.JSONDecodeError:
            return {"version": 1, "updated_at": _now(), "items": []}

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.root / path

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def _item_id(source: str, level: str, axis: str, phase: str, finding: str) -> str:
    qid = _qid(finding)
    digest = hashlib.sha1(_finding_key(source, level, axis, finding).encode("utf-8")).hexdigest()[:8]
    prefix = qid.lower() if qid else "iter"
    return f"{prefix}-{digest}"


def _finding_key(source: str, level: str, axis: str, finding: str) -> str:
    return f"{source}|{level}|{axis}|{_normalize_finding(finding)}"


def _normalize_finding(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip()).lower()


def _qid(text: str) -> str:
    match = re.search(r"\bQ([1-9])\b", text, flags=re.I)
    if match:
        return f"Q{match.group(1)}"
    cn_match = re.search(r"问题([一二三四五六七八九])", text)
    if not cn_match:
        return ""
    mapping = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
    return f"Q{mapping.get(cn_match.group(1), '')}"

def _stage_from_text(text: str) -> str:
    if not text:
        return ""
    raw = str(text).strip()
    if raw.lower() in STAGES:
        return raw.lower()
    match = re.search(r"(?:Phase\s*|G)([0-9](?:/[0-9])?(?:\.[0-9])?)", raw, flags=re.I)
    if match:
        return normalize_stage_path(match.group(0))
    for stage, terms in {
        "analysis": ["data", "attachment", "problem", "delivery brief", "unit", "missing_values", "duplicates"],
        "modeling": ["modeling", "method", "parameter source", "assumption", "model route", "domain knowledge", "derivation"],
        "implementation": ["code", "seed", "convergence", "history", "run", "rerun", "tuning", "multi-seed", "operator", "runtime", "result", "scale", "penalty", "objective", "baseline", "solver", "figure", "chart", "plot", "table", "visual"],
        "paper": ["paper", "claim", "conclusion", "wording", "write", "draft", "compile", "compliance", "semantic_audit", "quality_balance", "citation", "presentation"],
    }.items():
        if any(term.lower() in text.lower() for term in terms):
            return stage
    return "paper"


def _looks_like_stage(text: str) -> bool:
    raw = str(text).strip()
    return raw.lower() in STAGES or bool(re.search(r"^(?:Phase\s*[0-9](?:/[0-9])?(?:\.[0-9])?|G[0-9](?:\.[0-9])?|-)$", raw, flags=re.I))


def _axis_from_source(source: str) -> str:
    name = source.lower()
    if "poc" in name:
        return "poc_decision"
    if "data_quality" in name:
        return "data_quality"
    if "knowledge_application" in name:
        return "knowledge_application"
    if "mira_state" in name:
        return "shared_state"
    if "semantic" in name:
        return "semantic_audit"
    if "result_quality" in name:
        return "result_quality"
    if "model_solver" in name:
        return "model_solver_consistency"
    if "solver_efficiency" in name:
        return "solver_efficiency"
    if "flowchart_diagram" in name:
        return "flowchart_diagram"
    if "presentation" in name:
        return "presentation_strength"
    if "table_style" in name:
        return "table_style"
    if "visual_opportunity" in name:
        return "visual_opportunity"
    if "figure_claim_ownership" in name:
        return "figure_claim_ownership"
    if "diagram_tool_route" in name:
        return "diagram_tool_route"
    if "final_polish_language" in name:
        return "final_polish_language"
    if "prose_density" in name:
        return "prose_density"
    if "paper_quality_review" in name:
        return "paper_quality_review"
    if "paper_strategy" in name:
        return "paper_strategy"
    if "modeling_route" in name:
        return "modeling_route"
    if "derivation_logic" in name:
        return "derivation_logic"
    if "quality" in name:
        return "quality_balance"
    if "compliance" in name:
        return "compliance"
    return "audit"


def _recommend(phase: str, axis: str, finding: str) -> str:
    text = finding.lower()
    qid = _qid(finding)
    target = f"{qid}: " if qid else ""
    if "data_quality" in axis.lower() or "data readiness" in text or "unit" in axis.lower() or "missing_values" in axis.lower() or "duplicates" in axis.lower():
        if "unit" in text or "unit" in axis.lower():
            return target + "return to analysis to confirm field units from the problem statement, data dictionary, literature, or a documented user choice; update planning/data_quality_overrides.json and rerun data_quality_gate.py."
        if "readiness" in text:
            return target + "return to analysis to resolve dataset readiness; when a real choice is needed, record it as requires_user_decision in the analysis stage, then update planning/data_quality_overrides.json and rerun data_quality_gate.py."
        if "missing" in text or "duplicate" in text or "negative" in text or "cleaning" in text:
            return target + "return to analysis to record cleaning actions or waivers, save cleaned data under data_clean/, update planning/data_cleaning_log.json, and rerun data_quality_gate.py before modeling."
        return target + "return to analysis to repair the data-quality finding before modeling, implementation, or paper writing consumes the dataset; rerun data_quality_gate.py."
    if "figure_claim_ownership" in axis.lower() or "core_claim" in text:
        return target + "return to implementation to record each main-paper visual's core_claim in planning/figure_claims.json; rerun figure_claim_ownership_gate.py."
    if "diagram_tool_route" in axis.lower() or "diagram_intent" in text:
        if "data chart" in text:
            return target + "return to implementation to generate the data chart with Python/pyecharts/ECharts, then remove it from the structural diagram intent pack."
        if "source_file" in text or "export_file" in text:
            return target + "return to implementation to generate a reproducible Python/MATLAB source and PDF/PNG export, update planning/diagram_intent_pack.json and diagrams/diagram_index.md, then rerun diagram_tool_router.py."
        if "language" in text or "english" in text:
            return target + "return to implementation to replace default English diagram labels with Chinese labels and rerun diagram_tool_router.py."
        return target + "return to implementation to repair structural diagram routing, source/export records, or diagram intent fields; rerun diagram_tool_router.py."
    if "poc" in axis.lower() or "poc" in text or "smoke-test" in text or "smoke_test" in text:
        if "reject" in text or "rejected" in text:
            return target + "return to modeling to downgrade or reject the weak PoC method; do not select it as the main route without a waiver or later stronger benchmark."
        return target + "return to implementation to add a comparable baseline or alternative run and rerun poc_evaluate.py before using PoC as method evidence."
    if "knowledge" in axis.lower() or "knowledge" in text or "card" in text:
        if "retrieval" in text or "knowledge_injection" in text:
            return target + "return to modeling to run knowledge_retrieve.py, select/reject cards, and save planning/knowledge_injection.md/json before retrying."
        if "validation" in text or "evidence" in text:
            return target + "return to implementation to implement the selected card's validation requirements in code/results; rerun knowledge_application_audit.py."
        if "repair" in text or "failure signs" in text:
            return target + "return to implementation to execute or waive the selected card's repair moves before writing around the weakness."
        return target + "return to modeling or implementation to trace retrieved knowledge cards into modeling_plan, code/results, validation evidence, or an explicit waiver; rerun knowledge_application_audit.py."
    if "shared_state" in axis.lower() or "requires_user_decision" in text:
        return target + "return to the owning public stage in planning/mira_state.json; resolve the marker or record requires_user_decision with the question and evidence before downstream work."
    if "model_solver" in axis.lower() or "backend_execution" in axis.lower() or "qubo_scale" in axis.lower() or "solver_lineage" in axis.lower() or "paper_wording" in axis.lower() or "backend_requirement" in axis.lower():
        if "lineage" in text or "solver_lineage" in text or "actual solver" in text:
            return target + "return to implementation to add per-question solver lineage, result source, and run-log evidence; rerun model_solver_consistency.py before paper writing."
        if "backend" in text or "kaiwu" in text or "sdk" in text or "quantum" in text or "真机" in finding:
            return target + "return to implementation to produce real backend run artifacts, or return to paper to state clearly that the SDK/quantum/QUBO backend is a model interface, future route, or limitation rather than a result source."
        if "qubo" in text or "backend limit" in text or "binary variables" in text or "direct" in text:
            return target + "return to modeling or implementation to add decomposition or classical fallback evidence, or return to paper to remove direct QUBO/backend solve claims for over-capacity cases."
        if "optimality" in text or "wording" in text:
            return target + "return to paper to make wording match the actual executed solver and validation strength."
        return target + "return to implementation to align model, solver, backend, and frozen-number lineage; rerun model_solver_consistency.py before paper writing."
    if "solver_efficiency" in axis.lower() or "algorithm_complexity" in axis.lower() or "enumeration_feasibility" in axis.lower() or "dp_complexity" in axis.lower() or "runtime_evidence" in axis.lower():
        if "enumeration" in text or "枚举" in finding or "65536" in text:
            return target + "return to modeling and implementation to derive the search-space size, per-candidate cost, runtime, and pruning/layered-DP waiver; rerun solver_efficiency_gate.py."
        if "dp" in text or "dynamic" in text or "状态" in finding:
            return target + "return to modeling and implementation to add DP state count, transition count, memory/traceback cost, and a complexity table; rerun solver_efficiency_gate.py."
        if "heuristic" in text or "simulated" in text or "遗传" in finding or "退火" in finding:
            return target + "return to implementation to add iteration budget, stopping rule, runtime, convergence, or multi-seed stability evidence; rerun solver_efficiency_gate.py."
        if "solver" in text or "gap" in text or "status" in text:
            return target + "return to implementation to add variable/constraint scale, solver status, gap/tolerance, runtime, and a fallback route; rerun solver_efficiency_gate.py."
        return target + "return to modeling or implementation to add algorithm complexity, instance scale, runtime/status evidence, and claim-strength wording; rerun solver_efficiency_gate.py."
    if "skill_compaction" in axis.lower() or "lane_policy" in axis.lower():
        return target + "return to analysis to refresh the workflow lane or compact the skill, then rerun the current stage route."
    if "result_quality" in axis.lower() or "convergence_quality" in axis.lower() or "stability_quality" in axis.lower() or "baseline_quality" in axis.lower() or "recommendation_sensitivity" in axis.lower() or "parameter_criticality" in axis.lower():
        if "penalty/travel" in text or "scale-dominating" in text or "objective/travel" in text or "dominated by penalties" in text:
            return target + "retrieve relevant domain knowledge cards, then return to modeling or implementation to repair or justify penalty scaling with component ratios, structural/relaxed bounds, penalty-weight sensitivity, lexicographic or normalized objective handling, and comparable baselines before rerunning result_quality.py."
        if "alpha" in text or "weight" in text or "sensitivity table" in text or "penalty-weight" in text or "fixed_cost" in text:
            return target + "return to implementation to add parameter calibration or sensitivity scenarios for the dominant weight/cost, then rerun result_quality.py before freezing results."
        if "convergence" in text or "tail improvement" in text or "multi-seed" in text or "spread" in text or "unstable" in text:
            return target + "return to implementation to extend runs, tune operators/parameters, add multi-seed stability, or switch to a stronger decomposition strategy; rerun result_quality.py afterward."
        if "baseline" in text or "worse than" in text or "improvement" in text:
            return target + "return to implementation to rerun or repair the method, compare against the best baseline, and freeze only results that beat or justify the baseline."
        if "fixed-cost" in text or "vehicle-count" in text or "recommendation" in text or "breakpoint" in text:
            return target + "return to modeling or implementation to add fixed-cost sensitivity, state the valid recommendation interval, or split the recommendation by scenario."
        return target + "return to implementation to repair the numeric result-quality finding and rerun result_quality.py."
    if "paper_fullness" in axis or "short sections" in text or "page count" in text:
        return target + "return to implementation or paper to expand evidence-bearing figures, tables, derivations, validation prose, and result interpretation near the relevant claims."
    if (
        "final_polish_language" in axis.lower()
        or "abstract_result_emphasis" in axis.lower()
        or "figure_language" in axis.lower()
        or "paper_caption" in axis.lower()
        or "keyword" in axis.lower()
        or "formula_emphasis" in axis.lower()
    ):
        if "english" in text or "plot text" in text or "caption" in text:
            return target + "return to implementation or paper to translate figure/table captions and plot labels into Chinese, regenerate affected figures, and rerun final_polish_language_gate.py."
        if "abstract" in text or "keyword" in text:
            return target + "return to paper to rewrite the abstract as segmented per-question result paragraphs with a visible keyword line; rerun final_polish_language_gate.py."
        return target + "return to paper to selectively emphasize final-answer/key-conclusion formulas or results; keep auxiliary derivations unboxed and unnumbered unless later text references them; rerun final_polish_language_gate.py."
    if (
        "modeling_route" in axis.lower()
        or "route section" in text
        or "route card" in text
        or "technical route" in text
        or "建模思路" in finding
        or "技术路线" in finding
    ):
        if "planning" in text:
            return target + "return to analysis or modeling to write per-question route cards in problem_analysis.md/modeling_plan.md: input/output, transformation, model, solver, result evidence, and validation."
        if "visual" in text or "diagram" in text or "table" in text or "流程图" in finding or "路线表" in finding:
            return target + "return to implementation or paper to add a compact technical route diagram or route table only if it clarifies the model path; rerun modeling_route_audit.py."
        return target + "return to paper, and if needed analysis or modeling, to make the paper-visible route explicit before formulas: input -> transformation -> model -> solver -> result/validation; rerun modeling_route_audit.py."
    if (
        "flowchart_diagram" in axis.lower()
        or "flowchart_presence" in axis.lower()
        or "paper_inclusion" in axis.lower()
        or "diagram_index" in axis.lower()
        or "branch_logic" in axis.lower()
        or "domain_lanes" in axis.lower()
        or "stage_container_grammar" in axis.lower()
        or "decision_node_grammar" in axis.lower()
        or "repeated_instance_grammar" in axis.lower()
        or "feedback_loop_grammar" in axis.lower()
        or "abbreviation_caption" in axis.lower()
        or "diagram_toolchain" in axis.lower()
        or ("flowchart" in text and "diagram" in text)
        or "workflow/idea/architecture" in text
    ):
        if "decision" in text or "approval" in text or "yes-no" in text or "yes/no" in text:
            return target + "return to implementation or paper to redraw as a decision/approval swimlane with role lanes, diamond decisions, yes/no labels, return loops, and terminal records; update diagram_index.md and rerun flowchart_diagram_gate.py."
        if "repeated" in text or "batch" in text or "parallel" in text or "multi-instance" in text:
            return target + "return to implementation to redraw as a complex technical swimlane with repeated rows, stage containers, cross-lane arrows, split/merge/fetch labels, and boundary notes; update the storyboard and rerun flowchart_diagram_gate.py."
        if "architecture" in text or "idea-map" in text or "stage container" in text or "domain/lane" in text or "lane" in text:
            return target + "return to implementation or paper to choose a platform architecture map or grouped route diagram with dashed containers, main-flow arrows, support rails, and clear stage/lane labels; update diagram_index.md and rerun flowchart_diagram_gate.py."
        if "toolchain" in text or "source" in text or "provenance" in text:
            return target + "return to implementation to record truthful diagram provenance: PPTX/spec/SVG/Python/Mermaid source, export path, paper location, and waiver if no editable source exists; rerun flowchart_diagram_gate.py."
        return target + "return to implementation or paper to select the correct diagram grammar: compact route, platform architecture map, decision/approval swimlane, or complex technical swimlane; include the diagram in the paper, update storyboard/index, and rerun flowchart_diagram_gate.py."
    if "table_style" in axis.lower() or "three_line" in axis.lower() or "booktabs" in axis.lower() or "hline" in axis.lower() or "vertical_rules" in axis.lower():
        return target + "return to paper to convert final-paper tables to three-line/booktabs style, remove unnecessary vertical rules or repeated \\hline, and keep raw long tables in supporting result files; rerun table_style_audit.py."
    if (
        "derivation_logic" in axis.lower()
        or "symbol_definition" in axis.lower()
        or "objective_constraint" in axis.lower()
        or "logic_jump" in axis.lower()
        or "strong_claim" in axis.lower()
        or "constraint_source" in axis.lower()
        or "section_logic_chain" in axis.lower()
    ):
        if "symbol" in text or "undefined" in text:
            return target + "return to modeling or paper to complete the symbol table and add local `where/其中/式中` explanations before rerunning derivation_logic_gate.py."
        if "objective" in text or "constraint" in text:
            return target + "return to modeling to repair the formulation as objective + constraints + domain/source, then return to paper to trace it; rerun derivation_logic_gate.py."
        if "strong" in text or "optimality" in text or "convergence" in text or "robust" in text or "significance" in text:
            return target + "return to implementation or paper to add proof, bound, solver gap, baseline, convergence, multi-seed, or sensitivity evidence; otherwise weaken the claim wording and rerun derivation_logic_gate.py."
        return target + "return to modeling, implementation, or paper to repair the broken formula chain: problem condition -> symbol/objective/constraint -> solver -> result/validation -> conclusion scope; rerun derivation_logic_gate.py."
    if "mechanical_prose" in axis.lower() or "mechanical" in text or "template-like" in text:
        return target + "return to paper to rewrite mechanical repair sentences with figure-specific variables, exact values, local visual features, and the decision each visual supports; rerun paper_quality_review.py."
    if (
        "prose_density" in axis.lower()
        or "agent_prose_leak" in axis.lower()
        or "filler" in axis.lower()
        or "vague_claim" in axis.lower()
        or "generic_evaluation" in axis.lower()
        or "evidence_light" in axis.lower()
    ):
        if "agent" in text or "workflow" in text or "leak" in text:
            return target + "return to paper to remove internal tool, path, audit, and workflow wording from the main paper; translate evidence into paper-native modeling/result language and rerun prose_density_gate.py."
        return target + "return to paper to compress or delete empty prose; rewrite each weak paragraph as claim + number/equation/table/figure/citation/algorithm evidence + contest-question implication, then rerun prose_density_gate.py."
    if "figure_effectiveness" in axis.lower() or "figure_value" in axis.lower() or "low-value" in text or "low-information" in text:
        return target + "return to implementation or paper to redraw, annotate, replace with a compact table/diagram, or drop weak figures; rerun paper_quality_review.py and visual_reasoning_audit.py."
    if (
        "visual_opportunity" in axis.lower()
        or "radar_chart_opportunity" in axis.lower()
        or "high_value_visual_opportunity" in axis.lower()
        or "visual_toolchain" in axis.lower()
        or "visual_index_missing" in axis.lower()
    ):
        if "radar" in text or "雷达" in finding:
            return target + "return to implementation or paper to evaluate the multi-indicator table: if metric directions can be normalized, generate a radar chart; otherwise use parallel coordinates or a normalized score table; rerun visual_opportunity_audit.py."
        if "toolchain" in text or "工具链" in finding:
            return target + "return to implementation to record each figure's actual toolchain in figure/diagram indexes: Python, PPT/PowerPoint, Excel-compatible chart/table, MATLAB/Octave-style surface, or explicit waiver."
        if "index" in text:
            return target + "return to implementation to create figure_index.md/diagram_index.md with artifact, source data, script/toolchain, role, claim, and paper location; rerun visual_opportunity_audit.py."
        return target + "return to implementation or paper to choose the best visual grammar for the evidence table, generate or waive the recommended visual, and rerun visual_opportunity_audit.py."
    if "pdf_polish" in axis.lower() or "overfull" in text or "compiled pdf" in text:
        return target + "return to paper to fix page overflow, compile the reviewed paper, and visually inspect the affected PDF pages."
    if "contest_final_feel" in axis.lower() or "contest-final feel" in text:
        return target + "return to implementation or paper to improve the lowest scorecard axis: reasoning continuity, visual value, abstract ledger, formula emphasis, or polish."
    if "paper_revision_loop" in axis.lower() or "paper revision loop" in text:
        return target + "return to paper to inspect the repaired copy, polish mechanical insertions, rerun paper_revision_loop.py, and only then decide whether to replace the original paper."
    if "paper_strategy" in axis.lower() or "architecture" in axis.lower() or "argument_dependency" in axis.lower() or "universal_skeleton" in axis.lower():
        return target + "return to paper to repair planning/paper_strategy.json, then align the thesis, section roles, evidence bindings, dependencies, and paper heading order; rerun paper_strategy_gate.py."
    if "presentation" in axis.lower() or "visual_evidence" in axis.lower() or "contest_template" in axis.lower() or "section_depth" in axis.lower() or "citation_support" in axis.lower() or "paper_narrative" in axis.lower():
        if "citation" in text or "reference" in text:
            return target + "return to paper and, when needed, modeling to bind real sources to the exact claims they support; do not pad the bibliography."
        if "figure" in text or "visual" in text or "graph" in text:
            return target + "return to implementation or paper to add claim-bearing data-structure, result, and validation visuals with readable labels and local interpretation."
        if "cover" in text or "template" in text or "official" in text:
            return target + "return to paper to use the official or closest contest template with team/problem metadata and formal front matter."
        if "short" in text or "outline" in text or "section" in text:
            return target + "return to paper to expand the named sections with problem-specific analysis, model adaptation, evidence, and result interpretation."
        return target + "return to implementation or paper to repair contest-paper presentation strength, then rerun check_presentation_strength.py."
    if "method_execution" in axis:
        return target + "return to paper to make solver/platform wording match execution logs; if the platform was not run, state it as a modeling formulation only."
    if "penalty/travel" in text or "objective is more than" in text or "dominates" in text:
        action = target + "retrieve relevant domain knowledge cards, then return to implementation to explain objective scale with component ratios, lower/upper bound, and sensitivity; if scale remains implausible, return to modeling to change the formulation or penalty settings."
        if qid == "Q3":
            action += " For Q3 heuristic routing, use routing/time-window card obligations: time-window-aware operators, penalty normalization or lexicographic handling, multi-seed stability, and clustered/decomposed routing if penalties stay dominant."
        return action
    if _has_heuristic_trigger(finding):
        return target + "retrieve relevant domain knowledge cards, then return to implementation to run fixed-seed and multi-seed experiments, save convergence/history tables, compare baselines, and try operator/parameter tuning or decomposition if the result is weak."
    if "baseline" in text or "鍩虹嚎" in text:
        return target + "return to implementation to create exact, greedy, or relaxed baselines and record the comparison table."
    if "parameter" in text or "weight" in text or "鍙傛暟" in text or "cost" in text:
        return target + "retrieve relevant domain knowledge cards when available, then return to modeling or implementation to justify the parameter source and add sensitivity scenarios before freezing results."
    if "paper" in text or "claim" in text or "wording" in text or "conclusion" in text:
        return target + "return to paper after evidence is fixed; weaken claims to match proof, gap, or heuristic evidence."
    if "figure" in text or "table" in text or "fullness" in axis:
        return target + "return to implementation or paper to add evidence-bearing figures/tables near the supported claims."
    return target + f"return to {phase} and repair the smallest artifact that owns this finding; rerun the source audit afterward."


def _has_heuristic_trigger(text: str) -> bool:
    lower = text.lower()
    trigger_terms = [
        "heuristic",
        "simulated annealing",
        "local search",
        "convergence",
        "seed",
        "repeatability",
        "multi-seed",
        "routing",
        "route",
        "time window",
        "vrptw",
        "tsptw",
        "penalty",
        "neighborhood",
        "operator",
        "clustering",
        "decomposition",
    ]
    if any(term in lower for term in trigger_terms):
        return True
    return bool(re.search(r"\bSA\b|\bGA\b|\bPSO\b", text))


def _cluster_items(items: list[IterationItem]) -> list[RootCause]:
    groups: dict[str, list[IterationItem]] = {}
    for item in items:
        theme = _theme(item)
        scope = _scope(item, theme)
        key = f"{scope}:{theme}"
        groups.setdefault(key, []).append(item)

    clusters: list[RootCause] = []
    for key, grouped in groups.items():
        grouped.sort(key=lambda item: (_status_rank(item.status), _severity_rank(item.level), _phase_rank(item.return_phase), item.item_id))
        scope, theme = key.split(":", 1)
        open_items = [item for item in grouped if item.status in OPEN_STATUSES]
        severity_pool = open_items or grouped
        level = _worst_level(severity_pool)
        status = _cluster_status(grouped)
        item_ids = [item.item_id for item in grouped]
        sources = sorted({item.source_report for item in grouped})
        clusters.append(
            RootCause(
                cluster_id=_cluster_id(scope, theme),
                theme=theme,
                scope=scope,
                level=level,
                status=status,
                return_phase=_cluster_phase(theme, scope, grouped),
                item_ids=item_ids,
                source_reports=sources,
                summary=_cluster_summary(theme, scope, grouped),
                recommended_action=_cluster_recommendation(theme, scope, grouped),
            )
        )

    clusters.sort(key=lambda cluster: (_status_rank(cluster.status), _severity_rank(cluster.level), _phase_rank(cluster.return_phase), cluster.cluster_id))
    return clusters


def _theme(item: IterationItem) -> str:
    text = " ".join([item.axis, item.source_report, item.finding]).lower()
    if "agent_prose_leak" in text or "internal agent/workflow/process leak" in text:
        return "agent_prose_leak"
    if any(term in text for term in ["kaiwu", "quantum", "sdk", "qubo", "backend", "solver lineage", "solver_lineage"]):
        return "backend_lineage"
    if any(term in text for term in ["solver_efficiency", "algorithm complexity", "algorithm_complexity", "runtime_evidence", "enumeration_feasibility", "dp_complexity", "complexity", "runtime", "65536"]):
        return "solver_efficiency"
    if "knowledge_application" in text or "knowledge_retrieval" in text or "knowledge_validation" in text or "knowledge_repair" in text:
        return "knowledge_application"
    if "knowledge card" in text or "domain knowledge" in text or "planning/knowledge_injection" in text:
        return "knowledge_application"
    if any(term in text for term in ["penalty/travel", "objective/travel", "scale-dominating", "dominated by penalties", "objective is more than", "component ratio"]):
        return "result_scale"
    if any(term in text for term in ["reference support", "reference list", "reference count", "citation", "bibliography"]):
        return "citation_support"
    if any(term in text for term in ["short sections", "too short", "outline", "section_depth"]):
        return "section_depth"
    if any(term in text for term in ["figure count", "visual richness", "figure density", "visual_evidence", "claim-bearing visuals"]):
        return "visual_evidence"
    if any(term in text for term in ["visual_opportunity", "radar_chart_opportunity", "high_value_visual_opportunity", "visual_toolchain", "visual_index_missing", "recommended visual", "雷达图", "toolchain"]):
        return "visual_opportunity"
    if any(term in text for term in ["figure_portfolio", "visual_type_diversity", "visual_role_diversity", "validation_visual_gap", "operation_visual_gap", "definition_visual_gap", "advanced_visual_fit"]):
        return "visual_portfolio"
    if any(term in text for term in ["flowchart_diagram", "flowchart_presence", "paper_inclusion", "diagram_index", "branch_logic", "domain_lanes", "stage_container_grammar", "decision_node_grammar", "repeated_instance_grammar", "feedback_loop_grammar", "abbreviation_caption", "diagram_toolchain"]):
        return "flowchart_diagram"
    if any(term in text for term in ["complex technical swimlane", "platform architecture map", "decision/approval swimlane", "technical swimlane", "approval swimlane", "workflow/idea/architecture diagram"]):
        return "flowchart_diagram"
    if any(term in text for term in ["final_polish_language", "abstract_result_emphasis", "figure_language", "paper_caption", "formula_emphasis", "keyword line", "english captions", "matplotlib titles"]):
        return "final_polish_language"
    if any(term in text for term in ["modeling_route", "modeling-route", "technical route", "route card", "route section", "per_question_route", "formula_before_route", "建模思路", "技术路线", "建模路线", "求解流程"]):
        return "modeling_route"
    if any(term in text for term in ["reasoning_core", "candidate_diversity", "candidate_portfolio", "discriminating_test", "route_change_rule", "rejection_discipline", "model_selection"]):
        return "reasoning_core"
    if any(term in text for term in ["table_style", "three_line", "booktabs", "hline", "vertical_rules", "three-line table", "三线表"]):
        return "table_style"
    if any(term in text for term in ["derivation_logic", "symbol_definition_gap", "objective_constraint_gap", "constraint_source_gap", "logic_jump_gap", "strong_claim_support_gap", "section_logic_chain_gap", "equation_explanation_gap", "equation_reference_gap"]):
        return "derivation_logic"
    if "mechanical_prose" in text or "mechanical or template-like" in text or "template-like figure" in text:
        return "mechanical_prose"
    if any(term in text for term in ["prose_density", "filler_or_vague_claim", "filler_transition", "vague_claim", "generic_evaluation", "evidence_light_paragraph"]):
        return "prose_density"
    if "agent_prose_leak" in text or "internal agent/workflow/process leak" in text:
        return "agent_prose_leak"
    if "figure_effectiveness" in text or "weak visual" in text or "low-information" in text:
        return "weak_visual"
    if "figure_value" in text or "low-value" in text:
        return "weak_visual"
    if "pdf_polish" in text or "overfull hbox" in text or "compiled pdf" in text:
        return "pdf_polish"
    if "contest_final_feel" in text or "contest-final feel score" in text:
        return "contest_final_feel"
    if "paper_revision_loop" in text or "paper revision loop" in text:
        return "paper_revision_loop"
    if any(term in text for term in ["presentation strength gate", "paper presentation", "contest-final quality", "paper_fullness", "quality_balance"]):
        return "presentation_overall"
    if any(term in text for term in ["official-style", "contest cover", "front matter", "contest_template"]):
        return "contest_template"
    if "page count" in text:
        return "page_density"
    if any(term in text for term in ["newer than", "shared_state", "control-plane", "control_plane", "legacy"]):
        return "control_state"
    if any(term in text for term in ["poc", "smoke-test", "smoke_test"]):
        return "poc_decision"
    if any(term in text for term in ["baseline", "worse than", "improvement"]):
        return "baseline_quality"
    if any(term in text for term in ["convergence", "multi-seed", "seed", "stability", "heuristic", "local search", "simulated annealing"]):
        return "heuristic_validation"
    if any(term in text for term in ["parameter", "weight", "sensitivity", "fixed-cost", "fixed_cost"]):
        return "parameter_sensitivity"
    if any(term in text for term in ["claim", "wording", "optimality", "paper-ready interpretation"]):
        return "claim_strength"
    return _slug(item.axis or _axis_from_source(item.source_report)) or "audit"


def _scope(item: IterationItem, theme: str) -> str:
    qid = _qid(item.finding)
    if qid:
        return qid.lower()
    return "global"


def _cluster_id(scope: str, theme: str) -> str:
    return _slug(f"rc-{scope}-{theme}")


def _cluster_status(items: list[IterationItem]) -> str:
    statuses = {item.status for item in items}
    if "returned" in statuses:
        return "returned"
    if "in_progress" in statuses:
        return "in_progress"
    if "open" in statuses:
        return "open"
    if statuses and statuses <= {"waived"}:
        return "waived"
    if "waived" in statuses and "resolved" not in statuses:
        return "waived"
    return "resolved"


def _worst_level(items: list[IterationItem]) -> str:
    return min((item.level for item in items), key=_severity_rank, default="INFO")


def _cluster_phase(theme: str, scope: str, items: list[IterationItem]) -> str:
    stage_by_theme = {
        "result_scale": "implementation",
        "backend_lineage": "implementation",
        "solver_efficiency": "modeling",
        "knowledge_application": "modeling",
        "citation_support": "modeling",
        "section_depth": "paper",
        "visual_evidence": "implementation",
        "visual_opportunity": "implementation",
        "visual_portfolio": "implementation",
        "flowchart_diagram": "implementation",
        "final_polish_language": "paper",
        "modeling_route": "analysis",
        "reasoning_core": "analysis",
        "table_style": "paper",
        "derivation_logic": "modeling",
        "mechanical_prose": "paper",
        "prose_density": "paper",
        "agent_prose_leak": "paper",
        "weak_visual": "implementation",
        "pdf_polish": "paper",
        "contest_final_feel": "paper",
        "paper_revision_loop": "paper",
        "presentation_overall": "paper",
        "contest_template": "paper",
        "page_density": "paper",
        "control_state": "paper",
        "poc_decision": "modeling",
        "baseline_quality": "implementation",
        "heuristic_validation": "implementation",
        "parameter_sensitivity": "modeling",
        "claim_strength": "paper",
    }
    if theme in stage_by_theme:
        return stage_by_theme[theme]
    return min((item.return_phase for item in items), key=_phase_rank, default="paper")


def _cluster_summary(theme: str, scope: str, items: list[IterationItem]) -> str:
    scope_label = scope.upper() if scope.startswith("q") else scope
    open_count = sum(1 for item in items if item.status in OPEN_STATUSES)
    sources = ", ".join(sorted({Path(item.source_report).stem for item in items}))
    theme_name = {
        "result_scale": "objective/penalty scale",
        "backend_lineage": "solver/backend lineage",
        "knowledge_application": "knowledge card application and validation",
        "solver_efficiency": "algorithm complexity and solver efficiency",
        "citation_support": "citation/reference support",
        "section_depth": "section depth",
        "visual_evidence": "claim-bearing visual evidence",
        "visual_opportunity": "visual opportunity detection and toolchain selection",
        "visual_portfolio": "visual portfolio diversity and role fit",
        "flowchart_diagram": "workflow/idea/architecture diagram grammar",
        "final_polish_language": "final polish language and Chinese visual prose",
        "modeling_route": "modeling route and per-question route clarity",
        "reasoning_core": "problem structure, model competition, and route-changing evidence",
        "table_style": "three-line table style",
        "derivation_logic": "formula derivation and logic-chain integrity",
        "mechanical_prose": "mechanical repair prose",
        "prose_density": "prose density and filler control",
        "agent_prose_leak": "internal agent/workflow language leakage",
        "weak_visual": "weak or low-value figure decisions",
        "pdf_polish": "PDF and final-layout polish",
        "contest_final_feel": "contest-final scorecard weakness",
        "paper_revision_loop": "paper revision loop",
        "presentation_overall": "contest-paper presentation strength",
        "contest_template": "official contest template signal",
        "page_density": "page density",
        "control_state": "control-plane state freshness",
        "poc_decision": "PoC method-screening decision",
        "baseline_quality": "baseline quality",
        "heuristic_validation": "heuristic validation",
        "parameter_sensitivity": "parameter sensitivity",
        "claim_strength": "claim wording strength",
    }.get(theme, theme.replace("_", " "))
    return f"{scope_label}: {theme_name}; {open_count}/{len(items)} open source findings from {sources}"


def _cluster_recommendation(theme: str, scope: str, items: list[IterationItem]) -> str:
    prefix = f"{scope.upper()}: " if scope.startswith("q") else ""
    if theme == "result_scale":
        action = prefix + "retrieve relevant domain knowledge cards, then return to implementation to recompute component ratios, bounds/baselines, penalty-weight sensitivity, and objective normalization or lexicographic handling; rerun semantic and result-quality audits."
        if scope == "q3":
            action += " If the scale remains dominant, try time-window-aware operators, clustered/decomposed routing, or a structured route repair strategy before freezing."
        return action
    if theme == "backend_lineage":
        return "Return to implementation: either produce real Kaiwu/SDK/backend run artifacts, or rewrite solver lineage so QUBO/backend is only a formulation, interface, future route, or limitation; rerun model-solver consistency."
    if theme == "solver_efficiency":
        return "Return to modeling or implementation: add instance scale, time/space complexity or operation count, runtime/solver-status evidence, and pruning/decomposition/waiver logic; rerun solver_efficiency_gate.py."
    if theme == "knowledge_application":
        return "Return to modeling or implementation: rerun knowledge retrieval when needed, trace selected cards into modeling_plan, implement validation evidence in code/results, and run or waive repair moves before final delivery."
    if theme == "citation_support":
        return "Return to modeling or paper: bind real sources to the exact method, parameter, data, software, or domain claims they support, or downgrade unsupported claims; do not pad the bibliography."
    if theme == "section_depth":
        return "Return to paper: expand the named sections with problem-specific analysis, derivation, validation evidence, and result interpretation."
    if theme == "visual_evidence":
        return "Return to implementation or paper: add claim-bearing data-structure, model, result, validation, and sensitivity visuals with source data and local interpretation."
    if theme == "visual_opportunity":
        return "Return to implementation or paper: inspect checks/visual_opportunity_report.md, select or waive high-value visual opportunities, use the recommended toolchain only when it actually fits the data, record Python/PPT/Excel/MATLAB-style provenance in figure indexes, and rerun visual_opportunity_audit.py."
    if theme == "visual_portfolio":
        return "Return to implementation or paper: revise the figure storyboard and figure/diagram indexes so the visual portfolio matches evidence roles; add or replace visuals only when a different chart grammar improves definition, operation, result, validation, zoom, or comparison evidence."
    if theme == "flowchart_diagram":
        return "Return to implementation or paper: choose the diagram grammar that matches the claim, redraw or waive it, include it in the paper, update figure_storyboard and diagram_index, record truthful PPTX/spec/SVG/Python/Mermaid provenance, and rerun flowchart_diagram_gate.py. Use compact route diagrams for simple model paths, platform architecture maps for layered systems, decision/approval swimlanes for yes/no review loops, and complex technical swimlanes for repeated parallel tasks or split-merge exchanges."
    if theme == "final_polish_language":
        return "Return to paper: segment the abstract by question, expose keywords, selectively highlight final-answer/key-conclusion formulas or results, translate captions and plot labels into Chinese, regenerate affected figures, and rerun final_polish_language_gate.py."
    if theme == "modeling_route":
        return "Return to analysis, modeling, or paper: add a paper-visible route before heavy formulas, and give each subquestion a route card covering input/output, transformation, model, solver, result evidence, and validation; use a compact diagram or table only when it improves clarity; rerun modeling_route_audit.py."
    if theme == "reasoning_core":
        return "Return to analysis or modeling: repair the Problem Structure Map, Candidate Model Portfolio, discriminating tests, selection/rejection evidence, or proof/dominance waiver; rerun reasoning_core_gate.py before refreezing the route."
    if theme == "table_style":
        return "Return to paper: convert final-paper tables to three-line/booktabs style, remove unnecessary vertical rules or repeated \\hline, polish captions/units, and keep raw long tables in supporting result files; rerun table_style_audit.py."
    if theme == "derivation_logic":
        return "Return to modeling, implementation, or paper: repair the formula chain from problem condition to symbols, objective/constraints, solver, results, validation, and conclusion scope; rerun derivation_logic_gate.py."
    if theme == "mechanical_prose":
        return "Return to paper: rewrite automatic repair prose into figure-specific reasoning sentences, remove generic visual-loop phrases, and rerun paper_quality_review.py."
    if theme == "prose_density":
        return "Return to paper: delete empty transitions and vague praise; rewrite weak paragraphs as claim + evidence artifact + contest-question implication, then rerun prose_density_gate.py."
    if theme == "agent_prose_leak":
        return "Return to paper: remove tool names, local paths, audit/report labels, and workflow-status wording from the paper body; translate support into normal modeling/result language and rerun prose_density_gate.py."
    if theme == "weak_visual":
        return "Return to implementation or paper: use the figure-decision table to redraw, annotate, replace, or drop weak visuals; rerun paper_quality_review.py and visual_reasoning_audit.py."
    if theme == "pdf_polish":
        return "Return to paper: fix overfull tables/captions or missing compiled PDF, then inspect the rendered PDF pages rather than trusting source checks."
    if theme == "contest_final_feel":
        return "Return to implementation or paper: repair the lowest paper_quality_review scorecard axis before comparing with excellent papers."
    if theme == "paper_revision_loop":
        return "Return to paper: review the repaired copy, polish or reject automatic edits, rerun paper_revision_loop.py, and keep result/model/figure artifacts unchanged unless a stage finding returns to earlier work."
    if theme == "presentation_overall":
        return "Return to implementation or paper: repair contest-paper fullness with evidence-bearing figures/tables and stronger narrative, then rerun quality and presentation checks."
    if theme == "contest_template":
        return "Return to paper: add the official or closest contest template/front-matter signal with team/problem metadata."
    if theme == "page_density":
        return "Return to paper: add useful derivations, visuals, and validation tables only where they support claims."
    if theme == "control_state":
        return "Return to paper: refresh canonical stage state and rerun the affected checks so stale reports cannot override current artifacts."
    if theme == "poc_decision":
        return "Return to modeling: compare the PoC against a baseline or alternative, reject weak methods, and record the method-screening decision."
    if theme == "baseline_quality":
        return prefix + "return to implementation to add exact, greedy, relaxed, or incumbent baselines and freeze only results that beat or justify the comparison."
    if theme == "heuristic_validation":
        return prefix + "return to implementation to add fixed-seed and multi-seed runs, convergence/history tables, operator settings, and baseline comparison."
    if theme == "parameter_sensitivity":
        return prefix + "return to modeling or implementation to justify parameter sources and add sensitivity scenarios before freezing results."
    if theme == "claim_strength":
        return prefix + "return to paper after evidence repair; weaken optimum/platform/result claims to match proof, gap, or heuristic evidence."
    return items[0].recommended_action if items else "Return to the owning stage, repair the root cause, and rerun the source audit."


def _status_rank(status: str) -> int:
    return {"returned": 0, "in_progress": 1, "open": 2, "waived": 3, "resolved": 4}.get(status, 5)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return slug or "item"


def _dedupe(items: list[IterationItem]) -> list[IterationItem]:
    seen: set[str] = set()
    out: list[IterationItem] = []
    for item in items:
        if item.item_id in seen:
            continue
        seen.add(item.item_id)
        out.append(item)
    return out


def _severity_rank(level: str) -> int:
    return {"FAIL": 0, "WARN": 1, "INFO": 2}.get(level.upper(), 3)


def _phase_rank(phase: str) -> int:
    try:
        return STAGES.index(normalize_stage_path(phase))
    except (ValueError, TypeError):
        return len(STAGES)


def _escape_table(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _is_table_rule(cols: list[str]) -> bool:
    if not cols:
        return True
    return all(not re.sub(r"[-:\s]", "", str(col)) for col in cols)


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
    parser.add_argument("--write-report", help="Write markdown report, default revisions/iteration_report.md")
    parser.add_argument("--allow-warnings", action="store_true", help="Deprecated compatibility flag; WARN findings are nonblocking by default")
    parser.add_argument("--mark", help="Mark an existing item by ID")
    parser.add_argument("--status", default="resolved", help="Status for --mark: open, in_progress, returned, resolved, waived")
    parser.add_argument("--evidence", help="Evidence note/path when marking an item")
    parser.add_argument("--prune-resolved", action="store_true", help="Remove resolved/waived history from the queue after syncing")
    return parser.parse_args()


def main() -> int:
    return IterationLoop(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())


