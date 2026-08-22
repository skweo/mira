from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from change_impact import advise_changes  # noqa: E402
from stage_gate import StageGate  # noqa: E402


class ChangeImpactTests(unittest.TestCase):
    def test_advice_maps_paths_to_earliest_stage(self) -> None:
        payload = advise_changes(["paper/main.tex", "code/solver.py", "problem/A.pdf"])
        self.assertEqual(payload["earliest_stage"], "analysis")
        self.assertEqual(payload["suggested_stages"], ["analysis", "implementation", "paper"])
        self.assertEqual(payload["mode"], "advice_only")

    def test_unmapped_path_is_manual_review_not_failure(self) -> None:
        payload = advise_changes(["notes/private.txt"])
        self.assertEqual(payload["changed"][0]["stage"], "manual_review")
        self.assertIsNone(payload["earliest_stage"])

    def test_project_escape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "project-relative"):
            advise_changes(["../outside.txt"])

    def test_cli_reads_and_writes_no_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "change_impact.py"), "--root", str(root), "--changed", "code/solver.py", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(list(root.rglob("*")), [])
            self.assertEqual(json.loads(result.stdout)["mode"], "advice_only")

    def test_stage_gate_ignores_legacy_change_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
            self._write(root, "planning/problem_analysis.md", "problem contract\n")
            self._write(root, "planning/modeling_plan.md", "model contract\n")
            self._write(root, "planning/validation_plan.md", "validation contract\n")
            self._write(root, "planning/change_impact.json", "not valid json")
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()
        self.assertNotIn("change_impact_state", {item["check"] for item in payload["checks"]})

    def test_paper_gate_ignores_final_submission_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative in (
                "planning/delivery_brief.md", "planning/problem_analysis.md",
                "planning/modeling_plan.md", "planning/validation_plan.md",
                "code/solver.py", "results/run.csv", "figures/result.png",
                "paper/main.tex", "paper/main.pdf",
            ):
                self._write(root, relative, "fixture\n")
            self._write(root, "checks/submission_compliance_report.json", '{"verdict":"FAIL"}')
            payload = StageGate(root, "paper", "reproducible_draft").evaluate()
        blocked = [item for item in payload["checks"] if item["check"] == "internal_diagnostic"]
        self.assertNotIn("checks/submission_compliance_report.json", {item["evidence"] for item in blocked})

    @staticmethod
    def _write(root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
