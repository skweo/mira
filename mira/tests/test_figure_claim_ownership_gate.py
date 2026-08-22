from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "figure_claim_ownership_gate.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class FigureClaimOwnershipGateTests(unittest.TestCase):
    def make_project(self, root: Path, claim: str) -> None:
        (root / "figures").mkdir(parents=True)
        (root / "planning").mkdir()
        (root / "checks").mkdir()
        (root / "figures" / "figure_index.md").write_text(
            "| Figure | Source | Role | Claim | Paper location |\n"
            "|---|---|---|---|---|\n"
            "| figures/result.png | results/result.csv | result | 方案 A 的目标值最低 | 结果分析 |\n",
            encoding="utf-8",
        )
        (root / "planning" / "figure_claims.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {
                            "artifact": "figures/result.png",
                            "core_claim": claim,
                            "source_artifact": "results/result.csv",
                            "paper_section": "结果分析",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
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
                "--write-json",
                "checks/figure_claim_ownership_report.json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        payload = json.loads(
            (root / "checks" / "figure_claim_ownership_report.json").read_text(
                encoding="utf-8"
            )
        )
        return result, payload

    def test_evidence_linked_claim_passes_without_human_confirmation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, "方案 A 的目标值最低且满足全部约束")
            result, payload = self.run_gate(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(any(item["level"] == "FAIL" for item in payload["findings"]))

    def test_missing_core_claim_still_blocks_contest_final(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root, "")
            result, payload = self.run_gate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(
                any("core_claim is missing" in item["message"] for item in payload["findings"])
            )


if __name__ == "__main__":
    unittest.main()
