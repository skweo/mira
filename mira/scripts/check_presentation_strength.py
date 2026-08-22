#!/usr/bin/env python3
"""Check contest-paper presentation strength for Mira outputs.

This gate is about the paper as a competition artifact. It does not replace
numeric audits. It catches the gap between a technically correct engineering
report and a paper that looks, reads, and supports itself like a strong Chinese
mathematical modeling submission.
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


class PresentationStrengthChecker:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.paper_dir = Path(args.paper_dir).resolve() if args.paper_dir else self.root / "paper"
        self.main = Path(args.main).resolve() if args.main else self._infer_main()
        self.sections_dir = Path(args.sections_dir).resolve() if args.sections_dir else self.paper_dir / "sections"
        self.references = Path(args.references).resolve() if args.references else self._infer_refs()
        self.pdf = Path(args.pdf).resolve() if args.pdf else self._infer_pdf()
        self.figures_dir = Path(args.figures_dir).resolve() if args.figures_dir else self.root / "figures"
        self.diagrams_dir = Path(args.diagrams_dir).resolve() if args.diagrams_dir else self.root / "diagrams"
        self.figure_index = (
            Path(args.figure_index).resolve()
            if args.figure_index
            else self.figures_dir / "figure_index.md"
        )
        self.diagram_index = self.diagrams_dir / "diagram_index.md"
        self.presentation_budget = self.root / "planning" / "presentation_budget.json"
        self.findings: list[Finding] = []
        self.paper_files: list[Path] = []
        self.paper_text = ""
        self.visible_text = ""
        self.pdf_text = ""
        self.first_page_text = ""
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
        for name in (
            "references.tex",
            "references.typ",
            "references.bib",
            "refs.bib",
            "references.md",
        ):
            path = self.paper_dir / name
            if path.exists():
                return path.resolve()
        return (self.paper_dir / "references.tex").resolve()

    def _infer_pdf(self) -> Path:
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
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8-sig", errors="ignore")

    def fail(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("FAIL", axis, normalize_stage_path(phase, "paper"), message))

    def warn(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("WARN", axis, normalize_stage_path(phase, "paper"), message))

    def info(self, axis: str, phase: str, message: str) -> None:
        self.findings.append(Finding("INFO", axis, normalize_stage_path(phase, "paper"), message))

    def run(self) -> int:
        self._load()
        self._collect_metrics()
        self._check_cover_and_structure()
        self._check_effective_content_pages()
        self._check_visual_evidence()
        self._check_references()
        self._check_audit_smell()
        self._emit()
        if self.args.write_report:
            self._write_report(Path(self.args.write_report))
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _load(self) -> None:
        if not self.main.exists():
            self.fail("presentation_structure", "paper", f"paper entry file not found: {self.main}")
            return
        self.paper_files = self._paper_files()
        self.paper_text = "\n".join(self.read_text(path) for path in self.paper_files if path.exists())
        self.visible_text = _strip_markup(self.paper_text)
        self.pdf_text, self.first_page_text = _pdf_text(self.pdf)

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
        for ref in _reference_files(self.paper_dir):
            files.append(ref.resolve())
        seen: set[Path] = set()
        deduped: list[Path] = []
        for path in files:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                deduped.append(resolved)
        return deduped

    def _collect_metrics(self) -> None:
        expected = self._expected_subquestions()
        page_count = _pdf_page_count(self.pdf) if self.pdf.exists() else None
        effective_pages = _effective_content_metrics(self.pdf)
        figure_includes = _count_figure_includes(self.paper_text)
        flowchart_includes = _count_flowchart_includes(self.paper_text)
        claim_figure_includes = max(0, figure_includes - flowchart_includes)
        diagram_includes = _count_diagram_mentions(self.paper_text)
        table_count = _count_tables(self.paper_text)
        equation_count = _count_equations(self.paper_text)
        citation_count = _count_citations(self.paper_text)
        reference_count = max(
            _count_references("\n".join(self.read_text(path) for path in _reference_files(self.paper_dir))),
            _count_pdf_references(self.pdf_text),
        )
        citation_binding = _citation_binding_evidence(self.root)
        caption_count = _count_captions(self.paper_text)
        section_lengths = self._section_lengths()
        core_short_sections = [
            name for name, length in section_lengths.items() if 0 < length < self.args.short_section_chars
        ]
        official_cover_signal = _has_official_cover_signal(self.first_page_text, self.paper_text)
        figure_index_rows, figure_index_complete_rows = _index_rows(self.figure_index)
        diagram_index_rows, diagram_index_complete_rows = _index_rows(self.diagram_index)
        visual_index_rows = figure_index_rows + diagram_index_rows
        visual_index_complete_rows = figure_index_complete_rows + diagram_index_complete_rows
        figure_assets = _count_assets(self.figures_dir, FIGURE_SUFFIXES)
        diagram_assets = _count_assets(self.diagrams_dir, FIGURE_SUFFIXES)
        method_terms = _count_terms(self.visible_text + "\n" + self.pdf_text, METHOD_TERMS)
        audit_smell_hits = _count_terms(self.visible_text + "\n" + self.pdf_text, AUDIT_SMELL_TERMS)
        budget = _load_budget(self.presentation_budget)

        self.metrics = {
            "root": str(self.root),
            "main": self.rel(self.main),
            "pdf": self.rel(self.pdf) if self.pdf.exists() else "missing",
            "paper_files": [self.rel(path) for path in self.paper_files],
            "output_level": self.args.output_level,
            "page_count": page_count,
            "effective_content_pages": effective_pages["pages"],
            "effective_content_start_page": effective_pages["start_page"],
            "effective_content_end_page": effective_pages["end_page"],
            "effective_content_stop_page": effective_pages["stop_page"],
            "effective_content_page_min": EFFECTIVE_PAGE_MIN,
            "effective_content_page_max": EFFECTIVE_PAGE_MAX,
            "effective_content_detection": effective_pages["detection"],
            "expected_subquestions": expected,
            "visible_chars": len(self.visible_text),
            "pdf_text_chars": len(self.pdf_text),
            "official_cover_signal": official_cover_signal,
            "figure_includes": figure_includes,
            "claim_figure_includes": claim_figure_includes,
            "flowchart_includes": flowchart_includes,
            "diagram_mentions": diagram_includes,
            "figure_assets": figure_assets,
            "diagram_assets": diagram_assets,
            "figure_index_rows": figure_index_rows,
            "figure_index_complete_rows": figure_index_complete_rows,
            "diagram_index_rows": diagram_index_rows,
            "diagram_index_complete_rows": diagram_index_complete_rows,
            "visual_index_rows": visual_index_rows,
            "visual_index_complete_rows": visual_index_complete_rows,
            "caption_count": caption_count,
            "table_count": table_count,
            "equation_count": equation_count,
            "citation_count": citation_count,
            "reference_count": reference_count,
            "citation_binding_rows": citation_binding["rows"],
            "citation_binding_artifacts": citation_binding["files"],
            "source_support_terms": _count_terms(self.visible_text + "\n" + self.pdf_text, SOURCE_SUPPORT_TERMS),
            "section_count": len(section_lengths),
            "core_short_sections": core_short_sections[:16],
            "has_abstract": _has_any(self.visible_text + self.pdf_text, ["摘要", "abstract"]),
            "has_keywords": _has_any(self.visible_text + self.pdf_text, ["关键词", "keywords", "key words"]),
            "has_toc": "\\tableofcontents" in self.paper_text or _has_any(self.pdf_text, ["目录", "contents"]),
            "method_term_hits": method_terms,
            "audit_smell_hits": audit_smell_hits,
            "presentation_budget_exists": bool(budget),
            "budget_figure_minimum": budget.get("figure_minimum"),
            "budget_citation_binding_minimum": budget.get("citation_binding_minimum"),
            "budget_table_minimum": budget.get("table_minimum"),
        }

    def _expected_subquestions(self) -> int:
        if self.args.expected_subquestions is not None:
            return self.args.expected_subquestions
        text = self.visible_text + "\n" + self.pdf_text
        qn = [int(item) for item in re.findall(r"\bQ([1-9])\b", text, flags=re.I)]
        cn_mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        cn = [cn_mapping[item] for item in re.findall(r"问题([一二三四五六七八九])", text)]
        return max(qn + cn) if qn or cn else 0

    def _section_lengths(self) -> dict[str, int]:
        out: dict[str, int] = {}
        body_text = self.paper_text
        appendix_at = body_text.lower().find("\\appendix")
        if appendix_at >= 0:
            body_text = body_text[:appendix_at]
        if self.main.suffix.lower() == ".tex":
            parts = re.split(r"\\section\*?\s*\{", body_text)[1:]
        elif self.main.suffix.lower() == ".typ":
            parts = re.split(r"(?m)^=\s+", body_text)[1:]
        else:
            parts = re.split(r"(?m)^##?\s+", body_text)[1:]
        for idx, part in enumerate(parts, start=1):
            head = part[:80]
            if _has_any(head, ["参考文献", "references", "附录", "appendix"]):
                continue
            out[f"section_{idx}"] = len(_strip_markup(part))
        return out

    def _check_cover_and_structure(self) -> None:
        expected = int(self.metrics.get("expected_subquestions") or 0)
        if not self.metrics.get("has_abstract"):
            self.fail("contest_template", "paper", "abstract is missing")
        if not self.metrics.get("has_keywords"):
            self.warn("contest_template", "paper", "keywords are missing or not detectable")
        if expected >= 4 and not self.metrics.get("has_toc"):
            self.fail("contest_template", "paper", "table of contents is missing for a multi-question contest-final paper")
        if expected >= 4 and not self.metrics.get("official_cover_signal"):
            self.warn(
                "contest_template",
                "paper",
                "official-style contest cover signal is weak; add team/problem metadata block or closest contest template before final comparison",
            )
        if self.metrics.get("core_short_sections"):
            self.info(
                "section_depth",
                "paper",
                "short-section diagnostic only; inspect for missing model logic, evidence, or interpretation, but do not expand solely for length: "
                + ", ".join(self.metrics["core_short_sections"]),
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
                self.fail("effective_content_pages", "paper", message)
            else:
                self.warn("effective_content_pages", "paper", message)
            return
        if pages < EFFECTIVE_PAGE_MIN:
            message = (
                f"effective content pages {pages} below {EFFECTIVE_PAGE_MIN} "
                f"(total PDF pages={page_count}); repair with missing derivations, validation, sensitivity analysis, "
                "claim-bearing figures/tables, and result interpretation, not filler prose"
            )
            if is_final:
                self.fail("effective_content_pages", "implementation", message)
            else:
                self.warn("effective_content_pages", "implementation", message)
            return
        if pages > EFFECTIVE_PAGE_MAX:
            message = (
                f"effective content pages {pages} above {EFFECTIVE_PAGE_MAX}; compress repeated prose, "
                "move raw support material to supporting result files, and keep the main body decision-dense"
            )
            if is_final:
                self.fail("effective_content_pages", "paper", message)
            else:
                self.warn("effective_content_pages", "paper", message)
            return
        self.info(
            "effective_content_pages",
            "paper",
            f"effective content pages are within target range: {pages} ({EFFECTIVE_PAGE_MIN}-{EFFECTIVE_PAGE_MAX})",
        )

    def _check_visual_evidence(self) -> None:
        expected = int(self.metrics.get("expected_subquestions") or 0)
        figure_includes = int(self.metrics.get("figure_includes") or 0)
        claim_figure_includes = int(self.metrics.get("claim_figure_includes") or 0)
        flowchart_includes = int(self.metrics.get("flowchart_includes") or 0)
        figure_index_rows = int(self.metrics.get("figure_index_rows") or 0)
        figure_index_complete_rows = int(self.metrics.get("figure_index_complete_rows") or 0)
        diagram_index_rows = int(self.metrics.get("diagram_index_rows") or 0)
        diagram_index_complete_rows = int(self.metrics.get("diagram_index_complete_rows") or 0)
        visual_index_rows = int(self.metrics.get("visual_index_rows") or 0)
        visual_index_complete_rows = int(self.metrics.get("visual_index_complete_rows") or 0)
        caption_count = int(self.metrics.get("caption_count") or 0)
        figure_minimum = _metric_int(self.metrics.get("budget_figure_minimum"))
        table_minimum = _metric_int(self.metrics.get("budget_table_minimum"))
        if expected >= 4 and not self.metrics.get("presentation_budget_exists"):
            self.warn(
                "visual_evidence",
                "implementation",
                "presentation evidence guide is missing; run plan_presentation_budget.py during implementation when the paper needs visual/citation planning",
            )
        if figure_minimum and figure_includes < figure_minimum:
            self.info(
                "visual_evidence",
                "implementation",
                f"figure count {figure_includes} is below the evidence-guide review trigger {figure_minimum}; add visuals only if a claim lacks visual evidence",
            )
        elif figure_minimum and figure_includes == figure_minimum:
            self.info(
                "visual_evidence",
                "implementation",
                f"figure count meets the evidence-guide trigger ({figure_includes}); judge quality by supported claims, not count",
            )
        if expected >= 4:
            if figure_includes < expected + 2:
                self.info(
                    "visual_evidence",
                    "implementation",
                    f"figure-count diagnostic: {figure_includes} figures for {expected} subquestions; add only missing claim-bearing visuals",
                )
            elif figure_includes < expected + 4:
                self.info(
                    "visual_evidence",
                    "implementation",
                    f"figure-count diagnostic: {figure_includes} figures; compare evidence roles rather than padding to a benchmark",
                )
        elif figure_includes == 0:
            self.fail("visual_evidence", "implementation", "no figures detected")
        if figure_includes and caption_count < figure_includes:
            self.warn(
                "visual_evidence",
                "paper",
                f"some included graphics may lack captions: figures={figure_includes}, captions={caption_count}",
            )
        if claim_figure_includes and not self.figure_index.exists():
            self.fail("visual_evidence", "implementation", f"figure index is missing: {self.rel(self.figure_index)}")
        elif figure_index_rows < claim_figure_includes:
            self.warn(
                "visual_evidence",
                "implementation",
                f"figure index rows ({figure_index_rows}) do not cover claim figures ({claim_figure_includes})",
            )
        if flowchart_includes and not self.diagram_index.exists():
            self.fail("visual_evidence", "implementation", f"diagram index is missing: {self.rel(self.diagram_index)}")
        elif diagram_index_rows < flowchart_includes:
            self.warn(
                "visual_evidence",
                "implementation",
                f"diagram index rows ({diagram_index_rows}) do not cover flowcharts ({flowchart_includes})",
            )
        if visual_index_rows < figure_includes:
            self.warn(
                "visual_evidence",
                "implementation",
                f"visual index rows ({visual_index_rows}) do not cover all included graphics ({figure_includes})",
            )
        if figure_index_rows and figure_index_complete_rows < figure_index_rows:
            self.warn(
                "visual_evidence",
                "implementation",
                "some figure-index rows lack source data, generation script, supported claim, or paper location",
            )
        if diagram_index_rows and diagram_index_complete_rows < diagram_index_rows:
            self.warn(
                "visual_evidence",
                "implementation",
                "some diagram-index rows lack structured source, generator, supported claim, or paper location",
            )
        if visual_index_rows and visual_index_complete_rows < visual_index_rows:
            self.warn(
                "visual_evidence",
                "implementation",
                "some visual-index rows are incomplete",
            )
        if expected >= 4 and int(self.metrics.get("table_count") or 0) < expected + 3:
            self.warn(
                "visual_evidence",
                "paper",
                "table density is low for per-question results, validations, sensitivities, and key summaries",
            )
        if table_minimum and int(self.metrics.get("table_count") or 0) < table_minimum:
            self.info(
                "visual_evidence",
                "paper",
                f"table count {self.metrics.get('table_count')} is below the evidence-guide review trigger {table_minimum}; add tables only for missing results, audits, or sensitivities",
            )

    def _check_references(self) -> None:
        expected = int(self.metrics.get("expected_subquestions") or 0)
        method_hits = int(self.metrics.get("method_term_hits") or 0)
        citation_count = int(self.metrics.get("citation_count") or 0)
        reference_count = int(self.metrics.get("reference_count") or 0)
        citation_binding_rows = int(self.metrics.get("citation_binding_rows") or 0)
        citation_binding_artifacts = self.metrics.get("citation_binding_artifacts") or []
        source_support_terms = int(self.metrics.get("source_support_terms") or 0)
        citation_binding_minimum = _metric_int(self.metrics.get("budget_citation_binding_minimum"))
        has_citation_binding = citation_binding_rows > 0 or bool(citation_binding_artifacts)
        if method_hits == 0:
            return
        if citation_binding_minimum and citation_binding_rows < citation_binding_minimum and not has_citation_binding:
            self.warn(
                "citation_support",
                "paper",
                f"citation binding is below the presentation budget: {citation_binding_rows} rows; bind sources to method, parameter, data, software, or domain claims",
            )
        if not (citation_count or has_citation_binding or source_support_terms >= 3):
            self.fail(
                "citation_support",
                "paper",
                "nontrivial method terms appear but no in-text citations, source explanations, or citation-binding artifacts were detected",
            )
        elif expected >= 4 and citation_count >= 4 and not has_citation_binding:
            self.warn(
                "citation_support",
                "paper",
                "multiple citations are used, but no citation-binding artifact records what each source supports",
            )
        if reference_count >= 8 and citation_count == 0 and not has_citation_binding:
            self.warn(
                "citation_support",
                "paper",
                "the bibliography appears unbound: references exist, but no in-text citations or citation-binding artifact were detected",
            )

    def _check_audit_smell(self) -> None:
        hits = int(self.metrics.get("audit_smell_hits") or 0)
        if hits >= 3:
            self.warn(
                "paper_narrative",
                "paper",
                f"paper exposes too much internal audit/workflow language ({hits} hits); rewrite as contest-paper validation evidence",
            )
        elif hits:
            self.info("paper_narrative", "paper", f"minor internal audit/workflow wording detected: {hits} hits")

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
        path.write_text(self._markdown(), encoding="utf-8")
        print(f"INFO: wrote {self.rel(path)}")

    def _markdown(self) -> str:
        lines = [
            "# Mira Presentation Strength Report",
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
            rendered = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
            lines.append(f"| {key} | {rendered if rendered else '-'} |")
        lines.extend(["", "## Findings", "", "| Level | Axis | Return to | Finding |", "|---|---|---|---|"])
        for item in self.findings:
            lines.append(f"| {item.level} | {item.axis} | {item.phase} | {item.message} |")
        lines.extend(
            [
                "",
                "## Routing",
                "",
                "- Cover/template and section-depth issues return to paper.",
                "- Visual-evidence issues return to implementation before paper prose repair.",
                "- Citation-support issues return to paper, and may require modeling context repair.",
                "- Supporting-file issues return to implementation; they do not add paper sections.",
                "",
            ]
        )
        return "\n".join(lines)


METHOD_TERMS = [
    "QUBO",
    "TSP",
    "VRP",
    "VRPTW",
    "TSPTW",
    "Held-Karp",
    "dynamic programming",
    "label",
    "local search",
    "simulated annealing",
    "genetic",
    "integer programming",
    "AHP",
    "TOPSIS",
    "ARIMA",
    "Monte Carlo",
    "Ising",
    "Kaiwu",
    "quantum",
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

AUDIT_SMELL_TERMS = [
    "PASS_WITH_WARNINGS",
    "mira_state",
    "quality_balance",
    "result_quality.py",
    "model_solver_consistency.py",
    "semantic_audit",
    "planning/",
    "checks/",
    "revisions/",
]


def _path_sort_key(path: Path) -> tuple[int, int | str, str]:
    match = re.match(r"^(\d+)[_-]", path.name)
    if match:
        return (0, int(match.group(1)), path.name)
    return (1, path.name, "")


def _reference_files(paper_dir: Path) -> list[Path]:
    names = [
        "references.tex",
        "references.typ",
        "references.bib",
        "refs.bib",
        "references.md",
    ]
    return [paper_dir / name for name in names if (paper_dir / name).exists()]


def _strip_markup(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|caption|label|ref|cite\w*)\s*(?:\[[^\]]*\])?\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"#(?:heading|figure|table|image|cite|outline)\s*\(", " ", text)
    text = re.sub(r"[{}$&#_^~]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _has_any(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _count_terms(text: str, terms: Iterable[str]) -> int:
    lower = text.lower()
    total = 0
    for term in terms:
        term_lower = term.lower()
        if re.fullmatch(r"[a-z0-9_./+-]+", term_lower):
            total += len(re.findall(rf"\b{re.escape(term_lower)}\b", lower))
        else:
            total += lower.count(term_lower)
    return total


def _has_official_cover_signal(first_page_text: str, source_text: str) -> bool:
    text = first_page_text + "\n" + source_text[:3000]
    has_team = _has_any(text, ["队伍编号", "队号", "参赛队", "团队编号", "team number", "team id", "mc202"])
    has_contest = _has_any(text, ["高教社杯", "全国大学生数学建模竞赛", "cumcm"])
    has_problem = _has_any(text, ["题号", "问题编号", "problem number"]) or bool(
        re.search(r"(?<![A-Za-z])[A-F]\s*题", text, flags=re.I)
    )
    has_problem_title = _has_any(text, ["赛题名称", "题目：", "题目:", "problem title"])
    anonymous_review = _has_any(text, ["匿名评审稿", "匿名评审", "anonymous review"])
    return has_problem and (has_team or (has_contest and has_problem_title and anonymous_review))


def _without_latex_command_definitions(text: str) -> str:
    """Mask command definitions so graphics inside wrapper macros are not counted."""

    starts = re.compile(
        r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)\*?\s*"
    )
    ranges: list[tuple[int, int]] = []

    def group_end(start: int, opening: str, closing: str) -> int | None:
        if start >= len(text) or text[start] != opening:
            return None
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char not in (opening, closing):
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and text[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2:
                continue
            if char == opening:
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return index + 1
        return None

    for match in starts.finditer(text):
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] == "{":
            command_end = group_end(cursor, "{", "}")
            if command_end is None:
                continue
            cursor = command_end
        else:
            command = re.match(r"\\[A-Za-z@]+", text[cursor:])
            if command is None:
                continue
            cursor += command.end()
        while True:
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor >= len(text) or text[cursor] != "[":
                break
            option_end = group_end(cursor, "[", "]")
            if option_end is None:
                break
            cursor = option_end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        body_end = group_end(cursor, "{", "}")
        if body_end is not None:
            ranges.append((match.start(), body_end))

    if not ranges:
        return text
    chars = list(text)
    for start, end in ranges:
        for index in range(start, end):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def _count_figure_includes(text: str) -> int:
    source = _without_latex_command_definitions(text)
    latex = len(re.findall(r"\\(?:includegraphics|figinc|flowinc)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", source))
    typst = len(re.findall(r'image\(\s*"([^"]+)"', text))
    markdown = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", text))
    return latex + typst + markdown


def _count_flowchart_includes(text: str) -> int:
    source = _without_latex_command_definitions(text)
    latex = 0
    pattern = re.compile(
        r"\\(?P<command>includegraphics|figinc|flowinc)\s*"
        r"(?:\[[^\]]*\])?\s*\{(?P<path>[^}]+)\}",
        flags=re.I,
    )
    for match in pattern.finditer(source):
        command = match.group("command").lower()
        normalized_path = match.group("path").replace("\\", "/").lower()
        path_parts = {part for part in normalized_path.split("/") if part not in {"", ".", ".."}}
        if command == "flowinc" or path_parts.intersection({"diagram", "diagrams", "flowchart", "flowcharts"}):
            latex += 1

    typst = len(re.findall(r'image\(\s*"[^"]*/(?:diagrams?|flowcharts?)/[^"]+"', text, flags=re.I))
    markdown = len(re.findall(r"!\[[^\]]*\]\([^)]*/(?:diagrams?|flowcharts?)/[^)]+\)", text, flags=re.I))
    return latex + typst + markdown


def _count_diagram_mentions(text: str) -> int:
    return len(re.findall(r"diagram|flowchart|sequenceDiagram|sequence diagram|Mermaid|流程图|框图|技术路线|时序图|调用链", text, flags=re.I))


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


def _count_captions(text: str) -> int:
    latex = len(re.findall(r"\\caption\s*(?:\[[^\]]*\])?\s*\{", text))
    typst = len(re.findall(r"#figure\s*\(", text))
    markdown = len(re.findall(r"(?i)^\s*(?:图|figure)\s*\d+", text, flags=re.M))
    return latex + typst + markdown


def _count_citations(text: str) -> int:
    latex = len(re.findall(r"\\cite\w*\{[^}]+\}", text))
    typst = len(re.findall(r"@\w[\w:-]*|#cite\(", text))
    bracket = len(re.findall(r"\[[0-9]+(?:\s*[-,]\s*[0-9]+)*\]", _strip_markup(text)))
    return latex + typst + bracket


def _count_references(text: str) -> int:
    if not text.strip():
        return 0
    return max(
        len(re.findall(r"\\bibitem\{", text)),
        len(re.findall(r"@\w+\s*\{", text)),
        len(re.findall(r"(?m)^\s*(?:\[\d+\]|\d+\.|-\s+).{8,}", text)),
    )


def _count_pdf_references(text: str) -> int:
    if not text:
        return 0
    tail = text
    for marker in ("参考文献", "References", "REFERENCES"):
        idx = text.rfind(marker)
        if idx >= 0:
            tail = text[idx:]
            break
    return len(re.findall(r"(?m)^\s*\[\d+\]\s+.{8,}", tail))


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


def _count_assets(folder: Path, suffixes: set[str]) -> int:
    if not folder.exists():
        return 0
    return sum(1 for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def _index_rows(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    rows = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|") or _is_markdown_separator_row(stripped):
            continue
        next_row = next((item.strip() for item in lines[index + 1:] if item.strip()), "")
        if _is_markdown_separator_row(next_row):
            continue
        cols = [col.strip() for col in stripped.strip("|").split("|")]
        if len(cols) >= 5:
            rows.append(cols)
    complete = 0
    for cols in rows:
        joined = " ".join(cols)
        if all(term not in joined.lower() for term in ["todo", "tbd", "missing"]) and len([c for c in cols if c and c != "-"]) >= 5:
            complete += 1
    return len(rows), complete


def _is_markdown_separator_row(line: str) -> bool:
    if not line.startswith("|"):
        return False
    cols = [col.strip() for col in line.strip("|").split("|")]
    return bool(cols) and all(re.fullmatch(r":?-{3,}:?", col) for col in cols)


def _load_budget(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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


def _pdf_text(path: Path) -> tuple[str, str]:
    pages = _pdf_page_texts(path)
    return "\n".join(pages), pages[0] if pages else ""


def _pdf_page_count(path: Path) -> int | None:
    if not path.exists():
        return None
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
    parser.add_argument("--references", help="Reference file")
    parser.add_argument("--figures-dir", help="Figures directory")
    parser.add_argument("--diagrams-dir", help="Diagrams directory")
    parser.add_argument("--figure-index", help="Figure index markdown")
    parser.add_argument("--expected-subquestions", type=int, help="Override detected subquestion count")
    parser.add_argument("--output-level", default="contest_final", help="quick_draft, reproducible_draft, or contest_final")
    parser.add_argument("--short-section-chars", type=int, default=900, help="Core section warning threshold")
    parser.add_argument("--write-report", help="Write markdown report to this path")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return PresentationStrengthChecker(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
