from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pypdf import PdfWriter


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from contest_final_audit import (  # noqa: E402
    ContestFinalAuditor,
    heading_color_ratios,
    is_pdf_heading_candidate,
    naked_math_tokens,
)
from contest_final_pipeline import (  # noqa: E402
    COMPONENT_GATES,
    TEX_TOOL_COMMANDS,
    ContestFinalPipeline,
    build_environment,
    select_poppler_executable,
)
from check_presentation_strength import (  # noqa: E402
    _citation_binding_evidence as presentation_citation_binding_evidence,
    _count_figure_includes,
    _count_flowchart_includes,
    _has_official_cover_signal,
    _index_rows,
)
from check_quality_balance import (  # noqa: E402
    _citation_binding_evidence as balance_citation_binding_evidence,
    _count_figure_refs,
)
from delivery_contract import (  # noqa: E402
    DeliveryContractError,
    begin_batch,
    canonical_pdf,
    load_manifest,
    record_audit,
    record_build,
    record_pdf,
    write_manifest,
)
from render_structured_flowchart import StructuredFlowchart, wrap_label  # noqa: E402
from paper_scope import find_marker_page, page_has_heading_marker  # noqa: E402
from visual_reasoning_audit import figure_blocks, includegraphics  # noqa: E402


ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ContestFinalPipelineTests(unittest.TestCase):
    def test_contest_final_uses_objective_visual_gates_only(self) -> None:
        scripts = [script for script, _arguments in COMPONENT_GATES]

        self.assertIn("visual_render_gate.py", scripts)
        self.assertIn("visual_asset_audit.py", scripts)
        for script in (
            "statistical_evidence_gate.py",
            "figure_source_preflight.py",
            "reference_authenticity_gate.py",
            "contest_evidence_chain_gate.py",
            "submission_compliance.py",
        ):
            self.assertIn(script, scripts)
        self.assertNotIn("journal_figure_gate.py", scripts)
        self.assertLess(scripts.index("visual_render_gate.py"), scripts.index("figure_evidence_gate.py"))
        self.assertLess(scripts.index("visual_asset_audit.py"), scripts.index("figure_evidence_gate.py"))

    def make_tex_bin(self, root: Path, *, missing: str = "") -> Path:
        tex_bin = root / "texlive" / "bin" / "windows"
        tex_bin.mkdir(parents=True)
        suffix = ".exe" if os.name == "nt" else ""
        for tool in TEX_TOOL_COMMANDS:
            if tool != missing:
                (tex_bin / f"{tool}{suffix}").touch()
        return tex_bin

    def test_build_environment_prioritizes_complete_tex_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tex_bin = self.make_tex_bin(Path(temp_dir))

            env = build_environment({"PATH": ""}, tex_bin_candidates=[tex_bin])

            resolved = {Path(shutil.which(tool, path=env["PATH"])).resolve().parent for tool in TEX_TOOL_COMMANDS}
            self.assertEqual(resolved, {tex_bin.resolve()})
            self.assertEqual(Path(env["PATH"].split(os.pathsep)[0]), tex_bin.resolve())

    def test_build_environment_moves_existing_tex_suite_ahead_of_other_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tex_bin = self.make_tex_bin(root)
            other_bin = root / "miktex" / "bin"
            other_bin.mkdir(parents=True)
            original = os.pathsep.join((str(other_bin), str(tex_bin)))

            env = build_environment({"PATH": original}, tex_bin_candidates=[tex_bin])

            entries = [Path(item).resolve() for item in env["PATH"].split(os.pathsep)]
            self.assertEqual(entries[0], tex_bin.resolve())
            self.assertEqual(entries.count(tex_bin.resolve()), 1)

    def test_build_environment_uses_tex_live_perl_with_tex_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tex_bin = self.make_tex_bin(Path(temp_dir))
            perl = tex_bin.parent.parent / "tlpkg" / "tlperl" / "bin" / "perl.exe"
            perl.parent.mkdir(parents=True)
            perl.touch()

            env = build_environment({"PATH": ""}, tex_bin_candidates=[tex_bin])

            self.assertEqual(Path(env["PATH"].split(os.pathsep)[0]), perl.parent.resolve())
            resolved = {Path(shutil.which(tool, path=env["PATH"])).resolve().parent for tool in TEX_TOOL_COMMANDS}
            self.assertEqual(resolved, {tex_bin.resolve()})

    def test_build_environment_does_not_select_incomplete_tex_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tex_bin = self.make_tex_bin(Path(temp_dir), missing="bibtex")

            env = build_environment({"PATH": ""}, tex_bin_candidates=[tex_bin])

            self.assertEqual(env["PATH"], "")

    def test_build_environment_discovers_git_for_windows_perl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            git_root = Path(temp_dir) / "Git"
            git_executable = git_root / "cmd" / "git.exe"
            perl_executable = git_root / "usr" / "bin" / "perl.exe"
            git_executable.parent.mkdir(parents=True)
            perl_executable.parent.mkdir(parents=True)
            git_executable.touch()
            perl_executable.touch()

            env = build_environment({"PATH": "C:\\tools"}, git_executable, tex_bin_candidates=[])

            self.assertEqual(Path(env["PATH"].split(os.pathsep)[0]), perl_executable.parent)
            self.assertEqual(env["PYTHONIOENCODING"], "utf-8")

    def test_render_prefers_bundled_poppler_when_miktex_is_first_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            miktex_bin = root / "MiKTeX" / "miktex" / "bin" / "x64"
            bundled_bin = root / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "bin" / "override"
            bundled_real = root / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe"
            suffix = ".cmd" if os.name == "nt" else ""
            miktex = miktex_bin / f"pdftoppm{suffix}"
            bundled = bundled_bin / f"pdftoppm{suffix}"
            for executable in (miktex, bundled):
                executable.parent.mkdir(parents=True)
                executable.touch()
                executable.chmod(0o755)
            bundled_real.parent.mkdir(parents=True)
            bundled_real.touch()
            bundled_real.chmod(0o755)
            path_value = os.pathsep.join((str(miktex_bin), str(bundled_bin)))

            selected = select_poppler_executable(path_value)

            expected = bundled_real.resolve() if os.name == "nt" else bundled.resolve()
            self.assertEqual(selected, expected)
            args = argparse.Namespace(root=str(root), render_dpi=150, skip_components=True)
            pipeline = ContestFinalPipeline(args)
            pipeline.env = {"PATH": path_value}
            pipeline.toolchain = {"tools": {"pdftoppm": {"path": str(selected)}}}
            pipeline.pdf.parent.mkdir(parents=True, exist_ok=True)
            pipeline.pdf.touch()
            pipeline.render_dir.mkdir(parents=True, exist_ok=True)
            completed = subprocess.CompletedProcess([], 0, stdout="")
            with mock.patch("contest_final_pipeline.subprocess.run", return_value=completed) as run:
                self.assertIsNone(pipeline._render_pages())
            command = run.call_args.args[0]
            self.assertEqual(Path(command[0]), expected)
            self.assertIs(run.call_args.kwargs["env"], pipeline.env)

    def test_presentation_scorers_read_canonical_json_citation_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir()
            payload = {
                "version": 1,
                "bindings": [
                    {"claim_id": "C-Q1-01", "citation_key": "source_a"},
                    {"claim_id": "C-Q2-01", "citation_key": "source_b"},
                    {"claim_id": "", "citation_key": "invalid"},
                ],
            }
            (planning / "citation_bindings.json").write_text(json.dumps(payload), encoding="utf-8")

            for reader in (presentation_citation_binding_evidence, balance_citation_binding_evidence):
                evidence = reader(root)
                self.assertEqual(evidence["rows"], 2)
                self.assertEqual(evidence["files"], ["planning/citation_bindings.json"])

    def write_source(self, root: Path, extra: str = "") -> None:
        paper = root / "paper"
        paper.mkdir(parents=True, exist_ok=True)
        (paper / "main.tex").write_text(
            r"""\documentclass{ctexart}
\usepackage{booktabs}
\bibliographystyle{gbt7714-numerical}
\begin{document}
\begin{abstract}
\textbf{问题一：}建立模型并得到结果。验证残差后说明适用边界。
\par
\textbf{问题二：}采用算法求解，结果通过敏感性验证，并说明误差条件。
\par
\textbf{问题三：}建立模型并得到结果，以稳健性实验说明适用边界。
\end{abstract}
关键词：模型；验证
\clearpage
\tableofcontents
\clearpage
\section{问题重述}
见图可知结果。\cite{used}
"""
            + extra
            + r"""
\begin{thebibliography}{9}
\bibitem{used} 张三. 数学建模[M]. 北京: 示例出版社, 2024.
\end{thebibliography}
\end{document}
""",
            encoding="utf-8",
        )

    def write_blank_pdf(self, root: Path, pages: int = 1) -> None:
        path = canonical_pdf(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=595, height=842)
        with path.open("wb") as stream:
            writer.write(stream)

    def built_manifest(self, root: Path) -> dict:
        manifest = begin_batch(root)
        record_build(root, manifest, command=["latexmk"], returncode=0, log="ok", log_path="build.log")
        self.write_blank_pdf(root)
        record_pdf(root, manifest, page_count=1)
        write_manifest(root, manifest)
        return manifest

    def finding_codes(self, root: Path) -> set[str]:
        report = ContestFinalAuditor(root).run()
        return {item["code"] for item in report["findings"]}

    def test_manifest_rejects_wrong_pdf_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = begin_batch(root)
            manifest["canonical_pdf"] = "paper/main.pdf"
            path = root / "planning" / "delivery_manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(DeliveryContractError):
                load_manifest(root)

    def test_missing_pdf_and_stale_hash_are_hard_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_source(root)
            manifest = begin_batch(root)
            record_build(root, manifest, command=["latexmk"], returncode=0, log="ok", log_path="build.log")
            write_manifest(root, manifest)
            self.assertIn("canonical_pdf", self.finding_codes(root))

            self.write_blank_pdf(root)
            record_pdf(root, manifest, page_count=1)
            write_manifest(root, manifest)
            (root / "paper" / "main.tex").write_text("changed", encoding="utf-8")
            self.assertIn("artifact_hash", self.finding_codes(root))

    def test_declared_supplemental_evidence_is_hashed_and_stale_content_fails(self) -> None:
        from delivery_contract import record_supplemental_evidence

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_source(root)
            evidence = root / "checks" / "independent_recompute.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text('{"verdict":"PASS"}\n', encoding="utf-8")
            declaration = root / "planning" / "delivery_evidence.json"
            declaration.parent.mkdir(parents=True)
            declaration.write_text(
                json.dumps({"schema_version": 1, "files": [{"path": "checks/independent_recompute.json"}]}),
                encoding="utf-8",
            )
            manifest = self.built_manifest(root)
            record_supplemental_evidence(root, manifest)
            write_manifest(root, manifest)
            self.assertNotIn("artifact_hash", self.finding_codes(root))

            evidence.write_text('{"verdict":"CHANGED"}\n', encoding="utf-8")
            self.assertIn("artifact_hash", self.finding_codes(root))

    def test_new_batch_cannot_reuse_an_old_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_source(root)
            manifest = self.built_manifest(root)
            record_audit(root, manifest, verdict="PASS", report="checks/old.json", blockers=[])
            old_batch = manifest["batch_id"]

            new_manifest = begin_batch(root)
            self.assertEqual(new_manifest["status"], "DRAFT")
            self.assertNotEqual(new_manifest["batch_id"], old_batch)
            self.assertEqual(new_manifest["audit"]["status"], "NOT_RUN")

    def test_raw_math_markdown_table_and_orphan_reference_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_source(
                root,
                extra=r"""
x_i is outside math mode.
| raw | markdown |
|---|---|
\begin{thebibliography}{9}
\bibitem{orphan} 李四. 未引用材料[M]. 上海: 示例出版社, 2020.
\end{thebibliography}
""",
            )
            self.built_manifest(root)
            codes = self.finding_codes(root)
            self.assertIn("math_mode", codes)
            self.assertIn("markdown_tables", codes)
            self.assertIn("orphan_references", codes)

    def test_combined_usepackage_group_loads_booktabs(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""\usepackage{booktabs,array,tabularx}
\begin{table}
\caption{Result}
\begin{tabular}{ll}
\toprule A & B \\
\midrule 1 & 2 \\
\bottomrule
\end{tabular}
\end{table}
"""

        auditor._audit_tables()

        self.assertTrue(auditor.metrics["uses_booktabs"])
        self.assertNotIn("booktabs_package", {item.code for item in auditor.findings})

    def test_figinc_filename_is_not_naked_math(self) -> None:
        source = r"\figinc{fig01_spiral_coordinate_definition.pdf}"
        self.assertEqual(naked_math_tokens(source), [])

    def test_flowinc_filename_is_not_naked_math(self) -> None:
        source = r"\flowinc{q3_q4_search_scope.pdf}"
        self.assertEqual(naked_math_tokens(source), [])

    def test_stop_marker_requires_a_heading_line(self) -> None:
        pages = [
            "Contents",
            "Problem restatement\nThe appendix is not rewritten separately.",
            "Model derivation and validation",
            "References\n[1] Exact method source.",
        ]

        self.assertFalse(page_has_heading_marker(pages[1], ["appendix"]))
        self.assertEqual(find_marker_page(pages, ["appendix", "references"], 1, heading_only=True), 3)

        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.pages = pages
        auditor._audit_page_scope()
        self.assertEqual(auditor.metrics["effective_body_pages"], 2)
        self.assertEqual(auditor.metrics["body_stop_page"], 4)

    def test_all_supported_graphic_macros_are_counted(self) -> None:
        source = r"""
\begin{figure}\includegraphics{native.pdf}\caption{A}\end{figure}
\begin{figure}\figinc{claim_figure.pdf}\caption{B}\end{figure}
\begin{figure}\flowinc{overall_model_route.pdf}\caption{C}\end{figure}
"""
        expected = ["native.pdf", "claim_figure.pdf", "overall_model_route.pdf"]

        self.assertEqual(includegraphics(source), expected)
        self.assertEqual([item.path for item in figure_blocks(source)], expected)
        self.assertEqual(_count_figure_includes(source), 3)
        self.assertEqual(_count_flowchart_includes(source), 1)
        self.assertEqual(_count_figure_refs(source), 3)

    def test_graphics_inside_wrapper_macro_definitions_are_not_counted(self) -> None:
        source = r"""
\newcommand{\figinc}[1]{%
  \includegraphics[width=0.9\textwidth]{#1}%
}
\newcommand{\flowinc}[1][0.8\textwidth]{\includegraphics[width=#1]{#2}}
\begin{document}
\figinc{claim_figure.pdf}
\flowinc{overall_model_route.pdf}
\includegraphics{native.pdf}
\end{document}
"""

        self.assertEqual(_count_figure_includes(source), 3)
        self.assertEqual(_count_flowchart_includes(source), 1)

    def test_diagram_directory_graphics_are_counted_as_flowcharts(self) -> None:
        source = r"""
\includegraphics{../diagrams/overall_quality_route.pdf}
\figinc{figures/claim_figure.pdf}
\includegraphics{..\diagrams\q3_tree_dp.pdf}
"""

        self.assertEqual(_count_figure_includes(source), 3)
        self.assertEqual(_count_flowchart_includes(source), 2)

    def test_anonymous_b_problem_cover_is_an_official_signal(self) -> None:
        cover = "2024 年高教社杯全国大学生数学建模竞赛\n题号：B\n题目：生产过程中的决策问题\n匿名评审稿"

        self.assertTrue(_has_official_cover_signal(cover, ""))
        self.assertFalse(_has_official_cover_signal(cover.replace("匿名评审稿", ""), ""))

    def test_contest_audit_counts_canonical_diagram_paths_as_flowcharts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auditor = ContestFinalAuditor(Path(temp_dir))
            auditor.source_text = r"""
图 \ref{fig:tree-route} 给出递推与验证之间的关系。
\begin{figure}
\includegraphics{../diagrams/q3_tree_dp.pdf}
\caption{树形动态规划与完整枚举的双证据链}
\label{fig:tree-route}
\end{figure}
由图 \ref{fig:tree-route} 可知，两条证据链在最终利润上相互核验。
"""

            auditor._audit_figures_and_flowcharts()

            self.assertEqual(auditor.metrics["flowchart_figure_count"], 1)
            self.assertFalse(any(item.code == "figure_narrative" for item in auditor.findings))

    def test_chinese_markdown_index_header_is_not_counted_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index = Path(temp_dir) / "figure_index.md"
            index.write_text(
                "# 图表证据索引\n\n"
                "| 图文件 | 主张 ID | 数据来源 | 读者问题 | 论文位置 |\n"
                "|---|---|---|---|---|\n"
                "| `figures/a.pdf` | `C-Q1` | `data/a.csv` | 是否成立？ | 问题一 |\n",
                encoding="utf-8",
            )

            self.assertEqual(_index_rows(index), (1, 1))

    def test_figure_narrative_binds_current_label_around_figinc(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""
The domain scan in Figure \ref{fig:domain} lets the reader inspect the complete search interval.
\begin{figure}
  \figinc{fig06_q2_event_domain_scan.pdf}
  \caption{Complete event-domain scan}
  \label{fig:domain}
\end{figure}
Figure \ref{fig:domain} establishes that the first event lies strictly inside the search domain.
"""

        auditor._audit_figures_and_flowcharts()

        self.assertEqual(auditor.metrics["figure_count"], 1)
        self.assertNotIn("figure_narrative", {item.code for item in auditor.findings})

    def test_figure_narrative_accepts_flowinc(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""
The dependency structure in Figure \ref{fig:route} separates solving from validation.
\begin{figure}
  \flowinc{overall_model_route.pdf}
  \caption{Overall model route}
  \label{fig:route}
\end{figure}
Figure \ref{fig:route} shows that exact and best-found claims use different evidence branches.
"""

        auditor._audit_figures_and_flowcharts()

        self.assertEqual(auditor.metrics["figure_count"], 1)
        self.assertNotIn("figure_narrative", {item.code for item in auditor.findings})

    def test_figure_narrative_accepts_nested_latex_in_caption(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""
Figure \ref{fig:solver} compares the two independently computed objectives.
\begin{figure}
  \includegraphics{solver_check.pdf}
  \caption{Solver difference is \(8.47\times 10^{-12}\) units}
  \label{fig:solver}
\end{figure}
Figure \ref{fig:solver} shows that the remaining difference is floating-point error.
"""

        auditor._audit_figures_and_flowcharts()

        self.assertEqual(auditor.metrics["figure_count"], 1)
        self.assertNotIn("figure_narrative", {item.code for item in auditor.findings})

    def test_citation_binding_requires_records_fields_coverage_and_real_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper = root / "paper" / "main.tex"
            paper.parent.mkdir(parents=True)
            source = "\n".join(
                [
                    r"\documentclass{ctexart}",
                    r"\bibliographystyle{gbt7714-numerical}",
                    r"Method one follows \cite{first} and method two follows \cite{second}.",
                    r"\begin{thebibliography}{9}",
                    r"\bibitem{first} First source.",
                    r"\bibitem{second} Second source.",
                    r"\end{thebibliography}",
                ]
            )
            paper.write_text(source, encoding="utf-8")
            binding_path = root / "planning" / "citation_bindings.json"
            binding_path.parent.mkdir(parents=True)
            invalid_payloads = (
                {"version": 1, "bindings": []},
                {"version": 1, "bindings": [{"citation_key": "first"}]},
                {
                    "version": 1,
                    "bindings": [
                        {
                            "claim_id": "CLM-Q1-01",
                            "claim_type": "method",
                            "paper_location": "paper/main.tex:3",
                            "citation_key": "first",
                            "source_type": "book",
                            "support_scope": "Only the documented numerical method is supported.",
                            "used_for": "Method selection and reproducibility.",
                        }
                    ],
                },
            )
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    binding_path.write_text(json.dumps(payload), encoding="utf-8")
                    auditor = ContestFinalAuditor(root)
                    auditor.source_text = source
                    auditor.source_files = [paper]
                    auditor._audit_references()
                    self.assertIn("citation_binding", {item.code for item in auditor.findings})

            valid = {
                "version": 1,
                "bindings": [
                    {
                        "claim_id": "CLM-Q1-01",
                        "claim_type": "method",
                        "paper_location": "paper/main.tex:3",
                        "citation_key": key,
                        "source_type": "book",
                        "support_scope": "Only the cited algorithmic statement is supported.",
                        "used_for": "Method selection and reproducibility.",
                    }
                    for key in ("first", "second")
                ],
            }
            binding_path.write_text(json.dumps(valid), encoding="utf-8")
            auditor = ContestFinalAuditor(root)
            auditor.source_text = source
            auditor.source_files = [paper]
            auditor._audit_references()
            self.assertNotIn("citation_binding", {item.code for item in auditor.findings})

    def test_gbt_numeric_rejects_cite_package_and_author_year_pdf_labels(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""
\usepackage{cite}
\bibliographystyle{gbt7714-numerical}
Method follows \cite{davis}.
\begin{thebibliography}{9}
\bibitem[Davis(1993)]{davis} Davis. Spirals.
\end{thebibliography}
"""
        auditor.pages = ["References\n[Davis(1993)] DAVIS P J. Spirals. 1993."]

        auditor._audit_references()

        codes = {item.code for item in auditor.findings}
        self.assertIn("bibliography_numeric_config", codes)
        self.assertIn("bibliography_pdf_labels", codes)

    def test_gbt_numeric_accepts_natbib_and_numeric_pdf_labels(self) -> None:
        auditor = ContestFinalAuditor(Path(tempfile.gettempdir()))
        auditor.source_text = r"""
\usepackage[numbers,sort&compress]{natbib}
\bibliographystyle{gbt7714-numerical}
Method follows \cite{davis}.
\begin{thebibliography}{9}
\bibitem{davis} Davis. Spirals.
\end{thebibliography}
"""
        auditor.pages = ["References\n[1] DAVIS P J. Spirals. 1993."]

        auditor._audit_references()

        codes = {item.code for item in auditor.findings}
        self.assertNotIn("bibliography_numeric_config", codes)
        self.assertNotIn("bibliography_pdf_labels", codes)

    def test_heading_color_scan_ignores_top_figure_but_detects_colored_heading(self) -> None:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1000, 1400), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((80, 40, 920, 260), fill=(40, 110, 170))
        band = [(650.0, 18.0, 842.0)]
        self.assertEqual(heading_color_ratios(image, band), [0.0])

        center = int((842.0 - 650.0) * image.height / 842.0)
        draw.rectangle((140, center - 28, 500, center + 8), fill=(35, 105, 160))
        self.assertGreater(heading_color_ratios(image, band)[0], 0.001)

    def test_pdf_heading_candidate_rejects_vector_figure_text(self) -> None:
        figure_cm = [0.5, 0.0, 0.0, -0.5, 151.3, 47.463]
        figure_tm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        self.assertFalse(
            is_pdf_heading_candidate("1.1", 18.0, 23, figure_cm, figure_tm, {"1", "1.1"}, 3)
        )

    def test_pdf_heading_candidate_accepts_native_chapter_heading(self) -> None:
        page_cm = [1.0, 0.0, 0.0, 1.0, 72.0, 769.89]
        heading_tm = [1.0, 0.0, 0.0, 1.0, -2.551, -43.373]

        self.assertTrue(
            is_pdf_heading_candidate("1.1", 14.0, 3, page_cm, heading_tm, {"1", "1.1"}, 3)
        )
        self.assertFalse(
            is_pdf_heading_candidate("1.1", 14.0, 3, page_cm, heading_tm, {"1"}, 3)
        )
        self.assertFalse(
            is_pdf_heading_candidate("1.1", 14.0, 2, page_cm, heading_tm, {"1", "1.1"}, 3)
        )

    def test_flowchart_component_does_not_receive_unsupported_output_level(self) -> None:
        arguments = dict(COMPONENT_GATES)["flowchart_diagram_gate.py"]
        self.assertNotIn("--output-level", arguments)

    def test_markdown_only_project_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper").mkdir(parents=True)
            (root / "paper" / "main.md").write_text("# paper", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "contest_final_pipeline.py"), "--root", str(root), "--skip-components"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(load_manifest(root)["status"], "DRAFT")

    def test_toc_body_title_is_not_misclassified_as_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auditor = ContestFinalAuditor(Path(temp_dir))
            auditor.source_text = r"""\documentclass{ctexart}
\begin{document}
\begin{abstract}
\textbf{问题一：}建立模型并得到结果，以残差验证并说明适用边界。
\par
\textbf{问题二：}采用算法求解，结果经稳健性检验并说明误差条件。
\end{abstract}
关键词：模型；验证
\clearpage
\tableofcontents
\clearpage
\section{题意边界与回答口径}
\end{document}
"""
            auditor.pages = [
                "摘要\n问题一：模型与结果\n问题二：验证与边界\n关键词：模型；验证",
                "目录\n1 题意边界与回答口径 ........ 3\n2 统一几何与运动学基础 ........ 5",
                "1 题意边界与回答口径\n本文从题面约束和回答口径开始建立统一定义。",
                "2 统一几何与运动学基础\n正文内容继续。",
            ]

            auditor._audit_front_matter()
            auditor._audit_page_scope()

            codes = {item.code for item in auditor.findings}
            self.assertNotIn("toc_pdf_page", codes)
            self.assertNotIn("abstract_pdf_page", codes)
            self.assertEqual(auditor.metrics["detected_body_start_page"], 3)
            self.assertEqual(auditor.metrics["body_start_page"], 3)

    def test_appendix_mention_of_toc_is_not_classified_as_toc_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            auditor = ContestFinalAuditor(Path(temp_dir))
            auditor.pages = [
                "摘要\n关键词：模型；验证",
                "目录\n1 问题重述 ........ 3",
                "1 问题重述\n正文内容。",
                "附录\n本附录整理历史测试项目目录与运行清单。",
            ]

            self.assertEqual(auditor._toc_pages(), [2])
            self.assertEqual(auditor._body_start_index(), 2)

    def test_structured_flowchart_renders_vector_and_300_dpi_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "planning" / "flowcharts"
            source_dir.mkdir(parents=True)
            source = source_dir / "overall_technical_route.json"
            shutil.copy2(SKILL_ROOT / "assets" / "templates" / "flowchart_spec.json", source)
            intent = {
                "version": 1,
                "intents": [
                    {
                        "diagram_id": "overall_technical_route",
                        "tool_route": "python_matplotlib",
                        "source_file": "planning/flowcharts/overall_technical_route.json",
                        "export_file": "diagrams/overall_technical_route.pdf",
                        "png_file": "diagrams/overall_technical_route.png",
                    }
                ],
            }
            (root / "planning" / "diagram_intent_pack.json").write_text(json.dumps(intent, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "structured_flowchart_gate.py"), "--root", str(root), "--render"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / "checks" / "structured_flowchart_gate.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "PASS")
            self.assertTrue((root / "diagrams" / "overall_technical_route.pdf").is_file())
            self.assertTrue((root / "diagrams" / "overall_technical_route.png").is_file())

    def test_generic_three_node_flowchart_is_rejected(self) -> None:
        spec_path = SKILL_ROOT / "assets" / "templates" / "flowchart_spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["nodes"] = spec["nodes"][:3]
        ids = {item["id"] for item in spec["nodes"]}
        spec["edges"] = [item for item in spec["edges"] if item["from"] in ids and item["to"] in ids]
        with tempfile.TemporaryDirectory() as temp_dir:
            report = StructuredFlowchart(spec, spec_path, Path(temp_dir)).run(audit_only=True)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("information_value", {item["code"] for item in report["findings"]})

    def test_flowchart_label_preserves_manual_breaks_and_decimal_tokens(self) -> None:
        label, truncated = wrap_label("方案总长\n17.358924 米", max_chars=14, max_lines=3)
        self.assertEqual(label, "方案总长\n17.358924 米")
        self.assertFalse(truncated)

        label, truncated = wrap_label("冻结流量上限 2.718281 米每秒", max_chars=14, max_lines=3)
        self.assertIn("2.718281", label)
        self.assertNotIn("2.\n718281", label)
        self.assertFalse(truncated)

    def test_top_to_bottom_flowchart_uses_vertical_levels_and_lane_columns(self) -> None:
        spec_path = SKILL_ROOT / "assets" / "templates" / "flowchart_spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["orientation"] = "top_to_bottom"
        spec["layout"]["lane_width"] = 3.0
        with tempfile.TemporaryDirectory() as temp_dir:
            chart = StructuredFlowchart(spec, spec_path, Path(temp_dir))
            chart._validate_schema()
            chart._layout()
        self.assertEqual(chart.metrics["orientation"], "top_to_bottom")
        self.assertLess(chart.positions["core"][1], chart.positions["input"][1])
        self.assertNotEqual(chart.positions["q1"][0], chart.positions["q2"][0])

    def test_python_figure_evidence_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "q1_validation",
                    "--claim-id",
                    "C-Q1-VALIDATION",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["metrics"]["python_figures"], 1)

    def test_flowchart_gate_recognizes_figinc_macro(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper").mkdir(parents=True)
            (root / "diagrams").mkdir(parents=True)
            (root / "paper" / "main.tex").write_text(
                r"\begin{figure}\figinc{overall_workflow.pdf}\caption{Workflow}\end{figure}",
                encoding="utf-8",
            )
            (root / "diagrams" / "overall_workflow.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "flowchart_diagram_gate.py"),
                    "--root",
                    str(root),
                    "--write-json",
                    "checks/flowchart_diagram_report.json",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertIn(result.returncode, {0, 1})
            report = json.loads((root / "checks" / "flowchart_diagram_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["metrics"]["included_flow_diagrams"], ["overall_workflow.pdf"])

    def test_python_artifact_cannot_be_forged_as_matlab_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "matlab_validation",
                    "--claim-id",
                    "C-Q1-MATLAB",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            matlab_source = root / "code" / "matlab" / "matlab_validation.m"
            matlab_source.parent.mkdir(parents=True)
            shutil.copy2(root / "code" / "python" / "plot_matlab_validation.py", matlab_source)
            matlab_log = root / "results" / "logs" / "matlab_validation.log"
            matlab_log.write_text("backend=MATLAB R2025a\nstatus=success\n", encoding="utf-8")
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["figures"][0]
            record.update(
                {
                    "backend": "MATLAB R2025a",
                    "evidence_role": "sensitivity",
                    "backend_reason": "动态响应和稳态误差属于 MATLAB 优先的工程数值证据。",
                    "source_file": "code/matlab/matlab_validation.m",
                    "log_file": "results/logs/matlab_validation.log",
                    "reader_question": "动态控制响应是否在规定时间内收敛并保持在稳态误差范围内？",
                    "expected_inference": "响应轨迹进入目标邻域后保持稳定，局部误差未超过规定的容差界限。",
                }
            )
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("provenance_route", {item["code"] for item in report["findings"]})

    def test_python_override_for_matlab_priority_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "bad_override",
                    "--claim-id",
                    "C-Q2-ODE",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=True,
            )
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["figures"][0]
            record["reader_question"] = "Does the ODE control response remain stable throughout the parameter scan?"
            record["expected_inference"] = "The response surface and optimization trajectory support the stability claim."
            record["backend_reason"] = "easier"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("backend_choice", {item["code"] for item in report["findings"]})

    def test_local_inset_semantics_distinguish_structure_from_critical_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "collision_structure",
                    "--claim-id",
                    "C-Q2-STRUCTURE",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["figures"][0]
            record.update(
                {
                    "evidence_role": "structure",
                    "reader_question": "How is the collision geometry represented before the event search begins?",
                    "expected_inference": "The finite-width rectangles define the collision mechanism used by later computations.",
                    "layout": "single",
                }
            )
            record.pop("has_local_inset", None)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            structure = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            structure_report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertNotIn("local_inset", {item["code"] for item in structure_report["findings"]})

            record["evidence_role"] = "validation"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            critical = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertNotEqual(critical.returncode, 0)
            critical_report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("local_inset", {item["code"] for item in critical_report["findings"]})


if __name__ == "__main__":
    unittest.main()
