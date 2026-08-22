from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "reasoning_core_gate.py"


STRUCTURE = """# Problem Analysis

## Problem Structure Map

| Question | Entities | States | Decisions | Observations | Constraints | Dependencies | Leverage hypothesis | Material ambiguity | Selection check |
|---|---|---|---|---|---|---|---|---|---|
| Q1 | jobs and machines | queue and machine availability | assignment and order | arrivals and service times | capacity and due dates | upstream delay changes downstream load | bottleneck utilization may determine the regime | hard versus soft due dates | compare official wording and infeasibility rate |
"""


VALIDATION = """# Validation Plan

## Discriminating Tests

| Test ID | Question | Candidates compared | Test design | Observable | Route-change rule | Falsifier | Budget cap | Evidence path | Status |
|---|---|---|---|---|---|---|---|---|---|
| DT-1 | Q1 | C1, C2 | solve the same small exact instances and stressed instances | feasibility, objective gap, runtime | choose C1 when C1 is feasible and gap <= 1%; choose C2 when C1 violates capacity or gap > 1% | neither route reproduces the exact small-instance optimum | at most 3 tiny instances, 3 runs, and 10 minutes | proof:small-instance-comparison | completed |
"""


def portfolio(signature_1: str = "time-indexed-milp", signature_2: str = "event-driven-dp", rejected_evidence: str = "DT-1") -> str:
    return f"""# Modeling Plan

## Candidate Model Portfolio

| Candidate ID | Question | Structural signature | Representation | Core assumptions | Advantage hypothesis | Failure condition | Required evidence | Status | Decision evidence |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Q1 | {signature_1} | time-indexed mixed-integer program | discrete time and deterministic service | exact constraints expose feasibility margins | time grid becomes too large | exact small cases, gap, runtime | selected | DT-1 |
| C2 | Q1 | {signature_2} | event-state dynamic program | event order has a compact sufficient state | exploits state dominance without a time grid | state count grows exponentially | state count, exact comparison, runtime | rejected | {rejected_evidence} |
"""


class ReasoningCoreGateTests(unittest.TestCase):
    def run_gate(
        self,
        modeling: str,
        validation: str = VALIDATION,
        stage: str = "modeling",
        extra_files: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir(parents=True)
            (planning / "problem_analysis.md").write_text(STRUCTURE, encoding="utf-8")
            (planning / "modeling_plan.md").write_text(modeling, encoding="utf-8")
            (planning / "validation_plan.md").write_text(validation, encoding="utf-8")
            for rel, content in (extra_files or {}).items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            report_json = root / "checks" / "reasoning_core_report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--stage",
                    stage,
                    "--output-level",
                    "contest_final",
                    "--write-json",
                    str(report_json),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(report_json.read_text(encoding="utf-8"))
            return result, payload

    def test_structurally_distinct_candidates_with_route_changing_test_pass(self) -> None:
        result, payload = self.run_gate(portfolio())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["metrics"]["distinct_structural_signatures"], 2)

    def test_parameter_variants_cannot_masquerade_as_structural_candidates(self) -> None:
        result, payload = self.run_gate(portfolio("genetic-routing", "genetic-routing"))
        self.assertEqual(result.returncode, 1)
        axes = {item["axis"] for item in payload["findings"]}
        self.assertIn("candidate_diversity", axes)

    def test_rejected_candidate_requires_decision_evidence(self) -> None:
        result, payload = self.run_gate(portfolio(rejected_evidence="-"))
        self.assertEqual(result.returncode, 1)
        axes = {item["axis"] for item in payload["findings"]}
        self.assertIn("rejection_discipline", axes)

    def test_single_exact_route_can_use_proof_waiver(self) -> None:
        modeling = """# Modeling Plan

## Candidate Model Portfolio

| Candidate ID | Question | Structural signature | Representation | Core assumptions | Advantage hypothesis | Failure condition | Required evidence | Status | Decision evidence |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Q1 | convex-network-flow | convex min-cost flow | linear costs and integral capacities | total unimodularity gives an exact integral optimum | nonlinear coupling would break the proof | derivation and solver certificate | selected | proof:total-unimodularity |

## Reasoning Core Waivers

| Waiver ID | Scope | Waiver basis | Justification | Evidence path | Status |
|---|---|---|---|---|---|
| W1 | Q1 | proof | total unimodularity proves integrality and rules out a stronger competing integer formulation | proof:total-unimodularity | approved |
"""
        validation = """# Validation Plan

## Discriminating Tests

| Test ID | Question | Candidates compared | Test design | Observable | Route-change rule | Falsifier | Budget cap | Evidence path | Status |
|---|---|---|---|---|---|---|---|---|---|
| DT-1 | Q1 | C1 | verify the integrality certificate and primal feasibility | certificate and residual | keep C1 if the proof conditions hold; return to candidate generation otherwise | any nonlinear coupling or non-integral capacity | analytic proof only, no solver tournament | proof:total-unimodularity | completed |
"""
        result, payload = self.run_gate(modeling, validation)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["verdict"], "PASS")

    def test_scoped_budget_waiver_can_skip_expensive_candidate_tournament(self) -> None:
        modeling = portfolio(rejected_evidence="W-B1") + """

## Reasoning Core Waivers

| Waiver ID | Scope | Waiver basis | Justification | Evidence path | Status |
|---|---|---|---|---|---|
| W-B1 | DT-1 | time_budget | Full-scale comparison would consume the remaining contest writing window; analytic complexity and constraint fit already support C1, while both candidates remain recorded. | budget:contest-work-plan | approved |
"""
        validation = VALIDATION.replace(
            "proof:small-instance-comparison | completed",
            "waiver:W-B1 | waived",
        )
        result, payload = self.run_gate(modeling, validation, stage="results")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["metrics"]["budget_waiver_rows"], 1)

    def test_unscoped_budget_waiver_cannot_skip_candidate_screening(self) -> None:
        validation = VALIDATION.replace(
            "proof:small-instance-comparison | completed",
            "waiver:missing | waived",
        )
        result, payload = self.run_gate(portfolio(), validation, stage="results")
        self.assertEqual(result.returncode, 1)
        axes = {item["axis"] for item in payload["findings"]}
        self.assertIn("candidate_comparison_budget", axes)

    def test_results_stage_requires_completed_resolvable_evidence(self) -> None:
        validation = VALIDATION.replace("proof:small-instance-comparison", "results/discriminating.csv")
        result, payload = self.run_gate(
            portfolio(),
            validation,
            stage="results",
            extra_files={"results/discriminating.csv": "candidate,objective\nC1,10\nC2,12\n"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["verdict"], "PASS")

    def test_validation_plan_regeneration_preserves_discriminating_tests(self) -> None:
        validation_script = SKILL_ROOT / "scripts" / "validation_plan.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir(parents=True)
            report = planning / "validation_plan.md"
            report.write_text(VALIDATION, encoding="utf-8")
            output_json = planning / "validation_plan.json"
            subprocess.run(
                [
                    sys.executable,
                    str(validation_script),
                    "--root",
                    str(root),
                    "--write-report",
                    str(report),
                    "--write-json",
                    str(output_json),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            regenerated = report.read_text(encoding="utf-8")
            self.assertIn("choose C1 when C1 is feasible", regenerated)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertNotIn("discriminating_tests_section", payload)


if __name__ == "__main__":
    unittest.main()
