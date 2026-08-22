from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "blind_review_harness.py"
RUBRIC = json.loads((SKILL_ROOT / "benchmarks" / "award-readiness-rubric.json").read_text(encoding="utf-8"))
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class BlindReviewHarnessTests(unittest.TestCase):
    comparison_id = "internal_geometry_case"
    assignment_seed = "fixed-test-seed"

    def make_pdf(self, path: Path, text: str, author: str) -> None:
        path.parent.mkdir(parents=True)
        document = canvas.Canvas(str(path))
        document.setAuthor(author)
        document.setTitle(author)
        document.drawString(72, 760, text)
        document.save()

    def make_candidate(self, root: Path, name: str, role: str, floor: str = "PASS", paper_text: str = "Contest paper") -> dict:
        candidate_root = root / "runs" / name
        (candidate_root / "planning").mkdir(parents=True)
        (candidate_root / "checks").mkdir()
        (candidate_root / "materials").mkdir()
        (candidate_root / "materials" / "problem.txt").write_text("identical frozen problem", encoding="utf-8")
        (candidate_root / "checks" / "floor.json").write_text(
            json.dumps({"technical_readiness": floor}), encoding="utf-8"
        )
        generator_id = f"generator-{name}"
        self.make_pdf(candidate_root / "output" / "paper.pdf", paper_text, generator_id)
        run_manifest = {
            "version": 1,
            "clean_root_verified": True,
            "started_empty": True,
            "paper_pdf": "output/paper.pdf",
            "technical_floor_report": "checks/floor.json",
            "input_files": [{"logical_name": "problem", "path": "materials/problem.txt"}],
            "resource_budget": {
                "wall_clock_minutes": 180,
                "cpu_cores": 4,
                "memory_gb": 8,
                "output_level": "contest_final",
                "human_intervention": "frozen",
            },
        }
        (candidate_root / "planning" / "run_manifest.json").write_text(
            json.dumps(run_manifest), encoding="utf-8"
        )
        return {
            "candidate_id": name,
            "role": role,
            "root": f"runs/{name}",
            "run_manifest": "planning/run_manifest.json",
            "generator_id": generator_id,
        }

    def label_map(self, candidate_ids: list[str]) -> dict[str, str]:
        ordered = sorted(candidate_ids)
        digest = hashlib.sha256(f"{self.comparison_id}\0{self.assignment_seed}".encode("utf-8")).digest()
        if digest[0] % 2 == 1:
            ordered.reverse()
        return {"A": ordered[0], "B": ordered[1]}

    def make_reviews(self, candidate_label: str, outcome: str = "candidate", low_confidence: bool = False) -> dict:
        axes = [axis for axis in RUBRIC["weighted_axes"] if axis["review_owner"] in {"blind_reviewer", "mixed_review"}]
        other_label = "B" if candidate_label == "A" else "A"
        rounds = []
        for reviewer_index, order in enumerate((["A", "B"], ["B", "A"]), start=1):
            rows = []
            for axis_index, axis in enumerate(axes):
                scores = {"A": 2, "B": 2}
                if outcome == "candidate":
                    scores[candidate_label] = 3
                    scores[other_label] = 2
                elif outcome == "other":
                    scores[candidate_label] = 2
                    scores[other_label] = 3
                preference = "A" if scores["A"] > scores["B"] else ("B" if scores["B"] > scores["A"] else "TIE")
                rows.append(
                    {
                        "axis_id": axis["id"],
                        "score_A": scores["A"],
                        "score_B": scores["B"],
                        "preference": preference,
                        "confidence": "low" if low_confidence and reviewer_index == 1 and axis_index == 0 else "high",
                        "evidence_locators": {"A": ["A.pdf#page=1"], "B": ["B.pdf#page=1"]},
                        "rationale": "The cited pages support the problem-specific anchored comparison for both papers.",
                    }
                )
            rounds.append({"reviewer_id": f"reviewer-{reviewer_index}", "display_order": order, "axis_reviews": rows})
        return {
            "version": 1,
            "reviewers": [
                {
                    "reviewer_id": "reviewer-1",
                    "reviewer_model_id": "independent-a",
                    "authorized": True,
                    "independent": True,
                },
                {
                    "reviewer_id": "reviewer-2",
                    "reviewer_model_id": "independent-b",
                    "authorized": True,
                    "independent": True,
                },
            ],
            "rounds": rounds,
        }

    def make_project(
        self,
        root: Path,
        *,
        candidate_floor: str = "PASS",
        candidate_text: str = "Contest paper candidate",
        outcome: str = "candidate",
        low_confidence: bool = False,
    ) -> None:
        (root / "planning").mkdir()
        candidates = [
            self.make_candidate(root, "baseline", "baseline", paper_text="Contest paper baseline"),
            self.make_candidate(root, "candidate", "candidate", floor=candidate_floor, paper_text=candidate_text),
        ]
        manifest = {
            "version": 1,
            "comparison_id": self.comparison_id,
            "case_id": "GENERIC-CONTINUOUS-CASE",
            "comparison_kind": "internal",
            "evidence_class": "fresh_double_run",
            "problem_family": "continuous geometry",
            "assignment_seed": self.assignment_seed,
            "blind_output_dir": "checks/blind/internal_geometry_case",
            "review_file": "planning/blind_reviews.json",
            "identity_terms": ["mira 0.10", "mira 0.11"],
            "candidates": candidates,
        }
        labels = self.label_map(["baseline", "candidate"])
        candidate_label = next(label for label, candidate_id in labels.items() if candidate_id == "candidate")
        (root / "planning" / "blind_comparison.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        (root / "planning" / "blind_reviews.json").write_text(
            json.dumps(self.make_reviews(candidate_label, outcome, low_confidence), ensure_ascii=False), encoding="utf-8"
        )

    def run_harness(self, root: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        report = json.loads((root / "checks" / "blind_comparison_report.json").read_text(encoding="utf-8"))
        return result, report

    def test_complete_order_reversed_comparison_passes_and_scrubs_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            result, report = self.run_harness(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["evidence_class"], "fresh_double_run")
            self.assertTrue(report["promotion_eligible"])
            self.assertEqual(report["candidate_case_preference"], "PREFERRED")
            for record in report["anonymized_outputs"].values():
                metadata = PdfReader(root / record["path"]).metadata or {}
                self.assertNotIn("generator-", " ".join(str(value) for value in metadata.values()))

    def test_tie_remains_tie(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, outcome="tie")
            result, report = self.run_harness(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["candidate_case_preference"], "TIE")

    def test_visible_identity_leak_blocks_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, candidate_text="Mira 0.11 contest paper")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity_leak", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_l1_regression_blocks_preference_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, candidate_floor="FAIL")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("l1_regression", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_low_confidence_decisive_score_blocks_preference_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, low_confidence=True)
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("low_confidence_decisive", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_mismatched_frozen_input_hashes_block_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            (root / "runs" / "candidate" / "materials" / "problem.txt").write_text(
                "different problem input", encoding="utf-8"
            )
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(report["equivalent_inputs"])
            self.assertIn("input_mismatch", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_matching_unknown_budgets_are_not_treated_as_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            for name in ("baseline", "candidate"):
                manifest_path = root / "runs" / name / "planning" / "run_manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["resource_budget"] = {"status": "unknown"}
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(report["equivalent_resource_budget"])
            self.assertIn("budget_mismatch", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_missing_order_reversal_blocks_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            review_path = root / "planning" / "blind_reviews.json"
            reviews = json.loads(review_path.read_text(encoding="utf-8"))
            reviews["rounds"][1]["display_order"] = ["A", "B"]
            review_path.write_text(json.dumps(reviews), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("order_reversal", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_unauthorized_self_reviewer_blocks_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            review_path = root / "planning" / "blind_reviews.json"
            reviews = json.loads(review_path.read_text(encoding="utf-8"))
            reviews["reviewers"][0]["authorized"] = False
            reviews["reviewers"][0]["reviewer_model_id"] = "generator-candidate"
            review_path.write_text(json.dumps(reviews), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("reviewer_authorization", codes)
            self.assertIn("self_review", codes)
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_external_comparator_without_provenance_blocks_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            manifest_path = root / "planning" / "blind_comparison.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["comparison_kind"] = "external"
            manifest["evidence_class"] = "external_calibration"
            for candidate in manifest["candidates"]:
                if candidate["role"] == "baseline":
                    candidate["role"] = "external_comparator"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("external_provenance", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")

    def test_migration_audit_can_pass_but_is_not_promotion_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            manifest_path = root / "planning" / "blind_comparison.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["evidence_class"] = "migration_audit"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["evidence_class"], "migration_audit")
            self.assertFalse(report["promotion_eligible"])

    def test_evidence_class_must_match_comparison_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            manifest_path = root / "planning" / "blind_comparison.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["evidence_class"] = "external_calibration"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result, report = self.run_harness(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("evidence_class", {item["code"] for item in report["findings"]})
            self.assertEqual(report["candidate_case_preference"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
