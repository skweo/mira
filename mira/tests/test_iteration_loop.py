import argparse
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from iteration_loop import IterationLoop  # noqa: E402


def arguments(root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        write_report=None,
        allow_warnings=False,
        mark=None,
        status=None,
        evidence=None,
        prune_resolved=False,
    )


class IterationLoopTests(unittest.TestCase):
    def test_report_table_is_parsed_by_header_when_dataset_column_is_present(self) -> None:
        report = """# Data Quality Report

| Level | Axis | Dataset | Return to | Finding |
|---|---|---|---|---|
| FAIL | missing_values | `data_raw/sample.xlsx` | modeling.5/3 | unnamed_6 has 100.0% missing values |
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            loop = IterationLoop(arguments(Path(temp_dir)))
            items = loop._parse_markdown_table("checks/data_quality_report.md", report)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].axis, "missing_values")
        self.assertEqual(items[0].return_phase, "modeling")
        self.assertEqual(items[0].finding, "unnamed_6 has 100.0% missing values")

    def test_open_warning_is_visible_but_not_blocking(self) -> None:
        report = """# Result Quality Report

| Level | Axis | Return to | Finding |
|---|---|---|---|
| WARN | stability | implementation | multi-seed spread should be reported |
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "checks" / "result_quality_report.md"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(report, encoding="utf-8")
            loop = IterationLoop(arguments(root))
            exit_code = loop.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(loop.items[0].level, "WARN")
        self.assertEqual(loop._blocking_items(), [])


if __name__ == "__main__":
    unittest.main()
