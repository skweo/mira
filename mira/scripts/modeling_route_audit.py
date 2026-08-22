#!/usr/bin/env python3
"""Audit visible modeling route clarity in Mira contest papers.

This gate checks whether the final paper explains the path from the contest
problem to the model and results before it leans on formulas or output tables.
It is deliberately about route clarity, not page count.
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
    "paper/main_contest.tex",
    "paper/main.tex",
    "paper/main.typ",
    "paper/main.md",
    "main.tex",
    "main.typ",
    "main.md",
]

PLANNING_FILES = [
    "planning/problem_analysis.md",
    "planning/modeling_plan.md",
    "planning/method_decision_pack.md",
    "planning/validation_plan.md",
]

SECTION_RE = re.compile(
    r"\\(?P<kind>chapter|section|subsection|subsubsection)\*?\{(?P<title>[^}]*)\}|^#+\s+(?P<mdtitle>.+)$",
    re.M,
)
DISPLAY_MATH_RE = re.compile(
    r"\\\[(?P<bracket>.*?)\\\]|"
    r"\$\$(?P<dollar>.*?)\$\$|"
    r"\\begin\{(?P<env>equation\*?|align\*?|gather\*?|multline\*?|cases|array)\}(?P<envbody>.*?)\\end\{(?P=env)\}",
    re.S,
)
CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}", re.S)
PROBLEM_TOKEN_RE = re.compile(r"(?:问题\s*([一二三四五六七八九十]+|[1-9][0-9]*)|Q\s*([1-9][0-9]*))", re.I)

ROUTE_TITLE_RE = re.compile(
    r"建模思路|技术路线|建模路线|模型路线|求解路线|求解流程|总体思路|总体路线|分析路线|研究路线|模型框架|求解框架"
)
ROUTE_VISUAL_RE = re.compile(
    r"技术路线图|建模流程图|求解流程图|模型框架图|流程图|框图|路线表|技术路线表|流程表|控制链|模型链|输入.*状态.*输出"
)
MODEL_START_RE = re.compile(r"模型建立|建模与求解|模型求解|求解结果|结果分析|模型的建立|模型构建")

ROUTE_ROLE_PATTERNS = {
    "input": r"输入|已知|数据|附件|指标|特征|观测|测量|原始",
    "output": r"输出|结果|答案|决策|预测|评价|策略|方案|指标值",
    "target": r"目标|评价指标|优化|最小|最大|误差|损失|收益|成本|效用",
    "constraints": r"约束|限制|条件|边界|假设|可行|守恒|容量|时间窗|规则",
    "model": r"模型|方程|变量|状态|目标函数|约束式|指标体系|转换|转化|抽象",
    "solver": r"求解|算法|枚举|规划|仿真|模拟|迭代|搜索|优化器|DP|SA|GA|PSO|蒙特卡洛|Monte\s*Carlo",
    "validation": r"验证|检验|灵敏度|敏感性|鲁棒|基准|对比|残差|误差|收敛|可行性",
    "evidence": r"表\s*\d+|图\s*\d+|数据|曲线|矩阵|数值|案例|情景|场景",
}

QUESTION_ROUTE_PATTERNS = {
    "task_contract": r"输入|输出|目标|约束|要求|任务|已知|求解|评价指标",
    "transformation": r"转化|转换|抽象|等价|简化|建模思路|关键|难点|分解|状态",
    "model": r"模型|变量|参数|方程|目标函数|约束|指标体系|状态转移|力学|规划",
    "solver": r"求解|算法|步骤|流程|枚举|迭代|仿真|模拟|搜索|规划|优化器|递推",
    "result": r"结果|得到|方案|策略|预测|排名|参数值|最优|较优|如表|如图",
    "validation": r"验证|检验|灵敏度|敏感性|鲁棒|基准|对比|残差|误差|收敛|可行",
}

CN_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass
class Section:
    title: str
    line: int
    text: str


@dataclass
class RouteSection:
    title: str
    line: int
    roles: list[str]
    text_sample: str


@dataclass
class QuestionRoute:
    label: str
    titles: list[str]
    roles: list[str]
    chars: int


@dataclass
class Issue:
    level: str
    axis: str
    return_phase: str
    finding: str
    recommendation: str
    evidence: str = ""


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paper_files = collect_paper_files(root, args.paper)
    payload = audit(root, paper_files, args.output_level)

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


def audit(root: Path, paper_files: list[Path], output_level: str) -> dict[str, Any]:
    issues: list[Issue] = []
    if not paper_files:
        issues.append(
            Issue(
                "FAIL",
                "modeling_route_source",
                "paper",
                "no paper source found for modeling-route audit",
                "return to paper and create the final paper source before route clarity checks.",
            )
        )
        return make_payload(root, paper_files, [], [], [], issues, {"paper_files": []})

    raw = "\n".join(read_text(path) for path in paper_files)
    body = body_before_references(strip_comments(raw))
    sections = section_blocks(body)
    route_sections = find_route_sections(sections)
    question_routes = find_question_routes(sections, body)
    route_roles = sorted({role for section in route_sections for role in section.roles})
    first_route_line = min((section.line for section in route_sections), default=0)
    first_model_line = first_section_line(sections, MODEL_START_RE)
    formula_lines = display_formula_lines(body)
    formulas_before_route = count_before(formula_lines, first_route_line) if first_route_line else len(formula_lines)
    route_visual_count = count_route_visuals(body)
    planning_roles = planning_route_roles(root)
    contest_final = output_level.strip().lower() == "contest_final"
    multi_question = len(question_routes) >= 2

    if not route_sections:
        issues.append(
            Issue(
                final_level(contest_final, multi_question),
                "modeling_route_missing",
                "analysis",
                "paper has no visible modeling-route section such as `建模思路`, `技术路线`, or `求解流程`",
                "add an early route section or route table that states input -> transformation -> model -> solver -> validation/result before detailed formulas.",
            )
        )
    elif len(route_roles) < 5:
        issues.append(
            Issue(
                "WARN",
                "modeling_route_thin",
                "paper",
                f"route section covers only {len(route_roles)} route roles: {', '.join(route_roles) or 'none'}",
                "rewrite the route paragraph/table so it explicitly names inputs, outputs, objectives/constraints, model, solver, validation, and result evidence.",
                "; ".join(f"L{item.line}:{item.title}" for item in route_sections[:3]),
            )
        )

    if first_route_line and first_model_line and first_route_line > first_model_line:
        issues.append(
            Issue(
                "WARN",
                "modeling_route_late",
                "paper",
                f"first route section appears at line {first_route_line}, after model/result section line {first_model_line}",
                "move the route explanation before detailed model establishment or solver results so readers see the plan before the mechanics.",
            )
        )

    if formulas_before_route >= 4:
        issues.append(
            Issue(
                "WARN",
                "formula_before_route",
                "modeling",
                f"{formulas_before_route} display formula blocks appear before any visible modeling route",
                "insert a modeling-route paragraph/table before heavy formulas, or move early derivations after the route has defined the modeling path.",
            )
        )

    weak_question_routes = [item for item in question_routes if missing_question_roles(item)]
    if multi_question and weak_question_routes:
        missing = "; ".join(
            f"{item.label}: missing {', '.join(missing_question_roles(item))}" for item in weak_question_routes[:5]
        )
        level = "FAIL" if contest_final and len(weak_question_routes) >= 2 else "WARN"
        issues.append(
            Issue(
                level,
                "per_question_route_gap",
                "analysis",
                f"{len(weak_question_routes)} subquestion route(s) do not expose a complete task/model/solver/result/validation path",
                "for each official question, add a short route card: input/output, modeling transformation, chosen model, solver, result evidence, and validation plan.",
                missing,
            )
        )

    if multi_question and route_visual_count == 0:
        issues.append(
            Issue(
                "WARN",
                "route_visual_or_table_gap",
                "implementation",
                "multi-question paper has no detected technical route diagram or route table",
                "add a compact technical route diagram or route table when it improves readability; a clear table is enough if a diagram would be decorative.",
            )
        )

    if contest_final and not planning_roles:
        issues.append(
            Issue(
                "WARN",
                "planning_route_gap",
                "analysis",
                "planning artifacts do not expose modeling-route roles before paper writing",
                "update planning/problem_analysis.md or planning/modeling_plan.md with per-question route cards so paper is not inventing the route late.",
            )
        )

    metrics = {
        "paper_files": [rel(root, path) for path in paper_files],
        "section_count": len(sections),
        "detected_questions": [route.label for route in question_routes],
        "route_sections": len(route_sections),
        "route_roles": route_roles,
        "first_route_line": first_route_line,
        "first_model_or_result_line": first_model_line,
        "display_formulas": len(formula_lines),
        "formulas_before_route": formulas_before_route,
        "route_visual_or_table_count": route_visual_count,
        "planning_route_roles": planning_roles,
        "warnings": sum(1 for issue in issues if issue.level == "WARN"),
        "failures": sum(1 for issue in issues if issue.level == "FAIL"),
    }
    return make_payload(root, paper_files, sections, route_sections, question_routes, issues, metrics)


def final_level(contest_final: bool, multi_question: bool) -> str:
    return "FAIL" if contest_final and multi_question else "WARN"


def missing_question_roles(item: QuestionRoute) -> list[str]:
    required = ["task_contract", "transformation", "model", "solver", "result", "validation"]
    missing = [role for role in required if role not in item.roles]
    if "model" in missing or "solver" in missing:
        return missing
    if len(missing) >= 2:
        return missing
    return []


def find_route_sections(sections: list[Section]) -> list[RouteSection]:
    route_sections: list[RouteSection] = []
    for section in sections:
        if ROUTE_TITLE_RE.search(section.title):
            route_sections.append(
                RouteSection(
                    title=section.title,
                    line=section.line,
                    roles=route_roles(section.text),
                    text_sample=compact(clean_text(section.text), 220),
                )
            )
    return route_sections


def find_question_routes(sections: list[Section], body: str) -> list[QuestionRoute]:
    labels = ordered_question_labels(body)
    routes: list[QuestionRoute] = []
    main_body = body_from_first_section(body)
    for label in labels:
        blocks = [section for section in sections if label_matches_section(label, section.title)]
        mention_blocks = mention_windows(main_body, label)
        if not blocks and not mention_blocks:
            continue
        text = "\n".join([block.text for block in blocks] + mention_blocks)
        roles = question_roles(text)
        routes.append(
            QuestionRoute(
                label=label,
                titles=[block.title for block in blocks] or ["nearby question mentions"],
                roles=roles,
                chars=len(re.findall(r"[\u4e00-\u9fff]", clean_text(text))),
            )
        )
    return routes


def ordered_question_labels(text: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for match in PROBLEM_TOKEN_RE.finditer(clean_text(text)):
        value = match.group(1) or match.group(2) or ""
        number = int(value) if value.isdigit() else CN_NUMBERS.get(value)
        if not number:
            continue
        label = f"Q{number}"
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels[:8]


def label_matches_section(label: str, title: str) -> bool:
    number = int(label[1:])
    cn = next((key for key, value in CN_NUMBERS.items() if value == number), "")
    compact_title = re.sub(r"\s+", "", title)
    return bool(
        re.search(rf"问题(?:{cn}|{number})", compact_title)
        or re.search(rf"\bQ\s*{number}\b", title, flags=re.I)
    )


def mention_windows(text: str, label: str, radius: int = 900) -> list[str]:
    pattern = question_label_pattern(label)
    windows: list[str] = []
    for match in pattern.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        windows.append(text[start:end])
    return windows[:8]


def question_label_pattern(label: str) -> re.Pattern[str]:
    number = int(label[1:])
    cn = next((key for key, value in CN_NUMBERS.items() if value == number), "")
    parts = [rf"Q\s*{number}(?![0-9])", rf"问题\s*{number}(?![0-9])"]
    if cn:
        parts.append(rf"问题\s*{cn}(?![一二三四五六七八九十])")
    return re.compile(r"(?:" + "|".join(parts) + r")", re.I)


def body_from_first_section(text: str) -> str:
    match = SECTION_RE.search(text)
    return text[match.start() :] if match else text


def route_roles(text: str) -> list[str]:
    clean = clean_text(text)
    return sorted(role for role, pattern in ROUTE_ROLE_PATTERNS.items() if re.search(pattern, clean, flags=re.I))


def question_roles(text: str) -> list[str]:
    clean = clean_text(text)
    return sorted(role for role, pattern in QUESTION_ROUTE_PATTERNS.items() if re.search(pattern, clean, flags=re.I))


def count_route_visuals(text: str) -> int:
    count = len(ROUTE_VISUAL_RE.findall(clean_text(text)))
    for caption in CAPTION_RE.findall(text):
        if ROUTE_TITLE_RE.search(clean_text(caption)) or ROUTE_VISUAL_RE.search(clean_text(caption)):
            count += 1
    return count


def planning_route_roles(root: Path) -> list[str]:
    text = "\n".join(read_text(root / rel_path) for rel_path in PLANNING_FILES)
    if not text.strip():
        return []
    return route_roles(text)


def section_blocks(text: str) -> list[Section]:
    matches = list(SECTION_RE.finditer(text))
    line_starts = line_start_offsets(text)
    sections: list[Section] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = clean_text(match.group("title") or match.group("mdtitle") or "")
        if not title:
            continue
        sections.append(Section(title=title, line=line_number(line_starts, start), text=text[start:end]))
    if not sections:
        sections.append(Section(title="paper_body", line=1, text=text))
    return sections


def first_section_line(sections: list[Section], pattern: re.Pattern[str]) -> int:
    return min((section.line for section in sections if pattern.search(section.title)), default=0)


def display_formula_lines(text: str) -> list[int]:
    line_starts = line_start_offsets(text)
    return [line_number(line_starts, match.start()) for match in DISPLAY_MATH_RE.finditer(text)]


def count_before(lines: list[int], line: int) -> int:
    return sum(1 for item in lines if item < line)


def body_before_references(text: str) -> str:
    cut_patterns = [
        r"\\appendix\b",
        r"\\begin\{thebibliography\}",
        r"\\(?:chapter|section)\*?\{(?:参考文献|References|附录|Appendix)[^}]*\}",
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


def clean_text(text: str) -> str:
    text = re.sub(r"\\begin\{(?:equation|align|gather|multline|cases|array)\*?\}.*?\\end\{(?:equation|align|gather|multline|cases|array)\*?\}", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " EQUATION ", text, flags=re.S)
    text = re.sub(r"\$[^$]+\$|\\\([^)]*\\\)", " MATH ", text, flags=re.S)
    text = re.sub(r"\\(?:ref|eqref|cite)\{[^}]*\}", " REF ", text)
    text = re.sub(r"\\(?:chapter|section|subsection|subsubsection)\*?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:textbf|textit|emph|mathbf|mathrm|boldsymbol)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


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


def make_payload(
    root: Path,
    paper_files: list[Path],
    sections: list[Section],
    route_sections: list[RouteSection],
    question_routes: list[QuestionRoute],
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
        "route_sections": [asdict(item) for item in route_sections],
        "question_routes": [asdict(item) for item in question_routes],
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
        "# Mira 0.8.1 Modeling Route Audit",
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
        lines.append("| PASS | modeling_route | - | visible modeling route is adequate | keep route close to model/result sections | - |")
    lines.extend(["", "## Route Sections", "", "| Line | Title | Roles | Sample |", "|---:|---|---|---|"])
    for item in data.get("route_sections", []):
        lines.append(f"| {item['line']} | {escape(item['title'])} | {escape(', '.join(item['roles']))} | {escape(item['text_sample'])} |")
    lines.extend(["", "## Per-Question Route Coverage", "", "| Question | Chars | Roles | Section titles |", "|---|---:|---|---|"])
    for item in data.get("question_routes", []):
        lines.append(f"| {item['label']} | {item['chars']} | {escape(', '.join(item['roles']))} | {escape('; '.join(item['titles']))} |")
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
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


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


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper", help="Paper tex/typ/md path")
    parser.add_argument("--output-level", default="contest_final", help="quick_draft, reproducible_draft, or contest_final")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
