#!/usr/bin/env python3
"""Validate one of Mira's four public workflow stages."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from reference_trigger_coverage import current_stage_hits
from workflow_stages import STAGES, STAGE_NUMBERS, normalize_stage, normalize_stage_path


STAGE_REPORTS: Final[dict[str, tuple[str, ...]]] = {
    "analysis": (
        "checks/attachment_mapping_report.json",
        "checks/data_quality_report.json",
    ),
    "modeling": (
        "checks/reasoning_core_report.json",
        "checks/modeling_route_report.json",
    ),
    "implementation": (
        "checks/result_quality_report.json",
        "checks/model_solver_consistency_report.json",
        "checks/visual_render_report.json",
        "checks/figure_evidence_report.json",
    ),
    "paper": (
        "checks/paper_strategy_report.json",
        "checks/paper_consistency_report.json",
        "checks/paper_quality_review_report.json",
        "checks/reference_authenticity_report.json",
        "checks/contest_evidence_chain_report.json",
    ),
}

DECISION_MARKERS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\[REQUIRES_USER_DECISION\][^\n]*", re.I),
    re.compile(r"requires_user_decision\s*[:=]\s*(?!false\b|\[\s*\])[^\n]*", re.I),
    re.compile(r"待用户确认[^\n]*"),
    re.compile(r"需要用户(?:确认|决定|选择)[^\n]*"),
)

IGNORED_LEGACY_CONTROL_ARTIFACTS: Final[frozenset[str]] = frozenset(
    {
        "planning/decision_gates.json",
        "planning/human_decisions.json",
        "planning/human_decision_cards.json",
        "planning/human_decision_cards.md",
        "planning/human_judgment_prompts.json",
        "planning/human_judgment_prompts.md",
        "planning/interactive_gate_request.json",
        "planning/interactive_gate_request.md",
        "planning/decision_lineage_ledger.json",
        "planning/decision_lineage_ledger.md",
        "checks/decision_gate_report.md",
        "checks/decision_gate_report.json",
        "checks/human_decision_report.md",
        "checks/human_decision_report.json",
        "checks/human_decision_card_report.md",
        "checks/human_decision_card_report.json",
        "checks/human_judgment_prompt_report.md",
        "checks/human_judgment_prompt_report.json",
        "checks/interactive_gate_report.md",
        "checks/interactive_gate_report.json",
        "checks/decision_lineage_report.md",
        "checks/decision_lineage_report.json",
        "checks/control_plane_report.md",
        "checks/control_plane_report.json",
    }
)


@dataclass(frozen=True)
class Finding:
    stage: str
    level: str
    check: str
    message: str
    evidence: str = ""


def detect_output_level(root: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    brief = read_text(root / "planning" / "delivery_brief.md")
    match = re.search(
        r"(?:Output level|输出级别)\s*\|\s*(quick_draft|reproducible_draft|contest_final)",
        brief,
        re.I,
    )
    return match.group(1).lower() if match else "reproducible_draft"


class StageGate:
    def __init__(self, root: Path, stage: str, output_level: str) -> None:
        self.root = root.resolve()
        self.stage = normalize_stage(stage)
        self.output_level = output_level
        self.findings: list[Finding] = []
        self.requires_user_decision: list[dict[str, str]] = []

    def evaluate(self) -> dict[str, Any]:
        stages = STAGES[: STAGES.index(self.stage) + 1]
        for stage in stages:
            getattr(self, f"_check_{stage}")()
            self._check_internal_reports(stage)
        self._check_user_decisions(stages)
        self._check_reference_trigger_coverage()
        verdict = "FAIL" if any(item.level == "FAIL" for item in self.findings) else (
            "PASS_WITH_WARNINGS" if any(item.level == "WARN" for item in self.findings) else "PASS"
        )
        next_stage = None
        if verdict != "FAIL" and self.stage != STAGES[-1]:
            next_stage = STAGES[STAGES.index(self.stage) + 1]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "stage": self.stage,
            "stage_number": STAGE_NUMBERS[self.stage],
            "output_level": self.output_level,
            "evaluated_stages": list(stages),
            "verdict": verdict,
            "checks": [asdict(item) for item in self.findings],
            "requires_user_decision": self.requires_user_decision,
            "next_stage": next_stage,
        }

    def _check_analysis(self) -> None:
        self._require_one(
            "analysis",
            "delivery_brief",
            ("planning/delivery_brief.md",),
            "missing delivery brief with output level, source boundary, and expected deliverables",
        )
        self._require_one(
            "analysis",
            "problem_analysis",
            ("planning/problem_analysis.md", "planning/problem_brief.md"),
            "missing problem analysis with subquestions, outputs, fields, units, and ambiguities",
        )

    def _check_modeling(self) -> None:
        self._require_one(
            "modeling",
            "modeling_plan",
            ("planning/modeling_plan.md",),
            "missing modeling plan with variables, assumptions, objectives, constraints, and derivation",
        )
        self._require_one(
            "modeling",
            "validation_plan",
            ("planning/validation_plan.md", "planning/validation_plan.json"),
            "missing validation plan and solver-validation route",
        )

    def _check_implementation(self) -> None:
        code_files = self._files("code", {".py", ".m", ".ipynb"})
        if code_files:
            self._pass("implementation", "executable_code", f"found {len(code_files)} code file(s)", code_files[0])
        else:
            self._fail("implementation", "executable_code", "no executable Python, MATLAB, or notebook source under code/")

        result_files = []
        for folder in ("results", "outputs"):
            result_files.extend(self._files(folder, {".json", ".csv", ".tsv", ".xlsx", ".xls", ".txt", ".log"}))
        if result_files:
            self._pass("implementation", "run_results", f"found {len(result_files)} run/result artifact(s)", result_files[0])
        else:
            self._fail("implementation", "run_results", "no run log or structured result artifact was found")

        figures = []
        for folder in ("figures", "results/figures"):
            figures.extend(self._files(folder, {".png", ".jpg", ".jpeg", ".pdf", ".svg"}))
        if figures:
            self._pass("implementation", "figures", f"found {len(figures)} figure(s)", figures[0])
        elif self.output_level == "contest_final":
            self._fail("implementation", "figures", "contest_final requires generated evidence figures")
        else:
            self._warn("implementation", "figures", "no generated figure was found; confirm that tables or proofs are sufficient")

        if self.output_level == "contest_final":
            self._require_one(
                "implementation",
                "result_ledger",
                ("planning/result_ledger.json", "planning/result_ledger.md"),
                "contest_final requires a frozen, traceable result ledger",
            )

    def _check_paper(self) -> None:
        self._require_one(
            "paper",
            "paper_source",
            ("paper/main.tex", "paper/main.typ", "paper/main.md"),
            "missing canonical paper source",
        )
        pdfs = self._files("paper", {".pdf"})
        if not pdfs:
            pdfs = [self._rel(path) for path in self.root.glob("*.pdf") if path.is_file()]
        if pdfs:
            self._pass("paper", "compiled_pdf", f"found {len(pdfs)} compiled PDF(s)", pdfs[0])
        elif self.output_level == "contest_final":
            self._fail("paper", "compiled_pdf", "contest_final requires a compiled PDF")
        else:
            self._warn("paper", "compiled_pdf", "paper source exists but no compiled PDF was found")

        if self.output_level == "contest_final":
            manifest_path = self.root / "planning" / "delivery_manifest.json"
            manifest = load_json(manifest_path)
            if isinstance(manifest, dict) and manifest.get("status") == "READY":
                self._pass("paper", "delivery_manifest", "delivery manifest is READY", self._rel(manifest_path))
            else:
                status = manifest.get("status", "missing") if isinstance(manifest, dict) else "missing"
                self._fail("paper", "delivery_manifest", f"contest_final delivery manifest is {status}, not READY")

    def _check_internal_reports(self, stage: str) -> None:
        for relative in STAGE_REPORTS[stage]:
            path = self.root / relative
            if not path.is_file():
                continue
            verdict = report_verdict(load_json(path))
            if verdict in {"FAIL", "BLOCKED", "ERROR"}:
                self._fail(stage, "internal_diagnostic", f"internal diagnostic reports {verdict}", relative)

    def _check_user_decisions(self, stages: tuple[str, ...]) -> None:
        seen: set[tuple[str, str]] = set()
        for folder in ("planning", "results", "checks", "revisions"):
            base = self.root / folder
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json", ".tex", ".typ"}:
                    continue
                relative = self._rel(path)
                if relative.startswith("checks/stage_") or relative in IGNORED_LEGACY_CONTROL_ARTIFACTS or relative in {
                    "planning/mira_state.json",
                    "planning/mira_state.md",
                    "planning/reference_route.json",
                    "planning/reference_route.md",
                }:
                    continue
                for line in read_text(path).splitlines():
                    for pattern in DECISION_MARKERS:
                        match = pattern.search(line)
                        if not match:
                            continue
                        owner = owner_stage(relative)
                        if owner not in stages:
                            continue
                        message = compact(match.group(0))
                        key = (relative, message)
                        if key not in seen:
                            seen.add(key)
                            self.requires_user_decision.append(
                                {"stage": owner, "source": relative, "message": message}
                            )
                            self._fail(owner, "requires_user_decision", message, relative)
                        break

    def _check_reference_trigger_coverage(self) -> None:
        expected = current_stage_hits(self.root, self.stage)
        if not expected:
            return

        relative = "planning/reference_route.json"
        route = load_json(self.root / relative)
        rule_ids = ", ".join(item.rule_id for item in expected)
        if not isinstance(route, dict):
            self._fail(
                self.stage,
                "reference_trigger_coverage",
                f"conditional reference triggers require rerouting: {rule_ids}",
                relative,
            )
            return

        route_stage = str(route.get("stage") or route.get("phase") or "missing")
        if route_stage != self.stage:
            self._fail(
                self.stage,
                "reference_trigger_coverage",
                f"reference route stage is {route_stage}, expected {self.stage}; reroute {rule_ids}",
                relative,
            )
            return

        loaded = {
            str(item.get("path"))
            for item in route.get("load_now", [])
            if isinstance(item, dict)
        }
        routed_hits = {
            str(item.get("rule_id")): item
            for item in route.get("trigger_hits", [])
            if isinstance(item, dict)
        }
        missing: list[str] = []
        for expected_hit in expected:
            routed = routed_hits.get(expected_hit.rule_id)
            if not isinstance(routed, dict):
                missing.append(f"{expected_hit.rule_id} (missing trigger record)")
                continue
            if routed.get("reference") != expected_hit.reference or routed.get("disposition") != "load_now":
                missing.append(f"{expected_hit.rule_id} (wrong route disposition)")
                continue
            if expected_hit.reference not in loaded:
                missing.append(f"{expected_hit.rule_id} (reference absent from load_now)")
                continue
            current_evidence = {
                (item.source_type, item.location, item.summary)
                for item in expected_hit.evidence
            }
            routed_evidence = {
                (str(item.get("source_type")), str(item.get("location")), str(item.get("summary")))
                for item in routed.get("evidence", [])
                if isinstance(item, dict)
            }
            if not current_evidence.issubset(routed_evidence):
                missing.append(f"{expected_hit.rule_id} (new or changed evidence)")

        if missing:
            self._fail(
                self.stage,
                "reference_trigger_coverage",
                "reference route is stale or incomplete: " + "; ".join(missing),
                relative,
            )
        else:
            self._pass(
                self.stage,
                "reference_trigger_coverage",
                f"covered {len(expected)} conditional reference trigger(s)",
                relative,
            )

    def _require_one(self, stage: str, check: str, candidates: tuple[str, ...], message: str) -> None:
        for relative in candidates:
            path = self.root / relative
            if path.is_file() and path.stat().st_size > 0:
                self._pass(stage, check, "required artifact is present", relative)
                return
        self._fail(stage, check, message)

    def _files(self, relative: str, suffixes: set[str]) -> list[str]:
        base = self.root / relative
        if not base.exists():
            return []
        return [self._rel(path) for path in sorted(base.rglob("*")) if path.is_file() and path.suffix.lower() in suffixes]

    def _pass(self, stage: str, check: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding(stage, "PASS", check, message, evidence))

    def _warn(self, stage: str, check: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding(stage, "WARN", check, message, evidence))

    def _fail(self, stage: str, check: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding(stage, "FAIL", check, message, evidence))

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)


def owner_stage(value: str) -> str:
    text = str(value).lower().replace("\\", "/")
    try:
        return normalize_stage(text)
    except ValueError:
        pass
    if any(token in text for token in ("problem", "delivery", "attachment", "data_quality")):
        return "analysis"
    if any(token in text for token in ("model", "method", "validation", "symbol")):
        return "modeling"
    if any(token in text for token in ("code", "result", "figure", "visual", "solver", "run")):
        return "implementation"
    return "paper"


def report_verdict(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("verdict", "status", "overall_verdict"):
        value = data.get(key)
        if isinstance(value, str):
            return value.upper()
    summary = data.get("summary")
    if isinstance(summary, dict):
        return report_verdict(summary)
    return ""


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(read_text(path))
    except (json.JSONDecodeError, OSError):
        return None


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()[:300]


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Mira Stage {payload['stage_number']}: {payload['stage']}",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Output level: **{payload['output_level']}**",
        f"- Verdict: **{payload['verdict']}**",
        f"- Next stage: **{payload['next_stage'] or '-'}**",
        "",
        "## Checks",
        "",
        "| Stage | Level | Check | Evidence | Message |",
        "|---|---|---|---|---|",
    ]
    for item in payload["checks"]:
        lines.append(
            f"| {item['stage']} | {item['level']} | {item['check']} | `{item['evidence'] or '-'}` | {escape(item['message'])} |"
        )
    lines.extend(["", "## Requires User Decision", ""])
    if payload["requires_user_decision"]:
        for item in payload["requires_user_decision"]:
            lines.append(f"- `{item['source']}` ({item['stage']}): {item['message']}")
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--stage", required=True, help="analysis, modeling, implementation, paper, or a legacy phase/gate alias")
    parser.add_argument(
        "--output-level",
        default="auto",
        choices=("auto", "quick_draft", "reproducible_draft", "contest_final"),
    )
    parser.add_argument("--write-report", help="Markdown report path; defaults to checks/stage_<n>_<stage>.md")
    parser.add_argument("--write-json", help="JSON report path; defaults to checks/stage_<n>_<stage>.json")
    parser.add_argument("--no-write", action="store_true", help="Evaluate without writing the default reports")
    parser.add_argument("--json", action="store_true", help="Emit the complete JSON payload")
    return parser.parse_args()


def resolve_output(root: Path, value: str | None, default: str) -> Path:
    path = Path(value) if value else root / default
    return path if path.is_absolute() else root / path


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        stage = normalize_stage(args.stage)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output_level = detect_output_level(root, args.output_level)
    payload = StageGate(root, stage, output_level).evaluate()
    if not args.no_write:
        stem = f"stage_{STAGE_NUMBERS[stage]}_{stage}"
        report_path = resolve_output(root, args.write_report, f"checks/{stem}.md")
        json_path = resolve_output(root, args.write_json, f"checks/{stem}.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"STAGE: {stage}")
        print(f"OUTPUT_LEVEL: {output_level}")
        print(f"VERDICT: {payload['verdict']}")
        print(f"REQUIRES_USER_DECISION: {len(payload['requires_user_decision'])}")
        print(f"NEXT_STAGE: {payload['next_stage'] or '-'}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
