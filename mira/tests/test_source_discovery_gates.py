from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from award_review_gate import load_current_source_report  # noqa: E402
from abstract_layout_audit import paper_files as abstract_paper_files  # noqa: E402
from delivery_contract import aggregate_source_hash, collect_source_files, relative  # noqa: E402
from flowchart_diagram_gate import collect_metrics, paper_files  # noqa: E402
from iteration_loop import IterationLoop  # noqa: E402
from table_style_audit import paper_files as table_paper_files  # noqa: E402
from visual_reasoning_audit import audit  # noqa: E402


class SourceDiscoveryGateTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        (root / "paper" / "sections").mkdir(parents=True)
        (root / "diagrams").mkdir(parents=True)
        (root / "figures").mkdir(parents=True)
        (root / "paper" / "main.tex").write_text(
            "\\begin{abstract}Result 1.0.\\end{abstract}\n"
            "\\input{sections/q1}\n"
            "Figure~\\ref{fig:route} supports the decision.\n",
            encoding="utf-8",
        )
        (root / "paper" / "sections" / "q1.tex").write_text(
            "The workflow is shown below for validation.\n"
            "\\begin{figure}\n"
            "\\includegraphics{diagrams/overall_technical_route.pdf}\n"
            "\\caption{Overall technical workflow}\n"
            "\\label{fig:route}\n"
            "\\end{figure}\n"
            "The figure shows the model and validation branch.\n",
            encoding="utf-8",
        )
        (root / "paper" / "sections" / "orphan.tex").write_text(
            "This unreferenced draft must not affect current-paper audits.\n",
            encoding="utf-8",
        )
        (root / "diagrams" / "overall_technical_route.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")

    def test_explicit_tex_entry_recurses_like_automatic_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)

            explicit = paper_files(root, "paper/main.tex")
            automatic = paper_files(root, None)

            expected = ["paper/main.tex", "paper/sections/q1.tex"]
            self.assertEqual([relative(root, path) for path in explicit], expected)
            self.assertEqual([relative(root, path) for path in automatic], expected)
            self.assertEqual([relative(root, path) for path in abstract_paper_files(root, "paper/main.tex")], expected)
            self.assertEqual([relative(root, path) for path in table_paper_files(root, "paper/main.tex")], expected)

            metrics = collect_metrics(root, argparse.Namespace(paper="paper/main.tex"))
            self.assertEqual(metrics["paper_files"], expected)
            self.assertEqual(metrics["included_flow_diagrams"], ["diagrams/overall_technical_route.pdf"])

    def test_visual_audit_finds_figures_in_included_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)

            findings, metrics = audit(
                root,
                root / "paper" / "main.tex",
                root / "figures" / "figure_index.md",
                root / "diagrams" / "diagram_index.md",
            )

            self.assertEqual(metrics["source_files"], ["paper/main.tex", "paper/sections/q1.tex"])
            self.assertEqual(metrics["included_images"], 1)
            self.assertEqual(metrics["figure_blocks"], 1)
            self.assertEqual(metrics["captions"], 1)
            self.assertFalse(any(item.axis == "paper" for item in findings))

    def test_award_review_rejects_unfingerprinted_and_stale_flowchart_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            report_path = root / "checks" / "flowchart_diagram_report.json"
            report_path.parent.mkdir(parents=True)

            report_path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
            self.assertEqual(load_current_source_report(root, report_path), {})

            files = collect_source_files(root, root / "paper" / "main.tex")
            current = {
                "verdict": "PASS",
                "canonical_source": "paper/main.tex",
                "source_files": [relative(root, path) for path in files],
                "source_sha256": aggregate_source_hash(root, files),
            }
            report_path.write_text(json.dumps(current), encoding="utf-8")
            self.assertEqual(load_current_source_report(root, report_path).get("verdict"), "PASS")

            (root / "paper" / "sections" / "q1.tex").write_text("changed", encoding="utf-8")
            self.assertEqual(load_current_source_report(root, report_path), {})

    def test_iteration_loop_does_not_consume_unfingerprinted_flowchart_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            checks = root / "checks"
            checks.mkdir(parents=True)
            (checks / "flowchart_diagram_report.json").write_text(
                json.dumps({"verdict": "FAIL"}),
                encoding="utf-8",
            )
            (checks / "flowchart_diagram_report.md").write_text(
                "| Level | Axis | Message |\n"
                "|---|---|---|\n"
                "| FAIL | paper_inclusion | fake old failure |\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                root=str(root),
                write_report=None,
                allow_warnings=False,
                mark=None,
                status="resolved",
                evidence=None,
                prune_resolved=False,
            )

            self.assertEqual(IterationLoop(args).run(), 0)
            queue = json.loads((root / "revisions" / "iteration_queue.json").read_text(encoding="utf-8"))
            self.assertFalse(any("fake old failure" in item["finding"] for item in queue["items"]))
            self.assertTrue(any(item["axis"] == "control_state" for item in queue["items"]))
            report = (root / "revisions" / "iteration_report.md").read_text(encoding="utf-8")
            self.assertIn("Verdict: **PASS_WITH_WARNINGS**", report)


if __name__ == "__main__":
    unittest.main()
