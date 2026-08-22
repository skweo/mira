#!/usr/bin/env python3
"""Audit long mathematical-modeling skills and draft compact contracts.

Mira should not load long granular SKILL.md files for routine work. This script
identifies verbose skills and maps them to compact stage contracts or executable
helpers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


DEFAULT_LIMIT = 220

STAGE_MAP = [
    (re.compile(r"problem[-_ ]?(parser|classifier)|symbol[-_ ]?table|data[-_ ]?auditor", re.I), "planning/problem_analysis.md + planning/symbol_table.md", "Use canonical problem-analysis contract; no separate parser/classifier JSON unless deep trigger fires."),
    (re.compile(r"method[-_ ]?selector|model[-_ ]?assumption|analysis[-_ ]?modeling|final[-_ ]?method", re.I), "planning/modeling_plan.md", "Use canonical modeling-plan contract plus modeling decision gate."),
    (re.compile(r"paper|writing|polish|typst|author|reference[-_ ]?manager", re.I), "paper/main.* + checks/quality_balance_report.md", "Use contest-final writing contract and quality-balance gate."),
    (re.compile(r"figure|visual|drawio|diagram", re.I), "figures/figure_index.md + diagrams/diagram_index.md", "Use figure/diagram indexes and generated assets; avoid decorative planning prose."),
    (re.compile(r"result|robust|audit|verify|verity|quality[-_ ]?assurance|consistency|completeness", re.I), "results/result_report.md + checks/*.md", "Use semantic/quality/compliance scripts instead of narrative audit prompts."),
    (re.compile(r"code|python|matlab", re.I), "code/ + results/logs/run_summary.json", "Use executable code scripts and run logs; keep prose instructions short."),
    (re.compile(r"workflow|orchestrator|solution[-_ ]?package", re.I), "planning/delivery_brief.md + planning/workflow_lane.md", "Use Mira workflow lane selector and four-stage contracts."),
]


@dataclass
class SkillAudit:
    name: str
    path: str
    lines: int
    kb: float
    over_limit: bool
    mapped_artifact: str
    replacement: str
    compact_contract: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", action="append", required=True, help="Directory containing skill folders")
    parser.add_argument("--line-limit", type=int, default=DEFAULT_LIMIT, help="SKILL.md line threshold")
    parser.add_argument("--write-report", help="Markdown report path")
    parser.add_argument("--json", help="Optional JSON report path")
    args = parser.parse_args()

    audits: list[SkillAudit] = []
    for root_value in args.skills_root:
        root = Path(root_value).resolve()
        if not root.exists():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            if "__pycache__" in path.parts or ".git" in path.parts:
                continue
            audits.append(audit_skill(path, args.line_limit))

    audits.sort(key=lambda item: (not item.over_limit, -item.lines, item.name.lower()))
    report = markdown_report(audits, args.line_limit)
    if args.write_report:
        out = Path(args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        _print(f"INFO: wrote {out}")
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([asdict(item) for item in audits], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _print(f"INFO: wrote {out}")

    blockers = [item for item in audits if item.over_limit]
    for item in blockers:
        _print(f"WARN: {item.name} has {item.lines} lines; map to {item.mapped_artifact}")
    _print(f"VERDICT: {'PASS_WITH_WARNINGS' if blockers else 'PASS'}")
    return 0


def audit_skill(path: Path, limit: int) -> SkillAudit:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = text.splitlines()
    name = skill_name(path, text)
    artifact, replacement = route(name, text)
    return SkillAudit(
        name=name,
        path=str(path),
        lines=len(lines),
        kb=round(path.stat().st_size / 1024, 1),
        over_limit=len(lines) > limit,
        mapped_artifact=artifact,
        replacement=replacement,
        compact_contract=contract_for(name, artifact, replacement),
    )


def skill_name(path: Path, text: str) -> str:
    match = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+)", text)
    if match:
        return match.group(1).strip()
    return path.parent.name


def route(name: str, text: str) -> tuple[str, str]:
    for pattern, artifact, replacement in STAGE_MAP:
        if pattern.search(name):
            return artifact, replacement
    haystack = text[:2000]
    for pattern, artifact, replacement in STAGE_MAP:
        if pattern.search(haystack):
            return artifact, replacement
    return "canonical stage artifact", "Keep only trigger, inputs, outputs, and validation; move details to references or scripts."


def contract_for(name: str, artifact: str, replacement: str) -> str:
    return (
        f"{name}: read required inputs, write/update `{artifact}`, validate the owning stage, "
        f"and stop on blockers. {replacement}"
    )


def markdown_report(audits: list[SkillAudit], limit: int) -> str:
    long_items = [item for item in audits if item.over_limit]
    total_lines = sum(item.lines for item in audits)
    long_lines = sum(item.lines for item in long_items)
    lines = [
        "# Skill Compaction Report",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Line limit: {limit}",
        f"- Skills scanned: {len(audits)}",
        f"- Long skills: {len(long_items)}",
        f"- Total SKILL.md lines: {total_lines}",
        f"- Lines in long skills: {long_lines}",
        "",
        "## Long Skills",
        "",
        "| Skill | Lines | KB | Mapped artifact | Replacement rule |",
        "|---|---:|---:|---|---|",
    ]
    for item in long_items:
        lines.append(
            f"| {item.name} | {item.lines} | {item.kb} | `{item.mapped_artifact}` | {escape(item.replacement)} |"
        )
    if not long_items:
        lines.append("| - | 0 | 0 | - | - |")

    lines.extend(["", "## Compact Contract Drafts", ""])
    for item in long_items:
        lines.extend([f"### {item.name}", "", item.compact_contract, ""])

    lines.extend(
        [
            "## Mira Policy",
            "",
            "- In `compact` and `standard` lanes, do not load long granular SKILL.md files when the canonical stage artifact can carry the same contract.",
            "- Expand a long granular skill only when `workflow_lane.md` or `iteration_report.md` names a concrete failed stage.",
            "- Replace repeated natural-language instruction blocks with scripts, templates, or a short input/output/gate contract.",
            "- Do not require duplicate JSON+MD artifacts unless a downstream script consumes the JSON.",
            "",
        ]
    )
    return "\n".join(lines)


def escape(text: str) -> str:
    return text.replace("|", "\\|")


def _print(text: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(text, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
