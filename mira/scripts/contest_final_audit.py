#!/usr/bin/env python3
"""Authoritative audit for Mira's canonical XeLaTeX contest-final PDF."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow_stages import normalize_stage_path

from delivery_contract import (
    BUILD_ENGINE,
    CANONICAL_PDF,
    CANONICAL_SOURCE,
    DeliveryContractError,
    canonical_pdf,
    canonical_source,
    collect_source_files,
    load_manifest,
    relative,
    verify_hashes,
)
from paper_scope import page_has_heading_marker


BODY_PAGE_MIN = 23
BODY_PAGE_MAX = 30
BODY_START_TERMS = (
    "题意边界与回答口径",
    "问题重述",
    "问题分析",
    "符号说明",
    "模型假设",
    "problem restatement",
)
BODY_STOP_TERMS = ("参考文献", "附录", "references", "bibliography", "appendix")
FIGURE_PRELUDE_TERMS = ("如图", "见图", "图中", "为了展示", "为比较", "可视化", "下图")
FIGURE_CONCLUSION_TERMS = (
    "由图",
    "从图",
    "图中可见",
    "图表明",
    "说明",
    "表明",
    "可知",
    "因此",
    "这意味着",
)
FLOW_TERMS = ("技术路线", "总体流程", "求解流程", "算法流程", "验证流程", "flowchart", "workflow")
LOW_INFO_TEXT_CHARS = 80
CITATION_BINDING_FIELDS = (
    "claim_id",
    "claim_type",
    "paper_location",
    "citation_key",
    "source_type",
    "support_scope",
    "used_for",
)


@dataclass
class Finding:
    level: str
    code: str
    message: str
    owner_phase: str
    return_to: str
    evidence: str = ""


class ContestFinalAuditor:
    def __init__(self, root: Path | str, render_dir: Path | str | None = None) -> None:
        self.root = Path(root).resolve()
        self.source = canonical_source(self.root)
        self.pdf = canonical_pdf(self.root)
        self.render_dir = Path(render_dir).resolve() if render_dir else self.root / "output" / "contest_final" / "rendered"
        self.manifest: dict[str, Any] = {}
        self.source_files: list[Path] = []
        self.source_text = ""
        self.pages: list[str] = []
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        self._load_contract()
        if self.source.is_file():
            self.source_files = collect_source_files(self.root)
            self.source_text = "\n".join(read_text(path) for path in self.source_files)
        if self.pdf.is_file():
            self.pages = extract_pdf_pages(self.pdf, self._fail_pdf)
        self._audit_contract()
        self._audit_front_matter()
        self._audit_page_scope()
        self._audit_title_color()
        self._audit_tables()
        self._audit_math()
        self._audit_references()
        self._audit_figures_and_flowcharts()
        self._audit_rendered_pages()
        blockers = [asdict(item) for item in self.findings if item.level == "FAIL"]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "root": str(self.root),
            "profile": "contest_final",
            "batch_id": self.manifest.get("batch_id", ""),
            "source": CANONICAL_SOURCE,
            "pdf": CANONICAL_PDF,
            "verdict": "FAIL" if blockers else "PASS",
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
            "blockers": blockers,
        }

    def fail(self, code: str, message: str, owner_phase: str, return_to: str, evidence: str = "") -> None:
        self.findings.append(
            Finding(
                "FAIL",
                code,
                message,
                normalize_stage_path(owner_phase, "paper"),
                normalize_stage_path(return_to, "paper"),
                evidence,
            )
        )

    def warn(self, code: str, message: str, owner_phase: str, return_to: str, evidence: str = "") -> None:
        self.findings.append(
            Finding(
                "WARN",
                code,
                message,
                normalize_stage_path(owner_phase, "paper"),
                normalize_stage_path(return_to, "paper"),
                evidence,
            )
        )

    def _fail_pdf(self, message: str) -> None:
        self.fail("pdf_read", message, "paper", "paper", CANONICAL_PDF)

    def _load_contract(self) -> None:
        try:
            self.manifest = load_manifest(self.root)
        except DeliveryContractError as exc:
            self.fail("delivery_manifest", str(exc), "paper", "paper", "planning/delivery_manifest.json")
            self.manifest = {}

    def _audit_contract(self) -> None:
        self.metrics.update(
            {
                "manifest_status": self.manifest.get("status", "missing"),
                "build_engine": self.manifest.get("build_engine", "missing"),
                "source_exists": self.source.is_file(),
                "pdf_exists": self.pdf.is_file(),
                "pdf_page_count": len(self.pages) if self.pages else None,
            }
        )
        if self.manifest and self.manifest.get("status") != "BUILT":
            self.fail(
                "delivery_state",
                f"authoritative audit requires BUILT, got {self.manifest.get('status')}",
                "paper",
                "paper",
                "planning/delivery_manifest.json",
            )
        if self.manifest and self.manifest.get("build_engine") != BUILD_ENGINE:
            self.fail("build_engine", "contest_final accepts XeLaTeX only", "paper", "paper")
        if not self.source.is_file():
            self.fail("canonical_source", f"missing {CANONICAL_SOURCE}", "paper", "paper")
        elif self.source.suffix.lower() != ".tex":
            self.fail("canonical_source", "contest_final source must be LaTeX", "paper", "paper")
        if not self.pdf.is_file():
            self.fail("canonical_pdf", f"missing {CANONICAL_PDF}", "paper", "paper")
        if self.manifest:
            for error in verify_hashes(self.root, self.manifest):
                self.fail("artifact_hash", error, "paper", "paper", "planning/delivery_manifest.json")

    def _audit_front_matter(self) -> None:
        text = strip_comments(self.source_text)
        abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
        has_toc = "\\tableofcontents" in text
        self.metrics["has_abstract_environment"] = bool(abstract)
        self.metrics["has_table_of_contents"] = has_toc
        if not abstract:
            self.fail("abstract_missing", "摘要必须使用独立的 abstract 环境", "paper", "paper")
        else:
            content = abstract.group(1)
            labels = unique_problem_labels(content)
            bold_labels = unique_problem_labels(" ".join(re.findall(r"\\textbf\s*\{([^{}]*)\}", content)))
            paragraphs = [part for part in re.split(r"(?:\n\s*\n|\\par\b)", content) if visible_tex(part).strip()]
            required_axes = {
                "method": ("模型", "方法", "算法", "建立", "采用"),
                "result": ("结果", "得到", "为", "达到", "误差"),
                "validation": ("验证", "检验", "残差", "敏感性", "稳健"),
                "boundary": ("边界", "适用", "局限", "误差", "条件"),
            }
            self.metrics.update(
                {
                    "abstract_problem_labels": len(labels),
                    "abstract_bold_problem_labels": len(bold_labels),
                    "abstract_paragraphs": len(paragraphs),
                }
            )
            if len(labels) >= 2 and len(bold_labels) < len(labels):
                self.fail("abstract_emphasis", "摘要中的每个问题标签必须加粗", "paper", "paper")
            if len(labels) >= 2 and len(paragraphs) < len(labels):
                self.fail("abstract_structure", "摘要必须按问题分段陈述", "paper", "paper")
            for axis, terms in required_axes.items():
                if not any(term in visible_tex(content) for term in terms):
                    self.fail("abstract_coverage", f"摘要缺少 {axis} 信息", "paper", "paper", axis)
            tail = text[abstract.end() : abstract.end() + 700]
            if not re.search(r"关键词|key\s*words?", tail, flags=re.I):
                self.fail("abstract_keywords", "摘要页缺少关键词", "paper", "paper")
            if not re.search(r"\\(?:newpage|clearpage)\b", tail):
                self.fail("abstract_page_break", "摘要与后续内容之间必须显式分页", "paper", "paper")
        if not has_toc:
            self.fail("toc_missing", "contest_final 必须包含独立目录", "paper", "paper")
        if self.pages:
            abstract_pages = [index + 1 for index, page in enumerate(self.pages) if "摘要" in page and "关键词" in page]
            toc_pages = self._toc_pages()
            body_start = self._body_start_index(toc_pages)
            body_pages = list(range(body_start + 1, len(self.pages) + 1)) if body_start is not None else []
            self.metrics.update(
                {
                    "abstract_pages": abstract_pages,
                    "toc_pages": toc_pages,
                    "detected_body_start_page": body_start + 1 if body_start is not None else None,
                }
            )
            if len(abstract_pages) != 1:
                self.fail("abstract_pdf_page", "终稿 PDF 中摘要必须恰好独占一页", "paper", "paper", str(abstract_pages))
            elif abstract_pages[0] in body_pages or abstract_pages[0] in toc_pages:
                self.fail("abstract_pdf_page", "摘要页不得与目录或正文共页", "paper", "paper", str(abstract_pages[0]))
            if not toc_pages:
                self.fail("toc_pdf_page", "终稿 PDF 未检测到目录页", "paper", "paper")
            elif any(page in body_pages or page in abstract_pages for page in toc_pages):
                self.fail("toc_pdf_page", "目录必须与摘要和正文分离", "paper", "paper", str(toc_pages))

    def _audit_page_scope(self) -> None:
        if not self.pages:
            self.metrics["effective_body_pages"] = None
            return
        toc_pages = self._toc_pages()
        start = self._body_start_index(toc_pages)
        stop = next(
            (
                i
                for i, text in enumerate(self.pages)
                if start is not None and i > start and page_has_heading_marker(text, BODY_STOP_TERMS)
            ),
            None,
        )
        if start is None:
            self.metrics.update({"effective_body_pages": None, "body_start_page": None, "body_stop_page": None})
            self.fail("body_page_classification", "无法从 PDF 识别正文起始页", "paper", "paper")
            return
        end = (stop - 1) if stop is not None else len(self.pages) - 1
        effective = max(0, end - start + 1)
        self.metrics.update(
            {
                "effective_body_pages": effective,
                "body_start_page": start + 1,
                "body_end_page": end + 1,
                "body_stop_page": stop + 1 if stop is not None else None,
            }
        )
        if effective < BODY_PAGE_MIN or effective > BODY_PAGE_MAX:
            self.fail(
                "effective_body_pages",
                f"有效正文为 {effective} 页，默认要求 {BODY_PAGE_MIN}-{BODY_PAGE_MAX} 页",
                "paper",
                "implementation",
                f"PDF pages {start + 1}-{end + 1}",
            )
        low_info = []
        for page_no in range(start, end + 1):
            chars = len(re.sub(r"\s+", "", self.pages[page_no]))
            if chars < LOW_INFO_TEXT_CHARS:
                low_info.append(page_no + 1)
        self.metrics["low_information_body_pages"] = low_info
        if low_info:
            self.fail(
                "low_information_pages",
                "正文存在低信息页，不计作有效篇幅",
                "paper",
                "implementation",
                ", ".join(map(str, low_info)),
            )

    def _body_start_index(self, toc_pages: list[int] | None = None) -> int | None:
        """Return the first body marker strictly after the final TOC page."""
        if toc_pages is None:
            toc_pages = self._toc_pages()
        search_from = max(toc_pages, default=0)
        return next(
            (
                index
                for index, text in enumerate(self.pages)
                if index >= search_from and contains_any(text, BODY_START_TERMS)
            ),
            None,
        )

    def _toc_pages(self) -> list[int]:
        """Return pages whose extracted text contains a TOC heading."""
        return [
            index + 1
            for index, page in enumerate(self.pages)
            if page_has_heading_marker(page, ("目录", "contents"))
        ]

    def _audit_title_color(self) -> None:
        text = strip_comments(self.source_text)
        suspicious: list[str] = []
        for match in re.finditer(r"\\(?:title|section|subsection|subsubsection)\*?\s*\{([^{}]*)\}", text):
            block = match.group(1)
            if re.search(r"\\(?:color|textcolor)\s*\{(?!black\b)[^}]+\}", block, flags=re.I):
                suspicious.append(block[:100])
        heading_custom = re.findall(r"\\titleformat.*?(?=\n\s*\n|\\begin\{document\})", text, flags=re.S)
        for block in heading_custom:
            if re.search(r"\\(?:color|textcolor)\s*\{(?!black\b)[^}]+\}", block, flags=re.I):
                suspicious.append("titleformat")
        document_title = text[: text.find("\\begin{abstract}") if "\\begin{abstract}" in text else 2500]
        if re.search(r"\\(?:color|textcolor)\s*\{(?!black\b)[^}]+\}[^\n]{0,300}(?:\\maketitle|\\zihao|\\Huge|\\huge)", document_title, flags=re.I):
            suspicious.append("front-title")
        self.metrics["colored_title_heading_signals"] = suspicious
        if suspicious:
            self.fail("title_color", "标题和章节标题必须为纯黑色", "paper", "paper", "; ".join(suspicious[:5]))

    def _audit_tables(self) -> None:
        text = strip_comments(self.source_text)
        blocks = re.findall(r"\\begin\{(?:table\*?|longtable)\}.*?\\end\{(?:table\*?|longtable)\}", text, flags=re.S)
        self.metrics["formal_table_count"] = len(blocks)
        self.metrics["uses_booktabs"] = package_loaded(text, "booktabs")
        if blocks and not self.metrics["uses_booktabs"]:
            self.fail("booktabs_package", "正式表格必须加载 booktabs", "paper", "paper")
        invalid = []
        for index, block in enumerate(blocks, start=1):
            if not all(rule in block for rule in ("\\toprule", "\\midrule", "\\bottomrule")):
                invalid.append(f"table {index}: missing booktabs triplet")
            if "\\hline" in block:
                invalid.append(f"table {index}: uses hline")
            if re.search(r"\\begin\{(?:tabular\*?|tabularx|longtable)\}(?:\{[^}]*\})?\s*\{[^}]*\|", block):
                invalid.append(f"table {index}: vertical rule")
            if not re.search(r"\\caption(?:\[[^\]]*\])?\s*\{", block):
                invalid.append(f"table {index}: missing caption")
        if invalid:
            self.fail("three_line_tables", "所有正式表格必须为无竖线三线表", "paper", "paper", "; ".join(invalid[:12]))
        markdown_rows = len(re.findall(r"(?m)^\s*\|.+\|\s*$", text))
        self.metrics["markdown_table_rows"] = markdown_rows
        if markdown_rows:
            self.fail("markdown_tables", "XeLaTeX 终稿源文件中不得残留 Markdown 表格", "paper", "paper", str(markdown_rows))

    def _audit_math(self) -> None:
        text = strip_comments(self.source_text)
        naked = naked_math_tokens(text)
        self.metrics["naked_math_token_count"] = len(naked)
        if naked:
            self.fail(
                "math_mode",
                "检测到数学环境外的下标或指数符号",
                "paper",
                "paper",
                "; ".join(naked[:12]),
            )
        if text.count("$") % 2:
            self.fail("math_delimiter", "存在未闭合的 $ 数学环境", "paper", "paper")
        for left, right, name in (("\\(", "\\)", "inline"), ("\\[", "\\]", "display")):
            if text.count(left) != text.count(right):
                self.fail("math_delimiter", f"存在未闭合的 {name} 数学环境", "paper", "paper")
        defined = set(re.findall(r"(?:其中|式中|令|记)\s*\$?([A-Za-z][A-Za-z0-9]*)", visible_tex(text)))
        equation_count = len(re.findall(r"\\begin\{(?:equation|align|gather|multline)\*?\}", text))
        self.metrics.update({"numbered_equation_environments": equation_count, "defined_symbol_signals": len(defined)})

    def _audit_references(self) -> None:
        text = strip_comments(self.source_text)
        cite_groups = re.findall(r"\\(?:cite|parencite|textcite|supercite)(?:\[[^\]]*\])?\s*\{([^}]+)\}", text)
        cited = {key.strip() for group in cite_groups for key in group.split(",") if key.strip()}
        bib_keys: set[str] = set()
        for path in self.source_files:
            if path.suffix.lower() == ".bib":
                bib_keys.update(re.findall(r"@\w+\s*\{\s*([^,\s]+)", read_text(path)))
        bib_keys.update(re.findall(r"\\bibitem(?:\[[^\]]*\])?\s*\{([^}]+)\}", text))
        unresolved = sorted(cited - bib_keys)
        orphan = sorted(bib_keys - cited)
        self.metrics.update(
            {
                "citation_key_count": len(cited),
                "bibliography_entry_count": len(bib_keys),
                "unresolved_citations": unresolved,
                "orphan_references": orphan,
            }
        )
        if not cited:
            self.fail("citations_missing", "正文没有真实文献引用", "paper", "paper")
        if unresolved:
            self.fail("unresolved_citations", "存在未解析的引用键", "paper", "paper", ", ".join(unresolved))
        if orphan:
            self.fail("orphan_references", "参考文献表存在正文未引用条目", "paper", "paper", ", ".join(orphan))
        uses_gbt_numeric_bst = bool(
            re.search(r"\\bibliographystyle\s*\{\s*(?:gbt?7714|gb7714)[^}]*numerical[^}]*\}", text, flags=re.I)
        )
        if not re.search(r"(?:gbt?7714|gb7714)[^}\],]*", text, flags=re.I):
            self.fail("bibliography_style", "参考文献必须采用 GB/T 7714-2015 数字顺序制", "paper", "paper")
        incompatible_cite = uses_gbt_numeric_bst and package_loaded(text, "cite") and not package_loaded(text, "natbib")
        self.metrics["gbt_numeric_citation_config"] = {
            "uses_gbt_numeric_bst": uses_gbt_numeric_bst,
            "loads_natbib": package_loaded(text, "natbib"),
            "loads_cite": package_loaded(text, "cite"),
            "compatible": not incompatible_cite,
        }
        if incompatible_cite:
            self.fail(
                "bibliography_numeric_config",
                "gbt7714-numerical 必须使用兼容的数字引用配置；cite 会直接显示作者—年份可选标签",
                "paper",
                "paper",
                r"replace \\usepackage{cite} with \\usepackage[numbers,sort&compress]{natbib}",
            )
        pdf_text = "\n".join(self.pages)
        author_year_labels = sorted(
            set(
                re.findall(
                    r"(?m)^\s*(\[\s*[^\]\d][^\]]*\(\s*(?:18|19|20)\d{2}[a-z]?\s*\)[^\]]*\])",
                    pdf_text,
                    flags=re.I,
                )
            )
        )
        self.metrics["pdf_author_year_bibliography_labels"] = author_year_labels[:12]
        if author_year_labels:
            self.fail(
                "bibliography_pdf_labels",
                "终稿 PDF 的参考文献仍显示作者—年份标签，未形成数字顺序编号",
                "paper",
                "paper",
                "; ".join(author_year_labels[:6]),
            )
        binding_path = self.root / "planning" / "citation_bindings.json"
        binding_errors: list[str] = []
        bound_keys: set[str] = set()
        if cited and not binding_path.is_file():
            binding_errors.append("missing planning/citation_bindings.json")
        elif cited:
            try:
                payload = json.loads(read_text(binding_path))
            except (OSError, json.JSONDecodeError) as exc:
                binding_errors.append(f"invalid JSON: {exc}")
                payload = None
            if isinstance(payload, dict):
                if payload.get("version") != 1:
                    binding_errors.append("version must be 1")
                bindings = payload.get("bindings")
            else:
                bindings = None
            if not isinstance(bindings, list) or not bindings:
                binding_errors.append("bindings must be a non-empty list")
                bindings = []
            for index, item in enumerate(bindings, start=1):
                prefix = f"binding {index}"
                if not isinstance(item, dict):
                    binding_errors.append(f"{prefix}: record must be an object")
                    continue
                missing = [field for field in CITATION_BINDING_FIELDS if not str(item.get(field) or "").strip()]
                if missing:
                    binding_errors.append(f"{prefix}: missing {', '.join(missing)}")
                    continue
                key = str(item["citation_key"]).strip()
                bound_keys.add(key)
                if key not in cited:
                    binding_errors.append(f"{prefix}: citation key is not cited: {key}")
                claim_id = str(item["claim_id"]).strip()
                if not re.fullmatch(r"CLM-[A-Z0-9-]+", claim_id, flags=re.I):
                    binding_errors.append(f"{prefix}: invalid claim_id: {claim_id}")
                location = str(item["paper_location"]).strip()
                location_match = re.fullmatch(r"(.+):(\d+)", location)
                if not location_match:
                    binding_errors.append(f"{prefix}: paper_location must be relative/path.tex:line")
                    continue
                location_path = (self.root / location_match.group(1)).resolve()
                try:
                    location_path.relative_to(self.root)
                except ValueError:
                    binding_errors.append(f"{prefix}: paper_location escapes the project root")
                    continue
                if not location_path.is_file():
                    binding_errors.append(f"{prefix}: paper source does not exist: {location_match.group(1)}")
                    continue
                line_number = int(location_match.group(2))
                lines = read_text(location_path).splitlines()
                if line_number < 1 or line_number > len(lines):
                    binding_errors.append(f"{prefix}: line {line_number} is outside the source file")
                    continue
                if not citation_key_on_line(lines[line_number - 1], key):
                    binding_errors.append(f"{prefix}: {key} is not cited on {location}")
        missing_bindings = sorted(cited - bound_keys)
        if missing_bindings:
            binding_errors.append(f"unbound cited keys: {', '.join(missing_bindings)}")
        self.metrics.update(
            {
                "citation_binding_count": len(bound_keys),
                "unbound_citation_keys": missing_bindings,
                "citation_binding_errors": binding_errors,
            }
        )
        if binding_errors:
            self.fail(
                "citation_binding",
                "引用绑定表必须覆盖每个正文引用并指向真实引用行",
                "modeling",
                "modeling",
                "; ".join(binding_errors[:12]),
            )

    def _audit_figures_and_flowcharts(self) -> None:
        text = strip_comments(self.source_text)
        matches = list(re.finditer(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", text, flags=re.S))
        invalid: list[str] = []
        flow_count = 0
        for index, match in enumerate(matches, start=1):
            block = match.group(1)
            caption_argument = latex_command_argument(block, "caption")
            caption = visible_tex(caption_argument) if caption_argument is not None else ""
            graphic = " ".join(extract_graphic_paths(block))
            label_match = re.search(r"\\label\s*\{([^}]+)\}", block)
            label = label_match.group(1).strip() if label_match else ""
            if caption_argument is None:
                invalid.append(f"figure {index}: missing caption")
            if not label:
                invalid.append(f"figure {index}: missing label")
            if not graphic:
                invalid.append(f"figure {index}: missing includegraphics")
            before_raw = text[max(0, match.start() - 900) : match.start()]
            after_raw = text[match.end() : match.end() + 1200]
            before = visible_tex(before_raw)
            after = visible_tex(after_raw)
            prelude_bound = bool(label and figure_reference_present(before_raw, label))
            conclusion_bound = bool(label and figure_reference_present(after_raw, label))
            prelude_ok = (prelude_bound and len(before.strip()) >= 8) or contains_any(before, FIGURE_PRELUDE_TERMS)
            conclusion_ok = (conclusion_bound and len(after.strip()) >= 8) or contains_any(after, FIGURE_CONCLUSION_TERMS)
            if not prelude_ok:
                invalid.append(f"figure {index}: missing pre-figure guidance")
            if not conclusion_ok:
                invalid.append(f"figure {index}: missing post-figure interpretation")
            normalized_graphic = graphic.replace("\\", "/").lower()
            graphic_parts = {
                part for part in normalized_graphic.split("/") if part not in {"", ".", ".."}
            }
            indexed_as_diagram = bool(
                graphic_parts.intersection({"diagram", "diagrams", "flowchart", "flowcharts"})
            )
            if indexed_as_diagram or contains_any(caption + " " + graphic, FLOW_TERMS):
                flow_count += 1
        self.metrics.update({"figure_count": len(matches), "flowchart_figure_count": flow_count})
        if invalid:
            self.fail("figure_narrative", "主图必须具有图题、标签、图前引导和图后结论", "implementation", "implementation", "; ".join(invalid[:16]))
        problem_count = max(len(unique_problem_labels(text)), infer_q_count(text))
        self.metrics["problem_count_signal"] = problem_count
        intent = self.root / "planning" / "diagram_intent_pack.json"
        explicit_opportunity = False
        if intent.is_file():
            explicit_opportunity = contains_any(read_text(intent), FLOW_TERMS + ("shared", "dependency", "validation"))
        flow_opportunity = problem_count >= 3 or explicit_opportunity
        self.metrics["flowchart_opportunity"] = flow_opportunity
        if flow_opportunity and flow_count == 0:
            self.fail("flowchart_missing", "复杂多问题论文缺少具有信息价值的总体技术路线图", "implementation", "implementation")

    def _audit_rendered_pages(self) -> None:
        if not self.pdf.is_file():
            return
        images = sorted(self.render_dir.glob("page-*.png")) if self.render_dir.is_dir() else []
        self.metrics["rendered_page_count"] = len(images)
        if len(images) != len(self.pages):
            self.fail(
                "page_render",
                "逐页渲染数量与 PDF 页数不一致",
                "paper",
                "paper",
                f"rendered={len(images)}, pdf={len(self.pages)}",
            )
            return
        try:
            from PIL import Image, ImageStat
        except ImportError:
            self.fail("page_render", "Pillow 不可用，无法执行逐页视觉审计", "paper", "paper")
            return
        blank_pages: list[int] = []
        clipped_pages: list[int] = []
        colored_heading_pages: list[int] = []
        heading_bands = extract_pdf_heading_bands(
            self.pdf,
            declared_heading_numbers(self.source_text),
            int(self.metrics.get("body_start_page") or 2),
        )
        heading_region_ratios: dict[str, list[float]] = {}
        for index, path in enumerate(images, start=1):
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                gray = rgb.convert("L")
                stat = ImageStat.Stat(gray)
                mean = stat.mean[0]
                stddev = stat.stddev[0]
                if mean > 250.0 and stddev < 8.0:
                    blank_pages.append(index)
                width, height = rgb.size
                edge = max(2, min(width, height) // 500)
                bands = [
                    gray.crop((0, 0, width, edge)),
                    gray.crop((0, height - edge, width, height)),
                    gray.crop((0, 0, edge, height)),
                    gray.crop((width - edge, 0, width, height)),
                ]
                if any(dark_pixel_ratio(band) > 0.02 for band in bands):
                    clipped_pages.append(index)
                ratios = heading_color_ratios(rgb, heading_bands.get(index, []))
                if ratios:
                    heading_region_ratios[str(index)] = ratios
                if any(ratio > 0.001 for ratio in ratios):
                    colored_heading_pages.append(index)
        self.metrics.update(
            {
                "blank_rendered_pages": blank_pages,
                "edge_clipping_pages": clipped_pages,
                "colored_heading_page_signals": colored_heading_pages,
                "pdf_heading_region_count": sum(len(items) for items in heading_bands.values()),
                "pdf_heading_color_ratios": heading_region_ratios,
            }
        )
        if blank_pages:
            self.fail("blank_pages", "终稿包含异常空白页", "paper", "paper", ", ".join(map(str, blank_pages)))
        if clipped_pages:
            self.fail("page_clipping", "页面边界检测到可能的截断或溢出", "paper", "paper", ", ".join(map(str, clipped_pages)))
        if colored_heading_pages:
            self.fail("heading_color_pdf", "页面标题区域检测到非黑色深色像素", "paper", "paper", ", ".join(map(str, colored_heading_pages)))


def extract_pdf_pages(path: Path, on_error: Any) -> list[str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # pragma: no cover - parser errors vary by PDF
        on_error(f"cannot read canonical PDF: {exc}")
        return []


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def visible_tex(text: str) -> str:
    text = re.sub(r"\\(?:cite|ref|cref|Cref|label|includegraphics|figinc|flowinc|input|include)(?:\[[^\]]*\])?\s*\{[^}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("{", " ").replace("}", " ").replace("$", " ")
    return re.sub(r"\s+", " ", text)


def unique_problem_labels(text: str) -> list[str]:
    labels = re.findall(r"问题\s*(?:[一二三四五六七八九十]+|[1-9][0-9]*)", visible_tex(text))
    return list(dict.fromkeys(re.sub(r"\s+", "", item) for item in labels))


def infer_q_count(text: str) -> int:
    numbers = [int(item) for item in re.findall(r"\bQ([1-9][0-9]*)\b", text, flags=re.I)]
    return max(numbers) if numbers else 0


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def package_loaded(text: str, package: str) -> bool:
    for group in re.findall(r"\\usepackage(?:\[[^\]]*\])?\s*\{([^}]+)\}", text):
        if package in {item.strip() for item in group.split(",")}:
            return True
    return False


def extract_graphic_paths(text: str) -> list[str]:
    return re.findall(r"\\(?:includegraphics|figinc|flowinc)(?:\[[^\]]*\])?\s*\{([^}]+)\}", text)


def latex_command_argument(text: str, command: str) -> str | None:
    """Return a command's first braced argument, preserving nested groups."""
    match = re.search(rf"\\{re.escape(command)}(?:\s*\[[^\]]*\])?\s*\{{", text, flags=re.S)
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        escaped = index > 0 and text[index - 1] == "\\"
        if not escaped:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start + 1 : index]
        index += 1
    return None


