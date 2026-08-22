#!/usr/bin/env python3
"""Build and enforce shared state for Mira's four public stages."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from stage_gate import IGNORED_LEGACY_CONTROL_ARTIFACTS, detect_output_level, normalize_stage


RULE_REFERENCE = "references/shared-state.md"


MARKER_PATTERNS = [
    (re.compile(r"\[REQUIRES_USER_DECISION\][^\n]*", re.I), "requires_user_decision", "BLOCKER", "analysis"),
    (re.compile(r"requires_user_decision\s*[:=]\s*(?!false\b|\[\s*\])[^\n]*", re.I), "requires_user_decision", "BLOCKER", "analysis"),
    (re.compile(r"待用户确认[^\n]*"), "requires_user_decision", "BLOCKER", "analysis"),
    (re.compile(r"需要用户(?:确认|决定|选择)[^\n]*"), "requires_user_decision", "BLOCKER", "analysis"),
]

SCAN_RELS = [
    "planning",
    "results",
    "checks",
    "revisions",
]

TEXT_SUFFIXES = {".md", ".txt", ".json", ".tex", ".typ"}
SKIP_MARKER_FILES = {
    "planning/mira_state.json",
    "planning/mira_state.md",
    "planning/delivery_manifest.json",
    "revisions/iteration_report.md",
    "revisions/iteration_queue.json",
} | set(IGNORED_LEGACY_CONTROL_ARTIFACTS)
OPEN_STATUSES = {"open", "in_progress", "returned"}
BLOCKING_STAGES = {
    "analysis": {"analysis"},
    "modeling": {"analysis", "modeling"},
    "implementation": {"analysis", "modeling", "implementation"},
    "paper": {"analysis", "modeling", "implementation", "paper"},
}
FRESHNESS_DEPENDENCIES = (
    ("planning/problem_analysis.md", "checks/data_quality_report.json", "analysis", "problem analysis is newer than its data-quality check"),
    ("planning/modeling_plan.md", "checks/reasoning_core_report.json", "modeling", "modeling plan is newer than its reasoning check"),
    ("results/frozen_numbers.json", "planning/result_ledger.json", "implementation", "frozen results are newer than the result ledger"),
    ("planning/result_ledger.json", "checks/paper_consistency_report.json", "paper", "result ledger is newer than the paper-consistency check"),
    ("paper/main.tex", "checks/final_delivery_report.json", "paper", "paper source is newer than the final delivery check"),
)


@dataclass
class StateMarker:
    level: str
    type: str
    source: str
    message: str
    return_stage: str


@dataclass
class StaleItem:
    level: str
    source: str
    target: str
    message: str
    return_stage: str


class MiraState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        requested_stage = getattr(args, "stage", None) or getattr(args, "phase", None) or "paper"
        self.requested_stage = str(requested_stage)
        self.stage = normalize_stage(self.requested_stage)
        requested_output = getattr(args, "output_level", "auto") or "auto"
        self.output_level = detect_output_level(self.root, requested_output)
        self.state_path = self.root / "planning" / "mira_state.json"
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "planning" / "mira_state.md"
        self.markers: list[StateMarker] = []
        self.stale: list[StaleItem] = []
        self.open_items: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {}

    def run(self) -> int:
        self._collect()
        self.state = self._build_state()
        if self.args.write:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if self.args.write_report:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(self._markdown(), encoding="utf-8")
        if self.args.check:
            self._emit()
            return 1 if self._blocking_for_stage(self.stage) else 0
        self._emit()
        return 1 if self.state["verdict"] == "FAIL" else 0

    def _collect(self) -> None:
        self._scan_markers()
        self._load_iteration_queue()
        self._check_stale_reports()
        self._check_final_delivery_manifest()

    def _check_final_delivery_manifest(self) -> None:
        if self.stage != "paper" or self.output_level != "contest_final":
            return
        path = self.root / "planning" / "delivery_manifest.json"
        if not path.is_file():
            self.markers.append(
                StateMarker(
                    "BLOCKER",
                    "delivery_manifest",
                    self._rel(path),
                    "contest-final delivery manifest is missing",
                    "paper",
                )
            )
            return
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError:
            self.markers.append(
                StateMarker("BLOCKER", "delivery_manifest", self._rel(path), "delivery manifest is invalid JSON", "paper")
            )
            return
        if isinstance(data, dict) and data.get("status") == "BUILT" and getattr(self.args, "allow_built_manifest", False):
            build = data.get("build") if isinstance(data.get("build"), dict) else {}
            pdf = data.get("pdf") if isinstance(data.get("pdf"), dict) else {}
            audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
            transitional_batch_is_complete = (
                bool(str(data.get("batch_id") or "").strip())
                and build.get("status") == "PASS"
                and build.get("returncode") == 0
                and bool(str(pdf.get("sha256") or "").strip())
                and audit.get("status") == "NOT_RUN"
            )
            if transitional_batch_is_complete:
                return
            self.markers.append(
                StateMarker(
                    "BLOCKER",
                    "delivery_manifest",
                    self._rel(path),
                    "BUILT delivery manifest is incomplete and cannot enter the internal final-control check",
                    "paper",
                )
            )
            return
        if not isinstance(data, dict) or data.get("status") != "READY":
            status = data.get("status", "invalid") if isinstance(data, dict) else "invalid"
            self.markers.append(
                StateMarker(
                    "BLOCKER",
                    "delivery_manifest",
                    self._rel(path),
                    f"contest-final delivery status is {status}, not READY",
                    "paper",
                )
            )
            return
        batch_id = data.get("batch_id")
        audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
        if audit.get("status") != "PASS" or audit.get("batch_id") != batch_id:
            self.markers.append(
                StateMarker(
                    "BLOCKER",
                    "delivery_manifest",
                    self._rel(path),
                    "READY manifest does not have a PASS audit from the same build batch",
                    "paper",
                )
            )

    def _scan_markers(self) -> None:
        for rel in SCAN_RELS:
            folder = self.root / rel
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                rel_path = self._rel(path)
                if rel_path in SKIP_MARKER_FILES:
                    continue
                text = read_text(path)
                for line in text.splitlines():
                    for pattern, marker_type, level, default_stage in MARKER_PATTERNS:
                        match = pattern.search(line)
                        if match:
                            message = compact(line if line.strip() else match.group(0))
                            self.markers.append(
                                StateMarker(
                                    level=level,
                                    type=marker_type,
                                    source=rel_path,
                                    message=message,
                                    return_stage=owner_stage(rel_path) if rel_path else default_stage,
                                )
                            )
                            break

    def _load_iteration_queue(self) -> None:
        path = self.root / "revisions" / "iteration_queue.json"
        if not path.exists():
            return
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError:
            self.markers.append(StateMarker("BLOCKER", "invalid_iteration_queue", self._rel(path), "iteration_queue.json is invalid JSON", "paper"))
            return
        for item in data.get("items", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            if item.get("status") in OPEN_STATUSES and item.get("level") == "FAIL":
                normalized = dict(item)
                return_stage = normalize_owner(str(item.get("return_stage") or item.get("return_phase", "paper")))
                normalized["return_stage"] = return_stage
                normalized["return_phase"] = return_stage
                self.open_items.append(normalized)

    def _check_stale_reports(self) -> None:
        for source_rel, target_rel, stage, message in FRESHNESS_DEPENDENCIES:
            source = self.root / source_rel
            target = self.root / target_rel
            if source.exists() and target.exists() and source.stat().st_mtime > target.stat().st_mtime + 1:
                self.stale.append(StaleItem("WARN", source_rel, target_rel, message, stage))

    def _build_state(self) -> dict[str, Any]:
        stage_blockers = self._blocking_for_stage(self.stage)
        has_nonblocking_markers = bool(self.markers or self.open_items)
        verdict = "FAIL" if stage_blockers else ("PASS_WITH_WARNINGS" if has_nonblocking_markers or self.stale else "PASS")
        return {
            "version": 2,
            "updated_at": now(),
            "root": str(self.root),
            "stage": {"current": self.stage, "requested": self.requested_stage},
            "phase": {"current": self.stage, "requested": self.requested_stage},
            "output_level": self.output_level,
            "markers": [marker_payload(item) for item in self.markers],
            "open_items": self.open_items,
            "stale": [stale_payload(item) for item in self.stale],
            "requires_user_decision": [
                marker_payload(item)
                for item in self.markers
                if item.type == "requires_user_decision"
            ],
            "verdict": verdict,
        }

    def _blocking_for_stage(self, requested_stage: str) -> list[dict[str, Any]]:
        try:
            stage = normalize_stage(str(requested_stage))
        except ValueError:
            stage = "paper"
        allowed = BLOCKING_STAGES[stage]
        blockers: list[dict[str, Any]] = []
        for marker in self.markers:
            if marker.return_stage in allowed and marker.level == "BLOCKER":
                blockers.append(marker_payload(marker))
        for item in self.open_items:
            return_stage = normalize_owner(str(item.get("return_stage") or item.get("return_phase", "paper")))
            if return_stage in allowed:
                normalized = dict(item)
                normalized["return_stage"] = return_stage
                normalized["return_phase"] = return_stage
                blockers.append(normalized)
        return blockers

    def _markdown(self) -> str:
        lines = [
            "# Mira Shared State",
            "",
            f"- Generated: {now()}",
            f"- Verdict: **{self.state['verdict']}**",
            f"- Stage: **{self.stage}**",
            f"- State: `{self._rel(self.state_path)}`",
            "",
            "## Markers",
            "",
            "| Level | Type | Return to | Source | Message |",
            "|---|---|---|---|---|",
        ]
        if self.markers:
            for item in self.markers:
                lines.append(f"| {item.level} | {item.type} | {item.return_stage} | `{item.source}` | {escape(item.message)} |")
        else:
            lines.append("| INFO | none | - | - | no unresolved control markers |")

        lines.extend(["", "## Open Fail Items", "", "| Return to | Source | Finding |", "|---|---|---|"])
        if self.open_items:
            for item in self.open_items:
                lines.append(f"| {normalize_owner(str(item.get('return_stage') or item.get('return_phase', 'paper')))} | `{item.get('source_report', '-')}` | {escape(str(item.get('finding', '-')))} |")
        else:
            lines.append("| - | - | none |")

        lines.extend(["", "## Stale Signals", "", "| Level | Return to | Source | Target | Message |", "|---|---|---|---|---|"])
        if self.stale:
            for item in self.stale:
                lines.append(f"| {item.level} | {item.return_stage} | `{item.source}` | `{item.target}` | {escape(item.message)} |")
        else:
            lines.append("| INFO | - | - | - | no stale stage dependencies detected |")
        lines.append("")
        return "\n".join(lines)

    def _emit(self) -> None:
        blockers = self._blocking_for_stage(self.stage) if self.args.check else []
        print(f"VERDICT: {self.state['verdict']}")
        print(f"markers: {len(self.markers)}")
        print(f"open_fail_items: {len(self.open_items)}")
        print(f"stale: {len(self.stale)}")
        if self.args.check:
            print(f"stage_check: {self.stage}")
            for item in blockers:
                print(f"BLOCK: {item.get('return_stage', item.get('return_phase', '-'))}: {item.get('message') or item.get('finding')}")
        if self.args.write:
            print(f"wrote: {self.state_path}")
        if self.args.write_report:
            print(f"wrote: {self.report_path}")

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--stage", help="analysis, modeling, implementation, or paper")
    parser.add_argument("--phase", help="Legacy phase or gate alias")
    parser.add_argument("--output-level", default="auto", help="quick_draft, reproducible_draft, contest_final, or auto")
    parser.add_argument("--write", action="store_true", help="Write planning/mira_state.json")
    parser.add_argument("--check", action="store_true", help="Return nonzero when blockers affect the requested stage")
    parser.add_argument("--write-report", help="Write markdown state report")
    parser.add_argument("--allow-built-manifest", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:300]


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def normalize_owner(value: str) -> str:
    try:
        return normalize_stage(value)
    except ValueError:
        text = str(value).lower()
        if any(token in text for token in ("problem", "delivery", "attachment", "data")):
            return "analysis"
        if any(token in text for token in ("model", "method", "symbol", "validation")):
            return "modeling"
        if any(token in text for token in ("code", "result", "solver", "figure", "visual")):
            return "implementation"
        return "paper"


def owner_stage(source: str) -> str:
    text = str(source).lower().replace("\\", "/")
    if text.startswith("planning/model") or any(token in text for token in ("method", "symbol", "validation")):
        return "modeling"
    if text.startswith(("code/", "results/", "figures/", "outputs/")) or any(
        token in text for token in ("solver", "figure", "visual", "result")
    ):
        return "implementation"
    if text.startswith("paper/") or any(token in text for token in ("paper", "submission", "delivery_manifest")):
        return "paper"
    return "analysis"


def marker_payload(item: StateMarker) -> dict[str, Any]:
    payload = asdict(item)
    payload["return_phase"] = item.return_stage
    return payload


def stale_payload(item: StaleItem) -> dict[str, Any]:
    payload = asdict(item)
    payload["return_phase"] = item.return_stage
    return payload


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def main() -> int:
    return MiraState(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
