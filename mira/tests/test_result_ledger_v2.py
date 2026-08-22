from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "result_ledger.py"
EVIDENCE_SCRIPT = SKILL_ROOT / "scripts" / "evidence_planner.py"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from contest_final_pipeline import COMPONENT_GATES  # noqa: E402


class ResultLedgerV2Tests(unittest.TestCase):
    def run_ledger(
        self,
        root: Path,
        frozen: dict,
        existing: dict | None = None,
        *,
        output_level: str = "contest_final",
        check: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        frozen_path = root / "results" / "frozen_numbers.json"
        ledger_path = root / "planning" / "result_ledger.json"
        frozen_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        frozen_path.write_text(json.dumps(frozen, ensure_ascii=False), encoding="utf-8")
        if existing is not None:
            ledger_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--output-level",
            output_level,
            "--write-report",
            "planning/result_ledger.md",
            "--write-json",
            "planning/result_ledger.json",
        ]
        if check:
            command.append("--check")
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
        return result, payload

    def test_two_problem_families_accept_distinct_insight_forms(self) -> None:
        cases = [
            (
                {"q1": {"max_radius": 12.5}},
                {
                    "key": "q1.max_radius",
                    "claim_id": "CLM-Q1-GEOMETRIC-BOUND",
                    "centrality": "central",
                    "claim_type": "bound",
                    "insight_form": "bound",
                    "mechanism": "The tangent constraint becomes active before the curvature constraint.",
                    "scope": "Valid for the stated planar geometry and positive radius range.",
                    "assumptions": ["Rigid boundary", "Planar motion"],
                    "uncertainty": {
                        "characterization": "The bound is exact up to solver tolerance.",
                        "decision_switch_risk": "No route switch occurs within the audited tolerance.",
                    },
                    "evidence": ["results/tables/boundary_audit.csv"],
                    "decision_implication": "Use 12.5 as the admissible design ceiling.",
                    "surprise_status": "surprising",
                },
            ),
            (
                {"q2": {"switch_time": 18.0}},
                {
                    "key": "q2.switch_time",
                    "claim_id": "CLM-Q2-POLICY-SWITCH",
                    "centrality": "central",
                    "claim_type": "threshold",
                    "insight_form": "threshold",
                    "mechanism": "Delay cost overtakes setup cost at the threshold.",
                    "scope": "Valid for the audited demand and cost interval.",
                    "assumptions": ["Demand remains inside the scenario envelope"],
                    "uncertainty": {
                        "characterization": "Bootstrap intervals shift the threshold by at most 0.7 time units.",
                        "decision_switch_risk": "The action changes only when the interval crosses 18.0.",
                    },
                    "evidence": ["results/tables/threshold_sweep.csv"],
                    "decision_implication": "Switch policy when the observed delay reaches 18.0.",
                    "surprise_status": "expected",
                },
            ),
        ]
        for frozen, entry in cases:
            with self.subTest(claim_id=entry["claim_id"]), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                existing = {"schema_version": 2, "entries": [entry]}
                result, payload = self.run_ledger(root, frozen, existing)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(payload["insight_validation"]["verdict"], "PASS")
                self.assertEqual(payload["insight_validation"]["metrics"]["complete_central_claims"], 1)
                self.assertEqual(payload["entries"][0]["claim_id"], entry["claim_id"])

    def test_incomplete_central_claim_fails_contest_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = {
                "schema_version": 2,
                "entries": [
                    {
                        "key": "q1.max_radius",
                        "claim_id": "CLM-Q1-INCOMPLETE-BOUND",
                        "centrality": "central",
                    }
                ],
            }
            result, payload = self.run_ledger(Path(temp_dir), {"q1": {"max_radius": 12.5}}, existing)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["insight_validation"]["verdict"], "FAIL")
            fields = {item["field"] for item in payload["insight_validation"]["findings"] if item["level"] == "FAIL"}
            self.assertTrue({"claim_type", "scope", "uncertainty", "insight_form", "mechanism", "decision_implication", "surprise_status"}.issubset(fields))

    def test_nested_and_prefixed_question_results_are_discovered_without_auto_promoting_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            frozen = {
                "numbers": {
                    "q1_travel_time": {"value": 29, "source": "results/tables/q1.csv"},
                    "q2_objective": {"value": 86251, "source": "results/tables/q2.csv"},
                },
                "q3_with_relief": {"omega": 0.057823, "mean_mpa": 99.72},
            }
            result, payload = self.run_ledger(Path(temp_dir), frozen)
            self.assertEqual(result.returncode, 1)
            self.assertGreaterEqual(payload["entry_count"], 4)
            self.assertEqual({item["question"] for item in payload["entries"]}, {"Q1", "Q2", "Q3"})
            self.assertTrue(all(item["centrality"] == "supporting" for item in payload["entries"]))
            centrality_failures = [
                item for item in payload["insight_validation"]["findings"] if item["field"] == "centrality"
            ]
            self.assertEqual(len(centrality_failures), 3)

    def test_scoped_waiver_allows_only_unavailable_insight_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = {
                "schema_version": 2,
                "entries": [
                    {
                        "key": "q1.count",
                        "claim_id": "CLM-Q1-REQUIRED-COUNT",
                        "centrality": "central",
                        "claim_type": "numeric_result",
                        "insight_form": "none",
                        "mechanism": "",
                        "scope": "Exact count under the enumerated finite instance.",
                        "assumptions": [],
                        "uncertainty": {
                            "characterization": "Deterministic exhaustive enumeration; no sampling uncertainty.",
                            "decision_switch_risk": "No decision switch exists because the requested output is an exact count.",
                        },
                        "decision_implication": "",
                        "surprise_status": "not_assessed",
                        "evidence": ["results/tables/enumeration.csv"],
                        "waiver": {
                            "applies": True,
                            "waived_fields": ["insight_form", "mechanism", "decision_implication", "surprise_status"],
                            "reason": "The subquestion requests an exact finite count and has no action variable.",
                            "scope": "Only this enumerated count claim.",
                            "evidence": ["results/tables/enumeration.csv"],
                        },
                    }
                ],
            }
            result, payload = self.run_ledger(root, {"q1": {"count": 42}}, existing)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["insight_validation"]["verdict"], "PASS")
            self.assertEqual(payload["insight_validation"]["metrics"]["waived_central_claims"], 1)

    def test_waiver_cannot_replace_scope_or_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = {
                "schema_version": 2,
                "entries": [
                    {
                        "key": "q1.max_radius",
                        "claim_id": "CLM-Q1-INVALID-WAIVER",
                        "centrality": "central",
                        "claim_type": "bound",
                        "insight_form": "none",
                        "scope": "",
                        "uncertainty": {
                            "characterization": "Not assessed.",
                            "decision_switch_risk": "Not assessed.",
                        },
                        "waiver": {
                            "applies": True,
                            "waived_fields": ["scope", "evidence"],
                            "reason": "Attempt to bypass core evidence fields.",
                            "scope": "Entire claim.",
                            "evidence": ["results/frozen_numbers.json"],
                        },
                    }
                ],
            }
            result, payload = self.run_ledger(root, {"q1": {"max_radius": 12.5}}, existing)
            self.assertEqual(result.returncode, 1)
            fields = {item["field"] for item in payload["insight_validation"]["findings"] if item["level"] == "FAIL"}
            self.assertIn("waiver", fields)
            self.assertIn("scope", fields)

    def test_v1_ledger_migrates_without_losing_matched_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing_v1 = {
                "entries": [
                    {
                        "key": "q1.max_radius",
                        "label": "audited radius",
                        "stale_strings": ["12.4"],
                        "evidence": ["results/tables/legacy_audit.csv"],
                    }
                ]
            }
            result, payload = self.run_ledger(
                root,
                {"q1": {"max_radius": 12.5}},
                existing_v1,
                output_level="reproducible_draft",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["migration"]["source_schema_version"], 1)
            self.assertTrue(payload["migration"]["migrated"])
            self.assertEqual(payload["migration"]["matched_entries"], 1)
            entry = payload["entries"][0]
            self.assertEqual(entry["label"], "audited radius")
            self.assertEqual(entry["stale_strings"], ["12.4"])
            self.assertIn("results/tables/legacy_audit.csv", entry["evidence"])
            self.assertEqual(entry["claim_id"], "CLM-Q1-MAX-RADIUS")

    def test_evidence_planner_receives_only_central_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = {
                "schema_version": 2,
                "entries": [
                    {
                        "key": "q1.max_radius",
                        "claim_id": "CLM-Q1-GEOMETRIC-BOUND",
                        "centrality": "central",
                        "claim_type": "bound",
                        "insight_form": "bound",
                        "mechanism": "The tangent constraint becomes active first.",
                        "scope": "Valid for the stated planar geometry.",
                        "assumptions": ["Rigid boundary"],
                        "uncertainty": {
                            "characterization": "Exact up to solver tolerance.",
                            "decision_switch_risk": "No switch inside the audited tolerance.",
                        },
                        "evidence": ["results/tables/boundary_audit.csv"],
                        "decision_implication": "Use 12.5 as the design ceiling.",
                        "surprise_status": "surprising",
                    },
                    {
                        "key": "q1.sample_count",
                        "claim_id": "CLM-Q1-SAMPLE-COUNT",
                        "centrality": "supporting",
                    },
                ],
            }
            result, ledger = self.run_ledger(
                root,
                {"q1": {"max_radius": 12.5, "sample_count": 400}},
                existing,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            by_key = {entry["key"]: entry for entry in ledger["entries"]}
            self.assertTrue(by_key["q1.max_radius"]["final_claim"])
            self.assertFalse(by_key["q1.sample_count"]["final_claim"])

            evidence_path = root / "planning" / "evidence_plan.json"
            evidence_result = subprocess.run(
                [
                    sys.executable,
                    str(EVIDENCE_SCRIPT),
                    "--root",
                    str(root),
                    "--write-json",
                    "planning/evidence_plan.json",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(evidence_result.returncode, 0, evidence_result.stdout + evidence_result.stderr)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["metrics"]["final_claims"], 1)
            self.assertEqual([item["key"] for item in evidence["items"]], ["q1.max_radius"])

    def test_contest_final_pipeline_enforces_result_ledger_v2_check(self) -> None:
        components = dict(COMPONENT_GATES)
        self.assertIn("result_ledger.py", components)
        self.assertNotIn("control_plane_audit.py", components)
        arguments = components["result_ledger.py"]
        self.assertIn("--check", arguments)
        self.assertIn("--output-level", arguments)
        self.assertEqual(arguments[arguments.index("--output-level") + 1], "contest_final")


if __name__ == "__main__":
    unittest.main()