def figure_reference_present(text: str, label: str) -> bool:
    for group in re.findall(r"\\(?:ref|cref|Cref|autoref)\s*\{([^}]+)\}", text):
        if label in {item.strip() for item in group.split(",")}:
            return True
    return False


def citation_key_on_line(line: str, key: str) -> bool:
    groups = re.findall(r"\\(?:cite|parencite|textcite|supercite)(?:\[[^\]]*\])?\s*\{([^}]+)\}", line)
    return any(key in {item.strip() for item in group.split(",")} for group in groups)


def naked_math_tokens(text: str) -> list[str]:
    masked = re.sub(r"\\begin\{(?:verbatim|lstlisting|minted)\}.*?\\end\{(?:verbatim|lstlisting|minted)\}", "", text, flags=re.S)
    masked = re.sub(
        r"\\(?:includegraphics|figinc|flowinc|input|include|label|ref|eqref|cite|url|href|path|bibliography|addbibresource)(?:\[[^\]]*\])?\s*\{[^}]*\}",
        "",
        masked,
    )
    display_envs = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "math", "displaymath"}
    env_stack: list[str] = []
    in_dollar = False
    in_double = False
    in_paren = False
    in_bracket = False
    findings: list[str] = []
    line = 1
    i = 0
    while i < len(masked):
        char = masked[i]
        if char == "\n":
            line += 1
        if masked.startswith("\\begin{", i) or masked.startswith("\\end{", i):
            begin = masked.startswith("\\begin{", i)
            end = masked.find("}", i)
            if end >= 0:
                name_start = i + (7 if begin else 5)
                name = masked[name_start:end]
                if name in display_envs:
                    if begin:
                        env_stack.append(name)
                    elif env_stack:
                        env_stack.pop()
                i = end + 1
                continue
        if masked.startswith("\\(", i):
            in_paren = True
            i += 2
            continue
        if masked.startswith("\\)", i):
            in_paren = False
            i += 2
            continue
        if masked.startswith("\\[", i):
            in_bracket = True
            i += 2
            continue
        if masked.startswith("\\]", i):
            in_bracket = False
            i += 2
            continue
        if char == "$" and (i == 0 or masked[i - 1] != "\\"):
            if i + 1 < len(masked) and masked[i + 1] == "$":
                in_double = not in_double
                i += 2
                continue
            if not in_double:
                in_dollar = not in_dollar
            i += 1
            continue
        in_math = bool(env_stack or in_dollar or in_double or in_paren or in_bracket)
        if char in "_^" and not in_math and (i == 0 or masked[i - 1] != "\\"):
            context = re.sub(r"\s+", " ", masked[max(0, i - 22) : i + 23]).strip()
            findings.append(f"line {line}: {context}")
        i += 1
    return findings


