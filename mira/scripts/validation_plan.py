#!/usr/bin/env python3
"""Turn routed Mira knowledge cards into concrete validation-plan items."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ValidationItem:
    source: str
    route_or_card: str
    validation_group: str
    target_phase: str
    expected_artifacts: list[str]
    evidence_paths: list[str]
    missing_terms: list[str]
    status: str


VALIDATION_GROUPS: dict[str, dict[str, Any]] = {
    "feasibility_audit": {
        "phase": "implementation",
        "paths": ["results/audits", "checks", "results/tables"],
        "terms": ["feasible", "violation", "constraint", "capacity", "audit"],
    },
    "baseline": {
        "phase": "implementation",
        "paths": ["results/tables/baseline_comparison.csv", "results", "checks/result_quality_report.md"],
        "terms": ["baseline", "comparison", "alternative", "best"],
    },
    "decomposition": {
        "phase": "implementation",
        "paths": ["results", "checks/result_quality_report.md"],
        "terms": ["component", "ratio", "decomposition", "objective"],
    },
    "multi_seed": {
        "phase": "implementation",
        "paths": ["results", "checks/result_quality_report.md"],
        "terms": ["seed", "multi", "mean", "std", "stability"],
    },
    "convergence": {
        "phase": "implementation",
        "paths": ["results/tables", "results/logs", "checks/result_quality_report.md"],
        "terms": ["history", "iteration", "convergence", "best"],
    },
    "sensitivity": {
        "phase": "implementation",
        "paths": ["results/tables", "checks/result_quality_report.md"],
        "terms": ["sensitivity", "perturb", "robustness", "alpha", "beta"],
    },
    "regression_diagnostics": {
        "phase": "implementation",
        "paths": ["results/tables", "checks"],
        "terms": ["residual", "vif", "r2", "cross-validation", "holdout"],
    },
    "cluster_validation": {
        "phase": "implementation",
        "paths": ["results/tables", "figures", "checks"],
        "terms": ["silhouette", "elbow", "cluster", "stability"],
    },
    "pca_factor_diagnostics": {
        "phase": "implementation",
        "paths": ["results/tables", "checks"],
        "terms": ["kmo", "bartlett", "eigenvalue", "loading", "variance"],
    },
    "ode_validation": {
        "phase": "implementation",
        "paths": ["results", "checks", "code"],
        "terms": ["step size", "tolerance", "rk45", "solve_ivp", "initial condition"],
    },
    "pareto_validation": {
        "phase": "implementation",
        "paths": ["results", "figures", "checks"],
        "terms": ["pareto", "non-dominated", "front", "crowding", "hypervolume"],
    },
    "queue_validation": {
        "phase": "implementation",
        "paths": ["results", "checks"],
        "terms": ["little", "erlang", "utilization", "waiting time", "service level"],
    },
    "finite_queue_validation": {
        "phase": "implementation",
        "paths": ["results", "checks"],
        "terms": ["blocking", "loss probability", "finite capacity", "queue length"],
    },
    "solver_status": {
        "phase": "implementation",
        "paths": ["results/logs", "checks/model_solver_consistency_report.md", "code"],
        "terms": ["sol.problem", "solver status", "gap", "infeasible", "unbounded"],
    },
    "geometry_audit": {
        "phase": "implementation",
        "paths": ["results/audits", "results/tables", "code", "planning/modeling_plan.md"],
        "terms": ["arc length", "rigid", "chain", "handle", "distance", "spiral", "max_distance_error"],
    },
    "collision_audit": {
        "phase": "implementation",
        "paths": ["results/audits", "results/tables", "code", "planning/modeling_plan.md"],
        "terms": ["collision", "separating axis", "sat", "overlap", "min_collision_gap"],
    },
    "continuous_refinement": {
        "phase": "implementation",
        "paths": ["results/audits", "results/tables", "results/logs", "paper/main_final.tex"],
        "terms": ["continuous", "refined", "peak", "bisection", "ternary", "golden", "continuous_peak"],
    },
    "classification_validation": {
        "phase": "implementation",
        "paths": ["results/tables", "checks", "figures"],
        "terms": ["confusion matrix", "accuracy", "precision", "recall", "f1", "roc", "auc"],
    },
    "feature_importance_validation": {
        "phase": "implementation",
        "paths": ["results/tables", "checks", "figures"],
        "terms": ["miv", "mean impact", "feature importance", "permutation", "ablation"],
    },
    "traffic_ca_validation": {
        "phase": "implementation",
        "paths": ["results/tables", "results/logs", "figures"],
        "terms": ["vehicle count", "flow", "density", "average speed", "lane change", "random slowdown"],
    },
}


CARD_GROUP_RULES = [
    (["rigid-chain", "chain-kinematics", "rigid-segment", "linked-segment", "fixed-distance", "spiral"], ["geometry_audit"]),
    (["collision", "sat", "separating-axis", "oriented-rectangle"], ["collision_audit"]),
    (["continuous-extremum", "continuous", "extremum", "peak"], ["continuous_refinement"]),
    (["logistic", "svm", "classification"], ["classification_validation", "baseline"]),
    (["miv", "feature", "neural"], ["feature_importance_validation"]),
    (["traffic", "nasch", "cellular"], ["traffic_ca_validation", "multi_seed"]),
    (["queue", "m/m/s/k", "finite-capacity"], ["queue_validation", "finite_queue_validation"]),
    (["yalmip", "solver"], ["solver_status", "feasibility_audit"]),
    (["regression", "ols", "ridge", "lasso"], ["regression_diagnostics", "baseline"]),
    (["pca", "factor"], ["pca_factor_diagnostics"]),
    (["clustering", "cluster"], ["cluster_validation", "baseline"]),
    (["ode", "differential"], ["ode_validation"]),
    (["pareto", "nsga", "multiobjective"], ["pareto_validation", "baseline"]),
    (["heuristic", "routing", "pso", "genetic", "annealing"], ["baseline", "multi_seed", "convergence", "feasibility_audit"]),
]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    method_route = load_json(resolve_existing(root, args.method_json, ["planning/method_route.json"]))
    knowledge = load_json(resolve_existing(root, args.knowledge_json, ["planning/knowledge_injection.json"]))
    items = build_items(root, method_route, knowledge)
    payload = {
        "generated_at": now(),
        "root": str(root),
        "method_route_json": str(resolve_existing(root, args.method_json, ["planning/method_route.json"]) or ""),
        "knowledge_json": str(resolve_existing(root, args.knowledge_json, ["planning/knowledge_injection.json"]) or ""),
        "verdict": verdict(items),
        "items": [asdict(item) for item in items],
        "summary": summarize(items),
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        preserved_section = ""
        if path.exists():
            preserved_section = extract_markdown_section(
                read_text(path), "Discriminating Tests"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            markdown({**payload, "discriminating_tests_section": preserved_section}),
            encoding="utf-8",
        )
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"validation_items: {len(items)}")
    _print(f"verdict: {payload['verdict']}")
    for item in items:
        _print(f"{item.status}: {item.validation_group} <- {item.route_or_card}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    return 0


def build_items(root: Path, method_route: dict[str, Any], knowledge: dict[str, Any]) -> list[ValidationItem]:
    specs: list[tuple[str, str, str]] = []
    required_card_needles: list[str] = []
    for route in method_route.get("routes", []) if isinstance(method_route, dict) else []:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or route.get("id") or "route")
        for group in route.get("validation_groups", []):
            specs.append(("method_route", route_id, str(group)))
        required_card_needles.extend(str(item) for item in route.get("required_cards", []) if str(item).strip())
    for hit in knowledge.get("hits", []) if isinstance(knowledge, dict) else []:
        if not isinstance(hit, dict):
            continue
        if required_card_needles and not card_matches_required(hit, required_card_needles):
            continue
        card_id = card_identifier(hit)
        for group in card_validation_groups(hit):
            specs.append(("knowledge_card", card_id, group))

    if not specs:
        specs.append(("generic", "artifact_traceability", "feasibility_audit"))

    out: list[ValidationItem] = []
    seen: set[tuple[str, str, str]] = set()
    for source, route_or_card, group in specs:
        key = (source, route_or_card, group)
        if key in seen or group not in VALIDATION_GROUPS:
            continue
        seen.add(key)
        out.append(make_item(root, source, route_or_card, group))
    return out


def make_item(root: Path, source: str, route_or_card: str, group: str) -> ValidationItem:
    spec = VALIDATION_GROUPS[group]
    expected = [str(path) for path in spec["paths"]]
    evidence_paths = evidence_for(root, expected, spec["terms"])
    evidence_text = "\n".join(read_text(resolve_path(root, path))[:20000] for path in evidence_paths)
    missing_terms = [term for term in spec["terms"] if term.lower() not in evidence_text.lower()]
    status = "present" if evidence_paths and len(missing_terms) < len(spec["terms"]) else "missing"
    return ValidationItem(
        source=source,
        route_or_card=route_or_card,
        validation_group=group,
        target_phase=str(spec["phase"]),
        expected_artifacts=expected,
        evidence_paths=evidence_paths,
        missing_terms=missing_terms,
        status=status,
    )


def evidence_for(root: Path, expected: list[str], terms: list[str]) -> list[str]:
    candidates: list[Path] = []
    for item in expected:
        path = resolve_path(root, item)
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(
                child
                for child in sorted(path.rglob("*"))
                if child.is_file() and child.suffix.lower() in {".md", ".txt", ".json", ".csv", ".py", ".tex", ".typ"}
            )
    out: list[str] = []
    for path in candidates:
        text = read_text(path)[:50000].lower()
        if any(term.lower() in text for term in terms):
            out.append(rel(root, path))
    return out[:12]


def card_validation_groups(hit: dict[str, Any]) -> list[str]:
    text = "\n".join(
        [
            str(hit.get("path", "")),
            str(hit.get("title", "")),
        ]
    ).lower()
    groups: list[str] = []
    for needles, selected in CARD_GROUP_RULES:
        if text_has_any(text, needles):
            groups.extend(selected)
    if not groups:
        groups.append("feasibility_audit")
    return unique(groups)


def text_has_any(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    for needle in needles:
        item = needle.lower()
        if not item:
            continue
        if re.fullmatch(r"[a-z0-9]{1,3}", item):
            if re.search(rf"(?<![a-z0-9]){re.escape(item)}(?![a-z0-9])", lower):
                return True
        elif re.fullmatch(r"[a-z0-9][a-z0-9+\-_/ ]+", item):
            if re.search(rf"(?<![a-z0-9]){re.escape(item)}(?![a-z0-9])", lower):
                return True
        elif item in lower:
            return True
    return False


def card_identifier(hit: dict[str, Any]) -> str:
    path = str(hit.get("path") or "")
    title = str(hit.get("title") or "")
    return Path(path).name or title or "card"


def card_matches_required(hit: dict[str, Any], required_card_needles: list[str]) -> bool:
    text = "\n".join(
        [
            str(hit.get("path", "")),
            str(hit.get("title", "")),
            " ".join(str(item) for item in hit.get("matched_terms", []) if isinstance(hit.get("matched_terms", []), list)),
        ]
    ).lower()
    return any(needle.lower() in text for needle in required_card_needles)


def verdict(items: list[ValidationItem]) -> str:
    if not items:
        return "NO_ROUTE"
    if all(item.status == "present" for item in items):
        return "READY"
    return "HAS_MISSING_ITEMS"


def summarize(items: list[ValidationItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Validation Plan",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Items",
        "",
        "| Status | Source | Route/Card | Validation group | Target phase | Evidence | Missing terms |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            "| {status} | {source} | {route_or_card} | {group} | {phase} | {evidence} | {missing} |".format(
                status=item["status"],
                source=item["source"],
                route_or_card=escape(item["route_or_card"]),
                group=item["validation_group"],
                phase=item["target_phase"],
                evidence=escape(", ".join(item["evidence_paths"]) or "-"),
                missing=escape(", ".join(item["missing_terms"]) or "-"),
            )
        )
    lines.extend(
        [
            "",
            "## Use",
            "",
            "- `missing` items must be implemented, waived, or downgraded before contest-final delivery.",
            "- This plan is generated before or during implementation, so missing items are not by themselves a script failure.",
            "- Final blocking remains with `knowledge_application_audit.py`, `result_confidence.py`, and the delivery checks.",
            "",
        ]
    )
    preserved = str(payload.get("discriminating_tests_section") or "").strip()
    if preserved:
        lines.extend([preserved, ""])
    else:
        lines.extend(
            [
                "## Discriminating Tests",
                "",
                "Fill this table from the Candidate Model Portfolio. Use the cheapest decisive screen first (analytic, complexity, feasibility, tiny case, downsampling, or an existing baseline), set a time/run cap before computation, and stop once the route decision is supported.",
                "",
                "| Test ID | Question | Candidates compared | Test design | Observable | Route-change rule | Falsifier | Budget cap | Evidence path | Status |",
                "|---|---|---|---|---|---|---|---|---|---|",
                "",
            ]
        )
    return "\n".join(lines)


def extract_markdown_section(text: str, title: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(title)}\s*$.*?(?=^##\s+|\Z)",
        flags=re.M | re.S | re.I,
    )
    match = pattern.search(text)
    return match.group(0).rstrip() if match else ""


def resolve_existing(root: Path, explicit: str | None, defaults: list[str]) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(resolve_path(root, explicit))
    candidates.extend(resolve_path(root, item) for item in defaults)
    for path in candidates:
        if path.exists():
            return path
    return None


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    parser.add_argument("--method-json", help="method_route JSON path")
    parser.add_argument("--knowledge-json", help="knowledge_injection JSON path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
