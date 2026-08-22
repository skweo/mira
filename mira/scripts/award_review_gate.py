#!/usr/bin/env python3
"""Check a Mira final paper against an internal quality floor.

This diagnostic does not estimate an award band, award probability, or external
competitiveness. Those claims require the separate blind-comparison protocol.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from delivery_contract import (
    collect_source_files,
    load_current_source_report as _load_current_source_report,
    source_fingerprint,
    source_report_status,
)


@dataclass
class Finding:
    level: str
    axis: str
    message: str


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    metrics = collect_metrics(root, args)
    findings = review(metrics)
    paper = resolve_paper(root, args.paper)
    payload = {
        "generated_at": now(),
        "root": str(root),
        **source_fingerprint(root, paper),
        "verdict": verdict(findings),
        "diagnostic_scope": "internal_quality_floor",
        "competitive_profile": "UNVERIFIED",
        "external_competitiveness": "UNVERIFIED",
        "award_probability": "NOT_ESTIMATED",
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
    _print(f"VERDICT: {payload['verdict']}")
    _print(f"diagnostic_scope: {payload['diagnostic_scope']}")
    _print(f"competitive_profile: {payload['competitive_profile']}")
    _print(f"external_competitiveness: {payload['external_competitiveness']}")
    _print(f"award_probability: {payload['award_probability']}")
    for finding in findings:
        _print(f"{finding.level}: [{finding.axis}] {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve_path(root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve_path(root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    paper = resolve_paper(root, args.paper)
    source_files = paper_source_files(root, paper)
    paper_text = "\n".join(read_text(path) for path in source_files)
    checked_text = read_text(root / "paper" / "main_final_checked.txt")
    figure_index = read_text(root / "figures" / "figure_index.md")
    diagram_index = read_text(root / "diagrams" / "diagram_index.md")
    ledger = load_json(resolve_path(root, args.ledger_json))
    evidence = load_json(resolve_path(root, args.evidence_json))
    consistency = load_json(resolve_path(root, args.consistency_json))
    confidence = load_json(resolve_path(root, args.confidence_json))
    result_quality = load_json(resolve_path(root, args.result_quality_json))
    solver_efficiency = load_json(root / "checks" / "solver_efficiency_report.json")
    table_style_path = root / "checks" / "table_style_report.json"
    flowchart_path = root / "checks" / "flowchart_diagram_report.json"
    table_style = _load_current_source_report(root, table_style_path)
    flowchart = _load_current_source_report(root, flowchart_path)
    journal_figure = load_json(root / "checks" / "journal_figure_report.json")
    showcase = load_json(root / "checks" / "showcase_presentation_report.json")
    presentation_text = read_text(root / "checks" / "presentation_strength_report.md")
    baseline_csv = root / "results" / "tables" / "baseline_comparison.csv"
    baseline_text = read_text(baseline_csv)
    sensitivity_tables = sensitivity_table_rows(root)
    theoretical = theoretical_evidence(root)
    implementation = implementation_evidence(root)
    assumption_relaxation = assumption_relaxation_evidence(root)
    contribution = contribution_evidence(root)
    citation_binding = citation_binding_evidence(root)
    algorithm_efficiency = algorithm_efficiency_evidence(root)
    combined_text = paper_text + "\n" + checked_text
    visual_text = combined_text + "\n" + figure_index + "\n" + diagram_index
    visual_index_text = figure_index + "\n" + diagram_index
    main_body_text = contest_body_text(paper_text)
    internal_leaks = internal_process_leaks(main_body_text)
    body_chars = max(len(strip_tex(paper_text)), len(re.sub(r"\s+", "", checked_text)))
    return {
        "paper": rel(root, paper) if paper else "",
        "paper_source_files": [rel(root, path) for path in source_files],
        "paper_chars": body_chars,
        "paper_internal_leak_terms": len(internal_leaks),
        "paper_internal_leak_samples": internal_leaks[:8],
        "checked_text_chars": len(checked_text),
        "section_count": len(re.findall(r"\\section\{", paper_text)),
        "subsection_count": len(re.findall(r"\\subsection\{", paper_text)),
        "equation_count": len(re.findall(r"\\begin\{equation|\\\[", paper_text)),
        "figure_include_count": len(re.findall(r"\\includegraphics", paper_text)),
        "table_count": len(re.findall(r"\\begin\{table|\\begin\{tabular", paper_text)),
        "citation_count": len(re.findall(r"\\cite\{", paper_text)),
        "reference_count": max(len(re.findall(r"\\bibitem", paper_text)), count_reference_lines(paper_text)),
        "citation_binding_artifacts": citation_binding["files"],
        "citation_binding_rows": citation_binding["rows"],
        "citation_support_terms": count_terms(
            combined_text,
            ["引用", "参考文献", "文献", "来源", "出处", "依据", "题目给定", "由数据估计", "显式假设", "支撑", "citation", "source", "reference"],
        ),
        "source_need_terms": count_terms(
            combined_text,
            [
                "动态规划",
                "贝叶斯",
                "序贯",
                "支持向量机",
                "SVM",
                "遗传算法",
                "模拟退火",
                "蒙特卡洛",
                "排队论",
                "YALMIP",
                "求解器",
                "工具箱",
                "外部数据",
                "历史数据",
                "参数",
                "先验",
                "行业",
                "标准",
                "软件",
                "API",
            ],
        ),
        "has_abstract": "\\begin{abstract}" in paper_text or "摘要" in combined_text[:3000],
        "has_keywords": "关键词" in combined_text[:4000] or "keywords" in combined_text[:4000].lower(),
        "figure_index_rows": count_index_rows(figure_index),
        "diagram_index_rows": count_index_rows(diagram_index),
        "figure_narrative_terms": count_terms(
            visual_text,
            ["支撑", "表明", "说明", "解释", "对应", "决策", "临界", "边界", "机制", "验证", "由图", "从图", "caption", "claim", "mechanism"],
        ),
        "figure_role_terms": count_terms(
            visual_index_text,
            ["define", "derive", "compare", "validate", "explain", "decide", "定义", "推导", "对比", "验证", "解释", "决策"],
        ),
        "ledger_entries": len(ledger.get("entries", [])) if isinstance(ledger, dict) else 0,
        "evidence_missing": evidence.get("metrics", {}).get("missing") if isinstance(evidence, dict) else None,
        "consistency_verdict": consistency.get("verdict") if isinstance(consistency, dict) else "",
        "confidence_verdict": confidence.get("verdict") if isinstance(confidence, dict) else "",
        "result_quality_verdict": result_quality.get("verdict") if isinstance(result_quality, dict) else "",
        "solver_efficiency_verdict": solver_efficiency.get("verdict") if isinstance(solver_efficiency, dict) else "",
        "solver_efficiency_findings": len(solver_efficiency.get("findings", [])) if isinstance(solver_efficiency, dict) else 0,
        "table_style_verdict": table_style.get("verdict") if isinstance(table_style, dict) else "",
        "table_style_findings": len(table_style.get("findings", [])) if isinstance(table_style, dict) else 0,
        "table_style_report_status": source_report_status(root, table_style_path),
        "flowchart_diagram_verdict": flowchart.get("verdict") if isinstance(flowchart, dict) else "",
        "flowchart_diagram_findings": len(flowchart.get("findings", [])) if isinstance(flowchart, dict) else 0,
        "flowchart_diagram_report_status": source_report_status(root, flowchart_path),
        "journal_figure_verdict": journal_figure.get("verdict") if isinstance(journal_figure, dict) else "",
        "journal_figure_findings": len(journal_figure.get("findings", [])) if isinstance(journal_figure, dict) else 0,
        "showcase_presentation_verdict": showcase.get("verdict") if isinstance(showcase, dict) else "",
        "showcase_presentation_findings": len(showcase.get("findings", [])) if isinstance(showcase, dict) else 0,
        "presentation_verdict": extract_verdict(presentation_text),
        "model_terms": count_terms(combined_text, ["模型", "约束", "目标函数", "递推", "优化", "灵敏度", "误差", "验证", "审计", "基准"]),
        "alternative_terms": count_terms(combined_text, ["对比", "基准", "备选", "不同", "搜索", "候选", "敏感性", "稳健"]),
        "baseline_csv_exists": baseline_csv.exists(),
        "baseline_csv_rows": count_data_rows(baseline_text),
        "baseline_section_terms": count_terms(
            combined_text,
            ["基准模型对比", "信息价值", "无记忆", "简化模型", "传统模型", "消融", "对照模型", "baseline", "ablation"],
        ),
        "innovation_claim_terms": count_terms(combined_text, ["创新", "改进", "本文方法", "本文模型", "优于", "提升", "收益", "价值"]),
        "sensitivity_table_rows": sensitivity_tables["rows"],
        "sensitivity_table_files": sensitivity_tables["files"],
        "sensitivity_section_terms": count_terms(
            combined_text,
            ["定量灵敏度", "策略切换", "切换边界", "临界值", "阈值", "参数扫描", "样本量敏感性", "弹性", "sensitivity", "threshold"],
        ),
        "qualitative_sensitivity_terms": count_terms(combined_text, ["敏感", "稳健", "扰动", "不确定", "鲁棒", "保守"]),
        "theoretical_artifacts": theoretical["files"],
        "theoretical_rows": theoretical["rows"],
        "strong_theory_claim_terms": count_terms(
            combined_text,
            ["最优策略", "全局最优", "最优解", "最优性", "总是", "必然", "支配", "被支配", "单调", "策略切换", "临界条件", "阈值条件", "optimality", "dominance", "monotonicity"],
        ),
        "proof_scope_terms": count_terms(
            combined_text,
            ["命题", "引理", "证明", "推导", "不等式", "边际收益", "边际成本", "支配关系", "单调性", "作用域", "证据范围", "穷举", "完整枚举", "全枚举", "状态空间", "交换论证", "豁免", "waiver", "proof", "lemma", "proposition"],
        ),
        "implementation_artifacts": implementation["files"],
        "implementation_rows": implementation["rows"],
        "operational_context_terms": count_terms(
            combined_text,
            ["企业", "工厂", "生产", "质检", "检测", "调度", "管理", "库存", "资源配置", "物流", "路径", "排班", "订单", "批次", "来料", "装配", "运营", "决策建议", "执行"],
        ),
        "implementation_terms": count_terms(
            combined_text,
            ["执行流程", "落地", "实施", "应用方案", "操作流程", "岗位", "责任", "数据需求", "触发条件", "异常处理", "人工复核", "复抽样", "清单", "复盘", "指标", "KPI", "实施效果", "管理建议", "更新周期", "数据来源"],
        ),
        "assumption_relaxation_artifacts": assumption_relaxation["files"],
        "assumption_relaxation_rows": assumption_relaxation["rows"],
        "strong_assumption_terms": count_terms(
            combined_text,
            ["完全检测", "完全准确", "独立", "不会损坏", "不损坏", "固定", "等效样本量", "假设"],
        ),
        "relaxation_terms": count_terms(
            combined_text,
            ["漏检", "误检", "检测误差", "不完全检测", "混淆矩阵", "灵敏度", "特异度", "假设放宽", "状态转移", "后验", "拆解损坏", "相关缺陷", "有限产能"],
        ),
        "contribution_artifacts": contribution["files"],
        "contribution_rows": contribution["rows"],
        "algorithm_efficiency_artifacts": algorithm_efficiency["files"],
        "algorithm_efficiency_rows": algorithm_efficiency["rows"],
        "algorithm_need_terms": count_terms(
            combined_text,
            ["算法", "动态规划", "DP", "枚举", "穷举", "全枚举", "遍历", "65536", "启发式", "模拟退火", "遗传算法", "蒙特卡洛", "YALMIP", "求解器", "solver"],
        ),
        "algorithm_complexity_terms": count_terms(
            combined_text,
            ["时间复杂度", "空间复杂度", "复杂度", "O(", "O（", "运行时间", "耗时", "状态数", "策略数", "变量数", "约束数", "剪枝", "分层", "求解状态", "gap"],
        ),
        "innovation_section_terms": count_terms(
            combined_text,
            ["本文创新与贡献", "模型创新点", "主要贡献", "方法优势与证据", "创新与贡献", "模型贡献"],
        ),
        "contribution_evidence_terms": count_terms(combined_text, ["证据", "支撑", "相比", "收益", "价值", "解决", "改进幅度", "适用范围"]),
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if metrics.get("paper_internal_leak_terms", 0):
        samples = ", ".join(metrics.get("paper_internal_leak_samples", []))
        findings.append(Finding("FAIL", "paper_visible_boundary", f"contest paper body contains internal workflow/meta-process terms: {samples}"))
    if metrics["paper_chars"] < 18000:
        findings.append(Finding("FAIL", "paper_depth", "paper body is too short for high-award contest-final comparison"))
    elif metrics["paper_chars"] < 24000:
        findings.append(Finding("WARN", "paper_depth", "paper body may still be thin for a high-award final paper"))
    if metrics["figure_include_count"] < 8:
        findings.append(Finding("FAIL", "visual_evidence", "fewer than 8 included figures"))
    elif metrics["figure_include_count"] < 10:
        findings.append(Finding("WARN", "visual_evidence", "figure count is adequate but not strong"))
    if metrics["figure_include_count"] >= 8 and metrics["figure_narrative_terms"] < max(10, metrics["figure_include_count"] * 2):
        findings.append(Finding("WARN", "figure_narrative", "many figures are included but nearby mechanism/decision explanation signal is weak"))
    if metrics["figure_include_count"] >= 8 and metrics["figure_role_terms"] < max(4, metrics["figure_include_count"] // 2):
        findings.append(Finding("WARN", "figure_roles", "figure/diagram indexes do not record enough visual roles"))
    if metrics["table_count"] < 8:
        findings.append(Finding("WARN", "tables", "few tables for a claim-heavy contest paper"))
    has_citation_binding = metrics["citation_binding_rows"] > 0 or bool(metrics["citation_binding_artifacts"])
    has_text_source_support = metrics["citation_support_terms"] >= 6
    if metrics["source_need_terms"] >= 8 and not (has_citation_binding or has_text_source_support):
        findings.append(Finding("WARN", "citation_precision", "method/parameter/data/software/domain claims appear without precise source-binding support"))
    elif metrics["source_need_terms"] >= 8 and has_text_source_support and not has_citation_binding:
        findings.append(Finding("WARN", "citation_precision", "paper mentions source support but no citation-binding artifact was found"))
    if metrics["citation_count"] >= 6 and not has_citation_binding:
        findings.append(Finding("WARN", "citation_precision", "multiple citations are used but no citation-binding table or plan records what each source supports"))
    if metrics["reference_count"] >= 8 and metrics["citation_count"] == 0 and not has_citation_binding:
        findings.append(Finding("WARN", "citation_precision", "reference list appears unbound because no in-text citations or citation-binding artifact were found"))
    if not metrics["has_abstract"] or not metrics["has_keywords"]:
        findings.append(Finding("FAIL", "front_matter", "missing abstract or keywords"))
    if metrics.get("consistency_verdict") == "FAIL":
        findings.append(Finding("FAIL", "consistency", "paper consistency check has blocking findings"))
    if metrics.get("confidence_verdict") == "FAIL":
        findings.append(Finding("FAIL", "confidence", "result confidence check has blocking findings"))
    if metrics.get("result_quality_verdict") == "FAIL":
        findings.append(Finding("FAIL", "result_quality", "result quality check has blocking findings"))
    if metrics.get("solver_efficiency_verdict") == "FAIL":
        findings.append(Finding("FAIL", "solver_efficiency", "algorithm complexity or solver efficiency gate has blocking findings"))
    elif metrics.get("solver_efficiency_verdict") == "PASS_WITH_WARNINGS":
        findings.append(Finding("WARN", "solver_efficiency", "algorithm complexity or solver efficiency gate has warnings"))
    elif metrics["algorithm_need_terms"] >= 2 and not (
        metrics["algorithm_complexity_terms"] >= 3
        or metrics["algorithm_efficiency_rows"] > 0
        or metrics["algorithm_efficiency_artifacts"]
    ):
        findings.append(Finding("WARN", "solver_efficiency", "algorithm/search/solver terms appear without solver-efficiency report, complexity, runtime, or efficiency evidence"))
    if metrics.get("table_style_verdict") == "FAIL":
        findings.append(Finding("FAIL", "table_style", "table style audit has blocking findings"))
    elif metrics.get("table_style_verdict") == "PASS_WITH_WARNINGS":
        findings.append(Finding("WARN", "table_style", "table style audit recommends table-format, three-line/booktabs, or raw-header repairs"))
    elif metrics.get("table_style_report_status") == "STALE":
        findings.append(Finding("WARN", "table_style", "table style report is stale for the current paper sources; rerun table_style_audit.py"))
    elif metrics["table_count"] >= 8 and not metrics.get("table_style_verdict"):
        findings.append(Finding("WARN", "table_style", "many tables are present but table_style_audit.py has not been run"))
    if metrics.get("showcase_presentation_verdict") == "FAIL":
        findings.append(Finding("FAIL", "showcase_presentation", "scenario/showcase presentation gate has blocking findings"))
    elif metrics.get("showcase_presentation_verdict") == "PASS_WITH_WARNINGS":
        findings.append(Finding("WARN", "showcase_presentation", "scenario/showcase check recommends stronger process diagrams, experiments, batch interpretation, or reproducibility evidence"))
    elif metrics["figure_include_count"] >= 8 and not metrics.get("showcase_presentation_verdict"):
        findings.append(Finding("WARN", "showcase_presentation", "many figures are present but scenario_showcase_gate.py has not been run"))
    if metrics.get("journal_figure_verdict") == "FAIL":
        findings.append(Finding("FAIL", "journal_figure", "journal-grade figure gate has blocking findings"))
    elif metrics.get("journal_figure_verdict") == "PASS_WITH_WARNINGS":
        findings.append(Finding("WARN", "journal_figure", "journal-grade figure gate recommends stronger multi-panel core figures, callouts, style consistency, or resolution"))
    elif metrics["figure_include_count"] >= 8 and not metrics.get("journal_figure_verdict"):
        findings.append(Finding("WARN", "journal_figure", "many figures are present but journal_figure_gate.py has not been run"))
    if metrics.get("flowchart_diagram_verdict") == "FAIL":
        findings.append(Finding("FAIL", "flowchart_diagram", "flowchart/system-link diagram gate has blocking findings"))
    elif metrics.get("flowchart_diagram_verdict") == "PASS_WITH_WARNINGS":
        findings.append(Finding("WARN", "flowchart_diagram", "flowchart gate recommends stronger process diagrams, branch logic, domain lanes, or abbreviation captions"))
    elif metrics.get("flowchart_diagram_report_status") == "STALE":
        findings.append(Finding("WARN", "flowchart_diagram", "flowchart report is stale for the current paper sources; rerun flowchart_diagram_gate.py"))
    elif metrics["diagram_index_rows"] >= 1 and not metrics.get("flowchart_diagram_verdict"):
        findings.append(Finding("WARN", "flowchart_diagram", "diagrams are present but flowchart_diagram_gate.py has not been run"))
    if metrics.get("evidence_missing") not in {0, None}:
        findings.append(Finding("WARN", "evidence_plan", "some final claims lack planned figure/table evidence"))
    if metrics["model_terms"] < 30:
        findings.append(Finding("WARN", "model_depth", "model/validation vocabulary density is low"))
    if metrics["alternative_terms"] < 8:
        findings.append(Finding("WARN", "comparison", "alternative model or baseline comparison signal is weak"))
    has_quant_baseline = metrics["baseline_csv_rows"] > 0
    has_text_baseline = metrics["baseline_section_terms"] >= 2
    if not has_quant_baseline and not has_text_baseline:
        findings.append(Finding("WARN", "baseline_comparison", "no quantified baseline/ablation or information-value comparison found"))
    elif has_text_baseline and not has_quant_baseline:
        findings.append(Finding("WARN", "baseline_comparison", "paper mentions baseline/information value but results/tables/baseline_comparison.csv is missing or empty"))
    if metrics["innovation_claim_terms"] >= 4 and not (has_quant_baseline or has_text_baseline):
        findings.append(Finding("WARN", "innovation_evidence", "model innovation claims are not supported by baseline or ablation evidence"))
    has_quant_sensitivity = metrics["sensitivity_table_rows"] > 0
    has_text_sensitivity = metrics["sensitivity_section_terms"] >= 2
    if not has_quant_sensitivity and not has_text_sensitivity:
        findings.append(Finding("WARN", "sensitivity", "no quantitative sensitivity, threshold, or strategy-switch evidence found"))
    elif has_text_sensitivity and not has_quant_sensitivity:
        findings.append(Finding("WARN", "sensitivity", "paper mentions sensitivity/threshold analysis but no sensitivity table artifact was found"))
    if metrics["qualitative_sensitivity_terms"] >= 6 and not has_quant_sensitivity:
        findings.append(Finding("WARN", "sensitivity_evidence", "many robustness/sensitivity claims appear without saved scan or threshold evidence"))
    has_theoretical_artifact = metrics["theoretical_rows"] > 0 or bool(metrics["theoretical_artifacts"])
    has_theoretical_text = metrics["proof_scope_terms"] >= 6
    if metrics["strong_theory_claim_terms"] >= 8 and not (has_theoretical_artifact or has_theoretical_text):
        findings.append(Finding("WARN", "theoretical_threshold", "strong optimality/threshold claims appear without proof, condition, or evidence-scope support"))
    elif metrics["strong_theory_claim_terms"] >= 8 and has_theoretical_text and not has_theoretical_artifact:
        findings.append(Finding("WARN", "theoretical_threshold", "paper uses proof/threshold language but no theory-proof artifact or threshold-condition table was found"))
    has_implementation_artifact = metrics["implementation_rows"] > 0 or bool(metrics["implementation_artifacts"])
    has_implementation_text = metrics["implementation_terms"] >= 5
    if metrics["operational_context_terms"] >= 12 and not (has_implementation_artifact or has_implementation_text):
        findings.append(Finding("WARN", "engineering_implementation", "operational recommendations appear without executable workflow, owner/data/trigger, or KPI guidance"))
    elif metrics["operational_context_terms"] >= 12 and has_implementation_text and not has_implementation_artifact:
        findings.append(Finding("WARN", "engineering_implementation", "paper mentions implementation guidance but no implementation checklist or KPI artifact was found"))
    has_relaxation_artifact = metrics["assumption_relaxation_rows"] > 0 or bool(metrics["assumption_relaxation_artifacts"])
    has_relaxation_text = metrics["relaxation_terms"] >= 2
    if metrics["strong_assumption_terms"] >= 4 and not (has_relaxation_artifact or has_relaxation_text):
        findings.append(Finding("WARN", "assumption_relaxation", "strong assumptions appear without concrete relaxation or extension logic"))
    elif metrics["strong_assumption_terms"] >= 4 and has_relaxation_text and not has_relaxation_artifact:
        findings.append(Finding("WARN", "assumption_relaxation", "assumption relaxation is discussed but no relaxation artifact/table was found"))
    has_contribution_artifact = metrics["contribution_rows"] > 0 or bool(metrics["contribution_artifacts"])
    has_contribution_section = metrics["innovation_section_terms"] > 0
    if metrics["innovation_claim_terms"] >= 4 and not (has_contribution_artifact or has_contribution_section):
        findings.append(Finding("WARN", "innovation_contribution", "innovation claims are scattered without a named contribution section or innovation ledger"))
    elif has_contribution_section and metrics["contribution_evidence_terms"] < 4:
        findings.append(Finding("WARN", "innovation_contribution", "contribution section appears weakly tied to evidence, benefit, or scope"))
    return findings


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def resolve_paper(root: Path, paper_arg: str | None) -> Path:
    candidates = []
    if paper_arg:
        candidates.append(resolve_path(root, paper_arg))
    candidates.extend([root / "paper" / "main_final.tex", root / "paper" / "main.tex"])
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def paper_source_files(root: Path, paper: Path) -> list[Path]:
    if not paper.is_file():
        return []
    if paper.suffix.lower() == ".tex":
        return [path for path in collect_source_files(root, paper) if path.suffix.lower() == ".tex"]
    return [paper]


def strip_tex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", text)
    text = re.sub(r"\s+", "", text)
    return text


def contest_body_text(text: str) -> str:
    """Return the paper body before references/appendix for visible-prose checks."""
    cut_patterns = [
        r"\\appendix\b",
        r"\\begin\{thebibliography\}",
        r"\\section\*?\{参考文献\}",
        r"\\section\*?\{附录",
    ]
    cut = len(text)
    for pattern in cut_patterns:
        match = re.search(pattern, text)
        if match:
            cut = min(cut, match.start())
    return text[:cut]


def internal_process_leaks(text: str) -> list[str]:
    """Find internal workflow terms that should stay in project records."""
    terms = [
        "公开答案",
        "网上结果",
        "外部答案",
        "不借助外部答案",
        "不依赖外部答案",
        "没有把公开答案",
        "Mira",
        "Codex",
        "Claude",
        "DeepSeek",
        "agent",
        "AI决策",
        "本地脚本",
        "求解脚本",
        "冻结结果",
        "结果账本",
        "终稿冻结",
        "审计报告",
        "门禁",
        "frozen_numbers",
        "result_ledger",
        "delivery_brief",
        "agent_state",
        "award_review",
        "paper_consistency",
        "result_confidence",
        "checks/",
        "planning/",
        "scripts/",
        "code/python",
        "SKILL.md",
    ]
    found: list[str] = []
    for term in terms:
        if term in text and term not in found:
            found.append(term)
    return found


def count_reference_lines(text: str) -> int:
    match = re.search(r"\\begin\{thebibliography\}(.+?)\\end\{thebibliography\}", text, flags=re.S)
    if not match:
        return 0
    return len(re.findall(r"\\bibitem", match.group(1)))


def count_index_rows(text: str) -> int:
    rows = [line for line in text.splitlines() if line.startswith("|") and "---" not in line]
    return max(0, len(rows) - 1)


def count_terms(text: str, terms: list[str]) -> int:
    return sum(text.count(term) for term in terms)


def count_data_rows(text: str) -> int:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0
    return max(0, len(lines) - 1)


def sensitivity_table_rows(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    names = [
        "sensitivity_scan.csv",
        "threshold_analysis.csv",
        "sample_size_sensitivity.csv",
    ]
    files: list[str] = []
    rows = 0
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(name)
            rows += count
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in names:
                continue
            if any(token in lower for token in ["sensitivity", "threshold", "switch", "elasticity"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(path.name)
                    rows += count
    return {"rows": rows, "files": sorted(set(files))}


def assumption_relaxation_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    for name in ["imperfect_detection_sensitivity.csv", "assumption_relaxation.csv"]:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(name)
            rows += count
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in files:
                continue
            if any(token in lower for token in ["imperfect", "detection_error", "relaxation", "assumption"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(path.name)
                    rows += count
    plan = root / "planning" / "assumption_relaxation_plan.md"
    if plan.exists() and read_text(plan).strip():
        files.append("planning/assumption_relaxation_plan.md")
    return {"rows": rows, "files": sorted(set(files))}


def theoretical_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    names = [
        "theoretical_thresholds.csv",
        "dominance_conditions.csv",
        "monotonicity_check.csv",
    ]
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(name)
            rows += count
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in names:
                continue
            if any(token in lower for token in ["theory", "proof", "dominance", "monotonic", "threshold_condition"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(path.name)
                    rows += count
    plan = root / "planning" / "theory_proof_plan.md"
    if plan.exists() and read_text(plan).strip():
        files.append("planning/theory_proof_plan.md")
    return {"rows": rows, "files": sorted(set(files))}


def implementation_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    names = [
        "implementation_checklist.csv",
        "kpi_review_plan.csv",
    ]
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(name)
            rows += count
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in names:
                continue
            if any(token in lower for token in ["implementation", "deployment", "workflow", "checklist", "kpi", "operation"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(path.name)
                    rows += count
    plan = root / "planning" / "implementation_plan.md"
    if plan.exists() and read_text(plan).strip():
        files.append("planning/implementation_plan.md")
    return {"rows": rows, "files": sorted(set(files))}


def contribution_evidence(root: Path) -> dict[str, Any]:
    files: list[str] = []
    rows = 0
    table = root / "results" / "tables" / "contribution_ledger.csv"
    count = count_data_rows(read_text(table))
    if count:
        files.append("results/tables/contribution_ledger.csv")
        rows += count
    ledger = root / "planning" / "innovation_ledger.md"
    if ledger.exists() and read_text(ledger).strip():
        files.append("planning/innovation_ledger.md")
    return {"rows": rows, "files": files}


def citation_binding_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    names = [
        "citation_binding.csv",
        "source_binding.csv",
        "reference_binding.csv",
    ]
    seen: set[str] = set()
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(f"results/tables/{name}")
            rows += count
            seen.add(name)
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in seen:
                continue
            if any(token in lower for token in ["citation", "source_binding", "reference_binding", "source_trace"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(f"results/tables/{path.name}")
                    rows += count
    for rel_path in ["planning/citation_binding.md", "planning/source_binding.md"]:
        path = root / rel_path
        if path.exists() and read_text(path).strip():
            files.append(rel_path)
    return {"rows": rows, "files": sorted(set(files))}


def algorithm_efficiency_evidence(root: Path) -> dict[str, Any]:
    table_dir = root / "results" / "tables"
    files: list[str] = []
    rows = 0
    names = [
        "solver_efficiency.csv",
        "algorithm_complexity.csv",
        "complexity_analysis.csv",
        "runtime_profile.csv",
        "enumeration_feasibility.csv",
    ]
    seen: set[str] = set()
    for name in names:
        path = table_dir / name
        count = count_data_rows(read_text(path))
        if count:
            files.append(f"results/tables/{name}")
            rows += count
            seen.add(name)
    if table_dir.exists():
        for path in table_dir.glob("*.csv"):
            lower = path.name.lower()
            if path.name in seen:
                continue
            if any(token in lower for token in ["complexity", "efficiency", "runtime", "profile", "solver"]):
                count = count_data_rows(read_text(path))
                if count:
                    files.append(f"results/tables/{path.name}")
                    rows += count
    for rel_path in ["planning/algorithm_complexity.md", "planning/solver_efficiency.md"]:
        path = root / rel_path
        if path.exists() and read_text(path).strip():
            files.append(rel_path)
    return {"rows": rows, "files": sorted(set(files))}


def extract_verdict(text: str) -> str:
    match = re.search(r"Verdict:\s*\*\*([^*]+)\*\*", text)
    return match.group(1).strip() if match else ""


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Internal Quality Review",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Diagnostic scope: **{payload['diagnostic_scope']}**",
        f"- Competitive profile: **{payload['competitive_profile']}**",
        f"- External competitiveness: **{payload['external_competitiveness']}**",
        f"- Award probability: **{payload['award_probability']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    else:
        lines.append("| INFO | internal_quality | no internal quality-floor findings |")
    lines.append("")
    return "\n".join(lines)


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}


def load_current_source_report(root: Path, path: Path) -> dict[str, Any]:
    """Compatibility entry point for source-bound downstream reports."""

    return _load_current_source_report(root, path)


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
    parser.add_argument("--paper", help="Paper tex path")
    parser.add_argument("--ledger-json", default="planning/result_ledger.json", help="Result ledger JSON path")
    parser.add_argument("--evidence-json", default="planning/evidence_plan.json", help="Evidence plan JSON path")
    parser.add_argument("--consistency-json", default="checks/paper_consistency_report.json", help="Paper consistency JSON path")
    parser.add_argument("--confidence-json", default="checks/result_confidence_report.json", help="Result confidence JSON path")
    parser.add_argument("--result-quality-json", default="checks/result_quality_report.json", help="Result quality JSON path")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
