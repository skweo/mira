#!/usr/bin/env python3
"""Audit adaptive paper architecture, argument dependencies, and prose boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ARCHITECTURES = {"mechanism-first", "decision-first", "evidence-first", "theorem-first", "scenario-first"}
ANCHOR_ROLES = {
    "mechanism-first": {"mechanism"},
    "decision-first": {"decision"},
    "evidence-first": {"evidence"},
    "theorem-first": {"theorem", "proof"},
    "scenario-first": {"scenario"},
}
GENERIC_ROLES = {"foundation", "question_answer", "evaluation", "support"}
INTERNAL_PATTERNS = [
    re.compile(r"\b(?:Mira|Codex|Claude|DeepSeek|ChatGPT|GPT[- ]?\d*|AI agent|agent)\b", re.I),
    re.compile(r"\b(?:PASS_WITH_WARNINGS|PASS|FAIL|gate|audit|workflow)\b", re.I),
    re.compile(r"(?:planning|checks|scripts|revisions|results)/[\w./\\-]+", re.I),
    re.compile(r"(?:本轮优化|通过门槛|审计报告|结果账本|结果冻结|内部流程|工作流状态)"),
]


@dataclass
class Finding:
    level: str
    axis: str
    owner_phase: str
    finding: str
    action: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--strategy", default="planning/paper_strategy.json")
    parser.add_argument("--paper", help="Paper source; inferred when omitted")
    parser.add_argument("--stage", choices=("plan", "draft", "verify", "paper"), default="plan")
    parser.add_argument("--output-level", choices=("quick_draft", "reproducible_draft", "contest_final"), default="contest_final")
    parser.add_argument("--write-report", default="checks/paper_strategy_report.md")
    parser.add_argument("--write-json", default="checks/paper_strategy_report.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    strategy_path = resolve(root, args.strategy)
    strategy = load_json(strategy_path)
    paper = resolve(root, args.paper) if args.paper else infer_paper(root)
    audit_stage = "verify" if args.stage == "paper" else args.stage
    findings, metrics = audit(root, strategy, paper, audit_stage)
    if args.output_level == "quick_draft":
        for item in findings:
            if item.level == "FAIL":
                item.level = "WARN"
    verdict = verdict_for(findings)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "strategy": rel(root, strategy_path),
        "paper": rel(root, paper) if paper else "",
        "stage": args.stage,
        "output_level": args.output_level,
        "verdict": verdict,
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    write_json(resolve(root, args.write_json), payload)
    write_text(resolve(root, args.write_report), markdown(payload))
    print(f"VERDICT: {verdict}")
    print(json.dumps(metrics, ensure_ascii=False))
    for item in findings:
        print(f"{item.level}: [{item.axis}] {item.finding}")
    return 1 if verdict == "FAIL" else 0


def audit(root: Path, strategy: dict[str, Any], paper: Path | None, stage: str) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    if not strategy:
        findings.append(fail("strategy_missing", "planning/paper_strategy.json is missing or unreadable", "Run paper_strategy.py, then fill the strategy before drafting."))
        return findings, metrics_for(strategy, paper, [])

    primary = str(strategy.get("primary_architecture", ""))
    supporting = [str(item) for item in strategy.get("supporting_architectures", []) if str(item)]
    if primary not in ARCHITECTURES:
        findings.append(fail("architecture", f"unsupported primary architecture: {primary or 'missing'}", "Choose mechanism-first, decision-first, evidence-first, theorem-first, or scenario-first."))
    invalid_support = sorted(set(supporting) - ARCHITECTURES)
    if invalid_support or primary in supporting:
        findings.append(fail("architecture", "supporting architectures are invalid or duplicate the primary architecture", "Keep distinct valid supporting architectures only."))
    if supporting and not substantive(strategy.get("hybrid_reason")):
        findings.append(fail("hybrid_architecture", "hybrid architecture has no reason", "Explain what the supporting architecture contributes and where it appears."))
    for field in ("architecture_rationale", "one_sentence_thesis", "dominant_explanation_mode"):
        if not substantive(strategy.get(field)):
            findings.append(fail(field, f"{field} is missing or placeholder text", f"Write a problem-specific {field.replace('_', ' ')}."))

    contributions = strategy.get("core_contributions", [])
    if not isinstance(contributions, list) or len(contributions) < 2:
        findings.append(fail("core_contributions", "fewer than two evidence-bound contributions are recorded", "Record 2-4 real contributions with claim, evidence, and boundary."))
    else:
        for index, item in enumerate(contributions, start=1):
            if not isinstance(item, dict) or any(not substantive(item.get(field)) for field in ("claim", "evidence", "boundary")):
                findings.append(fail("core_contributions", f"contribution {index} lacks claim, evidence, or boundary", "Complete the contribution without calling routine complexity or tool use innovation."))

    sections = [item for item in strategy.get("section_plan", []) if isinstance(item, dict)]
    order = [str(item) for item in strategy.get("argument_dependency_order", [])]
    check_sections(findings, sections, order, primary, supporting)

    decisions = strategy.get("deleted_or_merged_sections", [])
    if not isinstance(decisions, list) or not decisions:
        findings.append(fail("section_decisions", "no deleted, merged, or explicit no-deletion decision is recorded", "Record what was removed or why every planned section is necessary."))
    else:
        for item in decisions:
            if not isinstance(item, dict) or any(not substantive(item.get(field)) for field in ("section", "decision", "reason")):
                findings.append(fail("section_decisions", "a section decision lacks section, decision, or reason", "Complete every deletion/merge/retention decision."))

    rhythm = strategy.get("paragraph_rhythm", {})
    if not isinstance(rhythm, dict) or len(rhythm.get("default_pattern", [])) < 3 or not rhythm.get("variation_rules"):
        findings.append(fail("paragraph_rhythm", "paragraph rhythm has no usable default pattern and variation rule", "Define the dominant reasoning cadence and at least one deliberate variation."))
    boundaries = strategy.get("terminology_boundaries", [])
    if not isinstance(boundaries, list) or len(boundaries) < 2:
        findings.append(fail("terminology_boundaries", "fewer than two terminology boundaries are recorded", "Define problem-specific terms whose scope or claim strength must stay stable."))
    if len(strategy.get("prohibited_internal_language", [])) < 3:
        findings.append(fail("paper_boundary", "internal-language boundary is incomplete", "Keep tool, path, gate, audit, and workflow language outside the paper."))

    headings: list[str] = []
    if stage in {"draft", "verify"}:
        if not paper or not paper.is_file():
            findings.append(fail("paper_missing", "paper source is missing at draft/verify stage", "Create the paper source from the approved strategy."))
        else:
            paper_text = read_text(paper)
            headings = extract_headings(paper_text)
            check_paper_alignment(findings, sections, order, headings)
            leaks = internal_leaks(paper_text)
            if leaks:
                findings.append(fail("internal_language_leak", f"paper contains internal agent/audit language: {', '.join(leaks[:5])}", "Translate the sentences into normal model, evidence, and limitation language."))

    return findings, metrics_for(strategy, paper, headings)


def check_sections(findings: list[Finding], sections: list[dict[str, Any]], order: list[str], primary: str, supporting: list[str]) -> None:
    if len(sections) < 5:
        findings.append(fail("section_plan", "section plan is too small to carry the argument", "Plan at least five purposeful body sections or record a concise-paper waiver."))
        return
    ids = [str(item.get("id", "")) for item in sections]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        findings.append(fail("argument_dependency", "section IDs are missing or duplicated", "Use one stable ID per planned section."))
    if set(order) != set(ids) or len(order) != len(ids):
        findings.append(fail("argument_dependency", "argument_dependency_order does not contain every section exactly once", "List all section IDs once in intended argument order."))
        return
    positions = {item: index for index, item in enumerate(order)}
    for section in sections:
        section_id = str(section.get("id", ""))
        for field in ("title", "role", "claim", "keep_reason"):
            if not substantive(section.get(field)):
                findings.append(fail("section_plan", f"{section_id or 'section'} lacks {field}", "Bind each section to a claim, role, and reason for keeping it."))
        if not substantive(section.get("evidence")):
            findings.append(fail("section_evidence", f"{section_id or 'section'} has no evidence binding", "Name the result, proof, table, figure, or source that carries the section claim."))
        for dependency in section.get("depends_on", []):
            dep = str(dependency)
            if dep not in positions or section_id not in positions or positions[dep] >= positions[section_id]:
                findings.append(fail("argument_dependency", f"{section_id} depends on {dep}, but the dependency does not precede it", "Reorder the argument or correct the dependency."))

    roles = [str(next(item for item in sections if str(item.get("id")) == section_id).get("role", "")) for section_id in order]
    primary_roles = ANCHOR_ROLES.get(primary, set())
    if primary_roles and not any(role in primary_roles for role in roles[:3]):
        findings.append(fail("universal_skeleton", f"the first three argument roles do not express the selected {primary} architecture", "Move the primary mechanism, decision, evidence, theorem, or scenario logic before the generic chapter sequence."))
    if roles and sum(role in GENERIC_ROLES for role in roles) / len(roles) > 0.6:
        findings.append(fail("universal_skeleton", "the plan is dominated by generic question/evaluation roles", "Replace the universal chapter skeleton with roles that expose this problem's actual argument."))
    for architecture in supporting:
        if not any(role in ANCHOR_ROLES[architecture] for role in roles):
            findings.append(fail("hybrid_architecture", f"supporting architecture {architecture} has no section role", "Add its real argumentative role or remove it from supporting_architectures."))


def check_paper_alignment(findings: list[Finding], sections: list[dict[str, Any]], order: list[str], headings: list[str]) -> None:
    normalized = [normalize_heading(item) for item in headings]
    section_by_id = {str(item.get("id")): item for item in sections}
    matched: dict[str, int] = {}
    for section_id in order:
        title = normalize_heading(str(section_by_id.get(section_id, {}).get("title", "")))
        for index, heading in enumerate(normalized):
            if title and (title == heading or (len(title) >= 4 and (title in heading or heading in title))):
                matched[section_id] = index
                break
    missing = [section_id for section_id in order if section_id not in matched]
    if missing:
        findings.append(fail("paper_strategy_alignment", f"paper is missing planned headings for: {', '.join(missing)}", "Use the approved section titles or update the strategy before changing the architecture."))
    observed = [matched[item] for item in order if item in matched]
    if observed != sorted(observed):
        findings.append(fail("argument_dependency", "paper heading order conflicts with the strategy dependency order", "Reorder the paper or revise the strategy with an explicit reason."))


def extract_headings(text: str) -> list[str]:
    text = re.sub(r"(?m)^\s*%.*$", "", text)
    headings = re.findall(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]+)\}", text)
    headings.extend(match.group(1) for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    headings.extend(match.group(1) for match in re.finditer(r"(?m)^={1,6}\s+(.+?)\s*$", text))
    return headings


def internal_leaks(text: str) -> list[str]:
    clean = re.sub(r"(?m)^\s*%.*$", "", text)
    out: list[str] = []
    for pattern in INTERNAL_PATTERNS:
        for match in pattern.finditer(clean):
            token = match.group(0).strip()
            if token and token not in out:
                out.append(token)
    return out


def metrics_for(strategy: dict[str, Any], paper: Path | None, headings: list[str]) -> dict[str, Any]:
    return {
        "primary_architecture": strategy.get("primary_architecture", "") if strategy else "",
        "supporting_architecture_count": len(strategy.get("supporting_architectures", [])) if strategy else 0,
        "section_count": len(strategy.get("section_plan", [])) if strategy else 0,
        "contribution_count": len(strategy.get("core_contributions", [])) if strategy else 0,
        "paper_exists": bool(paper and paper.is_file()),
        "paper_heading_count": len(headings),
    }


def substantive(value: Any) -> bool:
    if isinstance(value, list):
        return any(substantive(item) for item in value)
    if isinstance(value, dict):
        return any(substantive(item) for item in value.values())
    text = str(value or "").strip().lower()
    return bool(text) and text not in {"todo", "tbd", "none", "n/a", "to_be_filled", "to_be_decided", "待填写", "待定"}


def fail(axis: str, finding: str, action: str) -> Finding:
    return Finding("FAIL", axis, "paper", finding, action)


def verdict_for(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if findings:
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Paper Strategy Audit",
        "",
        f"- Verdict: **{data['verdict']}**",
        f"- Stage: **{data['stage']}**",
        f"- Strategy: `{data['strategy']}`",
        f"- Paper: `{data['paper'] or 'not found'}`",
        "",
        "## Findings",
        "",
        "| Level | Axis | Owner stage | Finding | Action |",
        "|---|---|---|---|---|",
    ]
    for item in data["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | {item['owner_phase']} | {escape(item['finding'])} | {escape(item['action'])} |")
    if not data["findings"]:
        lines.append("| PASS | paper_strategy | paper | adaptive architecture and argument order are coherent | keep the strategy synchronized with material paper changes |")
    lines.extend(["", "Automatic PASS proves contract coherence, not originality, model superiority, or award probability.", ""])
    return "\n".join(lines)


def infer_paper(root: Path) -> Path | None:
    candidates = [
        root / "paper" / "main.tex",
        root / "paper" / "main.typ",
        root / "paper" / "main.md",
        root / "paper" / "main_final.tex",
    ]
    return next((path for path in candidates if path.is_file()), None)


def normalize_heading(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value).lower()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
