from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "benchmark_regression.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class BenchmarkRegressionTests(unittest.TestCase):
    def test_explicit_generic_benchmark_blocks_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            benchmark_path = root / "fixtures" / "generic_capacity_case.json"
            benchmark = {
                "id": "generic_capacity_case",
                "frozen_numbers_path": "results/frozen_numbers.json",
                "expected": [
                    {
                        "name": "refined capacity",
                        "path": "design.refined_capacity",
                        "value": 7.5,
                        "abs_tol": 1e-9,
                    }
                ],
                "required_evidence": [
                    {
                        "name": "boundary refinement",
                        "paths": ["results/audits/boundary_refinement.json"],
                        "terms": ["bracket", "tolerance"],
                    }
                ],
                "required_cards": [
                    {
                        "name": "continuous refinement card",
                        "path_contains": "continuous-extremum-search",
                    }
                ],
                "stale_artifact_checks": [
                    {
                        "artifact": "results/result_report.md",
                        "forbidden_values": ["6.25", "coarse-only"],
                        "message": "retired coarse result remains in the report",
                    },
                    {
                        "artifact": "paper/main.tex",
                        "forbidden_values": ["6.25", "coarse-only"],
                        "message": "retired coarse result remains in the paper",
                    },
                ],
            }
            files = {
                "results/frozen_numbers.json": json.dumps({"design": {"refined_capacity": 7.5}}),
                "results/audits/boundary_refinement.json": (
                    '{"bracket": [7.4, 7.6], "tolerance": 1e-6}'
                ),
                "planning/modeling_plan.md": "Selected card: continuous-extremum-search.\n",
                "results/result_report.md": "Retired result: 6.25 from a coarse-only scan.\n",
                "paper/main.tex": "Retired result: 6.25 from a coarse-only scan.\n",
                "fixtures/generic_capacity_case.json": json.dumps(benchmark),
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            report = root / "checks" / "benchmark_regression.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--benchmark",
                    str(benchmark_path),
                    "--write-json",
                    str(report),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark"], "generic_capacity_case")
            self.assertEqual(payload["verdict"], "FAIL")
            failures = [item for item in payload["checks"] if item["level"] == "FAIL"]
            self.assertEqual(
                {(item["axis"], item["name"]) for item in failures},
                {
                    ("stale_artifact", "results/result_report.md"),
                    ("stale_artifact", "paper/main.tex"),
                },
            )
            for item in failures:
                self.assertIn("6.25", item["message"])
                self.assertIn("coarse-only", item["message"])


if __name__ == "__main__":
    unittest.main()
