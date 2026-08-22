from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RESULT_SCRIPT = SKILL_ROOT / "scripts" / "result_quality.py"
CONSISTENCY_SCRIPT = SKILL_ROOT / "scripts" / "model_solver_consistency.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ResultQualityContractTests(unittest.TestCase):
    def make_scale_project(self, root: Path) -> dict:
        (root / "paper").mkdir(parents=True)
        (root / "results" / "tables").mkdir(parents=True)
        (root / "paper" / "main.tex").write_text(
            r"\section{Q3}\label{q3-scale} travel 59, penalty 5038400, objective 5038459; best-found only.",
            encoding="utf-8",
        )
        evidence = root / "results" / "tables" / "q3_bound.csv"
        evidence.write_text("position,bound\n1,4588880\n", encoding="utf-8")
        return {
            "status": "CERTIFIED",
            "basis": "structural_lower_bound",
            "claim_scope": "best_found",
            "component_check": {
                "travel": 59,
                "penalty": 5038400,
                "objective": 5038459,
                "tolerance": 1e-9,
            },
            "evidence": ["results/tables/q3_bound.csv"],
            "structural_bound_source": "results/tables/q3_bound.csv",
            "paper_anchor": "q3-scale",
        }

    def make_quality(self, root: Path):
        module = runpy.run_path(str(RESULT_SCRIPT))
        args = type(
            "Args",
            (),
            {
                "root": str(root),
                "frozen": None,
                "write_report": None,
                "write_json": None,
                "strict_warnings": False,
                "allow_warnings": False,
            },
        )()
        return module["ResultQuality"](args)

    def test_structured_scale_certification_requires_numeric_evidence_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cert = self.make_scale_project(root)
            quality = self.make_quality(root)
            data = {
                "structural_penalty_lower_bound": 4588880,
                "penalty_scale_certification": cert,
            }
            structural = quality._structural_penalty_evidence(data, 5038400)
            result = quality._penalty_scale_certification(
                "Q3", data, 59, 5038400, 5038459, False, structural
            )
            self.assertTrue(result["valid"], result["errors"])

            cert["component_check"]["penalty"] = 1
            result = quality._penalty_scale_certification(
                "Q3", data, 59, 5038400, 5038459, False, structural
            )
            self.assertFalse(result["valid"])
            self.assertTrue(any("component_check.penalty" in error for error in result["errors"]))

    def test_analysis_only_case_does_not_require_solver_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "results" / "tables").mkdir(parents=True)
            (root / "paper").mkdir()
            (root / "paper" / "main.tex").write_text("Input data audit.", encoding="utf-8")
            (root / "results" / "frozen_numbers.json").write_text(
                json.dumps({"q0": {"method_kind": "data_audit", "analysis_only": True}}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(CONSISTENCY_SCRIPT), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("frozen result has no recoverable actual solver method", result.stdout)

    def test_result_quality_cli_accepts_explicit_output_level(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "results").mkdir(parents=True)
            (root / "results" / "frozen_numbers.json").write_text("{}", encoding="utf-8")
            report = root / "result_quality.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RESULT_SCRIPT),
                    "--root",
                    str(root),
                    "--output-level",
                    "quick_draft",
                    "--write-json",
                    str(report),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["metrics"]["output_level"], "quick_draft")

    def test_consistency_audits_only_manifest_canonical_paper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "planning").mkdir(parents=True)
            (root / "paper").mkdir()
            (root / "results" / "tables").mkdir(parents=True)
            (root / "checks").mkdir()
            (root / "paper" / "main.tex").write_text(
                r"\section{问题一} 四问互不相干，但本文统一建模。",
                encoding="utf-8",
            )
            (root / "paper" / "legacy_draft.md").write_text(
                "Kaiwu SDK quantum backend was not executed.",
                encoding="utf-8",
            )
            (root / "results" / "frozen_numbers.json").write_text(
                json.dumps({"q0": {"method_kind": "data_audit", "analysis_only": True}}),
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "profile": "contest_final",
                "project_root": str(root.resolve()),
                "canonical_source": "paper/main.tex",
                "canonical_pdf": "output/contest_final/paper.pdf",
                "build_engine": "xelatex",
                "status": "DRAFT",
                "batch_id": "test-canonical-source",
            }
            (root / "planning" / "delivery_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            report = root / "checks" / "model_solver_consistency.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CONSISTENCY_SCRIPT),
                    "--root",
                    str(root),
                    "--write-json",
                    str(report),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["metrics"]["paper_source"], "paper/main.tex")
            self.assertNotIn("paper/legacy_draft.md", payload["metrics"]["text_sources"])
            self.assertFalse(
                any(item["axis"] == "backend_execution" for item in payload["findings"]),
                payload["findings"],
            )


if __name__ == "__main__":
    unittest.main()
