#!/usr/bin/env python3
"""Audit the diversity and fit of Mira paper visuals.

This gate checks the visual portfolio, not the raw number of figures. A good
contest paper should not repeat the same plot grammar for every claim, but it
also should not add exotic figures without evidence roles.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROLE_NAMES = {"define", "derive", "operate", "result", "validate", "zoom", "compare"}

TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("mechanism_diagram", ["mechanism", "geometry", "structure", "schematic", "system", "coordinate", "state", "diagram"]),
    ("process_flow", ["flow", "workflow", "algorithm", "process", "pipeline", "step", "dp", "search", "theorem"]),
    ("line_curve", ["line", "curve", "trend", "timeseries", "time_series", "trajectory", "pressure", "convergence"]),
    ("bar_matrix", ["bar", "column", "hist", "matrix", "heatmap", "grid"]),
    ("distribution", ["box", "violin", "ridgeline", "density", "distribution", "histogram", "scatter", "hexbin", "joint", "marginal", "联合分布", "边际"]),
    ("spatial_surface", ["3d", "surface", "contour", "map", "slice", "field", "point_cloud"]),
    ("network_route", ["network", "route", "path", "graph", "node", "edge", "vrp", "tsp"]),
    ("comparison_panel", ["compare", "comparison", "baseline", "ablation", "scenario", "candidate", "sensitivity", "pareto"]),
    ("table_like", ["table", "schedule", "ledger", "summary", "ranking", "audit"]),
]

ADVANCED_TYPES = {"spatial_surface", "distribution", "network_route"}


@dataclass
class VisualItem:
    artifact: str
    source: str
    role: str
    visual_type: str
    claim: str


@dataclass
class Finding:
    level: str
    axis: str
    message: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    items = collect_visuals(root)
    findings, metrics = audit(root, items)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "verdict": verdict(findings),
        "metrics": metrics,
        "items": [asdict(item) for item in items],
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        out = resolve_path(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve_path(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: {payload['verdict']}")
    print("metrics: " + json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    for item in findings:
        print(f"{item.level}: {item.axis}: {item.message}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_visuals(root: Path) -> list[VisualItem]:
    rows: list[VisualItem] = []
    rows.extend(parse_index(root, "figures/figure_index.md", "figure_index"))
    rows.extend(parse_index(root, "diagrams/diagram_index.md", "diagram_index"))
    rows.extend(parse_storyboard(root))

    seen: set[str] = set()
    out: list[VisualItem] = []
    for item in rows:
        key = normalize_artifact(item.artifact)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def parse_index(root: Path, rel_path: str, source: str) -> list[VisualItem]:
    path = root / rel_path
    text = read_text(path)
    rows: list[VisualItem] = []
    for line in text.splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in {"figure", "diagram", "artifact"}:
            continue
        artifact = first_visual_artifact(cells)
        if not artifact:
            continue
        claim = " ".join(cells)
        row_text = claim
        rows.append(
            VisualItem(
                artifact=artifact,
                source=source,
                role=infer_role(row_text),
                visual_type=infer_type(row_text),
                claim=claim,
            )
        )
    return rows


def first_visual_artifact(cells: list[str]) -> str:
    for cell in cells:
        match = re.search(r"([^`\s|]+\.(?:png|jpg|jpeg|webp|svg|pdf))\b", cell, flags=re.I)
        if match:
            return match.group(1)
    return ""


def parse_storyboard(root: Path) -> list[VisualItem]:
    path = root / "planning" / "figure_storyboard.json"
    if not path.exists():
        return []
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return []
    rows: list[VisualItem] = []
    for item in data.get("items", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        artifact = str(item.get("source_artifact") or "")
        if not artifact or artifact == "TBD" or not looks_like_visual(artifact):
            continue
        text = " ".join(str(item.get(key) or "") for key in ["role", "proposed_visual", "nearby_claim", "callout", "source_artifact"])
        rows.append(
            VisualItem(
                artifact=artifact,
                source="figure_storyboard",
                role=normalize_role(str(item.get("role") or infer_role(text))),
                visual_type=infer_type(text),
                claim=str(item.get("nearby_claim") or ""),
            )
        )
    return rows


def audit(root: Path, items: list[VisualItem]) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    type_counts = Counter(item.visual_type for item in items)
    role_counts = Counter(item.role for item in items)
    main_count = len(items)
    dominant_type, dominant_count = ("none", 0)
    if type_counts:
        dominant_type, dominant_count = type_counts.most_common(1)[0]

    if main_count == 0:
        findings.append(Finding("INFO", "visual_portfolio", "no indexed visuals found; portfolio diversity cannot be assessed"))
    elif main_count >= 5 and dominant_count / main_count >= 0.75:
        findings.append(
            Finding(
                "WARN",
                "visual_type_diversity",
                f"{dominant_count}/{main_count} indexed visuals use `{dominant_type}`; consider adding a different evidence form only where the data/model need it",
            )
        )

    if main_count >= 4 and len(type_counts) < 3:
        findings.append(
            Finding(
                "WARN",
                "visual_type_diversity",
                f"only {len(type_counts)} visual type(s) detected across {main_count} indexed visuals; mix mechanism/process/result/validation forms when claims differ",
            )
        )

    if main_count >= 4 and len(role_counts) < 3:
        findings.append(
            Finding(
                "WARN",
                "visual_role_diversity",
                f"only {len(role_counts)} visual role(s) detected; record and use roles such as define, operate, result, validate, zoom, and compare",
            )
        )

    if role_counts.get("result", 0) >= 3 and role_counts.get("validate", 0) == 0:
        findings.append(Finding("WARN", "validation_visual_gap", "result visuals exist but no validation visual role is detected"))

    if role_counts.get("operate", 0) == 0 and context_has(root, ["algorithm", "search", "solver", "dynamic programming", "simulated annealing", "ga", "pso"]):
        findings.append(Finding("WARN", "operation_visual_gap", "model/code context mentions nontrivial algorithms but no operation/process visual is indexed"))

    if role_counts.get("define", 0) == 0 and context_has(root, ["geometry", "coordinate", "state", "network", "route", "collision", "spatial"]):
        findings.append(Finding("WARN", "definition_visual_gap", "context mentions geometry/state/network structure but no definition visual is indexed"))

    advanced_count = sum(count for typ, count in type_counts.items() if typ in ADVANCED_TYPES)
    if advanced_count >= 2 and role_counts.get("validate", 0) + role_counts.get("compare", 0) == 0:
        findings.append(
            Finding(
                "WARN",
                "advanced_visual_fit",
                "advanced visual types are present but no validate/compare role is detected; ensure they are not decorative",
            )
        )

    metrics = {
        "indexed_visuals": main_count,
        "visual_types": dict(sorted(type_counts.items())),
        "visual_roles": dict(sorted(role_counts.items())),
        "dominant_type": dominant_type,
        "dominant_type_share": round(dominant_count / main_count, 3) if main_count else 0.0,
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return findings, metrics


def infer_role(text: str) -> str:
    lower = text.lower()
    for role in ROLE_NAMES:
        if re.search(rf"\b{role}\b", lower):
            return role
    if has_any(lower, ["geometry", "coordinate", "structure", "state", "schema", "mechanism"]):
        return "define"
    if has_any(lower, ["formula", "constraint", "relation", "derive", "derivation"]):
        return "derive"
    if has_any(lower, ["flow", "algorithm", "search", "solver", "step", "process", "pipeline"]):
        return "operate"
    if has_any(lower, ["baseline", "sensitivity", "residual", "audit", "feasible", "validation", "robust"]):
        return "validate"
    if has_any(lower, ["zoom", "detail", "critical", "boundary", "peak", "local"]):
        return "zoom"
    if has_any(lower, ["compare", "comparison", "candidate", "scenario", "ablation", "before", "after"]):
        return "compare"
    return "result"


def infer_type(text: str) -> str:
    lower = text.lower()
    scores: list[tuple[int, str]] = []
    for visual_type, terms in TYPE_PATTERNS:
        score = sum(1 for term in terms if term.lower() in lower)
        if score:
            scores.append((score, visual_type))
    if scores:
        scores.sort(key=lambda item: (-item[0], item[1]))
        return scores[0][1]
    if looks_like_visual(text):
        name = Path(text.replace("\\", "/").split()[0]).stem.lower()
        if any(term in name for term in ["fig", "plot", "curve"]):
            return "line_curve"
    return "result_visual"


def normalize_role(value: str) -> str:
    value = value.strip().lower()
    return value if value in ROLE_NAMES else infer_role(value)


def looks_like_visual(value: str) -> bool:
    return bool(re.search(r"\.(?:png|jpg|jpeg|webp|svg|pdf)\b", value, flags=re.I))


def normalize_artifact(value: str) -> str:
    value = value.strip().replace("\\", "/")
    if not value or value.upper() == "TBD":
        return ""
    return value.lower()


def context_has(root: Path, terms: list[str]) -> bool:
    text = "\n".join(
        read_text(root / rel)[:20000]
        for rel in [
            "planning/problem_analysis.md",
            "planning/modeling_plan.md",
            "results/result_report.md",
            "planning/result_ledger.md",
            "paper/main.tex",
        ]
    ).lower()
    return has_any(text, terms)


def has_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Figure Portfolio Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Visual Items", "", "| Artifact | Source | Role | Type | Claim |", "|---|---|---|---|---|"])
    for item in payload["items"]:
        lines.append(
            f"| `{escape(item['artifact'])}` | {item['source']} | `{item['role']}` | `{item['visual_type']}` | {escape(item['claim'])} |"
        )
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    lines.append("")
    return "\n".join(lines)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
