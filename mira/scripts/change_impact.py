#!/usr/bin/env python3
"""Suggest targeted Mira rechecks for explicitly supplied changed paths."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import PurePosixPath


STAGES = ("analysis", "modeling", "implementation", "paper")
PATH_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("analysis", ("problem/**", "data_raw/**", "planning/problem_*", "planning/delivery_brief.md")),
    ("modeling", ("planning/model*", "planning/validation*", "planning/symbol*", "planning/assumption*")),
    ("implementation", ("code/**", "data_clean/**", "results/**", "figures/**", "diagrams/**", "planning/result_ledger.*")),
    ("paper", ("paper/**", "output/**", "planning/submission_requirements.json", "planning/delivery_manifest.json")),
)
CHECKS: dict[str, tuple[str, ...]] = {
    "analysis": ("problem interpretation", "attachment fields and units"),
    "modeling": ("assumptions and derivation", "baseline and validation plan"),
    "implementation": ("affected code and results", "solver/result/figure consistency"),
    "paper": ("affected claims and figures", "final artifact consistency"),
}


def path_matches(relative: str, pattern: str) -> bool:
    relative = relative.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/").lstrip("./")
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return relative == prefix or relative.startswith(prefix + "/")
    return fnmatch.fnmatchcase(relative, pattern)


def normalize_path(value: str) -> str:
    relative = str(value).strip().replace("\\", "/")
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or ":" in path.parts[0] or ".." in path.parts:
        raise ValueError(f"changed path must be project-relative: {value}")
    return path.as_posix().lstrip("./")


def stage_for_path(relative: str) -> str | None:
    for stage, patterns in PATH_RULES:
        if any(path_matches(relative, pattern) for pattern in patterns):
            return stage
    return None


def advise_changes(changed_paths: list[str]) -> dict[str, object]:
    suggestions = []
    stages: list[str] = []
    checks: list[str] = []
    for value in changed_paths:
        relative = normalize_path(value)
        stage = stage_for_path(relative)
        suggestions.append({"path": relative, "stage": stage or "manual_review"})
        if stage and stage not in stages:
            stages.append(stage)
            checks.extend(item for item in CHECKS[stage] if item not in checks)
    stages.sort(key=STAGES.index)
    return {
        "schema_version": 1,
        "mode": "advice_only",
        "changed": suggestions,
        "earliest_stage": stages[0] if stages else None,
        "suggested_stages": stages,
        "recommended_checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Compatibility option; no project files are read")
    parser.add_argument("--changed", action="append", required=True, help="Changed project-relative path; repeat as needed")
    parser.add_argument("--json", action="store_true", help="Print JSON advice")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = advise_changes(args.changed)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("MODE: ADVICE_ONLY")
        print(f"earliest_stage: {payload['earliest_stage'] or '-'}")
        print(f"suggested_stages: {', '.join(payload['suggested_stages']) or 'manual review'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