def dark_pixel_ratio(image: Any) -> float:
    histogram = image.histogram()
    dark = sum(histogram[:225])
    total = max(1, image.width * image.height)
    return dark / total


def colored_dark_ratio(image: Any) -> float:
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    colored = 0
    total = max(1, image.width * image.height)
    for red, green, blue in pixels:
        if max(red, green, blue) < 230 and max(red, green, blue) - min(red, green, blue) > 22:
            colored += 1
    return colored / total


def declared_heading_numbers(source_text: str) -> set[str]:
    """Derive the numbered heading labels declared by the canonical TeX source."""
    levels = {"section": 0, "subsection": 1, "subsubsection": 2}
    text = strip_comments(source_text)
    counters = [0, 0, 0]
    numbers: set[str] = set()
    pattern = r"\\(section|subsection|subsubsection)(?!\*)\s*\{"
    for match in re.finditer(pattern, text):
        depth = levels[match.group(1)]
        counters[depth] += 1
        for index in range(depth + 1, len(counters)):
            counters[index] = 0
        numbers.add(".".join(str(value) for value in counters[: depth + 1]))
    return numbers


def is_pdf_heading_candidate(
    value: str,
    font_size: float,
    page_index: int,
    cm: list[float],
    tm: list[float],
    heading_numbers: set[str],
    body_start_page: int,
) -> bool:
    """Distinguish native TeX headings from text embedded inside vector figures."""
    native_transform = all(
        abs(float(actual) - expected) < 1e-6
        for actual, expected in zip(cm[:4], (1.0, 0.0, 0.0, 1.0))
    )
    native_position = abs(float(tm[4])) > 1e-6 or abs(float(tm[5])) > 1e-6
    if not (native_transform and native_position):
        return False
    if page_index == 1:
        return font_size >= 18.0 and len(value) >= 2
    if page_index < body_start_page:
        return False
    number = re.fullmatch(r"\d+(?:\.\d+)*", value)
    return bool(number) and font_size >= 13.0 and value in heading_numbers


