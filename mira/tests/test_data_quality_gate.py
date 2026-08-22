from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "data_quality_gate.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class DataQualityGateTests(unittest.TestCase):
    def make_project(self, root: Path, cleaning_documented: bool) -> None:
        (root / "data_raw").mkdir(parents=True)
        (root / "planning").mkdir()
        (root / "checks").mkdir()
        (root / "data_raw" / "sample.csv").write_text(
            "node_id,demand,empty_layout\n0,0,\n1,5,\n",
            encoding="utf-8",
        )
        mapping = {
            "attachments": [
                {
                    "rel_path": "data_raw/sample.csv",
                    "candidate_subquestions": ["Q1"],
                }
            ]
        }
        (root / "planning" / "attachment_mapping.json").write_text(
            json.dumps(mapping), encoding="utf-8"
        )
        overrides = {
            "datasets": [
                {
                    "artifact": "data_raw/sample.csv",
                    "readiness": "accepted",
                }
            ],
            "field_units": {"data_raw/sample.csv::sample::demand": "items"},
            "field_meanings": {},
            "cleaning_actions": [
                {
                    "artifact": "data_raw/sample.csv",
                    "target": "empty_layout",
                    "action": "drop fully empty layout column" if cleaning_documented else "",
                    "reason": "source formatting only" if cleaning_documented else "",
                    "risk": "low",
                }
            ],
            "waivers": [],
        }
        (root / "planning" / "data_quality_overrides.json").write_text(
            json.dumps(overrides), encoding="utf-8"
        )

    def run_gate(self, root: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--output-level",
                "contest_final",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        payload = json.loads(
            (root / "checks" / "data_quality_report.json").read_text(encoding="utf-8")
        )
        return result, payload

    def test_undocumented_cleaning_action_does_not_bypass_contest_final_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, cleaning_documented=False)
            result, payload = self.run_gate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(
                any(
                    item["axis"] == "cleaning" and "documented cleaning action" in item["message"]
                    for item in payload["findings"]
                )
            )

    def test_documented_cleaning_action_downgrades_known_missing_layout_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, cleaning_documented=True)
            result, payload = self.run_gate(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(any(item["level"] == "FAIL" for item in payload["findings"]))


if __name__ == "__main__":
    unittest.main()
