#!/usr/bin/env python3
"""Audit professional modeling evidence, optimality, and numeric consistency."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


GLOBAL_TERMS = ("全局最优", "全域最优", "global optimum", "globally optimal")
CERTIFIED_GLOBAL = {
    "analytic_proof",
    "convexity",
    "interval_bound",
    "branch_and_bound_gap",
    "certified_global_solver",
    "exhaustive_discrete_enumeration",
}
NUMBER_RE = re.compile(
    r"(?<![A-Za-z])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?(?:[eE][-+]?\d+)?"
)


@dataclass
class Finding:
    level: str
    axis: str
    code: str
    message: str
    evidence: str = ""


class ProfessionalModelingGate:
    def __init__(self, root: Path, contract_path: Path) -> None:
        self.root = root.resolve()
        self.contract_path = contract_path.resolve()
        self.contract: dict[str, Any] = {}
        self.paper_path = self.root / "paper" / "main.tex"
        self.paper = ""
        self.findings: list[Finding] = []

    def run(self) -> dict[str, Any]:
        self._load()
        if self.contract:
            self._check_symbols()
            self._check_question_evidence()
            self._check_error_analysis()
            self._check_generalization()
            self._check_optimality()
            self._check_numeric_bindings()
            self._check_reference_bindings()
        failures = [item for item in self.findings if item.level == "FAIL"]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "root": str(self.root),
            "contract": relative(self.root, self.contract_path),
            "verdict": "FAIL" if failures else "PASS",
            "metrics": {
                "questions": len(self.contract.get("questions", [])),
                "symbols": len(self.contract.get("symbol_definitions", [])),
                "optimality_certificates": len(self.contract.get("optimality_certificates", [])),
                "numeric_bindings": len(self.contract.get("numeric_bindings", [])),
                "reference_bindings": len(self.contract.get("reference_bindings", [])),
                "failures": len(failures),
            },
            "findings": [asdict(item) for item in self.findings],
        }

    def fail(self, axis: str, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("FAIL", axis, code, message, evidence))

    def _load(self) -> None:
        if not self.contract_path.is_file():
            self.fail("contract", "missing", "planning/professional_modeling.json is missing", relative(self.root, self.contract_path))
            return
        try:
            payload = json.loads(self.contract_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.fail("contract", "invalid", f"invalid professional modeling contract: {exc}")
            return
        if not isinstance(payload, dict) or payload.get("version") != 1:
            self.fail("contract", "version", "professional modeling contract version must be 1")
            return
        self.contract = payload
        if not self.paper_path.is_file():
            self.fail("paper", "missing", "paper/main.tex is missing", relative(self.root, self.paper_path))
        else:
            self.paper = self.paper_path.read_text(encoding="utf-8-sig", errors="ignore")

    def _check_symbols(self) -> None:
        symbols = self.contract.get("symbol_definitions")
        if not isinstance(symbols, list) or not symbols:
            self.fail("mathematics", "symbol_table", "symbol_definitions must record every important variable and parameter")
            return
        seen: set[str] = set()
        for index, item in enumerate(symbols, start=1):
            if not isinstance(item, dict):
                self.fail("mathematics", "symbol_table", f"symbol record {index} must be an object")
                continue
            symbol = str(item.get("symbol") or "").strip()
            if not symbol or symbol.upper() in {"TBD", "TODO", "UNDEFINED"}:
                self.fail("mathematics", "symbol_table", f"symbol record {index} is undefined")
            if symbol in seen:
                self.fail("mathematics", "symbol_table", "duplicate symbol definition", symbol)
            seen.add(symbol)
            if len(str(item.get("definition") or "")) < 6:
                self.fail("mathematics", "symbol_table", f"symbol {symbol or index} lacks a concrete definition")
            if not str(item.get("unit") or "").strip():
                self.fail("mathematics", "symbol_table", f"symbol {symbol or index} must record a unit or 'dimensionless'")
            if not str(item.get("first_location") or "").strip():
                self.fail("mathematics", "symbol_table", f"symbol {symbol or index} lacks first_location")

    def _check_question_evidence(self) -> None:
        questions = self.contract.get("questions")
        if not isinstance(questions, list) or not questions:
            self.fail("coverage", "questions", "questions must enumerate every major problem")
            return
        seen: set[str] = set()
        for index, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                self.fail("coverage", "questions", f"question record {index} must be an object")
                continue
            qid = str(item.get("question_id") or f"question-{index}")
            if qid in seen:
                self.fail("coverage", "questions", "duplicate question_id", qid)
            seen.add(qid)
            for field, label in (("mechanism_evidence", "mechanism/structure"), ("result_validation_evidence", "result/validation")):
                evidence = item.get(field)
                if not isinstance(evidence, list) or not evidence:
                    self.fail("coverage", field, f"{qid} lacks {label} evidence or a scoped proof/table substitute")
                    continue
                for record in evidence:
                    if not isinstance(record, dict):
                        self.fail("coverage", field, f"{qid} has an invalid evidence record")
                        continue
                    form = str(record.get("form") or "").lower()
                    if form not in {"figure", "flowchart", "table", "proof", "equation"}:
                        self.fail("coverage", field, f"{qid} evidence form is not recognized", form)
                    if not str(record.get("claim_id") or "").strip():
                        self.fail("coverage", field, f"{qid} evidence lacks claim_id")
                    self._source(record.get("source"), "coverage", field)

    def _check_error_analysis(self) -> None:
        error = self.contract.get("error_analysis")
        if not isinstance(error, dict):
            self.fail("error_analysis", "missing", "error_analysis is required")
            return
        sources = error.get("sources")
        if not isinstance(sources, list) or not sources:
            self.fail("error_analysis", "sources", "record quantified error sources and their direction of influence")
        else:
            for item in sources:
                if not isinstance(item, dict) or any(not str(item.get(k) or "").strip() for k in ("name", "mechanism", "direction", "claim_id")):
                    self.fail("error_analysis", "sources", "each error source needs name, mechanism, direction, and claim_id")
                    continue
                self._source(item.get("source"), "error_analysis", "sources")
        quantified = error.get("residual_or_uncertainty")
        if not isinstance(quantified, dict) or any(k not in quantified for k in ("metric", "value", "source", "claim_id")):
            self.fail("error_analysis", "quantification", "residual_or_uncertainty needs metric, value, source, and claim_id")
        else:
            self._number(quantified.get("value"), "error_analysis", "quantification")
            self._source(quantified.get("source"), "error_analysis", "quantification")
        robust = error.get("sensitivity_or_robustness")
        if not isinstance(robust, dict) or any(len(str(robust.get(k) or "")) < 8 for k in ("method", "parameter_range", "finding")):
            self.fail("error_analysis", "robustness", "sensitivity_or_robustness needs method, parameter range, and substantive finding")
        else:
            self._source(robust.get("source"), "error_analysis", "robustness")
        impact = error.get("conclusion_impact")
        if not isinstance(impact, dict) or len(str(impact.get("text") or "")) < 20 or not impact.get("affected_claims"):
            self.fail("error_analysis", "impact", "explain how quantified error changes conclusions and name affected claims")

    def _check_generalization(self) -> None:
        item = self.contract.get("generalization")
        if not isinstance(item, dict):
            self.fail("generalization", "missing", "generalization contract is required")
            return
        for field in ("transferable_core", "assumptions_to_modify", "applicability_boundaries", "new_scenario_validation"):
            if len(str(item.get(field) or "")) < 20:
                self.fail("generalization", field, f"{field} is too short to establish a defensible transfer argument")
        self._source(item.get("source"), "generalization", "source")

    def _check_optimality(self) -> None:
        certificates = self.contract.get("optimality_certificates")
        if not isinstance(certificates, list):
            self.fail("optimality", "contract", "optimality_certificates must be a list")
            certificates = []
        paper_claims_global = any(term.lower() in self.paper.lower() for term in GLOBAL_TERMS)
        if paper_claims_global and not certificates:
            self.fail("optimality", "unsupported_global", "paper claims global optimality without a range/optimality certificate")
        for index, item in enumerate(certificates, start=1):
            if not isinstance(item, dict):
                self.fail("optimality", "contract", f"certificate {index} must be an object")
                continue
            claim_id = str(item.get("claim_id") or f"certificate-{index}")
            scope = str(item.get("conclusion_scope") or "").lower()
            problem_type = str(item.get("problem_type") or "").lower()
            certificate_type = str(item.get("certificate_type") or "").lower()
            if scope not in {"global", "local", "exact", "bounded"}:
                self.fail("optimality", "scope", f"{claim_id} has invalid conclusion_scope", scope)
            domain = item.get("search_domain")
            if not isinstance(domain, dict) or not domain.get("variables") or len(str(domain.get("basis") or "")) < 20:
                self.fail("optimality", "search_domain", f"{claim_id} lacks variables, bounds, or a reasoned search-domain basis")
            elif domain.get("boundary_checked") is not True:
                self.fail("optimality", "boundary", f"{claim_id} did not verify search-domain boundaries")
            if problem_type == "continuous" and scope == "global" and certificate_type not in CERTIFIED_GLOBAL:
                self.fail("optimality", "unsupported_global", f"{claim_id} uses {certificate_type or 'no certificate'} to claim a continuous global optimum")
            if scope == "local" and "local" not in str(item.get("paper_wording") or "").lower() and "局部" not in str(item.get("paper_wording") or ""):
                self.fail("optimality", "wording", f"{claim_id} must label the reported conclusion as local")
            self._source(item.get("evidence"), "optimality", "evidence")
            self._source(item.get("convergence_evidence"), "optimality", "convergence")

    def _check_numeric_bindings(self) -> None:
        bindings = self.contract.get("numeric_bindings")
        waiver = self.contract.get("numeric_waiver")
        if not isinstance(bindings, list) or not bindings:
            if not isinstance(waiver, dict) or len(str(waiver.get("reason") or "")) < 24:
                self.fail("numeric_consistency", "missing", "numeric_bindings are required unless a pure-proof waiver is documented")
            elif waiver:
                self._source(waiver.get("source"), "numeric_consistency", "waiver")
            return
        binding_map: dict[tuple[str, str], tuple[float, float]] = {}
        for index, item in enumerate(bindings, start=1):
            if not isinstance(item, dict):
                self.fail("numeric_consistency", "contract", f"numeric binding {index} must be an object")
                continue
            metric = str(item.get("metric") or "")
            claim_id = str(item.get("claim_id") or "")
            canonical = self._number(item.get("canonical_value"), "numeric_consistency", "canonical")
            tolerance = self._number(item.get("tolerance"), "numeric_consistency", "tolerance")
            if canonical is None or tolerance is None:
                continue
            if tolerance < 0:
                self.fail("numeric_consistency", "tolerance", f"{metric} tolerance cannot be negative")
                continue
            binding_map[(claim_id, metric)] = (canonical, tolerance)
            consumers = item.get("consumers")
            if not isinstance(consumers, list) or not consumers:
                self.fail("numeric_consistency", "consumers", f"{metric} has no cross-artifact consumers")
                continue
            kinds = {str(record.get("kind") or "") for record in consumers if isinstance(record, dict)}
            if not {"ledger", "paper"}.issubset(kinds):
                self.fail("numeric_consistency", "coverage", f"{metric} must be bound to both result ledger and paper", str(sorted(kinds)))
            for record in consumers:
                if not isinstance(record, dict):
                    self.fail("numeric_consistency", "consumer", f"{metric} has an invalid consumer")
                    continue
                observed = self._number(record.get("value"), "numeric_consistency", "consumer")
                if observed is not None and not math.isclose(observed, canonical, rel_tol=0.0, abs_tol=tolerance):
                    self.fail("numeric_consistency", "conflict", f"{metric} differs from canonical value", f"{observed} vs {canonical} ± {tolerance}")
                self._check_consumer_source(metric, canonical, tolerance, record)
        self._compare_figure_values(binding_map)

    def _check_consumer_source(self, metric: str, canonical: float, tolerance: float, record: dict[str, Any]) -> None:
        path = self._source(record.get("path"), "numeric_consistency", "consumer_source")
        if path is None:
            return
        pointer = str(record.get("json_pointer") or "")
        ledger_key = str(record.get("ledger_key") or "").strip()
        if ledger_key and path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                matches = [
                    item
                    for item in payload.get("entries", [])
                    if isinstance(item, dict) and str(item.get("key") or "") == ledger_key
                ]
                if len(matches) != 1:
                    raise ValueError(f"expected one ledger entry, found {len(matches)}")
                observed = float(matches[0]["value"])
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.fail("numeric_consistency", "ledger_key", f"cannot resolve {metric} consumer: {exc}", ledger_key)
                return
            if not math.isclose(observed, canonical, rel_tol=0.0, abs_tol=tolerance):
                self.fail("numeric_consistency", "source_conflict", f"{metric} source value conflicts with canonical", f"{observed} vs {canonical}")
            return
        if pointer and path.suffix.lower() == ".json":
            try:
                value: Any = json.loads(path.read_text(encoding="utf-8-sig"))
                for part in pointer.strip("/").split("/"):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                observed = float(value)
            except (OSError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                self.fail("numeric_consistency", "json_pointer", f"cannot resolve {metric} consumer: {exc}", pointer)
                return
            if not math.isclose(observed, canonical, rel_tol=0.0, abs_tol=tolerance):
                self.fail("numeric_consistency", "source_conflict", f"{metric} source value conflicts with canonical", f"{observed} vs {canonical}")
            return
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        values = parse_numbers(text)
        if not any(math.isclose(value, canonical, rel_tol=0.0, abs_tol=tolerance) for value in values):
            self.fail("numeric_consistency", "source_missing", f"{metric} canonical value is not present in consumer source", relative(self.root, path))

    def _compare_figure_values(self, bindings: dict[tuple[str, str], tuple[float, float]]) -> None:
        path = self.root / "planning" / "figure_evidence.json"
        if not path.is_file():
            return
        try:
            figures = json.loads(path.read_text(encoding="utf-8-sig")).get("figures", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return
        for figure in figures:
            if not isinstance(figure, dict):
                continue
            claim_id = str(figure.get("claim_id") or "")
            for value in figure.get("key_values", []):
                if not isinstance(value, dict):
                    continue
                metric = str(value.get("metric") or "")
                key = (claim_id, metric)
                if key not in bindings:
                    self.fail("numeric_consistency", "unbound_figure_value", f"figure key value lacks a canonical numeric binding: {claim_id}/{metric}")
                    continue
                canonical, tolerance = bindings[key]
                observed = self._number(value.get("value"), "numeric_consistency", "figure_value")
                if observed is not None and not math.isclose(observed, canonical, rel_tol=0.0, abs_tol=max(tolerance, float(value.get("tolerance") or 0))):
                    self.fail("numeric_consistency", "figure_conflict", f"figure value conflicts with canonical binding: {claim_id}/{metric}")

    def _check_reference_bindings(self) -> None:
        cited: set[str] = set()
        for match in re.finditer(r"\\cite[a-zA-Z*]*\s*(?:\[[^]]*\]\s*)?\{([^}]+)\}", self.paper):
            cited.update(key.strip() for key in match.group(1).split(",") if key.strip())
        bindings = self.contract.get("reference_bindings")
        if not isinstance(bindings, list):
            self.fail("references", "contract", "reference_bindings must be a list")
            return
        bound: set[str] = set()
        for item in bindings:
            if not isinstance(item, dict):
                self.fail("references", "contract", "reference binding must be an object")
                continue
            key = str(item.get("citation_key") or "").strip()
            if not key or not str(item.get("claim_id") or "").strip() or len(str(item.get("supported_statement") or "")) < 12 or not str(item.get("paper_location") or "").strip():
                self.fail("references", "binding", "each citation needs key, claim_id, supported statement, and paper location", key)
            bound.add(key)
            if key and key not in cited:
                self.fail("references", "not_cited", "reference binding is not cited in paper", key)
        for key in sorted(cited - bound):
            self.fail("references", "unbound_citation", "paper citation lacks a claim binding", key)

    def _source(self, value: Any, axis: str, code: str) -> Path | None:
        raw = str(value or "").split("#", 1)[0].strip()
        if not raw:
            self.fail(axis, code, "evidence source is missing")
            return None
        path = Path(raw)
        path = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        if self.root != path and self.root not in path.parents:
            self.fail(axis, code, "evidence source must stay inside project root", raw)
            return None
        if not path.is_file():
            self.fail(axis, code, "evidence source does not exist", raw)
            return None
        return path

    def _number(self, value: Any, axis: str, code: str) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            self.fail(axis, code, "expected a finite numeric value", str(value))
            return None
        if not math.isfinite(result):
            self.fail(axis, code, "numeric value must be finite", str(value))
            return None
        return result


def parse_numbers(text: str) -> list[float]:
    values: list[float] = []
    for token in NUMBER_RE.findall(text):
        try:
            values.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return values


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Professional Modeling Gate",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Contract: `{payload['contract']}`",
        "",
        "| Level | Axis | Code | Message | Evidence |",
        "|---|---|---|---|---|",
    ]
    for item in payload["findings"]:
        cells = [str(item.get(key, "")).replace("|", "\\|").replace("\n", " ") for key in ("level", "axis", "code", "message", "evidence")]
        lines.append("| " + " | ".join(cells) + " |")
    if not payload["findings"]:
        lines.append("| INFO | complete | - | no findings | - |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--contract", default="planning/professional_modeling.json")
    parser.add_argument("--write-json", default="checks/professional_modeling_report.json")
    parser.add_argument("--write-report", default="checks/professional_modeling_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = ProfessionalModelingGate(root, resolve(root, args.contract)).run()
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(json.dumps(payload["metrics"], ensure_ascii=False))
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