def extract_pdf_heading_bands(
    path: Path,
    heading_numbers: set[str] | None = None,
    body_start_page: int = 2,
) -> dict[int, list[tuple[float, float, float]]]:
    """Locate title baselines in PDF coordinates, excluding figures and page headers."""
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - pypdf is required by the pipeline
        return {}
    bands: dict[int, list[tuple[float, float, float]]] = {}
    try:
        reader = PdfReader(str(path))
        for page_index, page in enumerate(reader.pages, start=1):
            page_height = float(page.mediabox.height)
            candidates: list[tuple[float, float, float]] = []

            def visitor(text: str, cm: list[float], tm: list[float], _font: Any, font_size: float) -> None:
                value = " ".join(text.split())
                size = float(font_size or 0.0)
                if not is_pdf_heading_candidate(
                    value,
                    size,
                    page_index,
                    cm,
                    tm,
                    heading_numbers or set(),
                    body_start_page,
                ):
                    return
                x = float(tm[4]) * float(cm[0]) + float(tm[5]) * float(cm[2]) + float(cm[4])
                y = float(tm[4]) * float(cm[1]) + float(tm[5]) * float(cm[3]) + float(cm[5])
                if 0.0 < y < page_height and x < float(page.mediabox.width):
                    candidates.append((y, size, page_height))

            page.extract_text(visitor_text=visitor)
            unique: list[tuple[float, float, float]] = []
            for item in sorted(candidates, reverse=True):
                if not any(abs(item[0] - other[0]) < 2.0 for other in unique):
                    unique.append(item)
            if unique:
                bands[page_index] = unique
    except Exception:  # pragma: no cover - malformed PDFs are reported by the canonical PDF audit
        return {}
    return bands


