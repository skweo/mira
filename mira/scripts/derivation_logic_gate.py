#!/usr/bin/env python3
"""Audit formula derivation logic in Mira contest-final papers.

This gate complements derivation_density_audit.py. Density asks whether math
anchors exist throughout the paper; this script asks whether the visible
formula chain is plausible: symbols are defined, equations are explained,
objectives connect to constraints, jump words have nearby evidence, and strong
claims are supported by proof, bounds, solver gaps, or experiments.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PAPER_CANDIDATES = [
    "paper/main_final_checked.tex",
    "paper/main_final_repaired.tex",
    "paper/main_final.tex",
    "paper/main_contest.tex",
    "paper/main.tex",
    "paper/main.typ",
    "paper/main.md",
    "main.tex",
    "main.typ",
    "main.md",
]

DISPLAY_MATH_RE = re.compile(
    r"\\\[(?P<bracket>.*?)\\\]|"
    r"\$\$(?P<dollar>.*?)\$\$|"
    r"\\begin\{(?P<env>equation\*?|align\*?|gather\*?|multline\*?|cases|array)\}(?P<envbody>.*?)\\end\{(?P=env)\}",
    re.S,
)

SECTION_RE = re.compile(r"\\(?P<kind>section|subsection|subsubsection)\*?\{(?P<title>[^}]*)\}|^#+\s+(?P<mdtitle>.+)$", re.M)

IGNORE_COMMANDS = {
    "begin",
    "end",
    "frac",
    "dfrac",
    "tfrac",
    "sqrt",
    "sum",
    "prod",
    "min",
    "max",
    "argmin",
    "argmax",
    "log",
    "ln",
    "exp",
    "sin",
    "cos",
    "tan",
    "left",
    "right",
    "cdot",
    "times",
    "leq",
    "geq",
    "neq",
    "in",
    "notin",
    "forall",
    "exists",
    "text",
    "mathrm",
    "mathbf",
    "mathit",
    "mathbb",
    "mathcal",
    "boldsymbol",
    "label",
    "ref",
    "eqref",
}

GREEK_COMMANDS = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "varepsilon",
    "theta",
    "lambda",
    "mu",
    "rho",
    "sigma",
    "tau",
    "phi",
    "varphi",
    "omega",
}

ROLE_PATTERNS = {
    "objective": [
        r"\\(?:min|max|argmin|argmax)\b",
        r"\bmin\b|\bmax\b",
        r"目标函数|最小化|最大化|优化目标|objective",
    ],
    "constraint": [
        r"约束|限制|满足|容量|时间窗|守恒|非负|整数|边界|上限|下限|s\.t\.",
        r"\\leq|\\geq|<=|>=|≤|≥",
    ],
    "definition": [r"定义|记为|令|其中|式中|表示|变量|参数|集合"],
    "recurrence": [r"递推|转移|状态|Bellman|dynamic programming|DP|t\+1|k\+1"],
}

LOGIC_JUMP_PATTERNS = [
    r"显然",
    r"易得",
    r"不难得到",
    r"不难看出",
    r"可以直接得到",
    r"由此可得",
    r"于是可得",
    r"从而得到",
    r"因此得到",
    r"故可得",
]

STRONG_CLAIM_PATTERNS = [
    r"全局最优",
    r"最优解",
    r"精确最优",
    r"收敛到",
    r"保证收敛",
    r"鲁棒性(?:较好|较强|强|显著|稳定)",
    r"稳定性(?:较好|较强|强|显著)",
    r"显著(?:提高|提升|优于|降低|改善|相关|差异|影响)",
    r"证明了",
    r"定理",
    r"引理",
    r"误差.*较小",
    r"准确率.*较高",
]

SUPPORT_PATTERNS = [
    r"证明|推导|下界|上界|界|松弛|gap|Gap|最优性间隙",
    r"基准|对比|消融|多次|随机种子|multi-seed|置信区间|残差|误差表",
    r"灵敏度|敏感性|稳定性检验|鲁棒性检验|收敛曲线",
    r"表\s*\d+|图\s*\d+|式\s*\(?\d+|\\(?:ref|eqref|cite)\{|REF|EQUATION|MATH",
]


@dataclass
class EquationBlock:
    index: int
    line: int
    section: str
    text: str
    label: str
    role: str
    symbols: list[str]
    explained_nearby: bool
    source_hint_nearby: bool


@dataclass
class SectionBlock:
    title: str
    line: int
    text: str
    zh_chars: int
    equations: int
    roles: list[str]
    has_table_or_figure: bool


@dataclass
class Issue:
    level: str
    axis: str
    return_phase: str
    finding: str
    recommendation: str
    evidence: str = ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper source path; defaults to common paper/main* files")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper_files = collect_paper_files(root, args.paper)
    payload = audit(root, paper_files)

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


def audit(root: Path, paper_files: list[Path]) -> dict[str, Any]:
    if not paper_files:
        issues = [
            Issue(
                "FAIL",
                "paper_source",
                "paper",
                "no paper source found for derivation-logic audit",
                "return to paper and create the final paper source before running derivation logic checks.",
            )
        ]
        return payload(root, paper_files, [], [], issues, {})

    raw = "\n".join(read_text(path) for path in paper_files)
    body = body_before_references(strip_comments(raw))
    sections = section_blocks(body)
    equations = equation_blocks(body)
    symbol_text = symbol_definition_text(root, body)
    issues: list[Issue] = []

    issues.extend(audit_equation_explanations(equations))
    issues.extend(audit_symbol_definitions(equations, symbol_text))
    issues.extend(audit_objective_constraint_link(equations, body))
    issues.extend(audit_logic_jumps(body))
    issues.extend(audit_strong_claims(body))
    issues.extend(audit_section_chains(sections))

    metrics = {
        "paper_files": [rel(root, path) for path in paper_files],
        "section_count": len(sections),
        "display_equations": len(equations),
        "labeled_equations": sum(1 for eq in equations if eq.label),
        "objective_equations": sum(1 for eq in equations if eq.role == "objective"),
        "constraint_equations": sum(1 for eq in equations if eq.role == "constraint"),
        "definition_equations": sum(1 for eq in equations if eq.role == "definition"),
        "recurrence_equations": sum(1 for eq in equations if eq.role == "recurrence"),
        "unexplained_equations": sum(1 for eq in equations if not eq.explained_nearby),
        "warnings": sum(1 for issue in issues if issue.level == "WARN"),
        "failures": sum(1 for issue in issues if issue.level == "FAIL"),
    }
    return payload(root, paper_files, sections, equations, issues, metrics)


def audit_equation_explanations(equations: list[EquationBlock]) -> list[Issue]:
    if not equations:
        return [
            Issue(
                "WARN",
                "derivation_missing",
                "modeling",
                "no display equation block detected; if this is a contest-final modeling paper, the mathematical chain is likely invisible",
                "return to modeling to add objective, constraints, recurrence, calibration formula, or validation equation where the model needs it.",
            )
        ]
    unexplained = [eq for eq in equations if not eq.explained_nearby]
    reference_worthy = [eq for eq in equations if is_reference_worthy_equation(eq)]
    unlabeled_reference_worthy = [eq for eq in reference_worthy if not eq.label]
    issues: list[Issue] = []
    if len(unexplained) >= 5 and len(unexplained) / max(1, len(equations)) >= 0.45:
        sample = "; ".join(f"L{eq.line}:{compact(eq.text, 42)}" for eq in unexplained[:4])
        issues.append(
            Issue(
                "WARN",
                "equation_explanation_gap",
                "paper",
                f"{len(unexplained)}/{len(equations)} display equations have weak nearby explanation. {sample}",
                "add one sentence before or after each core equation explaining variable meaning, source, transformation, or how it supports the next step.",
                sample,
            )
        )
    if (
        len(unlabeled_reference_worthy) >= 4
        and len(unlabeled_reference_worthy) / max(1, len(reference_worthy)) >= 0.6
    ):
        sample = "; ".join(f"L{eq.line}:{eq.role}" for eq in unlabeled_reference_worthy[:6])
        issues.append(
            Issue(
                "WARN",
                "equation_reference_gap",
                "paper",
                f"{len(unlabeled_reference_worthy)}/{len(reference_worthy)} reference-worthy core formulas are unlabeled, making later result claims hard to trace. {sample}",
                "label only the objective, constraint group, recurrence, validation, complexity, or final-conclusion formulas that later text depends on; leave auxiliary substitutions unnumbered.",
                sample,
            )
        )
    return issues


def is_reference_worthy_equation(eq: EquationBlock) -> bool:
    """Return whether an equation should usually be labelable in a final paper."""

    combined = f"{eq.section}\n{eq.text}"
    if eq.role in {"objective", "recurrence"}:
        return True
    if eq.role == "constraint":
        if eq.source_hint_nearby:
            return True
        if len(eq.text) >= 90 or len(eq.symbols) >= 4:
            return True
        return bool(
            re.search(
                r"\\sum|\\forall|s\.t\.|subject|容量|时间窗|守恒|边界|约束组|非负|整数|上限|下限",
                combined,
                flags=re.I,
            )
        )
    return bool(
        re.search(
            r"验证|检验|误差|残差|灵敏|敏感|鲁棒|收敛|复杂度|最终|结论|结果|答案|目标值|评价指标|"
            r"validation|calibration|complexity|final|result|metric",
            combined,
            flags=re.I,
        )
    )


def audit_symbol_definitions(equations: list[EquationBlock], symbol_text: str) -> list[Issue]:
    symbol_counter: Counter[str] = Counter()
    examples: dict[str, int] = {}
    for eq in equations:
        for symbol in eq.symbols:
            if is_trivial_symbol(symbol):
                continue
            symbol_counter[symbol] += 1
            examples.setdefault(symbol, eq.line)
    unresolved = [
        symbol
        for symbol, count in symbol_counter.items()
        if count >= 2 and not symbol_defined(symbol, symbol_text)
    ]
    if len(unresolved) < 8:
        return []
    level = "FAIL" if len(unresolved) >= 22 else "WARN"
    sample = ", ".join(f"{symbol}(L{examples[symbol]})" for symbol in unresolved[:12])
    return [
        Issue(
            level,
            "symbol_definition_gap",
            "modeling",
            f"{len(unresolved)} repeatedly used formula symbols are not found in symbol definitions or nearby explanation. {sample}",
            "return to modeling to complete the symbol table or to paper to add 'where/其中/式中' explanations before using the symbols in results.",
            sample,
        )
    ]


def audit_objective_constraint_link(equations: list[EquationBlock], body: str) -> list[Issue]:
    objective_count = sum(1 for eq in equations if eq.role == "objective")
    constraint_count = sum(1 for eq in equations if eq.role == "constraint")
    optimization_context = bool(re.search(r"优化|最小化|最大化|目标函数|约束|规划|integer|linear programming|MILP|QP|VRP|TSP", body, re.I))
    issues: list[Issue] = []
    if optimization_context and objective_count > 0 and constraint_count == 0:
        issues.append(
            Issue(
                "FAIL",
                "objective_constraint_gap",
                "modeling",
                "objective function is visible but no explicit constraint equation/block is detected",
                "return to modeling to state constraints from the problem conditions, then paper to connect each constraint to the objective and solver.",
            )
        )
    elif optimization_context and objective_count == 0 and constraint_count >= 2:
        issues.append(
            Issue(
                "WARN",
                "objective_constraint_gap",
                "modeling",
                "constraint equations are visible but no objective-function equation is detected",
                "return to modeling to state the optimization objective or explain why the model is feasibility-only.",
            )
        )
    weak_sources = [eq for eq in equations if eq.role == "constraint" and not eq.source_hint_nearby]
    if len(weak_sources) >= 5:
        sample = "; ".join(f"L{eq.line}:{compact(eq.text, 36)}" for eq in weak_sources[:5])
        issues.append(
            Issue(
                "WARN",
                "constraint_source_gap",
                "modeling",
                f"{len(weak_sources)} constraint-like equations lack nearby source hints from problem conditions. {sample}",
                "state whether each constraint comes from capacity, time, conservation, boundary, data range, policy, or modeling assumption.",
                sample,
            )
        )
    return issues


def audit_logic_jumps(body: str) -> list[Issue]:
    issues = []
    sentences = sentence_windows(body)
    hits = []
    for line, prev_text, sentence, next_text in sentences:
        if any(re.search(pattern, sentence) for pattern in LOGIC_JUMP_PATTERNS):
            context = prev_text + sentence + next_text
            if not has_logic_support(context):
                hits.append((line, sentence))
    if len(hits) >= 10:
        level = "FAIL"
    elif len(hits) >= 4:
        level = "WARN"
    else:
        return []
    sample = "; ".join(f"L{line}:{compact(text, 46)}" for line, text in hits[:5])
    issues.append(
        Issue(
            level,
            "logic_jump_gap",
            "modeling",
            f"{len(hits)} derivation jump phrase(s) have no nearby equation, reference, bound, or numeric support. {sample}",
            "replace 'obvious/easy to get' wording with the missing transformation, proof step, cited equation, or computed evidence.",
            sample,
        )
    )
    return issues


def audit_strong_claims(body: str) -> list[Issue]:
    hits = []
    for line, prev_text, sentence, next_text in sentence_windows(body):
        if any(re.search(pattern, sentence) for pattern in STRONG_CLAIM_PATTERNS):
            if re.search(r"不(?:直接)?声称|不使用|不把|不提升为|不保证|不能保证|不是|未证明|并非|避免.*宣称|不恰当.*最优", sentence):
                continue
            context = prev_text + sentence + next_text
            if not has_claim_support(context):
                hits.append((line, sentence))
    if len(hits) >= 8:
        level = "FAIL"
    elif len(hits) >= 3:
        level = "WARN"
    else:
        return []
    sample = "; ".join(f"L{line}:{compact(text, 50)}" for line, text in hits[:5])
    return [
        Issue(
            level,
            "strong_claim_support_gap",
            "implementation",
            f"{len(hits)} strong optimality/convergence/robustness/significance claim(s) lack nearby proof or experimental support. {sample}",
            "add proof, lower/upper bound, solver gap, convergence/multi-seed evidence, sensitivity table, or weaken the wording to match the evidence.",
            sample,
        )
    ]


def audit_section_chains(sections: list[SectionBlock]) -> list[Issue]:
    issues: list[Issue] = []
    weak_sections = []
    for section in sections:
        title = section.title
        if section.zh_chars < 650:
            continue
        if not re.search(r"问题|模型|建立|求解|算法|结果", title):
            continue
        role_set = set(section.roles)
        if "model" in role_set and "objective" not in role_set and "constraint" not in role_set and section.equations == 0:
            weak_sections.append((section, "model section lacks objective/constraint/equation anchor"))
        if "result" in role_set and "validation" not in role_set and not section.has_table_or_figure:
            weak_sections.append((section, "result section lacks validation/table/figure support"))
    if len(weak_sections) >= 3:
        level = "FAIL"
    elif len(weak_sections) >= 1:
        level = "WARN"
    else:
        return []
    sample = "; ".join(f"L{section.line}:{section.title}({reason})" for section, reason in weak_sections[:5])
    issues.append(
        Issue(
            level,
            "section_logic_chain_gap",
            "modeling",
            f"{len(weak_sections)} substantial section(s) have incomplete model-result-validation chain. {sample}",
            "repair the owning stage: add missing model formulation in modeling, result/validation evidence in implementation, or explicit trace wording in paper.",
            sample,
        )
    )
    return issues


def equation_blocks(text: str) -> list[EquationBlock]:
    line_starts = line_start_offsets(text)
    sections = section_ranges(text)
    equations: list[EquationBlock] = []
    for index, match in enumerate(DISPLAY_MATH_RE.finditer(text), start=1):
        eq_text = match.group("bracket") or match.group("dollar") or match.group("envbody") or ""
        start = match.start()
        line = line_number(line_starts, start)
        section = section_for_offset(sections, start)
        context = nearby_context(text, start, match.end(), chars=700)
        label_match = re.search(r"\\label\{([^}]+)\}", eq_text)
        role = infer_equation_role(eq_text, context)
        equations.append(
            EquationBlock(
                index=index,
                line=line,
                section=section,
                text=compact(clean_equation(eq_text), 180),
                label=label_match.group(1) if label_match else "",
                role=role,
                symbols=sorted(extract_symbols(eq_text)),
                explained_nearby=has_equation_explanation(context),
                source_hint_nearby=has_constraint_source_hint(context),
            )
        )
    return equations


def section_blocks(text: str) -> list[SectionBlock]:
    matches = list(SECTION_RE.finditer(text))
    ranges = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = clean_text(match.group("title") or match.group("mdtitle") or "")
        ranges.append((start, end, title, match.start()))
    line_starts = line_start_offsets(text)
    out = []
    for start, end, title, title_offset in ranges:
        block = text[start:end]
        clean = clean_text(block)
        roles = section_roles(clean)
        out.append(
            SectionBlock(
                title=title,
                line=line_number(line_starts, title_offset),
                text=compact(clean, 260),
                zh_chars=len(re.findall(r"[\u4e00-\u9fff]", clean)),
                equations=len(DISPLAY_MATH_RE.findall(block)),
                roles=roles,
                has_table_or_figure=bool(re.search(r"\\begin\{(?:table|figure)\}|\\includegraphics|表\s*\d+|图\s*\d+", block)),
            )
        )
    return out


def infer_equation_role(eq_text: str, context: str) -> str:
    combined = eq_text + "\n" + context
    for role in ["objective", "recurrence", "constraint", "definition"]:
        if any(re.search(pattern, combined, flags=re.I) for pattern in ROLE_PATTERNS[role]):
            return role
    return "formula"


def extract_symbols(eq_text: str) -> set[str]:
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit|boldsymbol)\{([^}]*)\}", r"\1", eq_text)
    symbols: set[str] = set()
    for command in re.findall(r"\\([A-Za-z]+)", text):
        if command in GREEK_COMMANDS:
            symbols.add("\\" + command)
        elif command not in IGNORE_COMMANDS:
            continue
    token_re = re.compile(r"(?<![A-Za-z])([A-Za-z](?:\s*[_^]\s*(?:\{[^{}]+\}|[A-Za-z0-9]+)){0,2})(?![A-Za-z])")
    for match in token_re.finditer(text):
        token = normalize_symbol(match.group(1))
        if token and not is_word_token(token):
            symbols.add(token)
    return symbols


def symbol_definition_text(root: Path, body: str) -> str:
    pieces = [read_text(root / "planning" / "symbol_table.md"), read_text(root / "planning" / "modeling_plan.md")]
    for title in ["符号说明", "变量说明", "符号", "变量与参数"]:
        match = re.search(rf"\\section\*?\{{[^}}]*{title}[^}}]*\}}(?P<body>.*?)(?=\\section\*?\{{|$)", body, flags=re.S)
        if match:
            pieces.append(match.group("body"))
    return clean_text("\n".join(pieces))


def symbol_defined(symbol: str, definition_text: str) -> bool:
    raw = symbol
    compact_symbol = re.sub(r"[{}\\\s]", "", symbol)
    compact_defs = re.sub(r"[{}\\\s]", "", definition_text)
    if raw in definition_text or compact_symbol in compact_defs:
        return True
    base = re.sub(r"[_^].*$", "", compact_symbol)
    if len(base) == 1 and re.search(rf"\b{re.escape(base)}\b.*(?:表示|为|代表|变量|参数)", definition_text):
        return True
    return False


def is_trivial_symbol(symbol: str) -> bool:
    compact_symbol = re.sub(r"[{}\\\s]", "", symbol)
    if compact_symbol in {"i", "j", "k", "t", "n", "m", "N", "M", "T", "K"}:
        return True
    if compact_symbol.isdigit():
        return True
    return False


def is_word_token(token: str) -> bool:
    base = re.sub(r"[_^].*$", "", token)
    return len(base) > 1 and "_" not in token and "^" not in token


def normalize_symbol(symbol: str) -> str:
    symbol = re.sub(r"\s+", "", symbol)
    symbol = symbol.replace("\\_", "_")
    return symbol.strip()


def sentence_windows(text: str) -> list[tuple[int, str, str, str]]:
    cleaned = clean_text_preserve_lines(text)
    parts: list[tuple[int, str]] = []
    for line_no, line in enumerate(cleaned.splitlines(), start=1):
        for sentence in re.split(r"(?<=[。！？!?；;])\s*", line):
            sentence = sentence.strip()
            if sentence:
                parts.append((line_no, sentence))
    out: list[tuple[int, str, str, str]] = []
    for idx, (line_no, sentence) in enumerate(parts):
        prev_text = parts[idx - 1][1] if idx > 0 else ""
        next_text = parts[idx + 1][1] if idx + 1 < len(parts) else ""
        out.append((line_no, prev_text, sentence, next_text))
    return out


def section_roles(text: str) -> list[str]:
    roles = []
    role_terms = {
        "model": r"模型|变量|参数|假设|目标函数|约束|公式",
        "objective": r"目标函数|最小化|最大化|优化目标|objective",
        "constraint": r"约束|限制|满足|容量|时间窗|边界|非负|整数",
        "solver": r"求解|算法|迭代|搜索|枚举|规划|仿真|模拟|优化器|solver",
        "result": r"结果|方案|得到|如表|如图|见表|见图|最优|数值",
        "validation": r"验证|检验|灵敏度|敏感性|误差|鲁棒|稳定|基准|对比|残差|收敛",
    }
    for role, pattern in role_terms.items():
        if re.search(pattern, text, flags=re.I):
            roles.append(role)
    return roles


def has_equation_explanation(context: str) -> bool:
    return bool(re.search(r"其中|式中|表示|定义|记为|令|目标|约束|由|根据|可得|转化为|subject to|where|s\.t\.", context, re.I))


def has_constraint_source_hint(context: str) -> bool:
    return bool(re.search(r"题目|实际|容量|时间窗|距离|成本|资源|守恒|边界|上限|下限|非负|整数|假设|要求|不超过|至少|来自|根据", context))


def has_logic_support(context: str) -> bool:
    return bool(re.search(r"\\(?:ref|eqref|cite)\{|表\s*\d+|图\s*\d+|式\s*\(?\d+|\d+(?:\.\d+)?|=|≤|≥|\\leq|\\geq|证明|推导|下界|上界|因此有", context))


def has_claim_support(context: str) -> bool:
    return any(re.search(pattern, context, flags=re.I) for pattern in SUPPORT_PATTERNS)


def collect_paper_files(root: Path, paper_arg: str | None) -> list[Path]:
    if paper_arg:
        path = resolve_path(root, paper_arg)
        return [path] if path.exists() else []
    for rel_path in PAPER_CANDIDATES:
        path = root / rel_path
        if path.exists():
            files = [path]
            section_dir = root / "paper" / "sections"
            if section_dir.exists():
                files.extend(sorted(section_dir.glob("*.tex")))
                files.extend(sorted(section_dir.glob("*.typ")))
                files.extend(sorted(section_dir.glob("*.md")))
            return dedupe(files)
    tex_files = sorted((root / "paper").glob("*.tex")) if (root / "paper").exists() else []
    return dedupe(tex_files[:1])


def body_before_references(text: str) -> str:
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


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def nearby_context(text: str, start: int, end: int, chars: int = 700) -> str:
    left = max(0, start - chars)
    right = min(len(text), end + chars)
    return clean_text(text[left:start] + "\n" + text[end:right])


def clean_equation(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = re.sub(r"\\begin\{(?:equation|align|gather|multline|cases|array)\*?\}.*?\\end\{(?:equation|align|gather|multline|cases|array)\*?\}", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$[^$]+\$|\\\([^)]*\\\)", " MATH ", text, flags=re.S)
    text = re.sub(r"\\(?:ref|eqref|cite)\{[^}]*\}", " REF ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:textbf|textit|emph|mathbf|mathrm|boldsymbol)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_text_preserve_lines(text: str) -> str:
    return "\n".join(clean_text(line) for line in text.splitlines())


def line_start_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def line_number(line_starts: list[int], offset: int) -> int:
    lo, hi = 0, len(line_starts)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid
    return lo + 1


def section_ranges(text: str) -> list[tuple[int, int, str]]:
    matches = list(SECTION_RE.finditer(text))
    ranges = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = clean_text(match.group("title") or match.group("mdtitle") or "")
        ranges.append((start, end, title))
    return ranges


def section_for_offset(ranges: list[tuple[int, int, str]], offset: int) -> str:
    for start, end, title in ranges:
        if start <= offset < end:
            return title
    return ""


def dedupe(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def payload(
    root: Path,
    paper_files: list[Path],
    sections: list[SectionBlock],
    equations: list[EquationBlock],
    issues: list[Issue],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "paper_files": [rel(root, path) for path in paper_files],
        "verdict": verdict(issues),
        "metrics": metrics,
        "findings": [asdict(issue) for issue in issues],
        "equations": [asdict(eq) for eq in equations[:80]],
        "sections": [asdict(section) for section in sections[:80]],
    }


def verdict(issues: list[Issue]) -> str:
    if any(issue.level == "FAIL" for issue in issues):
        return "FAIL"
    if any(issue.level == "WARN" for issue in issues):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Mira Derivation Logic Gate",
        "",
        f"- Generated: {data['generated_at']}",
        f"- Verdict: **{data['verdict']}**",
        f"- Root: `{data['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in data.get("metrics", {}).items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding | Recommendation | Evidence |", "|---|---|---|---|---|---|"])
    if data["findings"]:
        for item in data["findings"]:
            lines.append(
                f"| {item['level']} | {item['axis']} | {item['return_phase']} | {escape(item['finding'])} | {escape(item['recommendation'])} | {escape(item.get('evidence', ''))} |"
            )
    else:
        lines.append("| PASS | derivation_logic | - | no blocking derivation-logic issue detected | keep formula chain explicit | - |")
    lines.extend(["", "## Equation Blocks", "", "| # | Line | Section | Role | Label | Explained | Symbols | Text |", "|---:|---:|---|---|---|---|---|---|"])
    for eq in data["equations"][:40]:
        lines.append(
            f"| {eq['index']} | {eq['line']} | {escape(eq['section'])} | {eq['role']} | `{escape(eq['label'])}` | {eq['explained_nearby']} | {escape(', '.join(eq['symbols'][:10]))} | {escape(eq['text'])} |"
        )
    lines.extend(["", "## Section Chain Samples", "", "| Line | Section | Chars | Equations | Roles | Table/Figure |", "|---:|---|---:|---:|---|---|"])
    for section in data["sections"][:40]:
        lines.append(
            f"| {section['line']} | {escape(section['title'])} | {section['zh_chars']} | {section['equations']} | {escape(', '.join(section['roles']))} | {section['has_table_or_figure']} |"
        )
    lines.append("")
    return "\n".join(lines)


def emit(data: dict[str, Any]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(f"VERDICT: {data['verdict']}")
    print("metrics: " + json.dumps(data.get("metrics", {}), ensure_ascii=False, sort_keys=True))
    for issue in data["findings"]:
        print(f"{issue['level']}: {issue['axis']}: {issue['finding']}")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
