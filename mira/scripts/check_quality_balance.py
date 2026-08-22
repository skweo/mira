#!/usr/bin/env python3
"""Check Mira's balanced contest-final quality.

This gate is deliberately broader than a compile or text lint check. It looks
for the two qualities Mira must optimize together: model depth and contest-paper
fullness. It is conservative and evidence-based; it does not judge style, but it
does catch common regressions such as a formally correct engineering report that
is too thin to read like a strong mathematical modeling paper.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from delivery_contract import canonical_pdf, canonical_source
from paper_scope import find_marker_page
from workflow_stages import normalize_stage_path


CHINESE_NUMERALS = "一二三四五六七八九十"
FIGURE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".webp"}
PAPER_SUFFIXES = {".tex", ".typ", ".md"}
EFFECTIVE_PAGE_MIN = 23
EFFECTIVE_PAGE_MAX = 30
CONTEST_FINAL_LEVELS = {"contest_final", "contest-final", "final", "high_award", "high-award", "award"}
MAIN_BODY_START_TERMS = [
    "\u95ee\u9898\u91cd\u8ff0",
    "\u95ee\u9898\u5206\u6790",
    "\u7b26\u53f7\u8bf4\u660e",
    "\u7b26\u53f7\u8bf4\u660e\u548c\u53d8\u91cf\u5b9a\u4e49",
    "\u6a21\u578b\u5047\u8bbe",
    "\u57fa\u672c\u5047\u8bbe",
    "\u6a21\u578b\u5efa\u7acb",
    "\u6a21\u578b\u7684\u5efa\u7acb",
    "\u6a21\u578b\u51c6\u5907",
    "\u6a21\u578b\u6c42\u89e3",
    "problem restatement",
    "problem analysis",
    "assumptions",
    "model establishment",
]
EFFECTIVE_STOP_TERMS = [
    "\u53c2\u8003\u6587\u732e",
    "\u53c2\u8003\u8d44\u6599",
    "\u9644\u5f55",
    "\u9644\u8868",
    "\u652f\u6491\u6750\u6599",
    "ai \u5de5\u5177\u4f7f\u7528",
    "ai\u5de5\u5177\u4f7f\u7528",
    "references",
    "bibliography",
    "appendix",
]
FRONT_MATTER_TERMS = [
    "\u6458\u8981",
    "\u5173\u952e\u8bcd",
    "\u76ee\u5f55",
    "abstract",
    "keywords",
    "contents",
]


@dataclass
class Finding:
    level: str
    axis: str
    phase: str
    message: str


class QualityBalanceChecker:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.paper_dir = Path(args.paper_dir).resolve() if args.paper_dir else self.root / "paper"
        self.main = Path(args.main).resolve() if args.main else self._infer_main()
        self.sections_dir = (
            Path(args.sections_dir).resolve()
            if args.sections_dir
            else self.paper_dir / "sections"
        )
        self.results_file = (
            Path(args.results_file).resolve()
            if args.results_file
            else self.root / "results" / "result_report.md"
        )
        self.frozen_numbers = self.root / "results" / "frozen_numbers.json"
        self.problem_analysis = (
            Path(args.problem_analysis).resolve()
            if args.problem_analysis
            else self.root / "planning" / "problem_analysis.md"
        )
        self.modeling_plan = (
            Path(args.modeling_plan).resolve()
            if args.modeling_plan
            else self.root / "planning" / "modeling_plan.md"
        )
        self.symbol_table = self.root / "planning" / "symbol_table.md"
        self.delivery_brief = self.root / "planning" / "delivery_brief.md"
        self.figure_index = (
            Path(args.figure_index).resolve()
            if args.figure_index
            else self.root / "figures" / "figure_index.md"
        )
        self.semantic_audit_report = self.root / "checks" / "semantic_audit_report.md"
        self.presentation_strength_report = self.root / "checks" / "presentation_strength_report.md"
        self.references = self._infer_refs()
        self.pdf = self._infer_pdf()
        self.findings: list[Finding] = []
        self.paper_files: list[Path] = []
        self.paper_text = ""
        self.planning_text = ""
        self.results_text = ""
        self.has_result_artifacts = False
        self.metrics: dict[str, object] = {}

    def _infer_main(self) -> Path:
        if _is_contest_final(self.args.output_level):
            return canonical_source(self.root)
        for candidate in (
            self.paper_dir / "main.tex",
            self.paper_dir / "main.typ",
            self.paper_dir / "main.md",
            self.root / "main.tex",
            self.root / "main.typ",
            self.root / "main.md",
        ):
            if candidate.exists():
                return candidate.resolve()
        return (self.paper_dir / "main.tex").resolve()

    def _infer_refs(self) -> Path:
        for name in ("references.tex", "references.typ", "references.bib", "references.md"):
            path = self.paper_dir / name
            if path.exists():
                return path.resolve()
        return (self.paper_dir / "references.tex").resolve()

    def _infer_pdf(self) -> Path:
        if self.args.pdf:
            return Path(self.args.pdf).resolve()
        if _is_contest_final(self.args.output_level):
            return canonical_pdf(self.root)
        for candidate in (
            self.paper_dir / "main.pdf",
            self.paper_dir / f"{self.main.stem}.pdf",
            self.root / "main.pdf",
        ):
            if candidate.exists():
                return candidate.resolve()
        return (self.paper_dir / "main.pdf").resolve()

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="ignore")

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, normalize_stage_path(phase, "paper"), message))

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, normalize_stage_path(phase, "paper"), message))

    def info(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("INFO", axis, normalize_stage_path(phase, "paper"), message))

    def run(self) -> int:
        self._load_inputs()
        self._collect_metrics()
        self._check_model_depth()
        self._check_paper_fullness()
        self._check_balance()
        self._emit()
        if self.args.write_report:
            self._write_report(Path(self.args.write_report))
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _load_inputs(self) -> None:
        if self.main.exists():
            self.paper_files = self._paper_files()
            self.paper_text = "\n".join(self.read_text(path) for path in self.paper_files)
        else:
            self.fail("paper_fullness", "paper", f"main paper file not found: {self.main}")

        planning_parts: list[str] = []
        for path in (self.delivery_brief, self.problem_analysis, self.modeling_plan, self.symbol_table):
            if path.exists():
                planning_parts.append(self.read_text(path))
        self.planning_text = "\n".join(planning_parts)

        result_parts: list[str] = []
        if self.results_file.exists():
            result_parts.append(self.read_text(self.results_file))
        if self.frozen_numbers.exists():
            result_parts.append(self.read_text(self.frozen_numbers))
        tables_dir = self.root / "results" / "tables"
        if tables_dir.exists():
            for path in sorted(tables_dir.glob("*"))[:40]:
                if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".csv"}:
                    result_parts.append(self.read_text(path))
        for folder in (self.root / "results" / "audits", self.root / "results" / "logs"):
            if folder.exists():
                for path in sorted(folder.glob("*"))[:30]:
                    if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".csv", ".log"}:
                        result_parts.append(self.read_text(path))
        self.has_result_artifacts = bool(result_parts)
        self.results_text = "\n".join(result_parts)

    def _paper_files(self) -> list[Path]:
        files = [self.main]
        suffix = self.main.suffix.lower()
        main_text = self.read_text(self.main)
        includes: list[Path] = []
        if suffix == ".tex":
            raw = re.findall(r"\\(?:input|include)\s*\{([^}]+)\}", main_text)
            includes = [self.main.parent / (item if item.endswith(".tex") else f"{item}.tex") for item in raw]
        elif suffix == ".typ":
            raw = re.findall(r'#include\(\s*"([^"]+\.typ)"\s*\)', main_text)
            includes = [self.main.parent / item for item in raw]

        for path in includes:
            if path.exists():
                files.append(path.resolve())

        if len(files) == 1 and self.sections_dir.exists():
            files.extend(sorted(self.sections_dir.glob(f"*{suffix}"), key=_path_sort_key))

        if self.references.exists():
            files.append(self.references)

        seen: set[Path] = set()
        deduped: list[Path] = []
        for path in files:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                deduped.append(resolved)
        return deduped

    def _collect_metrics(self) -> None:
        visible = _strip_markup(self.paper_text)
        planning_visible = _strip_markup(self.planning_text)
        results_visible = _strip_markup(self.results_text)
        combined = "\n".join([visible, planning_visible, results_visible])
        semantic_text = self.read_text(self.semantic_audit_report) if self.semantic_audit_report.exists() else ""
        semantic_fail_count = len(re.findall(r"(?m)^\|\s*FAIL\s*\|", semantic_text))
        semantic_warn_count = len(re.findall(r"(?m)^\|\s*WARN\s*\|", semantic_text))
        presentation_text = self.read_text(self.presentation_strength_report) if self.presentation_strength_report.exists() else ""
        presentation_fail_count = len(re.findall(r"(?m)^\|\s*FAIL\s*\|", presentation_text))
        presentation_warn_count = len(re.findall(r"(?m)^\|\s*WARN\s*\|", presentation_text))
        expected_subquestions = self._expected_subquestions(combined)
        figure_refs = _count_figure_refs(self.paper_text)
        table_count = _count_tables(self.paper_text)
        equation_count = _count_equations(self.paper_text)
        citation_count = _count_citations(self.paper_text)
        reference_count = _count_references(self.read_text(self.references) if self.references.exists() else "")
        citation_binding = _citation_binding_evidence(self.root)
        page_count = _pdf_page_count(self.pdf) if self.pdf.exists() else None
        effective_pages = _effective_content_metrics(self.pdf)

        section_lengths = self._section_lengths()
        short_sections = [name for name, length in section_lengths.items() if 0 < length < 800]
        validation_terms = _count_terms(combined, VALIDATION_TERMS)
        model_terms = _count_terms(combined, MODEL_TERMS)
        heuristic_terms = _count_terms(combined, HEURISTIC_TERMS)
        audit_terms = _count_terms(combined, AUDIT_TERMS)

        self.metrics = {
            "root": str(self.root),
            "main": self.rel(self.main),
            "pdf": self.rel(self.pdf) if self.pdf.exists() else "missing",
            "paper_files": [self.rel(path) for path in self.paper_files],
            "output_level": self.args.output_level,
            "visible_chars": len(visible),
            "paper_source_chars": len(self.paper_text),
            "page_count": page_count,
            "effective_content_pages": effective_pages["pages"],
            "effective_content_start_page": effective_pages["start_page"],
            "effective_content_end_page": effective_pages["end_page"],
            "effective_content_stop_page": effective_pages["stop_page"],
            "effective_content_page_min": EFFECTIVE_PAGE_MIN,
            "effective_content_page_max": EFFECTIVE_PAGE_MAX,
            "effective_content_detection": effective_pages["detection"],
            "expected_subquestions": expected_subquestions,
            "figure_refs": figure_refs,
            "table_count": table_count,
            "equation_count": equation_count,
            "citation_count": citation_count,
            "reference_count": reference_count,
            "citation_binding_rows": citation_binding["rows"],
            "citation_binding_artifacts": citation_binding["files"],
            "source_support_terms": _count_terms(combined, SOURCE_SUPPORT_TERMS),
            "section_count": len(section_lengths),
            "short_sections": short_sections[:12],
            "validation_term_hits": validation_terms,
            "model_term_hits": model_terms,
            "heuristic_term_hits": heuristic_terms,
            "audit_term_hits": audit_terms,
            "has_abstract": _has_any(visible, ["摘要", "Abstract"]),
            "has_keywords": _has_any(visible, ["关键词", "Keywords", "key words"]),
            "has_toc": _has_toc(self.paper_text, visible),
            "has_problem_analysis": self.problem_analysis.exists(),
            "has_modeling_plan": self.modeling_plan.exists(),
            "has_result_report": self.results_file.exists(),
            "has_result_artifacts": self.has_result_artifacts,
            "has_symbol_table": self.symbol_table.exists(),
            "has_figure_index": self.figure_index.exists(),
            "has_semantic_audit_report": self.semantic_audit_report.exists(),
            "semantic_fail_count": semantic_fail_count,
            "semantic_warn_count": semantic_warn_count,
            "has_presentation_strength_report": self.presentation_strength_report.exists(),
            "presentation_fail_count": presentation_fail_count,
            "presentation_warn_count": presentation_warn_count,
        }

    def _expected_subquestions(self, text: str) -> int:
        if self.args.expected_subquestions is not None:
            return self.args.expected_subquestions
        cn = [CHINESE_NUMERALS.index(item) + 1 for item in re.findall(r"问题([一二三四五六七八九])", text)]
        qn = [int(item) for item in re.findall(r"\bQ([1-9])\b", text, flags=re.IGNORECASE)]
        numbered = cn + qn
        if numbered:
            return max(numbered)
        return 0

    def _section_lengths(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for path in self.paper_files:
            if path == self.references or path == self.main:
                continue
            text = _strip_markup(self.read_text(path)).strip()
            out[path.name] = len(text)
        if self.paper_text:
            for idx, part in enumerate(re.split(r"\\section\s*\{|^=\s+", self.paper_text, flags=re.M)[1:], start=1):
                out[f"section_{idx}"] = len(_strip_markup(part))
        return out

    def _check_model_depth(self) -> None:
        if not self.metrics.get("has_problem_analysis"):
            self.fail("model_depth", "analysis", f"missing problem contract artifact: {self.rel(self.problem_analysis)}")
        if not self.metrics.get("has_modeling_plan"):
            self.fail("model_depth", "modeling", f"missing modeling plan artifact: {self.rel(self.modeling_plan)}")
        if not self.metrics.get("has_result_report"):
            if self.metrics.get("has_result_artifacts"):
                self.warn(
                    "model_depth",
                    "implementation",
                    f"canonical result analysis artifact is missing even though result files exist: {self.rel(self.results_file)}",
                )
            else:
                self.fail("model_depth", "implementation", f"missing result analysis artifact: {self.rel(self.results_file)}")
        if not self.metrics.get("has_symbol_table"):
            self.warn("model_depth", "modeling", f"symbol table not found: {self.rel(self.symbol_table)}")

        expected = int(self.metrics.get("expected_subquestions") or 0)
        model_hits = int(self.metrics.get("model_term_hits") or 0)
        validation_hits = int(self.metrics.get("validation_term_hits") or 0)
        audit_hits = int(self.metrics.get("audit_term_hits") or 0)
        heuristic_hits = int(self.metrics.get("heuristic_term_hits") or 0)
        combined = "\n".join([self.paper_text, self.planning_text, self.results_text])

        if model_hits < max(8, expected * 4):
            self.fail(
                "model_depth",
                "modeling",
                "model evidence is thin: variables/objectives/constraints/solver/adaptation terms are sparse",
            )

        if validation_hits < max(5, expected * 2):
            self.fail(
                "model_depth",
                "implementation",
                "validation evidence is thin: baseline, sensitivity, robustness, residual, bound, or convergence evidence is sparse",
            )

        if audit_hits < max(3, expected):
            self.fail(
                "model_depth",
                "implementation",
                "constraint or feasibility audit evidence is sparse for a contest-final result",
            )

        if heuristic_hits and not _has_any(combined, ["种子", "seed", "多次", "重复", "稳定", "收敛", "baseline", "基线"]):
            self.fail(
                "model_depth",
                "implementation",
                "heuristic/stochastic method appears, but seed, convergence, baseline, or repeatability evidence is missing",
            )

        if _has_any(combined, ["全局最优", "严格最优", "最优解"]) and heuristic_hits:
            if not _has_any(combined, ["下界", "上界", "gap", "证书", "证明", "精确", "exact", "MILP"]):
                self.fail(
                    "model_depth",
                    "implementation",
                    "strong optimality wording appears with heuristic terms but no bound, proof, or solver certificate",
                )

        if self.results_file.exists():
            result_text = self.read_text(self.results_file)
            if not _has_any(result_text, ["source", "来源", "路径", "文件", ".csv", ".json", ".xlsx", ".log", "表"]):
                self.warn(
                    "model_depth",
                    "implementation",
                    "result report does not clearly expose file/table provenance for paper numbers",
                )

        if not self.metrics.get("has_semantic_audit_report"):
            self.warn("model_depth", "paper", f"semantic audit report not found: {self.rel(self.semantic_audit_report)}")
        elif int(self.metrics.get("semantic_fail_count") or 0):
            self.fail(
                "model_depth",
                "implementation",
                f"semantic audit has {self.metrics['semantic_fail_count']} blocking findings",
            )
        elif int(self.metrics.get("semantic_warn_count") or 0):
            self.warn(
                "model_depth",
                "implementation",
                f"semantic audit has {self.metrics['semantic_warn_count']} warnings that should be summarized before final delivery",
            )

    def _check_paper_fullness(self) -> None:
        if not self.main.exists():
            return

        expected = int(self.metrics.get("expected_subquestions") or 0)
        figure_refs = int(self.metrics.get("figure_refs") or 0)
        table_count = int(self.metrics.get("table_count") or 0)
        equation_count = int(self.metrics.get("equation_count") or 0)
        citation_count = int(self.metrics.get("citation_count") or 0)
        reference_count = int(self.metrics.get("reference_count") or 0)
        citation_binding_rows = int(self.metrics.get("citation_binding_rows") or 0)
        citation_binding_artifacts = self.metrics.get("citation_binding_artifacts") or []
        source_support_terms = int(self.metrics.get("source_support_terms") or 0)
        section_count = int(self.metrics.get("section_count") or 0)
        has_citation_binding = citation_binding_rows > 0 or bool(citation_binding_artifacts)

        if not self.metrics.get("has_abstract"):
            self.fail("paper_fullness", "paper", "abstract/摘要 is missing")
        if not self.metrics.get("has_keywords"):
            self.warn("paper_fullness", "paper", "keywords/关键词 are missing")
        if expected >= 4 and not self.metrics.get("has_toc"):
            self.fail("paper_fullness", "paper", "table of contents is missing for a multi-question contest-final paper")
        self._check_effective_content_pages()

        if expected >= 4 and section_count < expected + 5:
            self.info(
                "paper_fullness",
                "paper",
                f"section-count diagnostic: {section_count} sections for {expected} subquestions; add sections only when a model/result/validation unit is missing",
            )
        if self.metrics.get("short_sections"):
            message = (
                "short-section diagnostic only; inspect for missing model logic, evidence, or interpretation, but do not expand solely for length: "
                + ", ".join(self.metrics["short_sections"])
            )
            self.info("paper_fullness", "paper", message)

        if figure_refs == 0:
            self.info("paper_fullness", "implementation", "no paper figure references detected; add figures only if a claim needs visual evidence")
        elif expected >= 4 and figure_refs < expected + 2:
            self.info(
                "paper_fullness",
                "implementation",
                f"figure-count diagnostic: {figure_refs} referenced figures; judge evidence roles rather than padding to a target",
            )
        elif expected >= 4 and figure_refs < expected + 4:
            self.info(
                "paper_fullness",
                "implementation",
                f"figure-count diagnostic: {figure_refs} referenced figures; add only missing claim-bearing visuals",
            )

        if table_count == 0:
            self.fail("paper_fullness", "paper", "no tables detected in the paper source")
        elif expected >= 4 and table_count < expected:
            self.info(
                "paper_fullness",
                "paper",
                f"table-count diagnostic: {table_count} tables; add tables only for missing results, audits, or sensitivities",
            )

        if equation_count < max(4, expected):
            self.warn(
                "paper_fullness",
                "paper",
                f"equation/formulation density is low for a modeling paper: {equation_count} detected equations",
            )

        method_terms = _count_terms(self.paper_text, METHOD_REFERENCE_TERMS)
        if method_terms and not (citation_count or has_citation_binding or source_support_terms >= 3):
            self.warn(
                "paper_fullness",
                "paper",
                "major method terms appear, but no citation markers, source explanation, or citation-binding artifact were detected",
            )
        if method_terms and citation_count >= 4 and not has_citation_binding:
            self.warn(
                "paper_fullness",
                "paper",
                "multiple citations are used, but no citation-binding artifact records which method, parameter, data, software, or domain claim each source supports",
            )
        if reference_count >= 8 and citation_count == 0 and not has_citation_binding:
            self.warn(
                "paper_fullness",
                "paper",
                "the bibliography appears unbound: references exist, but no in-text citations or citation-binding artifact were detected",
            )

        if not self.metrics.get("has_presentation_strength_report"):
            self.warn(
                "paper_fullness",
                "paper",
                f"presentation strength report not found: {self.rel(self.presentation_strength_report)}",
            )
        elif int(self.metrics.get("presentation_fail_count") or 0):
            self.fail(
                "paper_fullness",
                "implementation",
                f"presentation strength gate has {self.metrics['presentation_fail_count']} blocking findings",
            )
        elif int(self.metrics.get("presentation_warn_count") or 0):
            self.warn(
                "paper_fullness",
                "implementation",
                f"presentation strength gate has {self.metrics['presentation_warn_count']} warnings",
            )

    def _check_effective_content_pages(self) -> None:
        pages = _metric_int(self.metrics.get("effective_content_pages"))
        page_count = self.metrics.get("page_count")
        level = str(self.metrics.get("output_level") or "").lower()
        is_final = _is_contest_final(level)
        if pages is None:
            message = (
                "effective-content pages could not be measured; compile a text-extractable PDF with standard main-body markers, "
                "or the final check cannot separate main-body pages from front matter, references, and other non-body sections"
            )
            if is_final:
                self.fail("paper_fullness", "paper", message)
            else:
                self.warn("paper_fullness", "paper", message)
            return
        if pages < EFFECTIVE_PAGE_MIN:
            message = (
                f"effective content pages {pages} below {EFFECTIVE_PAGE_MIN} "
                f"(total PDF pages={page_count}); repair with missing derivations, validation, sensitivity analysis, "
                "claim-bearing figures/tables, and result interpretation, not filler prose"
            )
            if is_final:
                self.fail("paper_fullness", "implementation", message)
            else:
                self.warn("paper_fullness", "implementation", message)
            return
        if pages > EFFECTIVE_PAGE_MAX:
            message = (
                f"effective content pages {pages} above {EFFECTIVE_PAGE_MAX}; compress repeated prose, "
                "move raw support material to supporting result files, and keep the main body decision-dense"
            )
            if is_final:
                self.fail("paper_fullness", "paper", message)
            else:
                self.warn("paper_fullness", "paper", message)
            return
        self.info(
            "paper_fullness",
            "paper",
            f"effective content pages are within target range: {pages} ({EFFECTIVE_PAGE_MIN}-{EFFECTIVE_PAGE_MAX})",
        )

    def _check_balance(self) -> None:
        fail_axes = {item.axis for item in self.findings if item.level == "FAIL"}
        warn_axes = {item.axis for item in self.findings if item.level == "WARN"}
        if "model_depth" in fail_axes and "paper_fullness" in fail_axes:
            self.fail(
                "balance",
                "paper",
                "both model depth and paper fullness fail; revise from the earliest model-side stage before polishing",
            )
        elif "model_depth" in fail_axes:
            self.fail(
                "balance",
                "modeling",
                "model-side evidence is not strong enough; do not repair by prose expansion",
            )
        elif "paper_fullness" in fail_axes:
            self.fail(
                "balance",
                "implementation",
                "paper presentation is not contest-final quality even if engineering artifacts exist",
            )
        elif warn_axes:
            self.warn(
                "balance",
                "paper",
                "no blocking balance failure, but warnings remain that may weaken comparison quality",
            )
        else:
            self.info("balance", "paper", "model depth and contest-paper fullness checks passed")

    def _emit(self) -> None:
        for key, value in self.metrics.items():
            print(f"METRIC: {key}={value}")
        for finding in self.findings:
            print(f"{finding.level}: [{finding.axis}] {finding.phase}: {finding.message}")
        print(f"VERDICT: {self._verdict()}")

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def _write_report(self, path: Path) -> None:
        if not path.is_absolute():
            path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._markdown_report(), encoding="utf-8")
        print(f"INFO: wrote {self.rel(path)}")

    def _markdown_report(self) -> str:
        lines = [
            "# Mira Dual Quality Balance Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Verdict: **{self._verdict()}**",
            f"- Root: `{self.root}`",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        for key, value in self.metrics.items():
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value) if value else "-"
            else:
                rendered = str(value)
            lines.append(f"| {key} | {rendered} |")

        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        for item in self.findings:
            lines.append(f"| {item.level} | {item.axis} | {item.phase} | {item.message} |")

        lines.extend(
            [
                "",
                "## Routing",
                "",
                "- Model-depth failures return to modeling or implementation before paper writing.",
                "- Paper-fullness failures return to implementation or paper after artifacts are verified.",
                "- Balance failures should not be repaired by cosmetic prose alone.",
                "",
            ]
        )
        return "\n".join(lines)


MODEL_TERMS = [
    "变量",
    "决策变量",
    "状态变量",
    "参数",
    "目标函数",
    "约束",
    "目标",
    "模型",
    "递推",
    "状态转移",
    "求解器",
    "算法",
    "适应",
    "特殊机制",
]

VALIDATION_TERMS = [
    "验证",
    "检验",
    "基线",
    "对比",
    "灵敏度",
    "鲁棒",
    "稳健",
    "残差",
    "误差",
    "收敛",
    "下界",
    "上界",
    "gap",
    "重复",
    "多次",
    "稳定",
    "baseline",
    "sensitivity",
    "robust",
]

AUDIT_TERMS = [
    "审计",
    "可行性",
    "约束检查",
    "约束满足",
    "重算",
    "覆盖",
    "容量",
    "时间窗",
    "audit",
    "feasible",
    "constraint",
]

HEURISTIC_TERMS = [
    "模拟退火",
    "遗传算法",
    "粒子群",
    "蚁群",
    "启发式",
    "局部搜索",
    "随机搜索",
    "SA",
    "GA",
    "PSO",
]

METHOD_REFERENCE_TERMS = [
    "QUBO",
    "TSP",
    "VRP",
    "VRPTW",
    "模拟退火",
    "遗传算法",
    "动态规划",
    "整数规划",
    "AHP",
    "TOPSIS",
    "ARIMA",
    "蒙特卡洛",
]

SOURCE_SUPPORT_TERMS = [
    "引用",
    "参考文献",
    "文献",
    "来源",
    "出处",
    "依据",
    "题目给定",
    "由数据估计",
    "显式假设",
    "支撑",
    "citation",
    "source",
    "reference",
]


def _path_sort_key(path: Path) -> tuple[int, int | str, str]:
    match = re.match(r"^(\d+)[_-]", path.name)
    if match:
        return (0, int(match.group(1)), path.name)
    return (1, path.name, "")


def _strip_markup(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|caption|label|ref|cite\w*)\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"#(?:heading|figure|table|image|cite|outline)\s*\(", " ", text)
    text = re.sub(r"[{}$&#_^~]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _count_terms(text: str, terms: Iterable[str]) -> int:
    lower = text.lower()
    total = 0
    for term in terms:
        if re.fullmatch(r"[A-Za-z0-9_+-]+", term):
            total += len(re.findall(rf"\b{re.escape(term.lower())}\b", lower))
        else:
            total += lower.count(term.lower())
    return total


def _has_any(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _has_toc(source_text: str, visible_text: str) -> bool:
    return (
        "\\tableofcontents" in source_text
        or "#outline" in source_text
        or "目录" in visible_text
        or "contents" in visible_text.lower()
    )


def _is_appendix(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("a_") or name.startswith("append") or "appendix" in name


def _count_figure_refs(text: str) -> int:
    latex = len(re.findall(r"\\(?:includegraphics|figinc|flowinc)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", text))
    typst = len(re.findall(r'image\(\s*"([^"]+)"', text))
    markdown = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", text))
    return latex + typst + markdown


def _count_tables(text: str) -> int:
    latex = len(re.findall(r"\\begin\{(?:table|tabular|longtable|tabularx)\}", text))
    typst = len(re.findall(r"#table\s*\(", text))
    markdown = len(re.findall(r"(?m)^\s*\|.+\|\s*$", text))
    return latex + typst + max(0, markdown // 2)


def _count_equations(text: str) -> int:
    display_math = len(re.findall(r"\\\[.*?\\\]", text, flags=re.S))
    envs = len(re.findall(r"\\begin\{(?:equation|align|gather|cases|split)\*?\}", text))
    typst = len(re.findall(r"\$[^$\n]{8,}\$", text))
    return display_math + envs + typst


def _count_citations(text: str) -> int:
    latex = len(re.findall(r"\\cite\w*\{[^}]+\}", text))
    typst = len(re.findall(r"@\w[\w:-]*|#cite\(", text))
    return latex + typst


def _count_references(text: str) -> int:
    if not text.strip():
        return 0
    bibitems = len(re.findall(r"\\bibitem\{", text))
    bibtex = len(re.findall(r"@\w+\s*\{", text))
    numbered = len(re.findall(r"(?m)^\s*(?:\[\d+\]|\d+\.|-\s+).{8,}", text))
    return max(bibitems, bibtex, numbered)


def _citation_binding_evidence(root: Path) -> dict[str, object]:
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
        count = _count_data_rows(_read_text(path))
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
                count = _count_data_rows(_read_text(path))
                if count:
                    files.append(f"results/tables/{path.name}")
                    rows += count
    for rel_path in ["planning/citation_binding.md", "planning/source_binding.md"]:
        path = root / rel_path
        if path.exists() and _read_text(path).strip():
            files.append(rel_path)
    for rel_path in ["planning/citation_bindings.json", "planning/citation_binding.json"]:
        path = root / rel_path
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        records = payload.get("bindings", payload.get("records", [])) if isinstance(payload, dict) else []
        valid = [
            record
            for record in records
            if isinstance(record, dict) and str(record.get("citation_key", "")).strip() and str(record.get("claim_id", "")).strip()
        ]
        if valid:
            files.append(rel_path)
            rows += len(valid)
    return {"rows": rows, "files": sorted(set(files))}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _count_data_rows(text: str) -> int:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0
    return max(0, len(lines) - 1)


def _metric_int(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _is_contest_final(output_level: str) -> bool:
    return output_level.lower().replace(" ", "_") in CONTEST_FINAL_LEVELS


def _effective_content_metrics(path: Path) -> dict[str, object]:
    pages = _pdf_page_texts(path)
    if not path.exists():
        return {
            "pages": None,
            "start_page": None,
            "end_page": None,
            "stop_page": None,
            "detection": "missing_pdf",
        }
    if not pages:
        return {
            "pages": None,
            "start_page": None,
            "end_page": None,
            "stop_page": None,
            "detection": "pdf_text_unavailable",
        }
    start_idx = find_marker_page(pages, MAIN_BODY_START_TERMS, skip_terms=FRONT_MATTER_TERMS)
    if start_idx is None:
        return {
            "pages": None,
            "start_page": None,
            "end_page": None,
            "stop_page": None,
            "detection": "main_body_start_not_found",
        }
    stop_idx = find_marker_page(pages, EFFECTIVE_STOP_TERMS, start_idx + 1, heading_only=True)
    end_exclusive = stop_idx if stop_idx is not None else len(pages)
    effective = max(0, end_exclusive - start_idx)
    return {
        "pages": effective,
        "start_page": start_idx + 1,
        "end_page": end_exclusive if effective else None,
        "stop_page": stop_idx + 1 if stop_idx is not None else None,
        "detection": "pdf_text_markers",
    }


def _pdf_page_texts(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        import pypdf  # type: ignore

        with path.open("rb") as fh:
            reader = pypdf.PdfReader(fh)
            pages = []
            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pages.append("")
            return pages
    except Exception:
        pass
    try:
        import PyPDF2  # type: ignore

        with path.open("rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            pages = []
            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pages.append("")
            return pages
    except Exception:
        return []


def _pdf_page_count(path: Path) -> int | None:
    try:
        import pypdf  # type: ignore

        with path.open("rb") as fh:
            return len(pypdf.PdfReader(fh).pages)
    except Exception:
        pass
    try:
        import PyPDF2  # type: ignore

        with path.open("rb") as fh:
            return len(PyPDF2.PdfReader(fh).pages)
    except Exception:
        pass
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    count = len(re.findall(rb"/Type\s*/Page\b", raw))
    return count if count > 0 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--paper-dir", help="Paper directory, defaults to <root>/paper")
    parser.add_argument("--main", help="Paper entry file")
    parser.add_argument("--sections-dir", help="Sections directory")
    parser.add_argument("--pdf", help="Compiled PDF path")
    parser.add_argument("--results-file", help="Result report markdown")
    parser.add_argument("--problem-analysis", help="Problem analysis artifact")
    parser.add_argument("--modeling-plan", help="Modeling plan artifact")
    parser.add_argument("--figure-index", help="Figure index markdown")
    parser.add_argument("--expected-subquestions", type=int, help="Override detected subquestion count")
    parser.add_argument("--output-level", default="contest_final", help="quick_draft, reproducible_draft, or contest_final")
    parser.add_argument("--write-report", help="Write markdown report to this path")
    return parser.parse_args()


def main() -> int:
    return QualityBalanceChecker(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
