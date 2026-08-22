#!/usr/bin/env python3
"""Route a Mira project to likely modeling methods and knowledge-card queries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def powershell_script_command(script_name: str, arguments: str) -> str:
    executable = str(Path(sys.executable).resolve()).replace('"', '`"')
    script = str(SCRIPT_DIR / script_name).replace('"', '`"')
    return f'& "{executable}" "{script}" {arguments}'


@dataclass
class RouteHit:
    route_id: str
    label: str
    score: int
    matched_terms: list[str]
    query_terms: list[str]
    validation_groups: list[str]
    required_cards: list[str]


ROUTES: list[dict[str, Any]] = [
    {
        "id": "geometry_chain",
        "label": "rigid-chain geometry / curve kinematics",
        "keywords": ["rigid chain", "chain kinematics", "rigid link", "linked segment", "fixed distance", "joint spacing", "archimedean", "spiral", "arc length", "刚性链", "刚性杆", "固定间距", "铰接", "螺线", "弧长"],
        "query_terms": ["rigid-chain", "chain kinematics", "linked rigid segments", "fixed joint spacing", "archimedean spiral", "arc length"],
        "validation_groups": ["geometry_audit"],
        "required_cards": ["rigid-chain-kinematics"],
    },
    {
        "id": "collision_audit",
        "label": "collision / separating-axis audit",
        "keywords": ["collision", "separating axis", "sat", "obb", "oriented rectangle", "overlap", "碰撞", "分离轴", "矩形"],
        "query_terms": ["collision", "separating-axis", "sat", "oriented rectangle", "obb", "minimum gap"],
        "validation_groups": ["collision_audit", "feasibility_audit"],
        "required_cards": ["collision-sat"],
    },
    {
        "id": "continuous_extremum",
        "label": "continuous threshold / extremum refinement",
        "keywords": ["continuous peak", "continuous refinement", "extremum", "maximum", "minimum", "peak", "threshold", "grid scan", "coarse scan", "integer second", "bisection", "ternary", "golden", "临界", "峰值", "最大", "最小"],
        "query_terms": ["continuous-extremum", "continuous refinement", "grid scan", "bounded local search", "bisection", "ternary search", "peak"],
        "validation_groups": ["continuous_refinement"],
        "required_cards": ["continuous-extremum-search"],
    },
    {
        "id": "regression",
        "label": "regression / curve fitting",
        "keywords": ["regression", "ols", "least squares", "ridge", "lasso", "vif", "residual", "回归", "拟合"],
        "query_terms": ["regression", "ols", "least squares", "residual diagnostics", "vif", "cross-validation"],
        "validation_groups": ["regression_diagnostics", "baseline"],
        "required_cards": [],
    },
    {
        "id": "classification_logistic_svm",
        "label": "classification / logistic / SVM",
        "keywords": ["classification", "logistic", "logit", "svm", "support vector", "kernel", "auc", "roc", "confusion matrix", "分类", "支持向量"],
        "query_terms": ["logistic regression", "svm", "classification", "confusion matrix", "roc auc", "cross-validation"],
        "validation_groups": ["classification_validation", "baseline"],
        "required_cards": ["logistic-regression-classification", "svm-classification"],
    },
    {
        "id": "neural_miv",
        "label": "neural network / MIV feature screening",
        "keywords": ["neural", "bp", "miv", "mean impact value", "feature importance", "feature screening", "神经网络", "变量筛选"],
        "query_terms": ["neural network", "miv", "mean impact value", "feature importance", "ablation"],
        "validation_groups": ["feature_importance_validation", "classification_validation"],
        "required_cards": ["neural-network-miv-feature-screening"],
    },
    {
        "id": "clustering",
        "label": "clustering",
        "keywords": ["clustering", "cluster", "k-means", "kmeans", "dbscan", "silhouette", "hierarchical", "聚类"],
        "query_terms": ["clustering", "k-means", "dbscan", "silhouette", "cluster stability"],
        "validation_groups": ["cluster_validation", "baseline"],
        "required_cards": [],
    },
    {
        "id": "pca_factor",
        "label": "PCA / factor analysis",
        "keywords": ["pca", "principal component", "factor analysis", "kmo", "bartlett", "loading", "主成分", "因子分析"],
        "query_terms": ["pca", "factor analysis", "kmo", "bartlett", "variance explained", "loading"],
        "validation_groups": ["pca_factor_diagnostics"],
        "required_cards": [],
    },
    {
        "id": "ode_simulation",
        "label": "ODE / dynamic simulation",
        "keywords": ["ode", "differential equation", "solve_ivp", "rk45", "state equation", "dynamic simulation", "微分方程", "动态仿真"],
        "query_terms": ["ode", "differential equation", "step size", "solver tolerance", "initial condition"],
        "validation_groups": ["ode_validation"],
        "required_cards": [],
    },
    {
        "id": "sensitivity",
        "label": "sensitivity / robustness",
        "keywords": ["sensitivity", "robustness", "sobol", "morris", "perturb", "stability", "敏感性", "稳健性"],
        "query_terms": ["sensitivity", "robustness", "perturbation", "sobol", "morris"],
        "validation_groups": ["sensitivity"],
        "required_cards": [],
        "min_score": 4,
    },
    {
        "id": "queueing",
        "label": "queueing / discrete-event simulation",
        "keywords": ["queue", "queueing", "m/m/1", "m/m/c", "m/m/s/k", "erlang", "simpy", "waiting time", "finite capacity", "排队", "阻塞"],
        "query_terms": ["queueing", "finite capacity", "blocking probability", "little law", "warm-up", "replication"],
        "validation_groups": ["queue_validation", "finite_queue_validation"],
        "required_cards": ["mm-sk-queue-simulation"],
    },
    {
        "id": "traffic_ca",
        "label": "traffic cellular automata",
        "keywords": ["cellular automata", "traffic ca", "nasch", "traffic flow", "lane changing", "random slowdown", "元胞自动机", "交通流"],
        "query_terms": ["traffic cellular automata", "nasch", "flow density", "random slowdown", "lane changing", "multi-seed"],
        "validation_groups": ["traffic_ca_validation", "multi_seed"],
        "required_cards": ["traffic-cellular-automata-nasch"],
    },
    {
        "id": "yalmip_solver",
        "label": "YALMIP / solver-backed optimization",
        "keywords": ["yalmip", "sdpvar", "binvar", "intvar", "sdpsettings", "solver status", "gurobi", "cplex", "mosek"],
        "query_terms": ["yalmip", "sdpvar", "solver status", "sol.problem", "yalmiperror", "gap"],
        "validation_groups": ["solver_status", "feasibility_audit"],
        "required_cards": ["yalmip-optimization-modeling"],
    },
    {
        "id": "heuristic_optimization",
        "label": "heuristic / routing / metaheuristic",
        "keywords": ["heuristic", "routing", "vrp", "vrptw", "tsp", "genetic algorithm", "ga", "pso", "simulated annealing", "sa", "local search", "遗传算法", "粒子群", "模拟退火"],
        "query_terms": ["heuristic", "routing", "genetic algorithm", "pso", "simulated annealing", "baseline", "multi-seed", "convergence"],
        "validation_groups": ["baseline", "multi_seed", "convergence", "feasibility_audit"],
        "required_cards": [],
        "min_score": 6,
        "required_any": ["vrp", "vrptw", "tsp", "genetic algorithm", "ga", "pso", "simulated annealing", "sa", "local search", "遗传算法", "粒子群", "模拟退火"],
    },
    {
        "id": "multiobjective",
        "label": "multiobjective / Pareto optimization",
        "keywords": ["multiobjective", "multi-objective", "pareto", "nsga", "non-dominated", "hypervolume", "多目标", "帕累托"],
        "query_terms": ["multiobjective", "pareto", "nsga-ii", "non-dominated sorting", "hypervolume"],
        "validation_groups": ["pareto_validation", "baseline"],
        "required_cards": [],
    },
]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    context = collect_context(root, args.extra_file)
    hits = route_methods(context, args.limit, args.min_score)
    query = recommended_query(hits, args.extra_query)
    payload = {
        "generated_at": now(),
        "root": str(root),
        "routes": [asdict(hit) for hit in hits],
        "recommended_query": query,
        "command_query": ascii_command_query(query),
        "commands": commands(query),
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"routes: {len(hits)}")
    for hit in hits:
        _print(f"{hit.score:>3} {hit.route_id}: {', '.join(hit.matched_terms[:12])}")
    _print("recommended_query: " + query)
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    return 0


def route_methods(context: str, limit: int, min_score: int) -> list[RouteHit]:
    hits: list[RouteHit] = []
    for route in ROUTES:
        matched = sorted({term for term in route["keywords"] if term_present(context, term)})
        score = sum(term_weight(term) for term in matched)
        route_min_score = int(route.get("min_score", min_score))
        required_any = route.get("required_any", [])
        if required_any and not any(term in matched for term in required_any):
            continue
        if score < route_min_score:
            continue
        hits.append(
            RouteHit(
                route_id=route["id"],
                label=route["label"],
                score=score,
                matched_terms=matched,
                query_terms=route["query_terms"],
                validation_groups=route["validation_groups"],
                required_cards=route["required_cards"],
            )
        )
    hits.sort(key=lambda item: (-item.score, item.route_id))
    return hits[: max(limit, 1)]


def recommended_query(hits: list[RouteHit], extra_query: str = "") -> str:
    parts: list[str] = []
    if extra_query.strip():
        parts.append(extra_query.strip())
    for hit in hits:
        parts.extend(hit.query_terms)
        parts.extend(hit.matched_terms[:8])
    unique: list[str] = []
    seen: set[str] = set()
    for item in parts:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item.strip())
    return " ".join(unique)[:1600]


def commands(query: str) -> list[str]:
    safe_query = ascii_command_query(query).replace('"', "'")
    return [
        powershell_script_command(
            "knowledge_retrieve.py",
            rf'--root <project-root> --query "{safe_query}" --write-report planning\knowledge_injection.md --write-json planning\knowledge_injection.json',
        ),
        powershell_script_command(
            "validation_plan.py",
            r"--root <project-root> --write-report planning\validation_plan.md --write-json planning\validation_plan.json",
        ),
    ]


def ascii_command_query(query: str) -> str:
    text = query.encode("ascii", errors="ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    return text or "problem modeling validation"


def collect_context(root: Path, extras: list[str]) -> str:
    parts = [root.name]
    rels = [
        "planning/delivery_brief.md",
        "planning/problem_analysis.md",
        "planning/modeling_plan.md",
        "planning/symbol_table.md",
        "problem/problem_statement_extracted.txt",
        "results/frozen_numbers.json",
        "results/result_report.md",
        "checks/semantic_audit_report.md",
        "checks/result_quality_report.md",
        "revisions/iteration_report.md",
    ]
    rels.extend(extras or [])
    for rel_path in rels:
        path = resolve_path(root, rel_path)
        if path.exists() and path.is_file():
            parts.append(read_text(path)[:30000])
    problem_dir = root / "problem"
    if problem_dir.exists():
        for path in sorted(problem_dir.glob("*.txt"))[:6]:
            parts.append(read_text(path)[:12000])
    return "\n".join(parts)


def term_present(text: str, term: str) -> bool:
    lower = text.lower()
    needle = term.lower()
    if re.fullmatch(r"[a-z0-9+\-_/]{1,4}", needle):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lower))
    return needle in lower


def term_weight(term: str) -> int:
    if len(term) >= 12 or " " in term or "-" in term:
        return 4
    if len(term) >= 5:
        return 2
    return 1


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Method Route",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Root: `{payload['root']}`",
        f"- Routes: {len(payload['routes'])}",
        "",
        "## Recommended Knowledge Query",
        "",
        "```text",
        payload["recommended_query"] or "No strong route detected; use the problem statement and modeling plan as query.",
        "```",
        "",
        "## Command-Safe Query",
        "",
        "```text",
        payload["command_query"] or "problem modeling validation",
        "```",
        "",
        "## Routes",
        "",
        "| Score | Route | Matched terms | Validation groups | Required cards |",
        "|---:|---|---|---|---|",
    ]
    for route in payload["routes"]:
        lines.append(
            "| {score} | {route_id} | {matched} | {groups} | {cards} |".format(
                score=route["score"],
                route_id=route["route_id"],
                matched=escape(", ".join(route["matched_terms"][:16])),
                groups=escape(", ".join(route["validation_groups"])),
                cards=escape(", ".join(route["required_cards"]) or "-"),
            )
        )
    if not payload["routes"]:
        lines.append("| 0 | generic_modeling | no strong method signal | artifact_traceability | - |")
    lines.extend(["", "## Commands", ""])
    for command in payload["commands"]:
        lines.append(f"- `{command}`")
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
    parser.add_argument("--extra-file", action="append", default=[], help="Additional project file to scan")
    parser.add_argument("--extra-query", default="", help="Extra terms to force into the retrieval query")
    parser.add_argument("--limit", type=int, default=8, help="Maximum routes to report")
    parser.add_argument("--min-score", type=int, default=3, help="Minimum route score")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
