#!/usr/bin/env python3
"""Concise command profiles for Mira's four public stages.

Legacy phase and gate names are accepted only as input aliases. Specialized
diagnostics remain inside the contest-final pipeline instead of becoming
additional workflow stages.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from stage_gate import normalize_stage


SKILL_SCRIPTS: Final[Path] = Path(__file__).resolve().parent


def cmd(script: str, args: str) -> str:
    script_path = SKILL_SCRIPTS / script
    return f'"{sys.executable}" "{script_path}" {args}'.strip()


CONTEST_FINAL_PIPELINE_COMMAND: Final[str] = cmd(
    "contest_final_pipeline.py",
    "--root <project-root>",
)

BENCHMARK_REGRESSION_COMMAND: Final[str] = cmd(
    "benchmark_regression.py",
    "--root <project-root> --benchmark auto --write-report checks\\benchmark_regression_report.md --write-json checks\\benchmark_regression_report.json",
)


PUBLIC_STAGE_COMMANDS: Final[dict[str, list[str]]] = {
    "analysis": [
        cmd("attachment_mapping_guard.py", "--root <project-root> --output-level <output-level> --write-report checks\\attachment_mapping_report.md --write-json planning\\attachment_mapping.json --write-md planning\\attachment_mapping.md"),
        cmd("data_quality_gate.py", "--root <project-root> --output-level <output-level> --write-template planning\\data_quality_template.json --write-report checks\\data_quality_report.md --write-json checks\\data_quality_report.json"),
        cmd("stage_gate.py", "--root <project-root> --stage analysis --output-level <output-level>"),
    ],
    "modeling": [
        cmd("method_route.py", "--root <project-root> --write-report planning\\method_route.md --write-json planning\\method_route.json"),
        cmd("validation_plan.py", "--root <project-root> --write-report planning\\validation_plan.md --write-json planning\\validation_plan.json"),
        cmd("reasoning_core_gate.py", "--root <project-root> --stage modeling --output-level <output-level> --write-report checks\\reasoning_core_report.md --write-json checks\\reasoning_core_report.json"),
        cmd("stage_gate.py", "--root <project-root> --stage modeling --output-level <output-level>"),
    ],
    "implementation": [
        cmd("result_quality.py", "--root <project-root> --output-level <output-level> --write-report checks\\result_quality_report.md --write-json checks\\result_quality_report.json"),
        cmd("model_solver_consistency.py", "--root <project-root> --write-report checks\\model_solver_consistency_report.md --write-json checks\\model_solver_consistency_report.json"),
        cmd("visual_render_gate.py", "--root <project-root> --write-report checks\\visual_render_report.md --write-json checks\\visual_render_report.json"),
        cmd("stage_gate.py", "--root <project-root> --stage implementation --output-level <output-level>"),
    ],
    "paper": [
        cmd("paper_strategy_gate.py", "--root <project-root> --stage paper --output-level <output-level> --write-report checks\\paper_strategy_report.md --write-json checks\\paper_strategy_report.json"),
        cmd("paper_consistency.py", "--root <project-root> --ledger-json planning\\result_ledger.json --write-report checks\\paper_consistency_report.md --write-json checks\\paper_consistency_report.json"),
        cmd("stage_gate.py", "--root <project-root> --stage paper --output-level <output-level>"),
    ],
}


def commands_for_stage(stage: str, output_level: str = "reproducible_draft") -> list[str]:
    """Return the concise command profile for one normalized public stage."""
    normalized = normalize_stage(stage)
    commands = list(PUBLIC_STAGE_COMMANDS[normalized])
    if normalized == "paper" and output_level.strip().lower() == "contest_final":
        commands.insert(-1, CONTEST_FINAL_PIPELINE_COMMAND)
    return render_commands(commands, output_level=output_level)


def commands_for_phase(
    phase: str,
    output_level: str = "reproducible_draft",
    gate_tier: str = "auto",
) -> list[str]:
    """Compatibility wrapper for callers still passing a phase or gate alias."""
    del gate_tier
    if str(phase).strip().lower() == "benchmark":
        return render_commands([BENCHMARK_REGRESSION_COMMAND], output_level=output_level)
    return commands_for_stage(normalize_stage(phase), output_level=output_level)


def verify_commands(output_level: str = "reproducible_draft", gate_tier: str = "auto") -> list[str]:
    """Compatibility wrapper for callers that previously requested verify."""
    return commands_for_phase("paper", output_level=output_level, gate_tier=gate_tier)


def render_commands(commands: list[str], output_level: str) -> list[str]:
    return [command.replace("<output-level>", output_level) for command in commands]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", help="analysis, modeling, implementation, or paper")
    parser.add_argument("--phase", help="Legacy alias for --stage")
    parser.add_argument("--output-level", default="reproducible_draft", help="quick_draft, reproducible_draft, or contest_final")
    parser.add_argument("--gate-tier", default="auto", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()
    requested = args.stage or args.phase or "analysis"
    try:
        stage = normalize_stage(requested)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    commands = commands_for_phase(requested, output_level=args.output_level)
    if args.json:
        print(json.dumps({"stage": stage, "phase": stage, "requested": requested, "commands": commands}, ensure_ascii=False, indent=2))
    else:
        print(f"stage: {stage}")
        for command in commands:
            print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
