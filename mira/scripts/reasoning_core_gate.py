#!/usr/bin/env python3
"""Validate Mira's problem structure, model tournament, and route-changing tests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TABLE_ALIASES = {
    "structure": {"problem structure map", "problem structure", "问题结构地图", "问题结构图", "问题结构"},
    "candidates": {"candidate model portfolio", "model candidate portfolio", "候选模型组合", "候选模型表", "模型竞赛"},
    "tests": {"discriminating tests", "route changing tests", "区分性实验", "区分性检验", "路线改变实验"},
    "waivers": {"reasoning core waivers", "reasoning waivers", "推理核心豁免", "建模竞争豁免"},
}

COLUMN_ALIASES = {
    "question": {"question", "subquestion", "qid", "问题", "子问题"},
    "entities": {"entities", "entity", "实体"},
    "states": {"states", "state", "状态"},
    "decisions": {"decisions", "decision", "决策", "决策变量"},
    "observations": {"observations", "observation", "observables", "观测", "观测量"},
    "constraints": {"constraints", "constraint", "约束"},
    "dependencies": {"dependencies", "dependency", "依赖", "耦合关系"},
    "leverage": {"leverage hypothesis", "leverage", "杠杆点", "关键结构", "突破口"},
    "ambiguity": {"material ambiguity", "ambiguity", "关键歧义", "歧义"},
    "selection_check": {"selection check", "interpretation check", "选择检查", "判别检查"},
    "candidate_id": {"candidate id", "candidate", "route id", "候选id", "候选编号", "路线编号"},
    "structural_signature": {"structural signature", "structure signature", "结构签名", "结构特征"},
    "representation": {"representation", "mathematical representation", "数学表示", "模型表示"},
    "assumptions": {"core assumptions", "structural assumptions", "核心假设", "结构假设"},
    "advantage": {"advantage hypothesis", "expected advantage", "优势假设", "预期优势"},
    "failure_condition": {"failure condition", "failure conditions", "失效条件", "失败条件"},
    "required_evidence": {"required evidence", "evidence needed", "所需证据", "证据需求"},
    "status": {"status", "decision", "状态", "结论"},
    "decision_evidence": {"decision evidence", "status evidence", "选择证据", "淘汰证据", "决策证据"},
    "test_id": {"test id", "experiment id", "检验id", "实验编号", "测试编号"},
    "candidates_compared": {"candidates compared", "compared candidates", "比较候选", "候选对比"},
    "design": {"test design", "design", "实验设计", "检验设计"},
    "observable": {"observable", "metric", "判别量", "指标", "观测指标"},
    "route_change_rule": {"route change rule", "selection rule", "路线改变规则", "路线切换条件", "选择规则"},
    "falsifier": {"falsifier", "falsification criterion", "证伪标准", "否证条件"},
    "budget_cap": {"budget cap", "time/run cap", "compute budget", "预算上限", "时间/运行上限", "计算预算"},
    "evidence_path": {"evidence path", "evidence", "证据路径", "证据"},
    "waiver_id": {"waiver id", "豁免id", "豁免编号"},
    "scope": {"scope", "范围"},
    "basis": {"waiver basis", "basis", "豁免依据", "依据"},
    "justification": {"justification", "reason", "理由", "论证"},
}

STATUS_MAP = {
    "selected": "selected",
    "retained_as_baseline": "retained_as_baseline",
    "retained as baseline": "retained_as_baseline",
    "baseline": "retained_as_baseline",
    "deferred": "deferred",
    "rejected": "rejected",
    "选择": "selected",
    "已选择": "selected",
    "保留为基线": "retained_as_baseline",
    "基线": "retained_as_baseline",
    "暂缓": "deferred",
    "淘汰": "rejected",
    "拒绝": "rejected",
}

TEST_STATUS_MAP = {
    "planned": "planned",
    "completed": "completed",
    "waived": "waived",
    "已计划": "planned",
    "计划": "planned",
    "已完成": "completed",
    "完成": "completed",
    "豁免": "waived",
}

SINGLE_ROUTE_WAIVER_BASES = {"proof", "dominance", "证明", "支配性", "唯一性证明", "支配证明"}
BUDGET_WAIVER_BASES = {"time_budget", "compute_budget", "contest_time", "时间预算", "计算预算", "比赛时间"}
ACCEPTED_WAIVER_STATUSES = {"approved", "accepted", "已批准", "接受", "通过"}


@dataclass
class Finding:
    level: str
    axis: str
    owner_phase: str
    scope: str
    finding: str
    action: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    problem = read_text(root / "planning" / "problem_analysis.md")
    modeling = read_text(root / "planning" / "modeling_plan.md")
    validation = read_text(root / "planning" / "validation_plan.md")

    tables = {
        "structure": find_table(problem, TABLE_ALIASES["structure"]),
        "candidates": find_table(modeling, TABLE_ALIASES["candidates"]),
        "tests": find_table(validation, TABLE_ALIASES["tests"]),
        "waivers": find_table(modeling + "\n" + validation, TABLE_ALIASES["waivers"]),
    }
    findings, metrics = audit(root, args.stage, args.output_level, tables)
    verdict = verdict_for(findings)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "stage": args.stage,
        "output_level": args.output_level,
        "verdict": verdict,
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _print(f"VERDICT: {verdict}")
    _print(json.dumps(metrics, ensure_ascii=False))
    for item in findings:
        _print(f"{item.level}: [{item.axis}] {item.scope}: {item.finding}")
    return 1 if verdict == "FAIL" else 0


def audit(
    root: Path,
    stage: str,
    output_level: str,
    tables: dict[str, list[dict[str, str]] | None],
) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    structure = canonicalize(tables["structure"] or [])
    candidates = canonicalize(tables["candidates"] or [])
    tests = canonicalize(tables["tests"] or [])
    waivers = canonicalize(tables["waivers"] or [])

    required_tables = [
        ("structure", structure, "analysis", "problem_analysis.md needs a Problem Structure Map"),
        ("candidates", candidates, "modeling", "modeling_plan.md needs a Candidate Model Portfolio"),
        ("tests", tests, "modeling", "validation_plan.md needs Discriminating Tests"),
    ]
    for axis, rows, phase, message in required_tables:
        if not rows:
            findings.append(fail(axis, phase, "global", message, "Add the canonical table and fill its structured fields."))

    if not structure or not candidates or not tests:
        return findings, metrics_for(structure, candidates, tests, waivers)

    structure_by_q = rows_by_question(structure)
    candidates_by_q = rows_by_question(candidates)
    tests_by_q = rows_by_question(tests)
    accepted_waivers = accepted_waivers_by_scope(waivers)

    check_required_fields(
        findings,
        structure,
        "problem_structure",
        "analysis",
        ["question", "entities", "states", "decisions", "observations", "constraints", "dependencies", "leverage", "ambiguity", "selection_check"],
    )
    check_required_fields(
        findings,
        candidates,
        "candidate_portfolio",
        "modeling",
        ["candidate_id", "question", "structural_signature", "representation", "assumptions", "advantage", "failure_condition", "required_evidence", "status", "decision_evidence"],
    )
    check_required_fields(
        findings,
        tests,
        "discriminating_test",
        "modeling",
        ["test_id", "question", "candidates_compared", "design", "observable", "route_change_rule", "falsifier", "budget_cap", "evidence_path", "status"],
    )

    all_candidate_ids: dict[str, dict[str, str]] = {}
    duplicate_ids: set[str] = set()
    for row in candidates:
        cid = normalize_id(row.get("candidate_id", ""))
        if not cid:
            continue
        if cid in all_candidate_ids:
            duplicate_ids.add(cid)
        all_candidate_ids[cid] = row
    for cid in sorted(duplicate_ids):
        findings.append(fail("candidate_portfolio", "modeling", cid, "candidate ID is duplicated", "Use one stable ID per structural route."))

    for question in sorted(set(structure_by_q) | set(candidates_by_q)):
        q_candidates = candidates_by_q.get(question, [])
        if not q_candidates:
            findings.append(fail("candidate_portfolio", "modeling", question, "no model candidate is bound to this question", "Add at least one executable route or an explicit out-of-scope decision."))
            continue

        statuses = [normalize_status(row.get("status", "")) for row in q_candidates]
        if not any(status == "selected" for status in statuses):
            findings.append(fail("model_selection", "modeling", question, "no candidate is marked selected", "Select a route after the discriminating evidence is recorded."))
        invalid = [row.get("status", "") for row, status in zip(q_candidates, statuses) if status not in set(STATUS_MAP.values())]
        if invalid:
            findings.append(fail("model_selection", "modeling", question, f"unsupported candidate status: {', '.join(invalid)}", "Use selected, retained_as_baseline, deferred, or rejected."))

        signatures = [normalize_signature(row.get("structural_signature", "")) for row in q_candidates if substantive(row.get("structural_signature", ""))]
        distinct_signatures = set(signatures)
        waiver = accepted_waivers.get(question) or accepted_waivers.get("global")
        if len(q_candidates) == 1:
            if not single_route_waiver_valid(waiver):
                findings.append(fail("candidate_diversity", "modeling", question, "only one candidate route is recorded without a proof/dominance waiver", "Add a structurally different baseline or record an approved proof/dominance waiver with evidence."))
        elif len(distinct_signatures) < 2:
            findings.append(fail("candidate_diversity", "modeling", question, "multiple candidates share one structural signature and are only variants of the same route", "Compare genuinely different representations or collapse parameter variants into one candidate."))

        for row, status in zip(q_candidates, statuses):
            if status in {"rejected", "deferred"} and not substantive(row.get("decision_evidence", "")):
                cid = row.get("candidate_id", "candidate")
                findings.append(fail("rejection_discipline", "modeling", question, f"{cid} is {status} without decision evidence", "Bind the rejection/defer decision to a test, proof, feasibility check, or data limit."))

        if len(distinct_signatures) >= 2:
            q_tests = tests_by_q.get(question, [])
            candidate_ids = {normalize_id(row.get("candidate_id", "")) for row in q_candidates}
            discriminating = []
            for row in q_tests:
                compared = extract_ids(row.get("candidates_compared", ""))
                if len(compared & candidate_ids) >= 2:
                    discriminating.append(row)
                unknown = compared - set(all_candidate_ids)
                if unknown:
                    findings.append(fail("discriminating_test", "modeling", question, f"test {row.get('test_id', '')} references unknown candidates: {', '.join(sorted(unknown))}", "Use candidate IDs from the portfolio."))
            if not discriminating:
                findings.append(fail("discriminating_test", "modeling", question, "no test compares at least two structural candidates", "Add a budget-capped analytic, complexity, feasibility, tiny-case, downsampled, or baseline check whose outcome can change the selected route."))
            for row in discriminating:
                compared = extract_ids(row.get("candidates_compared", ""))
                rule_ids = extract_ids(row.get("route_change_rule", ""))
                if len(rule_ids & compared) < 2:
                    findings.append(fail("route_change_rule", "modeling", question, f"test {row.get('test_id', '')} does not name both branches of the route-change rule", "State the observed condition that selects each compared candidate."))
                test_status = normalize_test_status(row.get("status", ""))
                if test_status not in set(TEST_STATUS_MAP.values()):
                    findings.append(fail("discriminating_test", "modeling", question, f"test {row.get('test_id', '')} has unsupported status {row.get('status', '')}", "Use planned, completed, or waived."))
                if test_status == "waived" and not budget_waiver_valid(waivers, row.get("test_id", "")):
                    findings.append(fail("candidate_comparison_budget", "modeling", question, f"test {row.get('test_id', '')} is waived without a scoped time/compute-budget record", "Add an approved waiver scoped to this test ID with basis time_budget, compute_budget, or contest_time, plus justification and evidence."))
                if stage in {"results", "verify"} and test_status not in {"completed", "waived"}:
                    findings.append(fail("discriminating_evidence", "implementation", question, f"test {row.get('test_id', '')} is not completed or validly budget-waived at the {stage} stage", "Use the cheapest decisive screen within its cap, or record a scoped budget waiver when a full comparison is not worth contest time."))
                if stage in {"results", "verify"} and test_status == "completed" and not evidence_resolves(root, row.get("evidence_path", "")):
                    findings.append(fail("discriminating_evidence", "implementation", question, f"test {row.get('test_id', '')} has no resolvable evidence", "Point to an existing result/check artifact or an explicit proof/certificate reference."))

    if output_level == "quick_draft":
        for item in findings:
            if item.level == "FAIL" and item.axis not in {"candidate_portfolio", "model_selection"}:
                item.level = "WARN"
    return findings, metrics_for(structure, candidates, tests, waivers)


def check_required_fields(
    findings: list[Finding],
    rows: list[dict[str, str]],
    axis: str,
    phase: str,
    required: list[str],
) -> None:
    for index, row in enumerate(rows, start=1):
        missing = [field for field in required if not substantive(row.get(field, ""))]
        if missing:
            scope = row.get("question") or row.get("candidate_id") or row.get("test_id") or f"row-{index}"
            findings.append(fail(axis, phase, scope, f"structured row is missing: {', '.join(missing)}", "Fill the missing fields with problem-specific content or a reasoned not-applicable statement."))


def find_table(text: str, aliases: set[str]) -> list[dict[str, str]] | None:
    lines = text.splitlines()
    normalized_aliases = {normalize_label(item) for item in aliases}
    for index, line in enumerate(lines):
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if not match or normalize_label(match.group(1)) not in normalized_aliases:
            continue
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            if re.match(r"^\s*#{1,6}\s+", lines[cursor]):
                end = cursor
                break
        parsed = parse_first_table(lines[index + 1 : end])
        if parsed is not None:
            return parsed
    return None


def parse_first_table(lines: list[str]) -> list[dict[str, str]] | None:
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or not is_rule_row(lines[index + 1]):
            continue
        headers = split_row(lines[index])
        rows: list[dict[str, str]] = []
        for line in lines[index + 2 :]:
            if not line.strip().startswith("|"):
                if rows:
                    break
                continue
            if is_rule_row(line):
                continue
            values = split_row(line)
            values += [""] * max(0, len(headers) - len(values))
            rows.append({headers[i]: values[i] for i in range(len(headers))})
        return rows
    return None


def canonicalize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    alias_to_key = {
        normalize_label(alias): key
        for key, aliases in COLUMN_ALIASES.items()
        for alias in aliases
    }
    out: list[dict[str, str]] = []
    for row in rows:
        converted: dict[str, str] = {}
        for header, value in row.items():
            key = alias_to_key.get(normalize_label(header), normalize_label(header).replace(" ", "_"))
            converted[key] = value.strip()
        if any(substantive(value) for value in converted.values()):
            out.append(converted)
    return out


def rows_by_question(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        question = normalize_question(row.get("question", ""))
        if question:
            out.setdefault(question, []).append(row)
    return out


def accepted_waivers_by_scope(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if row.get("status", "").strip().lower() not in ACCEPTED_WAIVER_STATUSES:
            continue
        scope = normalize_question(row.get("scope", "")) or row.get("scope", "").strip().lower()
        if scope:
            out[scope] = row
    return out


def single_route_waiver_valid(row: dict[str, str] | None) -> bool:
    if not row:
        return False
    basis = row.get("basis", "").strip().lower()
    return basis in SINGLE_ROUTE_WAIVER_BASES and substantive(row.get("justification", "")) and substantive(row.get("evidence_path", ""))


def budget_waiver_valid(rows: list[dict[str, str]], test_id: str) -> bool:
    normalized_test_id = normalize_id(test_id)
    if not normalized_test_id:
        return False
    for row in rows:
        if normalize_id(row.get("scope", "")) != normalized_test_id:
            continue
        if row.get("status", "").strip().lower() not in ACCEPTED_WAIVER_STATUSES:
            continue
        if row.get("basis", "").strip().lower() not in BUDGET_WAIVER_BASES:
            continue
        if substantive(row.get("justification", "")) and substantive(row.get("evidence_path", "")):
            return True
    return False


def metrics_for(structure: list[dict[str, str]], candidates: list[dict[str, str]], tests: list[dict[str, str]], waivers: list[dict[str, str]]) -> dict[str, Any]:
    signatures = {normalize_signature(row.get("structural_signature", "")) for row in candidates if substantive(row.get("structural_signature", ""))}
    return {
        "structure_rows": len(structure),
        "candidate_rows": len(candidates),
        "distinct_structural_signatures": len(signatures),
        "discriminating_test_rows": len(tests),
        "waiver_rows": len(waivers),
        "budget_waiver_rows": sum(
            1
            for row in waivers
            if row.get("basis", "").strip().lower() in BUDGET_WAIVER_BASES
        ),
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Reasoning Core Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Stage: `{payload['stage']}`",
        f"- Output level: `{payload['output_level']}`",
        f"- Verdict: **{payload['verdict']}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Owner stage | Finding | Action |", "|---|---|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            finding = f"{item['scope']}: {item['finding']}"
            lines.append(f"| {item['level']} | {escape(item['axis'])} | {escape(item['owner_phase'])} | {escape(finding)} | {escape(item['action'])} |")
    else:
        lines.append("| PASS | reasoning_core | - | structural interpretation, candidate competition, and route-changing tests are complete | keep evidence synchronized after model changes |")
    lines.extend([
        "",
        "Automated PASS confirms contract completeness and cross-reference integrity. It does not prove that the interpretation is original or that the selected model is competitively superior; those remain human modeling decisions and blind-review judgments.",
        "",
    ])
    return "\n".join(lines)


def fail(axis: str, phase: str, scope: str, finding: str, action: str) -> Finding:
    return Finding("FAIL", axis, phase, scope, finding, action)


def verdict_for(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def normalize_status(value: str) -> str:
    return STATUS_MAP.get(value.strip().lower(), STATUS_MAP.get(value.strip(), value.strip().lower()))


def normalize_test_status(value: str) -> str:
    return TEST_STATUS_MAP.get(value.strip().lower(), TEST_STATUS_MAP.get(value.strip(), value.strip().lower()))


def normalize_label(value: str) -> str:
    value = re.sub(r"[`*_]", "", str(value)).strip().lower()
    value = re.sub(r"[-/：:（）()\[\]]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_question(value: str) -> str:
    match = re.search(r"(?:q|问题|第)\s*(\d+)", value.strip(), flags=re.I)
    if match:
        return f"q{int(match.group(1))}"
    return value.strip().lower()


def normalize_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", value.strip().lower())


def normalize_signature(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "|", value.strip().lower()).strip("|")


def extract_ids(value: str) -> set[str]:
    return {normalize_id(item) for item in re.findall(r"[A-Za-z][A-Za-z0-9_-]*\d+", value)}


def substantive(value: str) -> bool:
    text = str(value).strip()
    if not text:
        return False
    placeholders = {"-", "--", "tbd", "todo", "none", "n/a", "na", "无", "不适用", "待定", "待补充"}
    return text.lower() not in placeholders


def evidence_resolves(root: Path, value: str) -> bool:
    text = value.strip()
    if not substantive(text):
        return False
    if re.match(r"^(proof|certificate|derivation|table|figure|test):", text, flags=re.I):
        return True
    for token in re.split(r"[,;，；\s]+", text):
        token = token.strip("`[]()")
        if not token:
            continue
        path = Path(token)
        candidate = path if path.is_absolute() else root / path
        if candidate.exists():
            return True
    return False


def split_row(line: str) -> list[str]:
    body = line.strip().strip("|")
    return [part.replace("\\|", "|").strip() for part in re.split(r"(?<!\\)\|", body)]


def is_rule_row(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    parser.add_argument("--stage", choices=["modeling", "results", "verify"], default="verify")
    parser.add_argument("--output-level", choices=["quick_draft", "reproducible_draft", "contest_final"], default="reproducible_draft")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
