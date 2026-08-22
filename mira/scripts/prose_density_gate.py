#!/usr/bin/env python3
"""Audit contest-paper prose density and internal-process leakage.

This gate catches padding that survives structural paper checks: empty
transitions, vague praise, generic model-evaluation cliches, agent/workflow
leakage, and long paragraphs that do not carry numerical, formula, table,
figure, citation, constraint, algorithm, or result evidence.
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


PAPER_CANDIDATES = [
    "paper/main_final_checked.tex",
    "paper/main_final_repaired.tex",
    "paper/main_final.tex",
    "paper/main.tex",
    "paper/main.typ",
    "paper/main.md",
    "main.tex",
    "main.typ",
    "main.md",
]

LIGHT_SKIP_SECTIONS = [
    "摘要",
    "关键词",
    "目录",
    "问题重述",
    "模型假设",
    "符号说明",
    "参考文献",
    "附录",
    "appendix",
    "references",
]

EVIDENCE_DEMAND_SECTIONS = [
    "问题分析",
    "模型",
    "建立",
    "求解",
    "算法",
    "结果",
    "分析",
    "检验",
    "验证",
    "灵敏",
    "敏感",
    "误差",
    "评价",
    "推广",
    "复杂度",
    "仿真",
]

AGENT_LEAK_PATTERNS = [
    r"\bMira\b",
    r"\bCodex\b",
    r"\bClaude\b",
    r"\bDeepSeek\b",
    r"\bChatGPT\b",
    r"\bPASS_WITH_WARNINGS\b",
    r"\bfrozen_numbers\b",
    r"\bresult_ledger\b",
    r"\bdecision_gate\b",
    r"\bresult_quality\b",
    r"\bsemantic_audit\b",
    r"\bquality_balance\b",
    r"\bplanning[\\/]",
    r"\bchecks[\\/]",
    r"\brevisions[\\/]",
    r"\bscripts[\\/]",
    r"\bD:[\\/]",
    r"\bC:[\\/]",
    r"审计报告",
    r"(?:质量|流程|决策)门禁|门禁(?:检查|报告|通过|阻塞)",
    r"本轮优化",
    r"为了通过.*检查",
    r"为了通过.*门",
    r"\bagent\b",
    r"智能体.*(生成|撰写|检查|优化)",
]

FILLER_PATTERNS = [
    r"本文首先.*然后.*最后",
    r"首先.*其次.*最后",
    r"综上所述",
    r"通过上述分析",
    r"由此可见",
    r"可以看出",
    r"具有一定.*意义",
    r"具有较[强好].*适用",
    r"较好地",
    r"有效地",
    r"合理性和可行性",
    r"科学合理",
    r"为后续.*提供.*参考",
    r"在一定程度上",
    r"充分说明",
    r"取得.*良好.*效果",
    r"具有重要.*价值",
]

VAGUE_CLAIM_PATTERNS = [
    r"明显提升",
    r"显著提高",
    r"效果较好",
    r"结果较为理想",
    r"误差较小",
    r"鲁棒性较好",
    r"适应性较强",
    r"具有较强的推广性",
    r"具有较高的准确性",
    r"验证了模型的有效性",
    r"说明模型是合理的",
]

GENERIC_EVALUATION_PATTERNS = [
    r"优点.*(简单|易于实现|适用性强)",
    r"缺点.*(忽略|未考虑).*因素",
    r"不足.*(数据|因素).*有限",
    r"模型.*推广.*较好",
    r"模型.*具有.*普适性",
    r"未来.*进一步.*研究",
]

EVIDENCE_PATTERNS = [
    r"\d+(?:\.\d+)?\s*(?:%|元|秒|分钟|小时|天|米|公里|km|m|kg|吨|辆|次|个|组|万元)?",
    r"\\(?:ref|eqref|cite)\b",
    r"(?:图|表|式)\s*[\(（]?\s*\d+",
    r"(?:Fig\.|Figure|Table|Eq\.)\s*\d+",
    r"\[[0-9,\-\s]+\]",
    r"(?:EQUATION|MATH|FIG_REF|TAB_REF|CITE_REF)",
    r"[=<>≤≥∈∑∏√]|\\(?:leq|geq|sum|prod|frac|min|max)\b",
    r"(?:目标函数|约束|变量|参数|状态|转移|邻域|复杂度|收敛|基准|下界|上界|残差|误差|灵敏度|敏感性)",
    r"(?:迭代|抽样|仿真|校准|拟合|回归|聚类|线性化|松弛|剪枝|动态规划|模拟退火|遗传算法|粒子群|蒙特卡洛)",
    r"(?:可行解|最优解|候选解|路径|时间窗|惩罚项|权重|置信区间|显著性|相关系数)",
]


@dataclass
class Paragraph:
    line: int
    section: str
    raw: str
    text: str


@dataclass
class Finding:
    level: str
    axis: str
    return_phase: str
    finding: str
    recommendation: str
    evidence: str = ""


@dataclass
class ProseIssue:
    line: int
    section: str
    axis: str
    reason: str
    text: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper source path; defaults to common paper/main* files")
    parser.add_argument("--min-paragraph-chars", type=int, default=80, help="Minimum cleaned paragraph length for density checks")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper = resolve_path(root, args.paper) if args.paper else find_paper(root)
    payload = audit_paper(root, paper, min_chars=args.min_paragraph_chars)

    if args.write_report:
        out = resolve_path(root, args.write_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        out = resolve_path(root, args.write_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    emit(payload)
    return 1 if payload["verdict"] == "FAIL" else 0


def audit_paper(root: Path, paper: Path, min_chars: int = 80) -> dict[str, Any]:
    findings: list[Finding] = []
    issues: list[ProseIssue] = []
    if not paper.exists():
        findings.append(
            Finding(
                "FAIL",
                "paper_source",
                "paper",
                f"paper source not found: {rel(root, paper)}",
                "return to paper and create the final paper source before running prose-density checks.",
            )
        )
        return payload(root, paper, [], findings, issues, {})

    raw = read_text(paper)
    body = body_before_references(raw)
    paragraphs = split_paragraphs(body)
    checked = [p for p in paragraphs if should_density_check(p, min_chars)]

    agent_issues = agent_leaks(paragraphs)
    filler = sentence_issues(paragraphs, FILLER_PATTERNS, "filler_transition", "empty transition or contest-paper cliche")
    vague = sentence_issues(paragraphs, VAGUE_CLAIM_PATTERNS, "vague_claim", "vague quality claim without local evidence")
    generic_eval = sentence_issues(paragraphs, GENERIC_EVALUATION_PATTERNS, "generic_evaluation", "generic model evaluation without named limitation or evidence")
    evidence_light = [issue for p in checked if (issue := evidence_light_issue(p))]

    issues.extend(agent_issues)
    issues.extend(filler)
    issues.extend(vague)
    issues.extend(generic_eval)
    issues.extend(evidence_light)

    if agent_issues:
        sample = sample_text(agent_issues)
        findings.append(
            Finding(
                "FAIL",
                "agent_prose_leak",
                "paper",
                f"detected {len(agent_issues)} internal agent/workflow/process leak(s) in paper prose. {sample}",
                "rewrite the affected sentences into paper-native modeling/result language; keep tool names, paths, audits, and workflow status in project records only.",
                sample,
            )
        )

    filler_like = filler + vague
    if len(filler_like) >= 10:
        level = "FAIL"
    elif len(filler_like) >= 4:
        level = "WARN"
    else:
        level = ""
    if level:
        sample = sample_text(filler_like)
        findings.append(
            Finding(
                level,
                "filler_or_vague_claim",
                "paper",
                f"detected {len(filler_like)} filler/vague claim sentence(s). {sample}",
                "compress or replace each sentence with claim + number/equation/table/figure/citation + reason; delete it when it only connects paragraphs.",
                sample,
            )
        )

    if generic_eval:
        level = "FAIL" if len(generic_eval) >= 5 else "WARN"
        sample = sample_text(generic_eval)
        findings.append(
            Finding(
                level,
                "generic_evaluation",
                "paper",
                f"detected {len(generic_eval)} generic model-evaluation sentence(s). {sample}",
                "name the exact assumption, data condition, parameter, solver limitation, or scenario where the strength/weakness holds; otherwise remove the evaluation sentence.",
                sample,
            )
        )

    light_ratio = len(evidence_light) / max(1, len(checked))
    if len(evidence_light) >= 8 and light_ratio >= 0.40:
        level = "FAIL"
    elif len(evidence_light) >= 4 and light_ratio >= 0.25:
        level = "WARN"
    else:
        level = ""
    if level:
        sample = sample_text(evidence_light)
        findings.append(
            Finding(
                level,
                "evidence_light_paragraph",
                "paper",
                f"{len(evidence_light)}/{len(checked)} checked paragraphs are long but evidence-light (ratio={light_ratio:.2f}). {sample}",
                "for each paragraph, either delete it or attach a concrete artifact: formula, variable definition, constraint, result value, figure/table reference, citation, algorithm step, sensitivity result, or named limitation.",
                sample,
            )
        )

    metrics = {
        "paper": rel(root, paper),
        "paragraphs_total": len(paragraphs),
        "paragraphs_checked": len(checked),
        "agent_leaks": len(agent_issues),
        "filler_transitions": len(filler),
        "vague_claims": len(vague),
        "generic_evaluations": len(generic_eval),
        "evidence_light_paragraphs": len(evidence_light),
        "evidence_light_ratio": round(light_ratio, 3),
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return payload(root, paper, paragraphs, findings, issues, metrics)


def find_paper(root: Path) -> Path:
    for rel_path in PAPER_CANDIDATES:
        path = root / rel_path
        if path.exists():
            return path
    tex_files = sorted((root / "paper").glob("*.tex")) if (root / "paper").exists() else []
    if tex_files:
        return tex_files[0]
    return root / PAPER_CANDIDATES[3]


def body_before_references(text: str) -> str:
    text = strip_comments(text)
    cut_patterns = [
        r"\\appendix\b",
        r"\\begin\{thebibliography\}",
        r"\\(?:section|chapter)\*?\{(?:参考文献|References|附录|Appendix)[^}]*\}",
        r"^#+\s*(?:参考文献|References|附录|Appendix)\b",
    ]
    cut = len(text)
    for pattern in cut_patterns:
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            cut = min(cut, match.start())
    return text[:cut]


def split_paragraphs(text: str) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    section = ""
    buffer: list[str] = []
    start_line = 1
    skip_env = ""

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        section_match = re.search(r"\\(?:sub)*section\*?\{([^}]*)\}|^#+\s+(.+)$", line)
        if section_match:
            flush_paragraph(paragraphs, buffer, start_line, section)
            buffer = []
            section = clean_text(section_match.group(1) or section_match.group(2) or "")
            continue

        env_begin = re.search(r"\\begin\{(figure|table|tabular|lstlisting|verbatim|algorithm)\}", line)
        if env_begin:
            flush_paragraph(paragraphs, buffer, start_line, section)
            buffer = []
            skip_env = env_begin.group(1)
            continue
        if skip_env:
            if re.search(rf"\\end\{{{re.escape(skip_env)}\}}", line):
                skip_env = ""
            continue

        if not line:
            flush_paragraph(paragraphs, buffer, start_line, section)
            buffer = []
            start_line = line_no + 1
            continue
        if skip_line(line):
            continue
        if not buffer:
            start_line = line_no
        buffer.append(raw_line)

    flush_paragraph(paragraphs, buffer, start_line, section)
    return paragraphs


def flush_paragraph(out: list[Paragraph], buffer: list[str], line: int, section: str) -> None:
    if not buffer:
        return
    raw = "\n".join(buffer).strip()
    text = clean_text(raw)
    if text:
        out.append(Paragraph(line=line, section=section, raw=raw, text=text))


def skip_line(line: str) -> bool:
    stripped = line.strip()
    if re.match(r"\\(?:documentclass|usepackage|geometry|newcommand|renewcommand|title|author|date|maketitle|tableofcontents)\b", stripped):
        return True
    if re.match(r"\\(?:toprule|midrule|bottomrule|hline|caption|label)\b", stripped):
        return True
    if stripped in {"\\begin{document}", "\\end{document}", "\\newpage", "\\clearpage"}:
        return True
    if stripped.startswith("%"):
        return True
    return False


def should_density_check(paragraph: Paragraph, min_chars: int) -> bool:
    compact = re.sub(r"\s+", "", paragraph.text)
    if len(compact) < min_chars:
        return False
    lower_section = paragraph.section.lower()
    if any(term.lower() in lower_section for term in LIGHT_SKIP_SECTIONS):
        return False
    if any(term in paragraph.section for term in EVIDENCE_DEMAND_SECTIONS):
        return True
    return len(compact) >= min_chars + 45


def agent_leaks(paragraphs: list[Paragraph]) -> list[ProseIssue]:
    issues: list[ProseIssue] = []
    for paragraph in paragraphs:
        for pattern in AGENT_LEAK_PATTERNS:
            if re.search(pattern, paragraph.raw, flags=re.I):
                issues.append(ProseIssue(paragraph.line, paragraph.section, "agent_prose_leak", f"matched `{pattern}`", paragraph.text))
                break
    return dedupe_issues(issues)


def sentence_issues(paragraphs: list[Paragraph], patterns: list[str], axis: str, reason: str) -> list[ProseIssue]:
    issues: list[ProseIssue] = []
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph.text):
            if not sentence or has_evidence(sentence, sentence):
                continue
            for pattern in patterns:
                if re.search(pattern, sentence, flags=re.I):
                    issues.append(ProseIssue(paragraph.line, paragraph.section, axis, f"{reason}; matched `{pattern}`", sentence))
                    break
    return dedupe_issues(issues)


def evidence_light_issue(paragraph: Paragraph) -> ProseIssue | None:
    if has_evidence(paragraph.raw, paragraph.text):
        return None
    return ProseIssue(
        line=paragraph.line,
        section=paragraph.section,
        axis="evidence_light_paragraph",
        reason="long paragraph has no detected number, equation, figure/table reference, citation, variable/constraint marker, algorithm action, or result validation signal",
        text=paragraph.text,
    )


def has_evidence(raw: str, clean: str) -> bool:
    text = raw + "\n" + clean
    return any(re.search(pattern, text, flags=re.I) for pattern in EVIDENCE_PATTERNS)


def clean_text(text: str) -> str:
    text = re.sub(r"\\begin\{(?:equation|align|gather|multline|cases)\*?\}.*?\\end\{(?:equation|align|gather|multline|cases)\*?\}", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$[^$]+\$|\\\([^)]*\\\)", " MATH ", text, flags=re.S)
    text = re.sub(r"\\(?:eqref|ref)\{[^}]*fig[^}]*\}", " FIG_REF ", text, flags=re.I)
    text = re.sub(r"\\(?:eqref|ref)\{[^}]*tab[^}]*\}", " TAB_REF ", text, flags=re.I)
    text = re.sub(r"\\cite\{[^}]*\}", " CITE_REF ", text)
    text = re.sub(r"\\(?:textbf|textit|emph|mathbf|mathrm|boldsymbol)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", text)
    text = text.replace("\\", " ")
    text = re.sub(r"[{}_$^~&#]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?；;])\s*", text) if item.strip()]


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*$", "", line))
    return "\n".join(lines)


def dedupe_issues(issues: list[ProseIssue]) -> list[ProseIssue]:
    seen: set[str] = set()
    out: list[ProseIssue] = []
    for issue in issues:
        key = f"{issue.axis}|{issue.line}|{re.sub(r'\\s+', '', issue.text)[:80]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def payload(root: Path, paper: Path, paragraphs: list[Paragraph], findings: list[Finding], issues: list[ProseIssue], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper": rel(root, paper),
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
        "issues": [asdict(item) for item in issues[:80]],
        "paragraph_samples": [asdict(item) for item in paragraphs[:20]],
    }


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Mira Prose Density Gate",
        "",
        f"- Generated: {data['generated_at']}",
        f"- Verdict: **{data['verdict']}**",
        f"- Paper: `{data['paper']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in data.get("metrics", {}).items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding | Recommendation | Evidence |", "|---|---|---|---|---|---|"])
    for item in data["findings"]:
        lines.append(
            f"| {item['level']} | {item['axis']} | {item['return_phase']} | {escape(item['finding'])} | {escape(item['recommendation'])} | {escape(item.get('evidence', ''))} |"
        )
    if not data["findings"]:
        lines.append("| PASS | prose_density | - | no blocking prose-density issue detected | keep writing evidence-dense and paper-native | - |")
    lines.extend(["", "## Issue Samples", "", "| Line | Section | Axis | Reason | Text |", "|---:|---|---|---|---|"])
    for issue in data["issues"][:30]:
        lines.append(
            f"| {issue['line']} | {escape(issue['section'])} | {issue['axis']} | {escape(issue['reason'])} | {escape(compact(issue['text'], 140))} |"
        )
    if not data["issues"]:
        lines.append("| - | - | - | - | no obvious filler, internal-process leakage, or evidence-light paragraph samples |")
    lines.extend(
        [
            "",
            "## Repair Rule",
            "",
            "- Delete a sentence when it only connects, praises, or announces structure.",
            "- Keep a sentence when it carries one of: result number, equation, variable/constraint, algorithm action, figure/table reference, citation, validation, sensitivity, named limitation, or decision implication.",
            "- Rewrite weak paragraphs as: claim -> evidence artifact -> reason for the original contest question.",
            "",
        ]
    )
    return "\n".join(lines)


def emit(data: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(f"VERDICT: {data['verdict']}")
    print("metrics: " + json.dumps(data.get("metrics", {}), ensure_ascii=False, sort_keys=True))
    for item in data["findings"]:
        print(f"{item['level']}: {item['axis']}: {item['finding']}")


def sample_text(issues: list[ProseIssue], limit: int = 4) -> str:
    parts = [f"L{issue.line}: {compact(issue.text, 42)}" for issue in issues[:limit]]
    return "; ".join(parts)


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
