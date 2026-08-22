#!/usr/bin/env python3
"""Plan evidence-coverage guides for a Mira contest-final paper."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


METHOD_FAMILIES = {
    "exact_dp": ["held-karp", "dynamic programming", "label dp", "label-setting", "dp", "动态规划"],
    "routing_time_window": ["vrp", "vrptw", "tsptw", "time window", "routing", "route", "时间窗", "路径"],
    "heuristic_local_search": ["local search", "simulated annealing", "sa", "genetic", "ga", "heuristic", "邻域", "启发"],
    "qubo_backend": ["qubo", "ising", "kaiwu", "quantum", "sdk", "开物", "量子"],
    "validation_sensitivity": ["baseline", "sensitivity", "robust", "convergence", "multi-seed", "lower bound", "灵敏度", "收敛"],
}

FIGURE_LADDER = [
    ("data_structure", "data matrix, distribution, topology, or demand/time-window structure"),
    ("model_logic", "model or algorithm flow, state transition, variable/constraint structure"),
    ("result_evidence", "route/schedule/allocation/ranking/result comparison visual"),
    ("validation_evidence", "baseline, sensitivity, convergence, stability, bound, or audit visual"),
]


@dataclass
class Budget:
    generated_at: str
    output_level: str
    expected_subquestions: int
    method_families: list[str]
    figure_minimum: int
    figure_target_low: int
    figure_target_high: int
    table_minimum: int
    reference_minimum: int
    reference_target_low: int
    reference_target_high: int
    citation_minimum: int
    citation_binding_minimum: int
    citation_binding_target: str
    ladder_requirements: list[dict[str, str]]
    notes: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--write-report", help="Write markdown report, default planning/presentation_budget.md")
    parser.add_argument("--write-json", help="Write JSON, default planning/presentation_budget.json")
    parser.add_argument("--expected-subquestions", type=int, help="Override detected subquestion count")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    budget = build_budget(root, args.expected_subquestions)
    report = Path(args.write_report) if args.write_report else root / "planning" / "presentation_budget.md"
    data = Path(args.write_json) if args.write_json else root / "planning" / "presentation_budget.json"
    report = report if report.is_absolute() else root / report
    data = data if data.is_absolute() else root / data
    report.parent.mkdir(parents=True, exist_ok=True)
    data.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(budget), encoding="utf-8")
    data.write_text(json.dumps(asdict(budget), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(markdown(budget))
    print(f"INFO: wrote {rel(root, report)}")
    print(f"INFO: wrote {rel(root, data)}")
    return 0


def build_budget(root: Path, expected_override: int | None = None) -> Budget:
    context = collect_context(root)
    output_level = detect_output_level(root)
    expected = expected_override or detect_subquestions(context) or 1
    families = detect_method_families(context)
    multi_method = len(families) >= 3

    if output_level == "contest_final" and expected >= 4:
        figure_min = max(4, expected)
        figure_low = max(6, expected + 2)
        figure_high = max(8, figure_low + 2)
        table_min = max(4, expected)
    else:
        figure_min = max(2, expected + 1)
        figure_low = max(3, expected + 2)
        figure_high = figure_low + 2
        table_min = max(3, expected)

    citation_binding_min = max(1, len(families)) if families else 0
    if output_level == "contest_final" and expected >= 4 and multi_method:
        citation_binding_min = max(citation_binding_min, 3)
    citation_binding_target = "one row per method, parameter, data, software, or domain claim that needs a source"

    ladder = ladder_requirements(expected, families)
    notes = [
        "Generate this guide before implementation and keep it as the implementation evidence-coverage map.",
        "The numeric fields are review triggers, not quotas. Do not add pages, figures, or tables only to meet them.",
        "Do not satisfy the figure budget with decorative images; every figure needs source data or a reproducible diagram source.",
        "Do not satisfy citation needs with fabricated, unused, or generic bibliography entries; bind each source to the claim it supports.",
    ]
    if output_level == "contest_final" and expected >= 4:
        notes.append("For high-award comparison, prefer a compact evidence chain over count padding; add visuals only where they strengthen a specific claim.")

    return Budget(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        output_level=output_level,
        expected_subquestions=expected,
        method_families=families,
        figure_minimum=figure_min,
        figure_target_low=figure_low,
        figure_target_high=figure_high,
        table_minimum=table_min,
        reference_minimum=0,
        reference_target_low=0,
        reference_target_high=0,
        citation_minimum=0,
        citation_binding_minimum=citation_binding_min,
        citation_binding_target=citation_binding_target,
        ladder_requirements=ladder,
        notes=notes,
    )


def collect_context(root: Path) -> str:
    parts = []
    for rel_path in [
        "planning/delivery_brief.md",
        "planning/problem_analysis.md",
        "planning/modeling_plan.md",
        "results/result_report.md",
        "results/frozen_numbers.json",
        "results/tables/baseline_comparison.csv",
        "checks/result_quality_report.md",
        "checks/model_solver_consistency_report.md",
    ]:
        parts.append(read_text(root / rel_path)[:12000])
    return "\n".join(parts)


def detect_output_level(root: Path) -> str:
    text = read_text(root / "planning" / "delivery_brief.md")
    match = re.search(r"Output level\s*\|\s*([^|\n]+)", text, flags=re.I)
    if match:
        value = match.group(1).strip()
        if value in {"quick_draft", "reproducible_draft", "contest_final"}:
            return value
    return "contest_final" if re.search(r"MathorCup|PDF|final|提交|竞赛", text, flags=re.I) else "reproducible_draft"


def detect_subquestions(text: str) -> int:
    qn = [int(item) for item in re.findall(r"\bQ([1-9])\b", text, flags=re.I)]
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    cn = [cn_map[item] for item in re.findall(r"问题([一二三四五六七八九])", text)]
    return max(qn + cn) if qn or cn else 0


def detect_method_families(text: str) -> list[str]:
    families = []
    for family, terms in METHOD_FAMILIES.items():
        if any(contains_method_term(text, term) for term in terms):
            families.append(family)
    return families


def contains_method_term(text: str, term: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9 -]+", term):
        words = [re.escape(word) for word in term.split()]
        pattern = r"(?<![A-Za-z0-9_])" + r"\s+".join(words) + r"(?![A-Za-z0-9_])"
        return bool(re.search(pattern, text, flags=re.I))
    return term.lower() in text.lower()


def ladder_requirements(expected: int, families: list[str]) -> list[dict[str, str]]:
    rows = [{"role": role, "required": "yes", "example": example} for role, example in FIGURE_LADDER]
    if expected >= 4:
        rows.append({"role": "per_question_result", "required": "yes", "example": "at least one compact result visual/table per major subquestion"})
    if "heuristic_local_search" in families:
        rows.append({"role": "heuristic_validation", "required": "yes", "example": "convergence or multi-seed stability visual/table"})
    if "routing_time_window" in families:
        rows.append({"role": "routing_feasibility", "required": "yes", "example": "route, schedule timeline, time-window pressure, or load/coverage audit visual"})
    if "qubo_backend" in families:
        rows.append({"role": "solver_lineage", "required": "yes", "example": "model-to-solver lineage table/diagram that avoids false backend claims"})
    return rows


def markdown(budget: Budget) -> str:
    lines = [
        "# Mira Presentation Budget",
        "",
        f"- Generated: {budget.generated_at}",
        f"- Output level: `{budget.output_level}`",
        f"- Expected subquestions: {budget.expected_subquestions}",
        f"- Method families: {', '.join(budget.method_families) if budget.method_families else '-'}",
        "",
        "## Evidence Coverage Guide",
        "",
        "| Item | Review trigger | Suggested range |",
        "|---|---:|---|",
        f"| Claim-bearing figures | {budget.figure_minimum} | {budget.figure_target_low}-{budget.figure_target_high} |",
        f"| Paper tables | {budget.table_minimum} | >= {budget.table_minimum} |",
        f"| Citation-binding rows | {budget.citation_binding_minimum} | {budget.citation_binding_target} |",
        "",
        "## Evidence Ladder",
        "",
        "| Role | Required | Example |",
        "|---|---|---|",
    ]
    for row in budget.ladder_requirements:
        lines.append(f"| {row['role']} | {row['required']} | {row['example']} |")
    lines.extend(["", "## Notes", ""])
    for note in budget.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
