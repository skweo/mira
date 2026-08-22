#!/usr/bin/env python3
"""Audit statistical evidence without forcing inference onto deterministic work."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


MODES = {"deterministic", "descriptive", "inferential", "simulation"}


@dataclass
class Finding:
    level: str
    code: str
    analysis_id: str
    message: str
    evidence: list[str]


def finding(level: str, code: str, analysis_id: str, message: str, *evidence: str) -> Finding:
    return Finding(level, code, analysis_id or "contract", message, [item for item in evidence if item])


def substantive(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (dict, list)):
        return bool(value)
    return str(value).strip().lower() not in {"unknown", "undeclared", "tbd"}


def not_applicable(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"not_applicable", "n/a", "na"}


def evaluate_contract(root: Path, contract: dict[str, Any], paper_text: str = "") -> dict[str, Any]:
    root = root.resolve()
    findings: list[Finding] = []
    analyses = contract.get("analyses")
    if contract.get("schema_version") != 1:
        findings.append(finding("FAIL", "schema_version", "contract", "schema_version must be 1"))
    if not isinstance(analyses, list):
        findings.append(finding("FAIL", "analyses_type", "contract", "analyses must be a list"))
        analyses = []
    if not analyses:
        findings.append(finding("FAIL", "missing_analyses", "contract", "at least one claim-bearing analysis must be declared"))

    seen: set[str] = set()
    claim_ids: set[str] = set()
    for row in analyses:
        if not isinstance(row, dict):
            findings.append(finding("FAIL", "analysis_type", "contract", "analysis record must be an object"))
            continue
        analysis_id = str(row.get("analysis_id") or "")
        claim_id = str(row.get("claim_id") or "")
        mode = str(row.get("analysis_mode") or "").lower()
        if not analysis_id:
            findings.append(finding("FAIL", "analysis_id", "contract", "analysis_id is required"))
            analysis_id = "unnamed"
        elif analysis_id in seen:
            findings.append(finding("FAIL", "duplicate_analysis", analysis_id, "analysis_id must be unique"))
        seen.add(analysis_id)
        if not claim_id:
            findings.append(finding("FAIL", "claim_id", analysis_id, "claim_id is required"))
        claim_ids.add(claim_id)
        if mode not in MODES:
            findings.append(finding("FAIL", "analysis_mode", analysis_id, f"unsupported analysis_mode: {mode or 'missing'}"))
            continue
        for key in ("analysis_unit", "n_definition"):
            if not substantive(row.get(key)):
                findings.append(finding("FAIL", key, analysis_id, f"{key} must be declared for every analysis"))

        artifacts = row.get("evidence_artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            findings.append(finding("FAIL", "evidence_artifacts", analysis_id, "analysis needs at least one evidence artifact"))
        else:
            for artifact in artifacts:
                path = resolve(root, str(artifact).split("#", 1)[0])
                if not path.is_file():
                    findings.append(finding("FAIL", "missing_evidence_artifact", analysis_id, "evidence artifact is missing", str(artifact)))

        if mode == "deterministic":
            _check_deterministic(row, analysis_id, findings)
        elif mode == "descriptive":
            _check_descriptive(row, analysis_id, findings)
        elif mode == "inferential":
            _check_inferential(row, analysis_id, findings)
        else:
            _check_simulation(row, analysis_id, findings)

    _check_significance_language(paper_text, findings)
    _check_provenance_bindings(root, claim_ids, findings)
    fail_count = sum(item.level == "FAIL" for item in findings)
    warn_count = sum(item.level == "WARN" for item in findings)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "analyses_audited": len(analyses),
        "counts": {"FAIL": fail_count, "WARN": warn_count},
        "findings": [asdict(item) for item in findings],
        "verdict": "FAIL" if fail_count else "PASS",
    }


def _check_deterministic(row: dict[str, Any], analysis_id: str, findings: list[Finding]) -> None:
    inferential_fields = ("independent_n", "repeat_structure", "effect_size", "interval", "test", "multiplicity", "missing_data")
    na_fields = [key for key in inferential_fields if not_applicable(row.get(key))]
    if len(na_fields) != len(inferential_fields):
        missing = sorted(set(inferential_fields) - set(na_fields))
        findings.append(
            finding(
                "FAIL",
                "deterministic_na_contract",
                analysis_id,
                "deterministic analysis must consistently mark every inferential-only field as not_applicable",
                *missing,
            )
        )
    if na_fields and len(str(row.get("not_applicable_reason") or "").strip()) < 20:
        findings.append(finding("FAIL", "not_applicable_reason", analysis_id, "deterministic N/A fields need a substantive reason"))


def _check_descriptive(row: dict[str, Any], analysis_id: str, findings: list[Finding]) -> None:
    independent_n = row.get("independent_n")
    if not isinstance(independent_n, int) or isinstance(independent_n, bool) or independent_n <= 0:
        findings.append(finding("FAIL", "independent_n", analysis_id, "descriptive analysis needs a positive independent_n"))
    if not substantive(row.get("missing_data")):
        findings.append(finding("FAIL", "missing_data", analysis_id, "missing-data handling must be declared"))


def _check_inferential(row: dict[str, Any], analysis_id: str, findings: list[Finding]) -> None:
    independent_n = row.get("independent_n")
    if not isinstance(independent_n, int) or isinstance(independent_n, bool) or independent_n <= 0:
        findings.append(finding("FAIL", "independent_n", analysis_id, "inferential analysis needs a positive independent_n"))
    repeat = row.get("repeat_structure")
    observed_n = row.get("observed_n")
    if not isinstance(observed_n, int) or isinstance(observed_n, bool) or observed_n <= 0:
        findings.append(finding("FAIL", "observed_n", analysis_id, "inferential analysis needs a positive observed_n"))
    repeat_type = str(repeat.get("type") if isinstance(repeat, dict) else repeat or "").lower()
    if isinstance(observed_n, int) and isinstance(independent_n, int) and observed_n > independent_n and repeat_type in {"", "none", "undeclared", "independent"}:
        findings.append(finding("FAIL", "pseudoreplication", analysis_id, "observations exceed independent units but clustering/pairing/repeated measures are not modeled"))
    elif not substantive(repeat):
        findings.append(finding("FAIL", "repeat_structure", analysis_id, "pairing, clustering, or repeated-measure structure must be declared"))
    for key in ("effect_size", "interval", "test", "multiplicity"):
        if not substantive(row.get(key)):
            findings.append(finding("FAIL", key, analysis_id, f"inferential analysis requires {key}"))
    test = row.get("test")
    assumptions = row.get("test_assumptions")
    if isinstance(test, dict) and substantive(test.get("assumptions")):
        assumptions = test.get("assumptions")
    if not substantive(assumptions):
        findings.append(finding("FAIL", "test_assumptions", analysis_id, "inferential analysis must record test assumptions and how they were checked"))
    missing = row.get("missing_data")
    if not substantive(missing):
        findings.append(finding("FAIL", "missing_data", analysis_id, "missing-data handling must be declared"))
    elif isinstance(missing, dict) and str(missing.get("handling") or "").lower() not in {"none", "not_applicable"}:
        before, after = missing.get("before"), missing.get("after")
        if not isinstance(before, int) or not isinstance(after, int) or before < after:
            findings.append(finding("FAIL", "missing_data_counts", analysis_id, "missing-data exclusion needs valid before and after counts"))


def _check_simulation(row: dict[str, Any], analysis_id: str, findings: list[Finding]) -> None:
    repeats = row.get("simulation_repetitions")
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats <= 0:
        findings.append(finding("FAIL", "simulation_repetitions", analysis_id, "simulation needs a positive repetition count"))
    if not isinstance(row.get("seed"), int):
        findings.append(finding("FAIL", "simulation_seed", analysis_id, "simulation needs an integer seed"))
    if not substantive(row.get("interval")):
        findings.append(finding("FAIL", "interval", analysis_id, "simulation output needs uncertainty or empirical interval evidence"))
    for key, message in (
        ("scenario_design", "simulation must declare scenario construction and sampled uncertainty"),
        ("convergence_evidence", "simulation must bind its convergence or sample-size stability evidence"),
        ("claim_domain", "simulation must state the domain over which its claim is supported"),
    ):
        if not substantive(row.get(key)):
            findings.append(finding("FAIL", key, analysis_id, message))


def _check_significance_language(text: str, findings: list[Finding]) -> None:
    compact = re.sub(r"\s+", " ", text)
    patterns = (
        r"显著.{0,30}(?:而|但).{0,20}不显著.{0,40}(?:因此|所以).{0,25}(?:存在)?显著差异",
        r"significant.{0,40}(?:but|whereas).{0,25}not significant.{0,60}(?:therefore|thus).{0,30}significant difference",
    )
    if any(re.search(pattern, compact, flags=re.I) for pattern in patterns):
        findings.append(finding("FAIL", "significance_difference_fallacy", "paper", "a difference in significance was used as evidence of a significant difference"))


def _check_provenance_bindings(root: Path, claim_ids: set[str], findings: list[Finding]) -> None:
    directory = root / "results" / "figures_data"
    if not directory.is_dir():
        return
    for path in directory.glob("*_provenance.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(finding("FAIL", "provenance_parse", "contract", str(exc), relative(root, path)))
            continue
        statistics = payload.get("statistics")
        if substantive(statistics) and str(payload.get("claim_id") or "") not in claim_ids:
            findings.append(finding("WARN", "unbound_figure_statistics", str(payload.get("figure_id") or "figure"), "figure statistics are not bound to a statistical analysis", relative(root, path)))


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("contract must be a JSON object")
    return payload


def write_reports(payload: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Statistical Evidence Audit", "", f"- Verdict: **{payload['verdict']}**", f"- Analyses audited: `{payload['analyses_audited']}`", "", "| Level | Analysis | Code | Message |", "|---|---|---|---|"]
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['analysis_id']} | {item['code']} | {item['message'].replace('|', '/')} |")
    if not payload["findings"]:
        lines.append("| INFO | - | complete | no findings |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="planning/statistical_evidence.json")
    parser.add_argument("--paper", default="paper/main.tex")
    parser.add_argument("--write-json", default="checks/statistical_evidence_report.json")
    parser.add_argument("--write-report", default="checks/statistical_evidence_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    contract_path = resolve(root, args.contract)
    try:
        contract = load_json(contract_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        contract = {"schema_version": 0, "analyses": []}
        payload = evaluate_contract(root, contract)
        payload["findings"].insert(0, asdict(finding("FAIL", "contract_load", "contract", str(exc), relative(root, contract_path))))
        payload["counts"]["FAIL"] += 1
        payload["verdict"] = "FAIL"
    else:
        paper_path = resolve(root, args.paper)
        paper_text = paper_path.read_text(encoding="utf-8-sig", errors="replace") if paper_path.is_file() else ""
        payload = evaluate_contract(root, contract, paper_text)
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"analyses_audited: {payload['analyses_audited']}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
