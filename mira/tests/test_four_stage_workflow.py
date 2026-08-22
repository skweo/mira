from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from command_profiles import commands_for_phase, commands_for_stage  # noqa: E402
from check_presentation_strength import PresentationStrengthChecker  # noqa: E402
from check_quality_balance import QualityBalanceChecker  # noqa: E402
from contest_final_audit import ContestFinalAuditor  # noqa: E402
from mira_state import MiraState  # noqa: E402
from route_references import build_route, markdown  # noqa: E402
from stage_gate import StageGate, normalize_stage, normalize_stage_path  # noqa: E402


class FourStageWorkflowTests(unittest.TestCase):
    def test_canonical_and_legacy_names_normalize_to_four_stages(self) -> None:
        expected = {
            "analysis": "analysis",
            "analysis": "analysis",
            "modeling": "modeling",
            "implementation": "implementation",
            "implementation": "implementation",
            "benchmark": "implementation",
            "paper": "paper",
            "G7": "paper",
        }
        for value, stage in expected.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_stage(value), stage)

    def test_legacy_return_paths_normalize_to_the_earliest_public_stage(self) -> None:
        expected = {
            "analysis": "analysis",
            "modeling/modeling": "modeling",
            "implementation": "implementation",
            "implementation": "implementation",
            "paper": "paper",
            "material_anchor": "analysis",
            "model_derivation": "modeling",
            "visual_evidence": "implementation",
        }
        for value, stage in expected.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_stage_path(value), stage)

    def test_public_profiles_have_no_legacy_gate_commands(self) -> None:
        for stage in ("analysis", "modeling", "implementation", "paper"):
            commands = commands_for_phase(stage, output_level="contest_final")
            self.assertGreaterEqual(len(commands), 3, stage)
            self.assertLessEqual(len(commands), 4, stage)
            joined = "\n".join(commands)
            self.assertNotIn("decision_gate.py", joined)
            self.assertNotIn("human_decision", joined)
            self.assertNotIn("--gate G", joined)

        self.assertEqual(commands_for_stage("implementation"), commands_for_phase("implementation"))

    def test_public_stage_commands_are_real_cli_smoke_tests(self) -> None:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        with tempfile.TemporaryDirectory() as temp_dir:
            for stage in ("analysis", "modeling", "implementation", "paper"):
                for command in commands_for_stage(stage):
                    rendered = command.replace("<project-root>", temp_dir)
                    result = subprocess.run(
                        rendered,
                        shell=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        env=env,
                        check=False,
                    )
                    output = result.stdout + result.stderr
                    with self.subTest(stage=stage, command=rendered):
                        self.assertNotIn("unrecognized arguments:", output, output)
                        self.assertNotIn("Traceback (most recent call last)", output, output)

    def test_public_reports_normalize_internal_legacy_return_labels(self) -> None:
        presentation = PresentationStrengthChecker.__new__(PresentationStrengthChecker)
        presentation.findings = []
        presentation.fail("visual_evidence", "implementation", "missing figure")

        balance = QualityBalanceChecker.__new__(QualityBalanceChecker)
        balance.findings = []
        balance.warn("model_depth", "modeling", "weak validation")

        final = ContestFinalAuditor.__new__(ContestFinalAuditor)
        final.findings = []
        final.fail("figure_narrative", "missing context", "paper", "implementation")

        self.assertEqual(presentation.findings[0].phase, "implementation")
        self.assertEqual(balance.findings[0].phase, "modeling")
        self.assertEqual(final.findings[0].owner_phase, "paper")
        self.assertEqual(final.findings[0].return_to, "implementation")

    def test_router_reports_normalized_stage_for_legacy_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            route = build_route(Path(temp_dir), "implementation", "")
        self.assertEqual(route.stage, "implementation")
        self.assertEqual(route.phase, "implementation")
        self.assertFalse(hasattr(route, "gate_tier"))
        self.assertNotIn("Gate tier", markdown(route))

    def test_benchmark_is_an_implementation_maintenance_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            route = build_route(Path(temp_dir), "benchmark", "")
        self.assertEqual(route.stage, "implementation")
        self.assertTrue(any("benchmark-regression-rules.md" in item.path for item in route.load_now))
        self.assertTrue(any("benchmark_regression.py" in command for command in route.commands))

    def test_stage_pass_and_missing_artifact_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
            self._write(root, "planning/problem_analysis.md", "subquestions, fields, units, outputs\n")
            analysis = StageGate(root, "analysis", "reproducible_draft").evaluate()
            modeling = StageGate(root, "modeling", "reproducible_draft").evaluate()
        self.assertEqual(analysis["verdict"], "PASS")
        self.assertEqual(modeling["verdict"], "FAIL")
        self.assertIn("modeling", modeling["evaluated_stages"])

    def test_nonblocking_warning_still_routes_to_next_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
            self._write(root, "planning/problem_analysis.md", "subquestions, fields, units, outputs\n")
            self._write(root, "planning/modeling_plan.md", "variables, objective, constraints\n")
            self._write(root, "planning/validation_plan.md", "baseline and validation\n")
            self._write(root, "code/model.py", "print('ok')\n")
            self._write(root, "results/run.json", "{}\n")
            self._write(
                root,
                "planning/reference_route.json",
                json.dumps(asdict(build_route(root, "implementation", "")), ensure_ascii=False),
            )
            payload = StageGate(root, "implementation", "reproducible_draft").evaluate()

        self.assertEqual(payload["verdict"], "PASS_WITH_WARNINGS")
        self.assertEqual(payload["next_stage"], "paper")

    def test_later_stage_enforces_upstream_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "paper/main.tex", "\\documentclass{article}\n")
            payload = StageGate(root, "paper", "reproducible_draft").evaluate()
        failed_stages = {item["stage"] for item in payload["checks"] if item["level"] == "FAIL"}
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue({"analysis", "modeling", "implementation"}.issubset(failed_stages))

    def test_user_decision_is_a_stage_blocker_not_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
            self._write(root, "planning/problem_analysis.md", "problem contract\n")
            self._write(root, "planning/modeling_plan.md", "[REQUIRES_USER_DECISION] choose the solver\n")
            self._write(root, "planning/validation_plan.md", "baseline and validation\n")
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertEqual(payload["requires_user_decision"][0]["stage"], "modeling")

    def test_chinese_user_decision_marker_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
            self._write(root, "planning/problem_analysis.md", "problem contract\n")
            self._write(root, "planning/modeling_plan.md", "需要用户确认求解器选择\n")
            self._write(root, "planning/validation_plan.md", "baseline and validation\n")
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertEqual(payload["requires_user_decision"][0]["stage"], "modeling")

    def test_shared_state_normalizes_legacy_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = argparse.Namespace(
                root=temp_dir,
                stage=None,
                phase="implementation",
                write=False,
                write_report=None,
                check=False,
                allow_built_manifest=False,
            )
            state = MiraState(args)
            state._collect()
            payload = state._build_state()
        self.assertEqual(payload["stage"]["current"], "implementation")
        self.assertEqual(payload["phase"]["current"], "implementation")
        self.assertEqual(payload["requires_user_decision"], [])

    def test_shared_state_assigns_modeling_decision_to_modeling_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/modeling_plan.md", "需要用户决定是否使用整数规划\n")
            args = argparse.Namespace(
                root=temp_dir,
                stage="modeling",
                phase=None,
                output_level="reproducible_draft",
                write=False,
                write_report=None,
                check=False,
                allow_built_manifest=False,
            )
            state = MiraState(args)
            state._collect()
            payload = state._build_state()
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertEqual(payload["requires_user_decision"][0]["return_stage"], "modeling")
        self.assertEqual(payload["requires_user_decision"][0]["return_phase"], "modeling")

    @staticmethod
    def _write(root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