def heading_color_ratios(image: Any, bands: list[tuple[float, float, float]]) -> list[float]:
    """Measure chromatic dark pixels only on rows containing actual PDF headings."""
    ratios: list[float] = []
    for baseline, font_size, page_height in bands:
        scale = image.height / max(page_height, 1.0)
        center = (page_height - baseline) * scale
        top = max(0, int(center - font_size * scale * 1.35))
        bottom = min(image.height, int(center + font_size * scale * 0.60))
        left = int(image.width * 0.04)
        right = int(image.width * 0.96)
        if bottom > top and right > left:
            ratios.append(colored_dark_ratio(image.crop((left, top, right, bottom))))
    return ratios


def write_report(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Mira Contest Final Audit",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Batch: `{payload.get('batch_id', '')}`",
        f"- Source: `{payload['source']}`",
        f"- PDF: `{payload['pdf']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {escape(key)} | {escape(value)} |")
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Level | Code | Owner | Return to | Message | Evidence |",
            "|---|---|---|---|---|---|",
        ]
    )
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(
                f"| {item['level']} | {escape(item['code'])} | {escape(item['owner_phase'])} | "
                f"{escape(item['return_to'])} | {escape(item['message'])} | {escape(item.get('evidence', ''))} |"
            )
    else:
        lines.append("| INFO | complete | paper | - | no open findings | - |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape(value: Any) -> str:
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--render-dir", help="Directory containing page-*.png renders")
    parser.add_argument("--write-json", default="checks/final_delivery_report.json")
    parser.add_argument("--write-report", default="checks/final_delivery_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = ContestFinalAuditor(root, args.render_dir).run()
    json_path = Path(args.write_json)
    markdown_path = Path(args.write_report)
    if not json_path.is_absolute():
        json_path = root / json_path
    if not markdown_path.is_absolute():
        markdown_path = root / markdown_path
    write_report(payload, json_path, markdown_path)
    print(f"VERDICT: {payload['verdict']}")
    print(f"blockers: {len(payload['blockers'])}")
    print(f"wrote: {json_path}")
    print(f"wrote: {markdown_path}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
