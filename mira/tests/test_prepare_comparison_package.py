from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "prepare_comparison_package.py"
HARNESS = SKILL_ROOT / "scripts" / "blind_review_harness.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class PrepareComparisonPackageTests(unittest.TestCase):
    def make_pdf(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = canvas.Canvas(str(path))
        document.drawString(72, 760, text)
        document.save()

    def make_config(self, root: Path, expected_hash: str = "") -> Path:
        self.make_pdf(root / "sources" / "baseline.pdf", "baseline")
        self.make_pdf(root / "sources" / "candidate.pdf", "candidate")
        (root / "sources" / "problem.txt").write_text("same frozen problem", encoding="utf-8")
        (root / "sources" / "baseline_floor.json").write_text(
            json.dumps({"technical_readiness": "PASS"}), encoding="utf-8"
        )
        (root / "sources" / "candidate_delivery.json").write_text(
            json.dumps({"status": "READY"}), encoding="utf-8"
        )
        candidates = []
        for name, role, report in (
            ("baseline", "baseline", "sources/baseline_floor.json"),
            ("candidate", "candidate", "sources/candidate_delivery.json"),
        ):
            paper = {"path": f"sources/{name}.pdf"}
            if name == "candidate" and expected_hash:
                paper["sha256"] = expected_hash
            candidates.append(
                {
                    "candidate_id": name,
                    "role": role,
                    "generator_id": f"generator-{name}",
                    "paper": paper,
                    "technical_floor_source": report,
                    "input_files": [{"logical_name": "problem", "path": "sources/problem.txt"}],
                    "clean_root_verified": True,
                    "started_empty": True,
                    "resource_budget": {"status": "unknown"},
                    "historical_source": {"source_type": "historical_run", "locator": name},
                }
            )
        config = {
            "version": 1,
            "comparison_id": "migration_case",
            "case_id": "CASE-1",
            "comparison_kind": "internal",
            "evidence_class": "migration_audit",
            "problem_family": "geometry",
            "candidates": candidates,
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def run_script(self, root: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-root",
                str(root),
                "--config",
                "config.json",
                "--output-root",
                str(output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )

    def test_historical_package_records_real_hashes_without_claiming_clean_run_or_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_config(root)
            output = root / "package"
            result = self.run_script(root, output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((output / "planning" / "blind_reviews.json").exists())

            comparison = json.loads((output / "planning" / "blind_comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(comparison["evidence_class"], "migration_audit")
            for candidate in comparison["candidates"]:
                run_root = output / candidate["root"]
                run_manifest = json.loads((run_root / candidate["run_manifest"]).read_text(encoding="utf-8"))
                paper = run_root / run_manifest["paper_pdf"]
                self.assertFalse(run_manifest["clean_root_verified"])
                self.assertFalse(run_manifest["started_empty"])
                self.assertEqual(run_manifest["resource_budget"], {"status": "unknown"})
                self.assertEqual(run_manifest["paper_sha256"], digest(paper))
                input_record = run_manifest["input_files"][0]
                self.assertEqual(input_record["sha256"], digest(run_root / input_record["path"]))
                floor = json.loads((run_root / run_manifest["technical_floor_report"]).read_text(encoding="utf-8"))
                self.assertEqual(floor["technical_readiness"], "PASS")

            sources = json.loads((output / "planning" / "comparison_sources.json").read_text(encoding="utf-8"))
            self.assertEqual(sources["review_status"], "NOT_PROVIDED")
            self.assertEqual(len(sources["candidates"]), 2)

            harness = subprocess.run(
                [sys.executable, str(HARNESS), "--root", str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )
            self.assertNotEqual(harness.returncode, 0)
            report = json.loads((output / "checks" / "blind_comparison_report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report["anonymized_outputs"]), 2)
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("clean_root_claim", codes)
            self.assertIn("budget_mismatch", codes)
            self.assertIn("review_file", codes)
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_declared_source_hash_mismatch_fails_without_publishing_partial_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_config(root, expected_hash="0" * 64)
            output = root / "package"
            result = self.run_script(root, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256 mismatch", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
