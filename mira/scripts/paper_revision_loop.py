#!/usr/bin/env python3
"""Run Mira 0.4.5's paper revision loop on a contest-final draft.

The loop audits the current paper, builds a revision plan, writes a repaired
copy by default, audits the repaired copy, and reports metric deltas. It does
not overwrite the original paper unless `--overwrite` is explicitly set.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    name: str
    command: list[str]
    returncode: int


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper source, default inferred by repair_paper_text.py and visual_reasoning_audit.py")
    parser.add_argument("--repaired-paper", default="paper/main_final_repaired.tex", help="Repaired copy path")
    parser.add_argument("--overwrite", action="store_true", help="Repair the source paper in place")
    parser.add_argument("--write-report", default="revisions/paper_revision_loop_report.md")
    parser.add_argument("--write-json", default="revisions/paper_revision_loop_report.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    scripts = Path(__file__).resolve().parent
    repaired = resolve(root, args.repaired_paper)
    commands: list[CommandResult] = []

    original_audit_json = root / "checks" / "visual_reasoning_audit_report.json"
    original_audit_report = root / "checks" / "visual_reasoning_audit_report.md"
    repaired_audit_json = root / "checks" / "visual_reasoning_audit_repaired_report.json"
    repaired_audit_report = root / "checks" / "visual_reasoning_audit_repaired_report.md"

    original_audit_cmd = [
        sys.executable,
        str(scripts / "visual_reasoning_audit.py"),
        "--root",
        str(root),
        "--write-report",
        str(original_audit_report),
        "--write-json",
        str(original_audit_json),
    ]
    if args.paper:
        original_audit_cmd.extend(["--paper", args.paper])
    commands.append(run("audit_original", original_audit_cmd, allow_fail=True))

    commands.append(
        run(
            "figure_storyboard",
            [
                sys.executable,
                str(scripts / "figure_storyboard.py"),
                "--root",
                str(root),
                "--write-report",
                "planning/figure_storyboard.md",
                "--write-json",
                "planning/figure_storyboard.json",
            ],
            allow_fail=False,
        )
    )
    commands.append(
        run(
            "paper_revision_plan",
            [
                sys.executable,
                str(scripts / "paper_revision_plan.py"),
                "--root",
                str(root),
                "--audit-json",
                str(original_audit_json),
                "--storyboard-json",
                "planning/figure_storyboard.json",
                "--write-report",
                "revisions/paper_revision_plan.md",
                "--write-json",
                "revisions/paper_revision_plan.json",
            ],
            allow_fail=False,
        )
    )

    repair_cmd = [
        sys.executable,
        str(scripts / "repair_paper_text.py"),
        "--root",
        str(root),
        "--write-report",
        "revisions/paper_repair_report.md",
        "--write-json",
        "revisions/paper_repair_report.json",
    ]
    if args.paper:
        repair_cmd.extend(["--paper", args.paper])
    if args.overwrite:
        repair_cmd.append("--overwrite")
        repaired_for_audit = args.paper or str(infer_paper(root))
    else:
        repair_cmd.extend(["--out", str(repaired)])
        repaired_for_audit = str(repaired)
    commands.append(run("repair_paper_text", repair_cmd, allow_fail=False))

    repaired_audit_cmd = [
        sys.executable,
        str(scripts / "visual_reasoning_audit.py"),
        "--root",
        str(root),
        "--paper",
        repaired_for_audit,
        "--write-report",
        str(repaired_audit_report),
        "--write-json",
        str(repaired_audit_json),
    ]
    commands.append(run("audit_repaired", repaired_audit_cmd, allow_fail=True))

    before = read_json(original_audit_json)
    after = read_json(repaired_audit_json)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "original_audit": rel(root, original_audit_json),
        "repaired_audit": rel(root, repaired_audit_json),
        "repaired_paper": rel(root, resolve(root, repaired_for_audit)),
        "commands": [
            {
                "name": item.name,
                "returncode": item.returncode,
                "command": item.command,
            }
            for item in commands
        ],
        "before": summarize_audit(before),
        "after": summarize_audit(after),
        "delta": audit_delta(before, after),
        "verdict": loop_verdict(commands, before, after),
        "notes": [
            "A PASS repaired audit means writing-level visual reasoning issues were reduced on the repaired copy.",
            "Manual storyboard gaps still require real visual/table artifacts before final submission.",
            "Review the repaired copy before replacing the original paper.",
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
    return 0 if payload["verdict"] != "FAIL" else 1


def run(name: str, command: list[str], allow_fail: bool) -> CommandResult:
    completed = subprocess.run(command, text=True)
    if completed.returncode != 0 and not allow_fail:
        raise SystemExit(f"{name} failed with exit code {completed.returncode}")
    return CommandResult(name=name, command=command, returncode=completed.returncode)


def summarize_audit(data: dict[str, Any]) -> dict[str, Any]:
    metrics = data.get("metrics", {})
    return {
        "verdict": data.get("verdict", "UNKNOWN"),
        "warnings": metrics.get("warnings"),
        "failures": metrics.get("failures"),
        "figure_pre_intro": metrics.get("figure_pre_intro"),
        "figure_post_interpretation": metrics.get("figure_post_interpretation"),
        "referenced_figure_labels": metrics.get("referenced_figure_labels"),
        "abstract_bold_markers": metrics.get("abstract_bold_markers"),
        "final_formula_markers": metrics.get("final_formula_markers"),
    }


def audit_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b = before.get("metrics", {})
    a = after.get("metrics", {})
    keys = [
        "warnings",
        "failures",
        "figure_pre_intro",
        "figure_post_interpretation",
        "referenced_figure_labels",
        "abstract_bold_markers",
        "final_formula_markers",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if isinstance(b.get(key), (int, float)) and isinstance(a.get(key), (int, float)):
            out[key] = a[key] - b[key]
    return out


def loop_verdict(commands: list[CommandResult], before: dict[str, Any], after: dict[str, Any]) -> str:
    hard_fail = any(item.returncode != 0 for item in commands if item.name not in {"audit_original", "audit_repaired"})
    if hard_fail:
        return "FAIL"
    if after.get("verdict") == "PASS":
        return "PASS"
    if after.get("verdict") != before.get("verdict"):
        return "IMPROVED"
    if audit_delta(before, after).get("warnings", 0) < 0:
        return "IMPROVED"
    return "NEEDS_REVIEW"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Paper Revision Loop",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Repaired paper: `{payload['repaired_paper']}`",
        "",
        "## Audit Summary",
        "",
        "| Stage | Verdict | Warnings | Failures | Pre-intro | Post-interpretation | Referenced figures | Abstract bold | Final formulas |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for stage in ["before", "after"]:
        item = payload[stage]
        lines.append(
            "| {stage} | {verdict} | {warnings} | {failures} | {pre} | {post} | {refs} | {bold} | {formula} |".format(
                stage=stage,
                verdict=item.get("verdict"),
                warnings=item.get("warnings"),
                failures=item.get("failures"),
                pre=item.get("figure_pre_intro"),
                post=item.get("figure_post_interpretation"),
                refs=item.get("referenced_figure_labels"),
                bold=item.get("abstract_bold_markers"),
                formula=item.get("final_formula_markers"),
            )
        )
    lines.extend(["", "## Delta", "", "| Metric | After - Before |", "|---|---:|"])
    for key, value in payload["delta"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Commands", "", "| Name | Exit |", "|---|---:|"])
    for command in payload["commands"]:
        lines.append(f"| {command['name']} | {command['returncode']} |")
    lines.extend(["", "## Notes", ""])
    for note in payload["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def infer_paper(root: Path) -> Path:
    for rel_path in ["paper/main_final.tex", "paper/main.tex", "paper/main_final_checked.tex"]:
        candidate = root / rel_path
        if candidate.exists():
            return candidate
    return root / "paper" / "main_final.tex"


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


if __name__ == "__main__":
    raise SystemExit(main())

