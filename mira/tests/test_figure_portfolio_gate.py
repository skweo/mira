from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "figure_portfolio_gate.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class FigurePortfolioGateTests(unittest.TestCase):
    def test_index_accepts_figure_number_before_artifact_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "figures").mkdir(parents=True)
            (root / "checks").mkdir()
            (root / "figures" / "figure_index.md").write_text(
                "| Figure No. | File | Backend | Type | Claim |\n"
                "|---|---|---|---|---|\n"
                "| Figure 1 | `figures/risk_surface.png` / `figures/risk_surface.pdf` | MATLAB | surface | validates the response field |\n",
                encoding="utf-8",
            )
            report = root / "checks" / "figure_portfolio_report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--write-json",
                    str(report),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["metrics"]["indexed_visuals"], 1)
            self.assertEqual(payload["items"][0]["artifact"], "figures/risk_surface.png")
            self.assertEqual(payload["items"][0]["visual_type"], "spatial_surface")


if __name__ == "__main__":
    unittest.main()
