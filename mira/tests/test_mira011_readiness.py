from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "readiness_evaluator.py"
RUBRIC = SKILL_ROOT / "benchmarks" / "award-readiness-rubric.json"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ReadinessEvaluatorTests(unittest.TestCase):
    def complete_review(self) -> dict:
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
        floors = [
            {
                "axis_id": axis["id"],
                "status": "PASS",
                "evidence_locators": [f"checks/{axis['id'].lower()}.json"],
            }
            for axis in rubric["hard_floor"]["axes"]
        ]
        reviews = []
        for axis in rubric["weighted_axes"]:
            role = {
                "blind_reviewer": "blind_reviewer",
                "mixed_review": "mixed_reviewer",
                "deterministic_gate": "deterministic_gate",
            }[axis["review_owner"]]
            reviews.append(
                {
                    "axis_id": axis["id"],
                    "level": 3,
                    "reviewer_id": "gate" if role == "deterministic_gate" else "reviewer-01",
                    "reviewer_role": role,
                    "authorized": role == "deterministic_gate" or True,
                    "confidence": "high",
                    "evidence_locators": [f"paper.pdf#axis={axis['id']}"],
                    "rationale": "The located evidence satisfies the selected problem-specific rubric anchor.",
                }
            )
        return {"version": 1, "technical_floor": floors, "weighted_reviews": reviews}

    def run_evaluator(self, root: Path, review: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
        planning = root / "planning"
        planning.mkdir(parents=True)
        (planning / "readiness_review.json").write_text(
            json.dumps(review, ensure_ascii=False), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        report = json.loads((root / "checks" / "readiness_evaluation.json").read_text(encoding="utf-8"))
        return result, report

    def test_complete_authorized_review_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, report = self.run_evaluator(Path(temp_dir), self.complete_review())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["technical_readiness"], "PASS")
            self.assertEqual(report["competitive_profile"], "COMPLETE")
            self.assertIsNotNone(report["weighted_score"])

    def test_missing_subjective_review_remains_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review = self.complete_review()
            review["weighted_reviews"] = [
                item for item in review["weighted_reviews"] if item["axis_id"] != "P3"
            ]
            result, report = self.run_evaluator(Path(temp_dir), review)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(report["competitive_profile"], "UNVERIFIED")
            self.assertIn("P3", report["missing_axes"])

    def test_technical_failure_blocks_complete_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review = self.complete_review()
            review["technical_floor"][0]["status"] = "FAIL"
            result, report = self.run_evaluator(Path(temp_dir), review)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(report["technical_readiness"], "FAIL")
            self.assertNotEqual(report["competitive_profile"], "COMPLETE")
            self.assertIsNone(report["weighted_score"])

    def test_output_never_estimates_awards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, report = self.run_evaluator(Path(temp_dir), self.complete_review())
            self.assertEqual(report["award_probability"], "NOT_ESTIMATED")
            self.assertNotIn("award_band", report)
            self.assertNotIn("award_level", report)

    def test_failed_contest_evidence_chain_blocks_technical_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checks = root / "checks"
            checks.mkdir(parents=True)
            (checks / "contest_evidence_chain_report.json").write_text(
                json.dumps({"schema_version": 1, "verdict": "FAIL"}),
                encoding="utf-8",
            )

            result, report = self.run_evaluator(root, self.complete_review())

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(report["technical_readiness"], "FAIL")
            self.assertEqual(report["competitive_profile"], "INCOMPLETE")
            self.assertTrue(
                any(item["code"] == "contest_evidence_chain" for item in report["findings"])
            )

    def test_missing_contest_evidence_chain_report_keeps_legacy_review_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, report = self.run_evaluator(Path(temp_dir), self.complete_review())

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["technical_readiness"], "PASS")


if __name__ == "__main__":
    unittest.main()
